---------------------------- MODULE Template ----------------------------
(***************************************************************************)
(* WHAT IS MODELLED:    <the design aspect, e.g. leader election, retry   *)
(*                       + dedup, lease renewal>                            *)
(* ABSTRACTED AWAY:     <payloads, serialization, real time, ...>          *)
(* ENVIRONMENT/FAULTS:  <message loss / duplication / reordering, crash-   *)
(*                       restart, ...>. Must match spec.md's failure model. *)
(* WHY THE BOUNDS SUFFICE: <e.g. 3 nodes is the smallest cluster with a    *)
(*                       minority partition; 2 terms exercise term change> *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, Sequences, TLC

CONSTANTS Nodes          \* e.g. {n1, n2, n3} as model values

VARIABLES state, msgs    \* replace with the design's state
vars == <<state, msgs>>

TypeOK ==
    /\ state \in [Nodes -> {"init"}]
    /\ msgs \subseteq [type : {"m"}, from : Nodes]

Init ==
    /\ state = [n \in Nodes |-> "init"]
    /\ msgs = {}

\* --- system actions -------------------------------------------------------
Step(n) ==
    /\ UNCHANGED vars           \* replace

\* --- environment actions (faults the design must tolerate) ----------------
Lose(m) ==
    /\ m \in msgs
    /\ msgs' = msgs \ {m}
    /\ UNCHANGED state

Next ==
    \/ \E n \in Nodes : Step(n)
    \/ \E m \in msgs : Lose(m)

\* Fairness: only for actions the real system is guaranteed to eventually take.
Spec == Init /\ [][Next]_vars /\ \A n \in Nodes : WF_vars(Step(n))

\* --- properties --------------------------------------------------------------
\* SAFETY: something bad never happens (checked as INVARIANTS)
Safety == TRUE

\* LIVENESS: something good eventually happens (checked as PROPERTIES)
Liveness == TRUE

\* VACUITY PROBE: add as an INVARIANT temporarily; TLC MUST report it violated.
Probe == TRUE
=============================================================================
