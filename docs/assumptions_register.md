# Assumptions and Ambiguity Register

## 1. Purpose

This register records every important implementation decision that is not
completely and unambiguously specified in the source paper.

Each entry contains:

- an identifier;
- an evidence classification;
- what the paper establishes;
- what remains unclear;
- the baseline implementation decision;
- any planned sensitivity analysis;
- the corresponding question for the authors;
- the expected impact on the software.

## 2. Evidence classifications

| Status | Meaning |
|---|---|
| Explicit | Directly stated in the paper |
| Derived | Logically inferred from stated information |
| Assumed | Required for implementation but not fully specified |
| Sensitivity | Alternative interpretation to be tested |
| Unresolved | Requires clarification from the authors |

---

## A001 — Exact service schedules

**Status:** Unresolved

**Paper evidence:**
Services have fixed routes, schedules, capacities, and periodic operation.
Two service families are used in the experiments.

**Ambiguity:**
The complete departure and arrival schedule for every service leg is not
reported sufficiently to reconstruct the experimental networks exactly.

**Baseline implementation:**
Create documented synthetic service schedules that preserve:

- five consecutive terminals;
- bidirectional operation;
- weekly periodicity;
- lower-frequency Service Family 1;
- higher-frequency Service Family 2;
- equal travel times between consecutive terminals.

All schedules will be stored in configuration files rather than embedded in
Python code.

**Sensitivity:**
Test alternative departure offsets and service frequencies.

**Question for authors:**
Can the exact schedules or original service configuration files for both
service families be provided?

**Code impact:**
`configs/`, network builder, experiment configurations.

---

## A002 — Destination-time interpretation

**Status:** Assumed

**Paper evidence:**
Each demand has a physical destination \(d(k)\) and a due time
\(t^{due}(k)\). Flow conservation is defined over terminal-time nodes.

**Ambiguity:**
It is not fully clear whether delivery must occur:

1. exactly at terminal-time node \((d(k), t^{due}(k))\); or
2. at any destination-time node no later than \(t^{due}(k)\).

**Baseline implementation:**
Permit arrival at any destination-time node satisfying:

\[
t^{arrival}(k) \leq t^{due}(k).
\]

Connect all eligible destination-time nodes to a demand-specific super-sink.

**Reason:**
A due time is interpreted as a latest permissible delivery time rather than a
mandatory exact arrival time.

**Sensitivity:**
Compare with exact-due-time delivery on selected toy instances.

**Question for authors:**
Does the implementation permit delivery at any time before the deadline, or
only at the destination node corresponding exactly to the due time?

**Code impact:**
Demand-feasible subgraphs, super-sink construction, flow conservation.

---

## A003 — State of partially executed demands

**Status:** Assumed operational interpretation

**Paper evidence:**
Previously accepted but undelivered demands may have their itineraries
modified during rerouting. Accepted quantities remain commitments while their
future barge itineraries may be reoptimised.

**Ambiguity:**
The printed formulation does not explicitly encode a fragment-specific
terminal-time source for cargo that has already completed part of its route.
Its balance structure may therefore be read as restarting the accepted demand
from its original source, even when part of the itinerary has already been
executed.

The paper also does not fully specify how an accepted demand should be divided
when part of its volume is:

- already delivered;
- travelling on an in-transit service;
- waiting at an intermediate terminal;
- still assigned to future services.

**Baseline implementation:**
At each booking decision epoch, every accepted commitment is reconstructed from
its persisted path flows and separated into delivered and unfinished demand
fragments.

For every unfinished fragment, the implementation records:

- its fixed accepted volume;
- its execution-aware terminal-time position;
- completed physical arcs;
- any currently in-transit physical arc;
- future unexecuted physical and holding arcs;
- the original persisted commitment and delivery deadline.

Completed movement is irreversible.

An in-transit service is also immutable. Because the persisted fragment record
may remain at the service's tail until the service arrival time, the rerouting
decision layer explicitly locks the in-transit arc and uses its head
terminal-time node as the effective rerouting source.

Only future transport reservations that remain bookable at the current decision
time are released into rerouting capacity. Capacity used by completed,
in-transit, delivered, excluded, or otherwise fixed commitments is not released.

The joint DCA-Reroute model then:

1. keeps each unfinished fragment's accepted volume fixed;
2. preserves completed and in-transit movements;
3. reoptimises only future itinerary flows;
4. jointly routes the current demand and eligible unfinished fragments;
5. rebuilds prior commitments while preserving their original booking
   metadata;
6. appends the current booking event exactly once.

**Reporting rule:**
This is an execution-aware operational interpretation under Assumption A003.
It must not be presented as a verbatim implementation of printed Equation (5).

A prior commitment listed in evaluation output was included in joint
reoptimisation and rebuilt in persistent state. This does not by itself prove
that its physical route changed.

**Question for authors:**
During rerouting:

1. are completed and in-transit arcs fixed;
2. is each unfinished fragment restarted from its execution-aware
   terminal-time position; and
3. does the published implementation use fragment-specific source-balance
   constraints not displayed in the printed formulation?

**Code impact:**

- `src/barge_rerouting/domain/fragment.py`
- `src/barge_rerouting/rolling_horizon/execution.py`
- `src/barge_rerouting/rerouting/eligibility.py`
- `src/barge_rerouting/rerouting/in_transit.py`
- `src/barge_rerouting/rerouting/capacity.py`
- `src/barge_rerouting/rerouting/network.py`
- `src/barge_rerouting/rerouting/optimization.py`
- `src/barge_rerouting/rerouting/transition.py`
- `src/barge_rerouting/rerouting/orchestration.py`
- `src/barge_rerouting/rerouting/run.py`
## A004 — Construction of the future-demand set

**Status:** Unresolved

**Paper evidence:**
\(K(\tilde{k})\) contains potential future demands having direct possible
interactions in time with the current demand.

**Ambiguity:**
The exact operational rule used to decide whether a future demand belongs to
\(K(\tilde{k})\) is not provided.

**Implemented Phase 8 baseline:**
The current `FutureDemandForecast` object does not contain a separate
reservation-time field. The operational `A004_SHARED_ARC` rule therefore uses
future availability as the timing proxy.

