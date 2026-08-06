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
