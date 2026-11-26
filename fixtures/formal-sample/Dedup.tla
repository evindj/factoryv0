------------------------------ MODULE Dedup ------------------------------
(***************************************************************************)
(* WHAT IS MODELLED: a server that deduplicates client requests by id so  *)
(*   that each request's side effect is applied at most once, while the    *)
(*   client retries until it receives an acknowledgement.                  *)
(* ABSTRACTED AWAY: payloads, real time, persistence (state is durable),   *)
(*   failures of the effect itself.                                        *)
(* ENVIRONMENT: requests may be lost; the client retries (which also      *)
(*   produces duplicates); several server workers run concurrently.        *)
(* SEEDED BUG: Atomic = FALSE models a check-then-act race: a worker       *)
(*   checks `seen`, and only later (at apply time) records the id.         *)
(* HISTORY: the first "fixed" design acked a duplicate as soon as its id   *)
(*   was claimed. TLC: AckedImpliesApplied violated in 7 steps (duplicate  *)
(*   acked while the original was still applying). Fix: ids are claimed    *)
(*   (`seen`) and later completed (`done`); a duplicate of an in-flight id *)
(*   is dropped, not acked, and the client's retry later gets the ack.     *)
(* WHY THE BOUNDS SUFFICE: the races need 2 workers and 1 id; a 2nd id     *)
(*   shows that ids do not interfere. More workers/ids add no new          *)
(*   interleaving classes for a per-id protocol.                           *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS Ids, Workers, Atomic

VARIABLES sent, net, acked, seen, done, applied, pc, req
vars == <<sent, net, acked, seen, done, applied, pc, req>>

TypeOK ==
    /\ sent \subseteq Ids /\ net \subseteq Ids /\ acked \subseteq Ids
    /\ seen \subseteq Ids /\ done \subseteq seen
    /\ applied \in [Ids -> Nat]
    /\ pc \in [Workers -> {"idle", "check", "apply", "ack"}]
    /\ req \in [Workers -> Ids]

Init ==
    /\ sent = {} /\ net = {} /\ acked = {} /\ seen = {} /\ done = {}
    /\ applied = [i \in Ids |-> 0]
    /\ pc = [w \in Workers |-> "idle"]
    /\ req = [w \in Workers |-> CHOOSE i \in Ids : TRUE]

\* ---- client -------------------------------------------------------------
Send(i) ==
    /\ i \notin sent
    /\ sent' = sent \cup {i}
    /\ net' = net \cup {i}
    /\ UNCHANGED <<acked, seen, done, applied, pc, req>>

Retry(i) ==
    /\ i \in sent \ acked
    /\ i \notin net
    /\ net' = net \cup {i}
    /\ UNCHANGED <<sent, acked, seen, done, applied, pc, req>>

\* ---- environment ----------------------------------------------------------
Drop(i) ==
    /\ i \in net
    /\ net' = net \ {i}
    /\ UNCHANGED <<sent, acked, seen, done, applied, pc, req>>

\* ---- server workers -------------------------------------------------------
TakeAtomic(w, i) ==
    CASE i \in done        -> pc' = [pc EXCEPT ![w] = "ack"] /\ UNCHANGED seen
      [] i \in seen \ done -> pc' = pc /\ UNCHANGED seen   \* in flight: drop, client retries
      [] OTHER             -> pc' = [pc EXCEPT ![w] = "apply"] /\ seen' = seen \cup {i}

Take(w, i) ==
    /\ pc[w] = "idle"
    /\ i \in net
    /\ net' = net \ {i}
    /\ req' = [req EXCEPT ![w] = i]
    /\ IF Atomic
         THEN TakeAtomic(w, i)
         ELSE pc' = [pc EXCEPT ![w] = "check"] /\ UNCHANGED seen
    /\ UNCHANGED <<sent, acked, done, applied>>

Check(w) ==   \* only reached when Atomic = FALSE
    /\ pc[w] = "check"
    /\ pc' = [pc EXCEPT ![w] = IF req[w] \in seen THEN "ack" ELSE "apply"]
    /\ UNCHANGED <<sent, net, acked, seen, done, applied, req>>

Apply(w) ==
    /\ pc[w] = "apply"
    /\ applied' = [applied EXCEPT ![req[w]] = @ + 1]
    /\ seen' = seen \cup {req[w]}
    /\ done' = done \cup {req[w]}
    /\ pc' = [pc EXCEPT ![w] = "ack"]
    /\ UNCHANGED <<sent, net, acked, req>>

Ack(w) ==
    /\ pc[w] = "ack"
    /\ acked' = acked \cup {req[w]}
    /\ pc' = [pc EXCEPT ![w] = "idle"]
    /\ UNCHANGED <<sent, net, seen, done, applied, req>>

Done == acked = Ids /\ UNCHANGED vars   \* terminal stuttering, not a deadlock

Next ==
    \/ \E i \in Ids : Send(i) \/ Retry(i) \/ Drop(i)
    \/ \E w \in Workers, i \in Ids : Take(w, i)
    \/ \E w \in Workers : Check(w) \/ Apply(w) \/ Ack(w)
    \/ Done

Spec ==
    /\ Init /\ [][Next]_vars
    /\ \A w \in Workers : WF_vars(Check(w) \/ Apply(w) \/ Ack(w))
    /\ \A i \in Ids : WF_vars(Retry(i)) /\ SF_vars(\E w \in Workers : Take(w, i))

\* ---- properties -----------------------------------------------------------
AppliedAtMostOnce == \A i \in Ids : applied[i] <= 1               \* safety
AckedImpliesApplied == \A i \in acked : applied[i] = 1            \* safety
EveryRequestAcked == \A i \in Ids : (i \in sent) ~> (i \in acked) \* liveness

\* Vacuity probe: add as an INVARIANT; TLC must find a trace reaching it.
ProbeNeverAcked == acked = {}
=============================================================================