Include a forecast when:

1. its availability time is strictly later than the current decision time;
2. its availability time lies within the optional look-ahead horizon, when one
   is supplied;
3. it has a feasible time-space network; and
4. its feasible subgraph shares at least one capacity-constrained transport arc
   with the current demand's feasible subgraph.

An explicit-selection mode is also available for controlled experiments and
retains supplied feasible forecasts without requiring shared-arc interaction.

The Phase 8 DCA-RM implementation does not include accepted unfinished demands
when constructing shared-arc interaction because DCA-RM contains no past-demand
rerouting commodities. This interaction rule must be revisited for the combined
DCA-RRM model in Phase 9.

This is a disclosed operational interpretation and not a verbatim rule supplied
by the paper.

**Sensitivity:**
Compare:

- time-window overlap only;
- common-origin-destination corridor overlap;
- shared-feasible-arc overlap;
- fixed-number future-demand look-ahead.

**Question for authors:**
How was “direct possible interaction in time” operationally evaluated when
constructing \(K(\tilde{k})\)?

**Code impact:**
Forecast generation, policy input construction, model size.

---

## A005 — Future-demand expected-revenue expression

**Status:** Explicit baseline with sensitivity alternative

**Paper evidence:**
For protected level \(j\), the printed future-demand contribution uses:

\[
\sum_{x=0}^{j} xP_k(x).
\]

**Ambiguity:**
This expression does not credit probability outcomes for which \(x>j\). It is
therefore not generally equal to:

\[
E[\min(X_k,j)].
\]

**Baseline implementation:**
Implement the expression exactly as printed:

\[
R^{printed}_k(j)
=
f(k)\sum_{x=0}^{j}xP_k(x).
\]

**Sensitivity implementation:**
Also implement:

\[
R^{capped}_k(j)
=
f(k)E[\min(X_k,j)].
\]

The baseline results will use the printed expression. The capped version will
be reported separately and clearly labelled as a sensitivity analysis.

**Question for authors:**
When realised future volume exceeds protected level \(j\), is the request
assumed to be rejected entirely, or was a capped expectation intended?

**Code impact:**
Future-demand value tables, objective coefficients, sensitivity experiments.

---

## A006 — Splittable demand

**Status:** Derived

**Paper evidence:**
Demand arc-flow variables are continuous.

**Interpretation:**
A demand may be divided across more than one feasible itinerary unless
additional binary path-use restrictions are imposed.

**Baseline implementation:**
Treat demand as aggregated TEU flow that may be split across itineraries.

**Sensitivity:**
An unsplittable path-based or binary arc-use formulation may be tested on small
instances, but it is not part of the initial core reproduction.

**Question for authors:**
Were demand flows intentionally divisible, or were additional implementation
restrictions used to keep each request on a single itinerary?

**Code impact:**
Variable domains, path interpretation, model size.

---

## A007 — Holding-arc capacities and costs

**Status:** Assumed

**Paper evidence:**
Holding arcs allow cargo to wait at origins or intermediate terminals.

**Ambiguity:**
No terminal-storage capacities or holding costs are clearly specified.

**Baseline implementation:**
Holding arcs will have:

- no binding capacity;
- zero direct operating cost;
- availability only between consecutive time periods;
- no movement revenue.

**Sensitivity:**
Terminal-storage limits or waiting costs may be added as an extension, not as
part of the baseline reproduction.

**Question for authors:**
Were holding arcs treated as unlimited and costless in the experiments?

**Code impact:**
Network parameters and objective function.

---

## A008 — Truck recourse representation

**Status:** Assumed

**Paper evidence:**
Truck transport is available as an alternative mode and penalties are incurred
when accepted barge volume is shifted to truck.

**Ambiguity:**
The displayed mathematical formulation does not completely specify:

- truck decision variables;
- truck arcs or routes;
- truck capacities;
- exact penalty calculation;
- which demand categories may be transferred.

**Baseline implementation:**
For each accepted unfinished demand, define:

\[
q_k^{truck} \geq 0.
\]

Require:

\[
\text{remaining accepted volume}
=
\text{barge-delivered volume}
+
q_k^{truck}.
\]

Assume truck capacity is available when recourse is activated. Apply a
configurable penalty per TEU transferred to truck.

**Sensitivity:**
Test different truck penalties and, if needed, limited truck capacity.

**Question for authors:**
How were truck-transfer volumes, availability, and penalty costs represented
in the implementation?

**Code impact:**
Disruption model, recourse variables, objective, performance indicators.

---

## A009 — Water-level capacity transformation

**Status:** Explicit scenario rule with modelling simplification

**Paper evidence:**
Actual service capacity is reduced under lower water levels using scenario
factors such as:

\[
\lambda \in \{1.0,0.9,0.8,0.7\}.
\]

**Baseline implementation:**

\[
C_a^{actual}
=
\lambda_a C_a^{nominal}.
\]

The multiplier may vary by service leg and update time, although the initial
reproduction will use scenario-wide factors where appropriate.

**Limitation:**
The proportional relationship is treated as a scenario abstraction rather than
a physically calibrated vessel-draught model.

**Sensitivity:**
Test leg-specific and time-specific capacity factors.

**Question for authors:**
Was the proportional capacity transformation empirically calibrated or used
only as a controlled experimental scenario?

**Code impact:**
Capacity-update events, dynamic scenarios, AFR and NFR calculations.

---

## A010 — Synthetic demand generation

**Status:** Partly explicit, partly unresolved

**Paper evidence:**
The experiments use synthetic demands with attributes including volume,
origin, destination, booking time, availability time, deadline, customer
category, and fare.

**Missing inputs include:**

- exact \(VMAX\);
- complete volume probability distributions;
- random seeds;
- exact anticipation-time pools;
- exact delivery-time pools;
- base fares;
- fare multipliers;
- scenario-specific demand counts.

**Baseline implementation:**
Place all generation parameters in YAML configuration files. Use explicit,
fixed random seeds and save generated instances before optimisation.

**Scientific rule:**
Synthetic parameters will not be tuned merely to force the reported percentage
improvements.

**Question for authors:**
Can the original demand-generation parameters, seeds, or generated instances
be provided?

