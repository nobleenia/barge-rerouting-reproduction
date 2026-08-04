# Published DCA-Reroute Reproduction Specification

## 1. Purpose

This document defines the implementation contract for reproducing the
DCA-Reroute mechanism presented by Cui et al. (2024).

The primary implementation must reproduce the published mathematical model
before any operational correction or methodological extension is introduced.

The execution-aware fragment interpretation developed during Phase 6 is
retained for later sensitivity analysis, but it must not silently replace the
published equations.

## 2. Mechanism definition

Let \(\tilde{k}\) denote the current booking request.

The published DCA-Reroute mechanism solves one optimisation problem for:

\[
D(\tilde{k}) \cup \{\tilde{k}\},
\]

where \(D(\tilde{k})\) is the set of relevant previously accepted requests.

Potential future requests are excluded:

\[
K(\tilde{k}) = \varnothing.
\]

The routing plans of eligible previously accepted demands may be recomputed.

Scheduled services remain fixed. Demand is reallocated among fixed transport
and holding arcs; barge services themselves are not rescheduled or rerouted.

## 3. Eligible previously accepted set

The paper describes DCA-Reroute as including already accepted demands that
have not yet reached their final destination.

Table 3 gives the eligibility condition:

\[
k \in D(\tilde{k}),
\qquad
t_{res}(\tilde{k}) < t_{arr}(k).
\]

For Phase 7's published-equation baseline, the eligible past set therefore
contains demands satisfying all of the following:

1. the demand was processed before the current request;
2. its previous acceptance value is strictly positive;
3. its arrival threshold \(t_{arr}(k)\) is later than the current reservation
   time \(t_{res}(\tilde{k})\).

The exact operational meaning of \(t_{arr}(k)\) is treated as an ambiguity
because the paper describes it as the latest allowed arrival time of any
fragment, while also discussing demands not yet physically delivered.

## 4. Decision variables

### 4.1 Current request

For the current request \(\tilde{k}\):

\[
\xi(\tilde{k})
\]

is the acceptance variable.

Its domain follows Equation (10):

\[
\xi(\tilde{k}) =
\begin{cases}
1, & cat(\tilde{k}) = R,\\
[0,1], & cat(\tilde{k}) = P,\\
\{0,1\}, & cat(\tilde{k}) = F.
\end{cases}
\]

For every feasible arc \(a\):

\[
v(\tilde{k},a) \geq 0
\]

is the current request's routed volume.

### 4.2 Previously accepted requests

For every \(k \in D(\tilde{k})\), the acceptance value:

\[
\xi(k)
\]

is fixed to the acceptance decision made when \(k\) originally arrived.

The fixed accepted volume is:

\[
q_k^{accepted} = \xi(k)vol(k).
\]

For every feasible arc \(a\):

\[
v(k,a) \geq 0
\]

is recalculated by the DCA-Reroute model.

Previously accepted demands are mandatory at their previously accepted
volumes. Their original customer categories do not permit rejection or
acceptance reduction during rerouting.

A partially accepted past demand remains mandatory at:

\[
\xi(k)vol(k),
\]

not necessarily at its complete originally requested volume.

### 4.3 Excluded variables

Because:

\[
K(\tilde{k})=\varnothing,
\]

DCA-Reroute contains no:

- future-demand flow variables;
- \(maxvol(k)\) variables;
- \(y_{kj}\) variables;
- expected future-demand revenue term.

## 5. Objective function

The general published objective is Equation (1):

\[
\max
f(\tilde{k})\xi(\tilde{k})vol(\tilde{k})
+
\text{expected future revenue}
-
\text{truck-shifting penalties}.
\]

For DCA-Reroute:

\[
K(\tilde{k})=\varnothing,
\]

so the future-demand term disappears.

The resulting objective structure is:

\[
\max
f(\tilde{k})\xi(\tilde{k})vol(\tilde{k})
-
\sum_{k\in D(\tilde{k})\cup\{\tilde{k}\}}
pen(k)\,vol(k).
\]

Revenue already earned from previously accepted demands is not included as a
decision-dependent term because their acceptance decisions are fixed.

## 6. Truck-penalty ambiguity

The paper states that the penalty term represents demand volume shifted from
barge to truck.

However, the displayed formulation does not provide:

- an explicit truck-flow decision variable;
- a truck-capacity constraint;
- a clear mathematical link between \(pen(k)\) and volume actually shifted to
  truck;
- an unambiguous distinction between requested volume and truck-rerouted
  volume in the penalty expression.

Therefore, the first Phase 7 structural baseline will use:

\[
pen(k)=0
\]

and will be explicitly labelled:

**published DCA-Reroute, barge-only structural baseline**.

Truck recourse will not be invented inside the baseline model. It will be
implemented only as a separate, documented interpretation after the
barge-only published structure has been validated.

## 7. Capacity constraints — Equation (2)

For every transport arc \(a\in A^L\):

\[
\sum_{k\in D(\tilde{k})\cup\{\tilde{k}\}}
v(k,a)
\leq
cap_{avl}(a).
\]

Holding arcs remain uncapacitated unless a later experiment explicitly states
otherwise.

### 7.1 Capacity interpretation

