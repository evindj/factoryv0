package com.example.dedup;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.example.dedup.DedupProcessor.Outcome;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import net.jqwik.api.ForAll;
import net.jqwik.api.Label;
import net.jqwik.api.Property;
import net.jqwik.api.constraints.IntRange;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class DedupProcessorTest {

  @Test
  @DisplayName("V-01 first request is applied")
  void firstRequestApplied() {
    List<String> applied = new ArrayList<>();
    assertThat(new DedupProcessor().process("r1", () -> applied.add("r1")))
        .isEqualTo(Outcome.APPLIED);
    assertThat(applied).containsExactly("r1");
  }

  @Property
  @Label("V-02 each id applied exactly once")
  void eachIdAppliedExactlyOnce(@ForAll List<@IntRange(min = 0, max = 5) Integer> ids) {
    Map<String, Integer> counts = new HashMap<>();
    DedupProcessor proc = new DedupProcessor();
    for (Integer i : ids) {
      String id = String.valueOf(i);
      proc.process(id, () -> counts.merge(id, 1, Integer::sum));
    }
    assertThat(counts.keySet()).hasSameSizeAs(new HashSet<>(ids));
    assertThat(counts.values()).allMatch(c -> c == 1);
  }

  @Test
  @DisplayName("V-03 regression (DedupRace): duplicate during apply window is not re-applied")
  void duplicateDuringApplyWindowNotReapplied() {
    List<String> applied = new ArrayList<>();
    DedupProcessor[] holder = new DedupProcessor[1];
    holder[0] = new DedupProcessor(id -> holder[0].process(id, () -> applied.add(id)));
    holder[0].process("r1", () -> applied.add("r1"));
    assertThat(applied).containsExactly("r1");
  }

  @Test
  @DisplayName("V-04 regression (AckedImpliesApplied): in-flight duplicate is not acked")
  void inFlightDuplicateNotAcked() {
    List<Outcome> outcomes = new ArrayList<>();
    DedupProcessor[] holder = new DedupProcessor[1];
    holder[0] = new DedupProcessor(id -> outcomes.add(holder[0].process(id, () -> {})));
    holder[0].process("r1", () -> {});
    assertThat(outcomes).containsExactly(Outcome.IN_PROGRESS);
    assertThat(Outcome.IN_PROGRESS.acknowledge()).isFalse();
    assertThat(holder[0].process("r1", () -> {})).isEqualTo(Outcome.ALREADY_DONE);
    assertThat(Outcome.ALREADY_DONE.acknowledge()).isTrue();
  }

  @Test
  @DisplayName("V-05 failed effect releases the claim so a retry can apply")
  void failedEffectReleasesClaim() {
    DedupProcessor proc = new DedupProcessor();
    assertThatThrownBy(
            () ->
                proc.process(
                    "r1",
                    () -> {
                      throw new IllegalStateException("effect failed");
                    }))
        .isInstanceOf(IllegalStateException.class);
    List<String> applied = new ArrayList<>();
    assertThat(proc.process("r1", () -> applied.add("r1"))).isEqualTo(Outcome.APPLIED);
    assertThat(applied).containsExactly("r1");
  }
}