**Code impact:**
Demand generator, configurations, reproducibility metadata.

---

## A011 — Customer-category acceptance domains

**Status:** Explicit

**Paper evidence:**

- Regular customers \(R\): all demand must be accepted.
- Partially-spot customers \(P\): demand may be partially accepted.
- Fully-spot customers \(F\): demand must be fully accepted or rejected.

**Baseline implementation:**

For a current request:

\[
\xi_k = 1
\qquad \text{for }R,
\]

\[
0 \leq \xi_k \leq 1
\qquad \text{for }P,
\]

\[
\xi_k \in \{0,1\}
\qquad \text{for }F.
\]

Previously accepted demand retains its committed accepted volume during
rerouting.

**Code impact:**
Decision-variable domains and policy-equivalence tests.

---

## A012 — Performance-indicator denominators

**Status:** Unresolved

**Paper evidence:**
The experiments report AFR, NFR, VTR, VFB, VOB, VOA, TR, and ST.

**Ambiguity:**
The exact denominators for several volume-rate indicators are not fully clear
from the abbreviated definitions.

**Baseline implementation:**
Every indicator will be implemented with an explicit mathematical definition
stored in the reporting documentation.

No indicator will be reported until its numerator, denominator, time horizon,
and unit are documented.

**Question for authors:**
What are the precise numerator and denominator definitions for VTR, VFB, VOB,
and VOA?

**Code impact:**
Result aggregation and comparison with Tables 5–7.

---

## A013 — Apparent numerical inconsistencies

**Status:** Unresolved

**Observed issues include:**

- Table 5 appears to contain an AFR value of \(855\%\), possibly intended as
  \(85\%\).
- Table 6 appears to contain an NFR value of \(8\%\) where the relationship
  \(0.9 \times 89\% \approx 80\%\) suggests \(80\%\).
- Demand-density and total-demand descriptions may refer to different
  experimental constructions.

**Baseline implementation:**
Do not silently modify the published values.

Report them as printed and, separately, identify the mathematically plausible
interpretation.

**Question for authors:**
Can the apparent AFR and NFR entries and the demand-count construction be
confirmed?

**Code impact:**
Validation report and result-comparison tables.

---

## A014 — Sustainability interpretation

**Status:** Explicit limitation

**Paper evidence:**
The research is motivated partly by the environmental advantages of inland
waterway transport.

**Limitation:**
The displayed objective maximises expected revenue and applies recourse
penalties. It does not explicitly optimise:

- greenhouse-gas emissions;
- energy consumption;
- road congestion;
- environmental externalities;
- modal-shift sustainability.

**Baseline implementation:**
Do not claim that a higher-revenue solution with greater truck use is
environmentally superior.

**Extension:**
Add emissions or multimodal external costs only as a clearly labelled research
extension after reproducing the baseline model.

**Question for authors:**
Is explicit environmental-cost integration envisaged in future versions of the
model?

**Code impact:**
Interpretation of disruption results and future research section.

---

## A015 — Software-environment difference

**Status:** Explicit reproduction difference

**Paper environment:**

- Python 3.8;
- CPLEX 22.1.1.

**Current reproduction environment:**

- Python 3.12.3;
- CPLEX API/engine 22.2.0.0;
- CPLEX Python package 22.2.0.1;
- DOcplex 2.32.264.

**Baseline implementation:**
Record all software versions and solver parameters with every experiment.

Do not directly compare solving times without acknowledging hardware, software,
presolve, and solver-version differences.

**Code impact:**
Environment metadata and computational-results reporting.

---

## 3. Register maintenance rule

Every new uncertainty discovered during implementation must receive:

1. a unique identifier;
2. a status;
3. a documented baseline decision;
4. a test or validation consequence;
5. an author question when appropriate.

The code should refer to assumption identifiers where the implementation choice
is scientifically consequential.

---

## A016 — Zero future-volume selector

**Status:** Assumed to remove degeneracy

**Paper evidence:**
The linking and exclusivity constraints sum over positive levels
\(1,\ldots,VMAX_k\), while the variable-domain statement appears to permit
\(j=0\).

**Ambiguity:**
It is unclear whether an explicit binary variable \(y_{k0}\) was created.

If \(y_{k0}\) exists but is absent from the linking equation and objective, it
can create equivalent zero-volume solutions without changing the decision.

**Baseline implementation:**
Create selectors only for:

\[
j\in\{1,\ldots,VMAX_k\}.
\]

Represent zero protected volume by:

\[
y_{kj}=0
\qquad
\forall j.
\]

**Question for authors:**
Was an explicit \(y_{k0}\) variable used, or was zero protected volume
represented by selecting no positive level?

**Code impact:**
Future-selector construction, solution uniqueness, and model size.

---

## A017 — Parallel scheduled transport arcs

**Status:** Derived implementation requirement

**Paper evidence:**
The transportation system contains multiple scheduled services and service
legs.

**Implementation issue:**
Different services may connect the same departure and arrival terminal-time
nodes. A simple directed graph would overwrite one service arc with another.

**Baseline implementation:**
Represent the time-space network using a directed multigraph:

\[
G=(N^{IT},A)
\]

where parallel arcs are allowed and every arc has a unique identifier.

**Reason:**
Service identity, capacity, direction, and schedule must remain distinct even
when two services share the same tail and head nodes.

**Code impact:**
Time-space builder, arc indexing, plotting, CPLEX flow variables, and capacity
constraints.

---

## A018 — Interpretation of future-demand value

**Status:** Baseline plus sensitivity analysis

**Paper evidence:**
The printed revenue-management expression contains:

\[
\sum_{x=0}^{j}xP_k(x).
\]

**Ambiguity:**
This differs from the commonly expected protected-volume expression:

\[
E[\min(X_k,j)].
\]

For outcomes above \(j\), the printed expression contributes zero, whereas the
capped expectation contributes \(j\).

**Baseline implementation:**
Use the printed prefix expression in the strict reproduction model.

**Sensitivity implementation:**
Run a separate experiment using the capped expectation.

**Reporting requirement:**
Do not silently replace one expression with the other. Report the objective
and allocation effects of both formulations.