The left-hand side contains the newly optimised flows of all demands included
in the rerouting problem.

Consequently, \(cap_{avl}(a)\) must not already subtract the old allocations of
those same demands.

For the published-equation reproduction, we define:

\[
cap_{avl}^{reroute}(a)
=
cap_{actual}(a)
-
fixedOutsideAllocation(a),
\]

where `fixedOutsideAllocation` contains only allocations belonging to demands
that are not included in the current rerouting problem.

This is a required implementation convention because the paper does not
provide the detailed capacity-release state-transition algorithm.

The following incorrect construction is prohibited:

\[
cap_{avl}(a)
=
cap_{actual}(a)
-
oldReroutableAllocation(a)
-
fixedOutsideAllocation(a),
\]

while also including the reroutable demands on the left-hand side of
Equation (2). That would double-count their capacity usage.

## 8. Current-request flow conservation — Equation (3)

For the current request:

\[
\sum_{a\in A^+(n)}v(\tilde{k},a)
-
\sum_{a\in A^-(n)}v(\tilde{k},a)
=
\begin{cases}
\xi(\tilde{k})vol(\tilde{k}), & n=o(\tilde{k}),\\
-\xi(\tilde{k})vol(\tilde{k}), & n=d(\tilde{k}),\\
0, & \text{otherwise}.
\end{cases}
\]

## 9. Previously accepted flow conservation — Equation (5)

For every \(k\in D(\tilde{k})\):

\[
\sum_{a\in A^+(n)}v(k,a)
-
\sum_{a\in A^-(n)}v(k,a)
=
\begin{cases}
\xi(k)vol(k), & n=o(k),\\
-\xi(k)vol(k), & n=d(k),\\
0, & \text{otherwise}.
\end{cases}
\]

The primary reproduction will follow Equation (5) as printed:

- source at the demand's original origin;
- complete previously accepted volume \(\xi(k)vol(k)\);
- destination at the demand's original destination.

It will not replace this equation with fragment-current-position flow
conservation.

## 10. Time-space source and destination convention

The paper defines \(o(k)\) and \(d(k)\) as terminals, while its flow equations
operate over terminal-time nodes.

The implementation convention already used in the reproduction is:

\[
source(k)=(o(k),t_{avl}(k)).
\]

Delivery is represented by a demand-specific auxiliary sink connected to
eligible destination-time nodes:

\[
(d(k),t),
\qquad
t\leq t_{due}(k).
\]

This convention operationalises the paper's availability and due-time
attributes without introducing revenue-management or rerouting behaviour not
present in the publication.

## 11. Variable domains — Equations (8) and (10)

All demand-arc flow variables are nonnegative:

\[
v(k,a)\geq 0.
\]

The baseline permits splittable demand flow because the publication uses
continuous nonnegative arc-volume variables and does not impose unsplittable
path-selection variables.

Only the current request has a newly decided acceptance variable.

Previously accepted requests use fixed acceptance values.

## 12. Published baseline versus execution-aware sensitivity

### 12.1 Primary published-equation baseline

The Phase 7 primary model uses:

- original demand source;
- fixed previously accepted volume;
- complete rerouting of the printed \(v(k,a)\) variables;
- Equation (5) as displayed.

### 12.2 Later execution-aware sensitivity

A separately labelled sensitivity model may use:

- current fragment location;
- executed arc history;
- undelivered volume only;
- immutable completed movements;
- release of only unexecuted reservations.

The sensitivity model must not be reported as an exact implementation of
Equation (5).

## 13. DCA-Reroute model contents

The Phase 7 optimiser must contain:

- one current-demand acceptance variable;
- current-demand flow variables;
- fixed acceptance values for eligible past demands;
- newly optimised flow variables for eligible past demands;
- shared transport capacity constraints;
- current-demand flow conservation;
- past-demand flow conservation;
- nonnegativity;
- no future-demand variables;
- no future-demand objective term.

## 14. Required validation properties

A solved DCA-Reroute instance must satisfy:

1. the current acceptance variable obeys its customer category;
2. every included past demand preserves its fixed accepted volume;
3. all flow-conservation equations hold;
4. all transport capacities are respected;
5. no eligible past demand is silently rejected;
6. old reroutable allocations are not double-subtracted;
7. future-demand variables are absent;
8. services and schedules remain unchanged;
9. repeated runs are deterministic;
10. the resulting solution is independently validated outside DOcplex.

## 15. Phase 7 implementation order

The implementation order is:

1. equation-to-code mapping;
2. eligible accepted-demand set construction;
3. rerouting-capacity construction;
4. DCA-Reroute model;
5. independent solution validation;
6. controlled hand-verifiable example;
7. rolling Full-Reroute integration;
8. DCA versus DCA-Reroute comparison;
9. reproduction audit.

## 16. Out of scope for the initial Phase 7 baseline

The following are deferred:

- potential future-demand revenue management;
- \(y_{kj}\) and \(maxvol(k)\);
- DCA-RRM;
- water-level capacity-update scenarios;
- Partial-Reroute forecast cadence;
- truck recourse;
- execution-aware fragment rerouting;
- rerouting penalties not supported by an explicit truck variable.
