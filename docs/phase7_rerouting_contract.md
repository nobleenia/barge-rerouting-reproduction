# Phase 7 — Demand Rerouting Contract

## 1. Reproduction objective

Phase 7 reproduces the demand-rerouting mechanism described in the source
publication.

The publication permits previously accepted but unfinished demand to have its
future itinerary recalculated while scheduled services remain fixed.

The displayed mathematical formulation is compressed and does not explicitly
represent partially executed cargo. Assumption A003 resolves this ambiguity by
reconstructing unfinished fragments at their actual terminal-time positions.

## 2. Primary implementation interpretation

At physical decision time \(\tau\), an accepted demand is separated into:

\[
acceptedVolume_k
=
deliveredVolume_k
+
unfinishedVolume_k.
\]

Only unfinished volume enters the rerouting problem.

Each unfinished fragment \(f\) contains:

- its original demand identifier;
- its fixed remaining volume;
- its current terminal-time node;
- its executed-arc history;
- its old unexecuted planned itinerary.

## 3. Irreversible decisions

Every arc completed by time \(\tau\) is historical and immutable.

For fragment \(f\), the executed arc sequence:

\[
H_f(\tau)
\]

must remain unchanged after rerouting.

The new itinerary begins at the fragment's current node:

\[
n_f(\tau),
\]

not at the demand's original source.

## 4. Fixed accepted quantity

A previously accepted quantity cannot be reduced during rerouting.

For accepted demand \(k\):

\[
q_k^{accepted}
=
\xi_k vol_k.
\]

At time \(\tau\):

\[
q_k^{accepted}
=
q_k^{delivered}
+
\sum_{f\in F_k(\tau)} q_f.
\]

Rerouting changes future itinerary variables, not the accepted quantity.

## 5. Rerouting eligibility

A previous commitment is reroutable at time \(\tau\) when:

1. its booking decision occurred before the current event;
2. its acceptance fraction is positive;
3. it has at least one unfinished fragment;
4. at least one fragment has future feasible movement;
5. its delivery deadline has not already passed;
6. it is included by the selected rerouting policy.

For Full-Reroute, every eligible unfinished commitment is included whenever a
new booking request is processed.

## 6. Reservation release

Let:

\[
u_{fa}^{old}
\]

be fragment \(f\)'s old unexecuted reservation on future transport arc \(a\).

Ordinary bookable capacity is:

\[
C_{a,\tau}^{bookable}
=
C_a
-
fixedOutsideAllocation_{a,\tau}
-
\sum_{f\in F^R(\tau)}u_{fa}^{old}.
\]

Before jointly reoptimising the reroutable fragments, release their old future
reservations:

\[
C_{a,\tau}^{released}
=
C_{a,\tau}^{bookable}
+
\sum_{f\in F^R(\tau)}u_{fa}^{old}.
\]

Equivalently:

\[
C_{a,\tau}^{released}
=
C_a
-
fixedOutsideAllocation_{a,\tau}.
\]

The rerouting capacity constraint is:

\[
v_{\tilde{k}a}
+
\sum_{f\in F^R(\tau)}v_{fa}^{new}
\leq
C_{a,\tau}^{released}.
\]

The old reroutable reservations must not remain subtracted while the same
fragments are included as new flow decisions.

## 7. Fragment flow conservation

For fragment \(f\) at current node \(n_f(\tau)\):

\[
\sum_{a\in\delta^+(n_f(\tau))}v_{fa}
-
\sum_{a\in\delta^-(n_f(\tau))}v_{fa}
=
q_f.
\]

At intermediate nodes:

\[
\sum_{a\in\delta^+(n)}v_{fa}
-
\sum_{a\in\delta^-(n)}v_{fa}
=
0.
\]

Delivery through the demand-specific sink must equal:

\[
q_f.
\]

## 8. Current request

The current request retains the publication's acceptance rule:

\[
\xi_{\tilde{k}}=
\begin{cases}
1, & R,\\
[0,1], & P,\\
\{0,1\}, & F.
\end{cases}
\]

Its source is:

\[
(o(\tilde{k}),t_{avl}(\tilde{k})).
\]

Its accepted flow and all rerouted fragment flows share the same future
transport capacities.

## 9. Services remain fixed

Rerouting changes demand allocation only.

The following remain unchanged:

- physical terminal network;
- service sequence;
- service departure times;
- service arrival times;
- transport-arc identities;
- nominal and actual service capacities.

## 10. Full-Reroute sequence

For every incoming booking event:

1. advance to its decision time;
2. execute movements completed by that time;
3. reconstruct accepted-demand fragments;
4. detect reroutable fragments;
5. release their old unexecuted reservations;
6. jointly optimise reroutable fragments and the current request;
7. preserve executed histories;
8. replace old unexecuted itineraries;
9. persist the current booking decision;
10. validate capacity and volume accounting.

## 11. Phase 7 gate

The controlled validation case must demonstrate that:

1. ordinary sequential DCA rejects a new demand;
2. an earlier accepted demand has unfinished volume;
3. at least one movement of that demand has already executed;
4. rerouting moves only its unexecuted itinerary;
5. the new demand becomes accepted;
6. executed movements remain unchanged;
7. every previously accepted quantity remains fixed;
8. all accepted volume reaches its destination;
9. every service capacity remains feasible.

## 12. Out of scope

Phase 7 does not yet implement:

- potential-future-demand capacity protection;
- \(y_{kj}\) variables;
- `maxvol`;
- DCA-RM;
- DCA-RRM;
- water-level capacity disruption;
- Partial-Reroute;
- truck recourse.

These belong to later reproduction phases.