---

## A019 — Ordering of simultaneous booking requests

**Status:** Baseline implementation assumption

**Paper evidence:**
The demand-allocation mechanism is dynamic and requests are processed as they
become known.

**Missing information:**
The exact request-arrival sequence is not available for demands sharing the
same recorded reservation time.

**Baseline implementation:**
Process requests sequentially using deterministic order:

\[
(t_k^{res},k).
\]

That is, reservation time is primary and demand identifier is the tie-breaker.

**Reason:**
Sequential allocation requires a complete order. Deterministic ordering makes
the experiment reproducible.

**Sensitivity requirement:**
Later experiments may randomise the order within equal-time groups while
preserving the same demand instance.

**Reporting requirement:**
Do not describe the demand-ID tie-breaker as an empirically observed arrival
order.

---

## A003 Phase 7 operationalisation

Phase 7 applies A003 as a primary reproduction assumption.

The publication's displayed past-demand flow equation uses the original demand
origin and complete accepted quantity. Its surrounding rerouting description,
however, concerns accepted cargo that has not yet reached its destination.

The implementation resolves this by reconstructing physical execution state at
every decision epoch.

For each accepted demand:

\[
acceptedVolume
=
deliveredVolume
+
unfinishedFragmentVolume.
\]

Only unfinished fragments are reoptimised.

Each fragment begins at its actual current terminal-time node. Its executed arc
history remains fixed, while only future unexecuted reservations may be
released and replaced.

This is not presented as a verbatim transcription of the displayed equation.
It is the documented implementation interpretation required to prevent
already transported cargo from restarting at the original source.

A literal original-source interpretation may later be implemented as a
diagnostic sensitivity, but it is not the primary rolling-horizon rerouting
mechanism.
---

## A020 — Combined DCA-RRM future-set interaction boundary

**Status:** Baseline implementation assumption

**Paper evidence:**
The combined DCA-RRM formulation includes accepted unfinished demand,
the current request, and a future-demand set \(K(\tilde{k})\).

**Missing information:**
The paper does not fully specify whether a forecast should enter
\(K(\tilde{k})\) because it interacts with:

1. the current request;
2. an unfinished accepted fragment;
3. either of the above.

**Baseline implementation:**
Phase 9 preserves the Phase 8 A004 selection rule.

A future forecast enters the combined DCA-RRM model when its feasible
network shares at least one scheduled transport arc with the feasible
network of the **current request**.

A forecast that interacts only with a prior unfinished fragment is not
selected by the baseline rule.

**Reason:**
Keeping the same future-set construction in DCA-RM and DCA-RRM makes
their forecast inputs directly comparable and avoids silently expanding
the information set in the combined mechanism.

**Sensitivity requirement:**
A fragment-expanded future-set rule may later be evaluated as a separate,
explicitly labelled sensitivity.

**Reporting requirement:**
Do not claim that the current-request shared-arc rule is the paper's
uniquely established construction of \(K(\tilde{k})\).

**Code impact:**
`revenue_management/future_set.py`,
`revenue_management/rrm_orchestration.py`, canonical policy comparison,
and future Phase 10 sensitivity experiments.

---

## A021 — Rerouting-aware capacity-transition diagnostics

**Status:** Derived implementation requirement

**Implementation issue:**
The original rolling-horizon capacity-transition diagnostic was designed
for myopic booking decisions. Under that mechanism, one event cannot
increase residual bookable transport capacity.

DCA-R and DCA-RRM may release an earlier future reservation before
reconstructing accepted unfinished cargo. Residual capacity on an
individual arc may therefore increase legitimately between the pre-event
and post-event states.

**Baseline implementation:**
Keep the original myopic `ArcCapacityTransition` invariant unchanged.

Use a separate DCA-RRM transition diagnostic that permits:

\[
C^{after}_{a} > C^{before}_{a}
\]

when rerouting releases capacity on arc \(a\).

Define the net reserved-volume change as:

\[
\Delta R_a
=
C^{before}_{a}
-
C^{after}_{a}.
\]

Therefore:

- \(\Delta R_a>0\) means additional capacity was reserved;
- \(\Delta R_a<0\) means capacity was released;
- \(\Delta R_a=0\) means no net reservation change.

**Validation requirement:**
Residual capacities must remain finite and non-negative within numerical
tolerance. Allowing a release does not relax the combined transport-capacity
constraint in the optimisation model.

**Reporting requirement:**
A capacity release does not by itself prove that a complete physical route
changed. Route change requires comparison of before-and-after physical arc
sequences.

**Code impact:**
`revenue_management/rrm_orchestration.py`, capacity-transition diagnostics,
and DCA-RRM run tests.

---

## A022 — Phase 9 stable-capacity and truck-disabled boundary

**Status:** Explicit experimental scope plus implementation boundary

**Paper evidence:**
The stable-capacity experiment applies Full-Reroute without allowing demand
volume to move to an alternative transportation mode.

The general printed objective nevertheless mentions penalties incurred when
volumes are shifted from barge to truck.

**Phase 9 implementation:**
Phase 9 implements DCA-RRM under:

\[
C_{a,\tau}^{actual}=C_a^{nominal}
\]

and:

\[
q_k^{truck}=0.
\]

It therefore contains no truck-flow variable and no truck-penalty term.

This corresponds to the stable-capacity, truck-disabled mechanism evaluated
before service-status changes and truck recourse are introduced.

**Boundary:**
Phase 9 must not be described as implementing the paper's complete
service-disruption and alternative-mode formulation.

**Phase 10 responsibility:**
Phase 10 introduces:

- actual capacities;
- water-level status changes;
- explicit truck volumes;
- truck penalties;
- Partial-Reroute;
- disruption-aware Full-Reroute.

**Reporting requirement:**
Phase 9 canonical results are mechanism-validation results for the
stable-capacity, truck-disabled core.

---

## A023 — Proportional water-adjusted actual capacity

**Status:** Baseline operational assumption

**Paper evidence:**
The service-status-change experiment states that vessel capacity changes
proportionally with the water level.

**Baseline implementation:**

For a future transport arc \(a\) covered by water-status factor
\(\lambda_\tau\),

