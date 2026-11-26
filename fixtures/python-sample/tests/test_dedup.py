from collections import Counter
from collections.abc import Hashable
from functools import partial

import pytest
from hypothesis import given
from hypothesis import strategies as st

from sample.dedup import DedupProcessor, Outcome


def test_v01_first_request_is_applied() -> None:
    applied: list[str] = []
    assert DedupProcessor().process("r1", lambda: applied.append("r1")) is Outcome.APPLIED
    assert applied == ["r1"]


@given(st.lists(st.integers(min_value=0, max_value=5)))
def test_v02_each_id_applied_exactly_once(ids: list[int]) -> None:
    counts: Counter[int] = Counter()
    proc = DedupProcessor()
    for i in ids:
        proc.process(i, partial(counts.update, [i]))
    assert counts == Counter(set(ids))


def test_v03_regression_tlc_race_duplicate_is_not_applied_twice() -> None:
    """DedupRace.cfg trace: a retry arrives between claim and apply -> must not re-apply."""
    applied: list[Hashable] = []
    proc: DedupProcessor

    def duplicate_arrives(request_id: Hashable) -> None:
        proc.process(request_id, lambda: applied.append(request_id))

    proc = DedupProcessor(on_claimed=duplicate_arrives)
    proc.process("r1", lambda: applied.append("r1"))
    assert applied == ["r1"]


def test_v04_regression_tlc_duplicate_in_flight_is_not_acked() -> None:
    """Dedup.tla v1 trace (AckedImpliesApplied): a duplicate seen while the original is
    still applying must not be reported as done; the client has to retry."""
    outcomes: list[Outcome] = []
    proc: DedupProcessor

    def duplicate_arrives(request_id: Hashable) -> None:
        outcomes.append(proc.process(request_id, lambda: None))

    proc = DedupProcessor(on_claimed=duplicate_arrives)
    proc.process("r1", lambda: None)
    assert outcomes == [Outcome.IN_PROGRESS]
    assert not Outcome.IN_PROGRESS.acknowledge
    assert proc.process("r1", lambda: None) is Outcome.ALREADY_DONE
    assert Outcome.ALREADY_DONE.acknowledge


def test_v05_failed_effect_releases_claim_so_retry_can_apply() -> None:
    applied: list[str] = []

    def boom() -> None:
        raise RuntimeError("effect failed")

    proc = DedupProcessor()
    with pytest.raises(RuntimeError):
        proc.process("r1", boom)
    assert proc.process("r1", lambda: applied.append("r1")) is Outcome.APPLIED
    assert applied == ["r1"]
