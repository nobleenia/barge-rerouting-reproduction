# Rolling-Horizon Allocation

## 1. Static versus rolling-horizon information

The static DCA model receives every realised demand simultaneously.

A rolling-horizon model instead receives one booking request at each decision
event.

At event \(e\), demands are partitioned into:

- prior demands already processed;
- the current arriving demand;
- future demands not yet revealed.

## 2. Booking-event sequence

Requests are sorted using:

\[
(t_k^{res},k).
\]

The first component is the reservation time.

The demand identifier provides deterministic ordering when several requests
share the same reservation time.

## 3. Information boundary

For event \(e\):

\[
K_e^{prior}
=
\{k: sequence(k)<e\},
\]

\[
K_e^{known}
=
K_e^{prior}\cup\{k_e\},
\]

and:

\[
K_e^{future}
=
\{k: sequence(k)>e\}.
\]

The baseline DCA decision at event \(e\) must not use realised attributes of
\(K_e^{future}\).

Revenue management may later use probability distributions for future demand,
but not its realised future values.

## 4. Equal-time requests

Requests with the same reservation time are still processed sequentially.

No physical network time passes between those booking decisions.

A request processed earlier at the same time may reserve capacity before the
next equal-time request is considered.

## 5. Next state components

Later rolling-horizon checkpoints will add:

- accepted commitments;
- fixed future route plans;
- executed movements;
- remaining demand fragments;
- residual arc capacity;
- modifiable rerouting decisions.

## 6. Persistent demand commitment

A positive booking decision creates a `DemandCommitment`.

It records:

- the booking-event sequence and time;
- original demand;
- acceptance fraction;
- accepted volume;
- positive planned arc flows.

A rejected request creates no commitment.

## 7. Planned versus executed flow

A planned arc flow reserves capacity for future movement.

It does not mean the cargo has already traversed the arc.

Several booking decisions may occur at the same reservation time without any
physical execution between them.

Execution is introduced only when network time advances.

## 8. Residual capacity before execution

Before any rerouting or execution, residual transport capacity is:

\[
C_a^{residual}
=
C_a
-
\sum_{k\in K^{accepted}}v_{ka}^{planned}.
\]

This ensures that later bookings cannot reuse capacity already promised to
earlier accepted demands.

When execution and rerouting are introduced, executed and modifiable planned
flows will be separated explicitly to prevent capacity from being
double-subtracted.

## 9. Sequential DCA decision

At booking event \(e\), only the current arriving demand is optimised.

Prior accepted commitments remain fixed.

For transport arc \(a\), the current model receives residual capacity:

\[
C_{a,e}^{residual}
=
C_a
-
\sum_{k\in K_e^{accepted}}v_{ka}^{planned}.
\]

The current demand flow therefore satisfies:

\[
v_{k_ea}
\leq
C_{a,e}^{residual}.
\]

The event objective is:

\[
\max f_{k_e}q_{k_e}\xi_{k_e}.
\]

This is a myopic DCA decision: realised future demands are not considered.

## 10. Sequential versus static optimisation

Static optimisation can compare all demands simultaneously and select the
globally strongest combination.

Sequential DCA cannot revise earlier accepted commitments.

Consequently, an early accepted request may consume capacity that would later
have been more valuable.

This distinction is necessary for evaluating future-demand revenue management.

## 6. Persistent demand commitment

A positive booking decision creates a `DemandCommitment`.

It records:

- the booking-event sequence and time;
- original demand;
- acceptance fraction;
- accepted volume;
- positive planned arc flows.

A rejected request creates no commitment.

## 7. Planned versus executed flow

A planned arc flow reserves capacity for future movement.

It does not mean the cargo has already traversed the arc.

Several booking decisions may occur at the same reservation time without any
physical execution between them.

Execution is introduced only when network time advances.

## 8. Residual capacity before execution

Before any rerouting or execution, residual transport capacity is:

\[
C_a^{residual}
=
C_a
-
\sum_{k\in K^{accepted}}v_{ka}^{planned}.
\]

This ensures that later bookings cannot reuse capacity already promised to
earlier accepted demands.

When execution and rerouting are introduced, executed and modifiable planned
flows will be separated explicitly to prevent capacity from being
double-subtracted.

## 14. Residual-capacity bottleneck diagnosis

When a mandatory request is infeasible, the implementation constructs a
single-demand residual-capacity flow network.

The diagnostic computes:

\[
Q_k^{max},
\]

the maximum demand volume routable through the remaining transport capacity.

The unmet volume is:

\[
shortfall_k
=
q_k-Q_k^{max}.
\]

A minimum source-to-sink cut identifies the scheduled transport arcs that
prevent additional flow.

This is stronger than merely listing every saturated arc because the reported
cut separates the demand source from its logical delivery sink.

For the canonical baseline failure, the expected diagnosis is:

\[
q_{K0011}=2,\qquad
Q_{K0011}^{max}=0,\qquad
shortfall=2.
\]

The expected minimum-cut transport arc is service S2.

## 15. Physical-time execution

Accepted commitments initially contain planned arc flows.

A planned physical arc is considered executed at time \(\tau\) when:

\[
headTime(a)\leq\tau.
\]

Execution is therefore based on arrival time.

At physical time zero, a service arriving at time one remains unexecuted.

At physical time one, that service is completed and its cargo fragment is
located at the service head node.

## 16. Flow-path decomposition

A committed demand flow may be split across several feasible routes.

Before reconstructing execution, the positive source-to-sink flow is
decomposed deterministically into `PlannedDemandPath` objects.

Each path records:

- path volume;
- ordered physical and holding arcs;
- one final auxiliary delivery arc.

One unfinished fragment is maintained per decomposed path.

## 17. Fragment execution

For an unfinished path, the fragment location at time \(\tau\) is:

- the demand source when no physical arc has arrived;
- the head of the latest executed physical arc otherwise.

Executed physical arc identifiers are preserved in the fragment history.

When the path's eligible destination time has been reached, its volume moves
from unfinished fragments to `delivered_barge_volume`.

## 18. Execution accounting identity

At every physical time:

\[
acceptedVolume_k
=
remainingVolume_k
+
deliveredBargeVolume_k
+
deliveredTruckVolume_k.
\]

The `AcceptedDemandState` domain object validates this identity.

## 19. Equal-time booking decisions

No physical execution occurs merely because another request is processed at
the same reservation time.

Physical advancement occurs only when the rolling process moves to a later
time value.