\[
C_{a,\tau}^{actual}
=
\lambda_\tau C_a^{nominal}.
\]

The baseline applies no integer rounding after the multiplication.

Only not-yet-departed transport legs are modified by a newly available
status update. Completed and currently in-transit movements retain their
historical execution state.

**Missing information:**
The publication does not specify:

- a TEU-capacity rounding rule;
- whether all services receive the same water factor;
- the exact realised water-level sequence used in the reported experiments.

**Reporting requirement:**
Do not describe the no-rounding convention or a synthetic water-status
sequence as a uniquely established paper implementation.

**Code impact:**
`disruption/status.py`,
`disruption/capacity.py`,
`disruption/assessment.py`,
and Phase 10 dynamic experiments.

---

## A024 — Same-time status precedence and immutable execution

**Status:** Baseline operational assumption

**Missing information:**
The publication does not specify the ordering when a new service-status
forecast and a booking request occur at the same model timestamp.

**Baseline implementation:**

At a common physical time:

1. the status update is processed first;
2. actual future capacities are reconstructed;
3. unfinished accepted demand is recovered when required;
4. the booking decision then observes the newest capacity information.

Already completed movement and movement already in transit are immutable.

The operational timeline therefore uses the deterministic ordering:

\[
(\text{time},\ \text{status before booking},\ \text{local sequence}).
\]

**Reason:**
A booking occurring at the publication time of a new forecast should not
silently optimise against superseded capacity information.

**Reporting requirement:**
This ordering must be reported as an implementation assumption, not as a
timing rule explicitly stated by the authors.

**Code impact:**
`disruption/timeline.py`,
`disruption/recovery.py`,
`disruption/operational_execution.py`,
`disruption/partial_reroute.py`,
and `disruption/dynamic_full_reroute_run.py`.

---

## A025 — Explicit direct truck recourse

**Status:** Transparent operationalisation of an under-specified paper term

**Paper evidence:**
The printed general objective contains a penalty for demand volume shifted
from barge to trucks, and the service-status-change discussion states that
trucks can be used when accepted cargo cannot be transported by barge.

**Missing information:**
The displayed formulation does not fully define:

- a truck decision variable;
- truck arcs or routes;
- truck capacity;
- truck travel time;
- the exact transfer terminal;
- the numerical truck penalty.

**Baseline implementation:**
For every reroutable unfinished fragment \(r\), introduce:

\[
q_r^{truck}\geq0.
\]

The remaining contractual volume satisfies:

\[
Q_r^{remaining}
=
Q_r^{barge}
+
q_r^{truck}.
\]

Truck transfer is:

- direct from the fragment's execution-aware rerouting source;
- unlimited in capacity;
- assumed able to satisfy the existing delivery deadline;
- terminal, so trucked volume cannot return to the barge network;
- penalised linearly per TEU.

At a status-only recovery epoch:

\[
\min
\sum_r c_r^{truck}q_r^{truck}.
\]

The penalty coefficients must be supplied explicitly by the experiment.
They are never silently inferred.

**Interpretation boundary:**
This is an operationalisation of the paper's truck-penalty concept.
It is not presented as a verbatim reconstruction of an unpublished truck
submodel.

**Code impact:**
`disruption/truck_recourse.py`,
`disruption/recovery_transition.py`,
and dynamic PR/FR orchestration.

---

## A026 — Current-request trucking boundary in production dynamic FR

**Status:** Baseline implementation boundary

**Paper ambiguity:**
The printed general penalty expression may be read as permitting truck
allocation for the current request as well as previously accepted demand,
but the publication does not specify when an incoming request may be
initially assigned to truck.

**Model capability:**
The Phase 10 dynamic Full-Reroute optimisation exposes an explicit
current-request truck variable as a diagnostic/general modelling capability.

**Production baseline:**
The operational dynamic Full-Reroute runner sets:

\[
q_{\tilde{k}}^{truck}=0
\]

for the newly arriving request.

Truck recourse is therefore used for already accepted unfinished cargo,
while the current request is accepted only when its accepted volume can be
represented by the barge booking state.

**Reason:**
`RollingBookingState` and `DemandCommitment` intentionally preserve the
Phase 6--9 contractual barge-plan invariant. Hiding an immediate current
truck assignment inside that state would silently corrupt its semantics.

**Sensitivity boundary:**
Allowing direct current-request trucking remains an explicit diagnostic or
future sensitivity and must be labelled separately.

**Code impact:**
`disruption/dynamic_full_reroute.py`,
`disruption/dynamic_full_reroute_transition.py`,
and `disruption/dynamic_full_reroute_run.py`.

---

## A027 — Repeated recovery uses incremental terminal truck history

**Status:** Derived implementation requirement

**Operational issue:**
The same accepted demand may be rerouted more than once, for example:

1. after a status update; and
2. again after a same-time or later Full-Reroute booking trigger.

Already trucked cargo must not re-enter the barge recovery commodity set.

**Baseline implementation:**
Each new recovery solve operates only on the demand volume that remains
operationally unfinished after previous terminal truck transfers.

Truck history is cumulative:

\[
Q_k^{truck,total}
=
\sum_g q_{kg}^{truck,new},
\]

where \(g\) indexes successive recovery generations.

For example, if an initial status recovery sends 3 TEU to truck and a later
booking-triggered recovery sends one additional TEU, the cumulative volume is:

\[
3+1=4,
\]

not 7 TEU and not a new four-TEU transfer.

Recovery-generation chronology is determined by the persisted
`recovery_event_ids` sequence, not by lexicographic event-ID ordering.

**Validation requirement:**
At every execution epoch:

\[
Q_k^{accepted}
=
Q_k^{remaining}
+
Q_k^{delivered,barge}
+
Q_k^{delivered,truck}.
\]

**Code impact:**
`disruption/recovery_transition.py`,
`disruption/operational_execution.py`,
and dynamic Full-Reroute transition/run tests.

---

## A028 — Phase 11 periodic service-schedule reconstruction

**Status:** Controlled substitute-input assumption

**Paper evidence:**
The experimental network contains five consecutive terminals A--E with equal
travel times between adjacent terminals.

The time unit is half a day.

Scheduled services repeat weekly, corresponding to 14 model periods.

The publication distinguishes two service formations:

- Service Family 1: two recurring services in each direction;
- Service Family 2: four recurring services in each direction.

Service Family 2 therefore has twice the service frequency of Service
Family 1.

**Missing information:**
The publication does not uniquely disclose:

- the exact within-week departure offsets;
- the first departure epoch;
- the numerical travel duration between adjacent terminals.

**Controlled baseline:**
Phase 11 uses a 14-period repetition cycle.

Service Family 1 uses departure offsets:

\[
(0,7).
\]

Service Family 2 uses departure offsets:

\[
(0,3,7,10).
\]

Both sets of offsets apply independently in both directions.

Adjacent-terminal travel time is set to one model period, corresponding to
one half-day in the implementation.

A recurring service slot retains the same service identifier across weekly
cycles.

Only complete corridor occurrences that fit within the configured
experimental horizon are generated.

**Reason:**
The baseline preserves:

- the published five-terminal corridor;
- equal adjacent travel times;
- weekly periodicity;
- two versus four service slots per direction;
- the exact 2:1 frequency relationship;

without pretending that unpublished departure times are known.

**Sensitivity requirement:**
Alternative departure offsets and adjacent travel durations must be evaluated
as explicitly labelled schedule sensitivities rather than silently replacing
this baseline.

**Reporting requirement:**
No numerical result depending on these schedule offsets may be described as
an exact reconstruction of the authors' unpublished timetable.

**Code impact:**
`experiments/phase11_services.py` and all Phase 11 publication-facing
experiment configurations.

---

## A029 — Phase 11 structural demand-generation boundary

**Status:** Paper-supported structure with controlled substitute timing pools

**Paper-supported structure:**
The Phase 11 publication-facing demand process preserves:

- ten request arrivals per half-day period;
- ordered origin-destination selection over terminals A--E;
- uniform OD sampling;
- uniform selection among customer categories R, P and F;
- anticipation parameters selected from distance-dependent pools;
- delivery-time parameters selected from distance-dependent pools.

**Missing information:**
The publication does not uniquely disclose:

- the numerical distance-dependent anticipation pools;
- the numerical distance-dependent delivery pools;
- the exact realised-demand volume distribution;
- the value of VMAX needed to reconstruct realised volumes;
- complete base fares and fare multipliers;
- the original random seeds.

**Implementation boundary:**
Phase 11 first generates immutable structural request templates containing:

- OD;
- reservation time;
- anticipation lag;
- availability time;
- delivery slack;
- due time;
- customer category.

Volume and fare are deliberately absent from this structural layer.

They may be attached only after their own controlled-input contract is
defined.

**Common-random-number requirement:**
The structural request generator must not depend on:

- service family;
- nominal vessel capacity;
- policy.

For a fixed seed and structural demand specification, the identical request
template fingerprint must therefore be reusable across all relevant
experimental cells.

**Horizon rule:**
Request periods must be chosen so every value in every configured timing pool
fits inside the horizon. The generator does not silently truncate, redraw or
bias late-horizon timing values.

**Reporting requirement:**
The structural generation process may be described as publication-facing.
The undisclosed numerical timing pools remain controlled substitute inputs.

**Code impact:**
`experiments/phase11_demands.py` and the later Phase 11 demand-realisation
layer.

---

## A030 — Phase 11 horizon and demand-count interpretation

**Status:** Unresolved publication ambiguity

**Paper evidence:**
Section 4.1 states a simulated rolling-time horizon of `400/800` time
instants.

The same section states a demand density of 10 requests per half-day time
unit.

For the service-status-change experiments, the paper separately reports a set
of 800 demands and states that 40 demand requests occur during four
half-day periods.

**Ambiguity:**
The publication does not establish a unique mapping between:

- the 400/800 time-instants statement;
- the number of generated demand opportunities;
- the number of positive-volume realised requests;
- the 800-demand dynamic experiment.

At density 10, interpreting 800 time instants as 800 realised requests would
be inconsistent.

**Baseline implementation rule:**
Do not infer the experiment demand count by multiplying or identifying these
quantities silently.

Store separately:

- network horizon;
- request-generation periods;
- demand density;
- generated structural request count;
- zero-volume realisations;
- positive-volume booking-event count.

The Table 4 pilot will not be promoted to the full experiment until this
distinction is explicit in configuration and outputs.

**Reporting requirement:**
Do not claim that 400/800 time instants means 400/800 demands.

**Question for authors:**
How do the reported 400/800 time instants, density 10, and 800-demand dynamic
experiment relate to one another?

**Code impact:**
Phase 11 experiment configuration, demand realisation, run metadata and
Table 4/5 reproduction.

---

## A031 — Phase 11 volume and fare numerical inputs

**Status:** Published structure with unresolved numerical values

**Paper evidence:**
For the experimental demand process:

- demand volume is a discrete random realisation on `0..VMAX`;
- one maximum volume is assumed for the experimental demands;
- volume follows a specified probability distribution;
- OD pairs are generated uniformly;
- anticipation and delivery values are selected uniformly from
  distance-dependent pools;
- thresholds classify early/late reservation and standard/express delivery;
- each OD distance has a base fare `p`;
- unit fare follows the multiplicative structure

\[
f(k)
=
p
\times r_{\mathrm{anticipation}}
\times r_{\mathrm{delivery}};
\]

- the early-reservation rate equals 1;
- the standard-delivery rate equals 1;
- premium timing-class rates are strictly greater than 1.

**Missing numerical information:**
The article does not disclose sufficiently for exact numerical reproduction:

- `VMAX`;
- the probability mass over `0..VMAX`;
- the anticipation pools;
- the delivery pools;
- the timing-class thresholds;
- base fares by OD distance;
- the late-reservation multiplier;
- the express-delivery multiplier;
- original random seeds.

**Baseline implementation rule:**
The software first encodes and validates the published input structure without
assigning substitute values.

Any numerical baseline subsequently introduced must be classified as
`controlled_substitute_input`, stored in configuration, fingerprinted, and
fixed before comparison with Table 4.

No parameter may be calibrated merely to move the reproduced IR values toward
the published values.

**Zero-volume boundary:**
The paper explicitly permits a volume realisation of zero while also describing
ten requests entering the system per half-day.

The implementation must therefore distinguish a generated demand opportunity
from a positive-volume optimisation booking event until this interpretation is
resolved.

**Code impact:**
`experiments/phase11_economics.py`, demand realisation, forecast generation,
configuration fingerprints and Table 4 experiments.

---

## A032 — Pre-registered controlled Table 4 numerical baseline

**Status:** Controlled substitute input

The source paper specifies the structure of the volume, timing and fare
generation processes but does not publish the complete numerical inputs needed
for exact Table 4 reproduction.

The following baseline is fixed before the first Table 4 optimisation run.

### Volume

\[
VMAX=2
\]

with:

\[
P(X=0)=0.40,\quad
P(X=1)=0.40,\quad
P(X=2)=0.20.
\]

Hence:

\[
E[X]=0.8.
\]

A zero-volume draw represents a generated demand opportunity that does not
become a positive-volume optimisation booking.

### Timing pools

For corridor distance \(d\):

\[
anticipation \in \{d,d+1,d+2\},
\]

and:

\[
deliverySlack \in \{d+7,d+8,d+9\}.
\]

The anticipation threshold is \(d+1\).

The delivery threshold is \(d+8\).

Anticipation at or above the threshold is classified as early reservation.

Delivery slack at or above the threshold is classified as standard delivery.

The minimum delivery slack \(d+7\) is a controlled feasibility choice aligned
with the seven-period maximum Family-1 departure headway plus corridor travel.

### Fare

For corridor distance \(d\):

\[
p_d=100d.
\]

The published reference rates remain:

\[
r_{early}=1,\qquad
r_{standard}=1.
\]

The controlled premium rates are:

\[
r_{late}=1.25,\qquad
r_{express}=1.25.
\]

### Pilot request window

Demand opportunities are generated for periods 0 through 13 inclusive:

\[
14\times10=140
\]

opportunities per demand set.

The network/delivery horizon extends to period 32 solely so that every
configured timing-pool outcome fits without truncation.

### Random streams

Structural generation uses the registered demand-set seed.

Economic realisation uses:

\[
seed_{economic}=seed+1,000,000.
\]

This separates volume draws from structural OD/timing/category random draws.

### Scientific boundary

None of these unresolved numerical values is claimed to be the value used by
Cui et al.

They are not calibrated against Table 4.

If original supplementary inputs become available, those inputs replace A032
for strict numerical reproduction. A032 remains a controlled sensitivity
baseline.

**Code impact:** `experiments/phase11_baseline.py`.

---

## A033 — Ex-ante non-oracle Table 4 forecast catalogue

**Status:** Controlled substitute input

**Paper-supported structure:**
DCA-RM and DCA-RRM consider potential future demands using probability
distributions.

DCA and DCA-Reroute do not use future-demand revenue management.

The exact construction of the experimental future-demand set and forecast
information is not sufficiently disclosed for exact numerical reproduction.

**Problem with the Phase 8/9 diagnostic provider:**
The earlier diagnostic provider deliberately reused unrevealed realised
future-request attributes while replacing only realised volume by a probability
distribution.

That provider remains valid for Phase 8/9 mechanism diagnostics but is not used
as the Phase 11 publication-facing baseline.

**Controlled Phase 11 forecast process:**
Before any optimisation decision, an independent forecast catalogue is
generated from the same controlled structural and economic distributions used
by A032.

For registered demand-set seed \(s\):

\[
s_{forecast}=s+2,000,000.
\]

The catalogue contains ten independent potential forecast opportunities for
each configured half-day request period.

Forecast structural attributes are therefore statistically generated rather
than copied from the realised future demand set.

Each forecast retains the complete A032 volume distribution:

\[
P(X=0)=0.40,\qquad
P(X=1)=0.40,\qquad
P(X=2)=0.20.
\]

**Information rule at decision time \(t\):**
Only forecast entries whose forecast reservation period is strictly later than
\(t\) are provided.

Potential forecasts from the same half-day as the current realised request are
excluded because the publication does not uniquely specify within-period
request ordering and information revelation.

**Future-set rule:**
The supplied forecasts are subsequently filtered by the existing A004
shared-transport-arc interpretation of direct possible interaction.

The baseline uses:

- `FutureDemandSelectionMode.A004_SHARED_ARC`;
- no additional numerical look-ahead truncation for the one-week pilot;
- the printed future-value expression.

The capped future-value interpretation remains sensitivity analysis.

**Common-random-number requirement:**
DCA-RM and DCA-RRM must receive the identical catalogue fingerprint within a
paired experiment.

The catalogue must also be identical across capacities and service families
for the same registered demand-set seed; network interaction is determined
afterward by the selected network.

**Non-oracle guarantee:**
Forecast construction must not inspect:

- realised future volume;
- realised future OD;
- realised future availability;
- realised future deadline;
- realised future category;
- realised future fare.

**Scientific boundary:**
A033 reproduces the disclosed stochastic-forecast concept but not an
undisclosed original forecasting algorithm.

No Phase 11 result may describe A033 as the authors' exact forecast data.

**Code impact:**
`experiments/phase11_forecasts.py`, Table 4 DCA-RM/DCA-RRM execution and
forecast traceability.

---

## A034 — Stable Table 4 pilot reporting boundary

**Status:** Controlled reporting interpretation

The first Phase 11 Table 4 pilot uses the frozen A028--A033 input stack and
runs:

- DCA;
- DCA-RM;
- DCA-Reroute / Full-Reroute;
- DCA-RRM.

The cell is fixed as Service Family 1, nominal capacity 10 TEU and
`demand_set_01`.

Truck recourse is disabled and water factor is 1.

### Volume reporting

The existing stable-capacity models create full barge commitments for accepted
positive-volume demand.

For this pilot:

\[
transportedVolume = acceptedVolume.
\]

This is the controlled mapping used for the Table 4 volume IR pipeline.

It must be revisited if later source evidence distinguishes accepted volume
from the paper's transported-volume denominator.

### Timing reporting

`solve_time_seconds` in the pilot raw record is external wall-clock time for
the complete sequential policy run.

It is not presented as the paper's CPLEX `ST` metric.

### Solver diagnostics

The existing high-level sequential run APIs do not currently propagate
aggregate:

- MIP gap;
- variable count;
- constraint count;
- branch-and-bound node count.

These fields remain null during the first pipeline-validation pilot.

They must be instrumented before solver-complexity comparisons are promoted to
full Phase 11 scientific results.

### Completion gate

DCA-relative Table 4 IR is produced only if all four policy runs complete.

If any mechanism terminates on an infeasible or unsolved booking event, raw
results are retained but paper-facing IR aggregation is blocked.

### Determinism

The four-policy pilot is executed twice.

Scientific fields must match between runs. Wall-clock time is excluded from
the determinism comparison.

**Code impact:** `experiments/phase11_pilot.py`.

---

## A035 — HiGHS solver substitution for unrestricted MILP execution

**Status:** Controlled computational substitution

The publication reports IBM CPLEX as its optimisation solver. The local
reproduction environment provides CPLEX Community Edition, whose model-size
limit prevents execution of some Phase 11 revenue-management models.

The mathematical formulations remain constructed with DOcplex and are not
rewritten for HiGHS.

For HiGHS execution, the already-constructed DOcplex model is exported in
CPLEX LP format, read by HiGHS, solved, and the resulting primal values are
mapped back to the existing solution structures by preserved variable names.

The substitution has been regression-validated on:

- a DCA-RM model, where CPLEX and HiGHS produced the same objective,
  acceptance decision and tested protection decision, and the HiGHS-derived
  solution passed the existing independent DCA-RM validator;
- a genuine DCA-RRM model containing unfinished past demand, current demand
  and future demand protection, where both solvers produced the same
  objective and complete primal assignment within tolerance, and the
  HiGHS-derived solution passed every existing independent DCA-RRM validation
  check.

HiGHS version 1.15.1 is the validated implementation version.

This is a solver substitution, not a change to the published mathematical
method or to the controlled Phase 11 input data.

Solver backend and solver version must be reported with experimental results.
No silent automatic fallback between CPLEX and HiGHS is permitted.

Solver runtime obtained with HiGHS must not be presented as a reproduction of
the publication's CPLEX runtime. Numerical objective, allocation and flow
results remain subject to the existing independent validators and numerical
tolerances.

Alternative optimal primal assignments may differ between solvers even when
the objective is identical. Such cases must be assessed through feasibility,
objective equivalence and downstream state validity rather than requiring
bit-for-bit route equality.

---

## A036 — Infeasible incoming Regular demand during controlled experiments

**Status:** Controlled experimental interpretation

**Paper evidence:**

The paper defines Regular customers as customers for whom the carrier
undertakes to transport all demands. The mathematical acceptance domain
therefore fixes the current Regular request to full acceptance.

The paper also states that the acceptance/rejection decision for each
incoming request depends on demand feasibility, where feasibility means
that sufficient residual capacity exists on the time-space network to
satisfy the current request.

**Missing information:**

The publication does not explicitly specify the simulation transition when
these two statements conflict: a current Regular request arrives but cannot
be accommodated by the available network capacity.

**Controlled Phase 11 interpretation:**

If and only if the optimisation solver explicitly certifies the current
Regular booking problem as infeasible after all policy-specific flexibility
has been considered, the request is recorded as a feasibility rejection
outside the category-dependent optimisation acceptance variable.

No commitment is created for that request.

Existing accepted commitments remain unchanged.

The rolling booking state advances to the next incoming request.

**Non-applicability:**

This rule MUST NOT convert any of the following into a booking rejection:

- time-limit termination;
- numerical failure;
- unknown solver status;
- unbounded status;
- ambiguous infeasible-or-unbounded status;
- independent-validation failure;
- infeasibility of a P or F request, because those categories already
  possess an explicit zero-acceptance decision.

Such cases remain computational or modelling failures and terminate the
controlled experiment.

**Scope:**

A036 is an experiment-layer interpretation used for Phase 11 controlled
reproduction. It does not modify the mathematical acceptance domain of
Regular demand and does not retroactively change the validated Phase 6–10
core-policy semantics.

**Reporting requirement:**

Every Phase 11 raw policy result must report the number and identifiers of
A036 feasibility-rejected requests.

This interpretation must not be represented as uniquely established by the
published paper.

**Author clarification required:**

Ask how the original simulator handled an incoming Regular request when no
feasible time-space itinerary remained under the selected booking policy.

---

## A037 — Deterministic CPLEX Community Edition-aware solver selection

**Status:** Controlled computational-environment rule

The publication reports CPLEX as its optimisation solver. The local
reproduction environment contains CPLEX Community Edition, which imposes
a 1000-variable and 1000-constraint model-size limit.

Phase 11 therefore retains CPLEX whenever the already-constructed
optimisation model lies within both local Community Edition limits.

If either:

- number of variables > 1000; or
- number of constraints > 1000,

the same already-constructed linear/mixed-integer model is solved with
HiGHS through the validated solver bridge.

The backend is selected before optimisation using model dimensions only.

No solver is selected on the basis of:

- objective value;
- acceptance decision;
- feasibility outcome;
- solution quality;
- runtime observed after the solve starts; or
- agreement with an expected experimental result.

This rule supersedes any Phase 11 use of HiGHS as the unconditional
backend for DCA-RM or DCA-RRM.

The mathematical model, decision variables, constraints, objective,
demand inputs, forecasts, and rolling-horizon state are unchanged by
backend selection.

**Observed motivation:**

For the frozen Table 4 pilot, event K0050 produced a DCA-RM model with
194 variables and 159 constraints. The model was solved by local CPLEX
to integer optimality in approximately 0.006 seconds and independently
validated, while unconditional HiGHS execution exhibited pathological
runtime on the same event.

Conversely, models exceeding the Community Edition size ceiling have
already been cross-validated through the HiGHS bridge.

**Reporting requirement:**

Phase 11 must identify the solver-selection rule as
`cplex_ce_aware`. Timings obtained under mixed CPLEX/HiGHS execution
must not be represented as reproductions of the publication's CPLEX
runtime results.
