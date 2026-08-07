# Paper-to-Code Traceability Matrix

## 1. Purpose

This document maps every major concept in the source paper to:

- its mathematical role;
- its planned software location;
- its configuration inputs;
- its validation tests;
- its expected outputs;
- any related assumption identifiers.

The mapping will evolve as implementation progresses.

---

## 2. Core traceability matrix

| Paper concept | Mathematical or operational role | Planned code location | Configuration or data | Validation | Related assumptions |
|---|---|---|---|---|---|
| Physical terminal network | Defines physical origins, destinations, and service corridor | `src/barge_rerouting/network/physical.py` | `configs/*.yaml` | Node and adjacency tests | A001 |
| Time-space node \(n(i,t)\) | Represents terminal \(i\) at time \(t\) | `src/barge_rerouting/domain/node.py` | Time horizon and discretisation | Node-count and identity tests | A001 |
| Transport arc \(A_L\) | Represents one scheduled service leg | `src/barge_rerouting/domain/arc.py` and `network/time_space.py` | Service schedules and capacities | Arc-existence and travel-time tests | A001 |
| Holding arc \(A_H\) | Allows waiting at a terminal | `network/time_space.py` | Holding cost and capacity settings | Consecutive-time and reachability tests | A007 |
| Demand attributes | Defines volume, OD, times, category, and fare | `src/barge_rerouting/domain/demand.py` | Generated or loaded demand files | Input-validation tests | A010, A011 |
| Regular category \(R\) | Mandatory full acceptance | `models/common.py` | Demand category | Variable-domain test | A011 |
| Partially-spot category \(P\) | Fractional acceptance | `models/common.py` | Demand category | Fractional-acceptance test | A011 |
| Fully-spot category \(F\) | Full acceptance or rejection | `models/common.py` | Demand category | Binary-domain test | A011 |
| Current demand \(\tilde{k}\) | Request currently being decided | `simulation/state.py` | Chronological demand sequence | Decision-epoch tests | — |
| Past demand set \(D(\tilde{k})\) | Accepted but unfinished requests | `simulation/state.py` | Current system state | Commitment-preservation tests | A003 |
| Future set \(K(\tilde{k})\) | Potential future demands competing for capacity | `generation/forecast.py` | Forecast horizon and selection rule | Future-set membership tests | A004 |
| Acceptance variable \(\xi_k\) | Determines accepted proportion | `models/common.py` | Customer category | Domain and objective tests | A011 |
| Demand arc flow \(v(k,a)\) | Routes accepted or protected volume | `models/common.py` | Feasible subgraph | Flow-conservation tests | A002, A006 |
| Shared arc capacity | Couples demand commodities | `models/common.py` | Nominal, actual, and residual capacities | Capacity-residual tests | A009 |
| Source flow conservation | Injects accepted volume at origin | `models/common.py` | Demand source node | Manual equation comparison | A002 |
| Intermediate flow conservation | Prevents flow creation or loss | `models/common.py` | Network incidence | Node-balance tests | — |
| Destination flow conservation | Delivers accepted volume | `models/common.py` | Eligible destination nodes and super-sink | Deadline and delivery tests | A002 |
| Future selector \(y_{kj}\) | Selects one protected future-volume level | `models/dca_rm.py` | Discrete volume probabilities | Selector and exclusivity tests | A005 |
| `maxvol(k)` | Records selected protected level | `models/dca_rm.py` | Future-volume levels | Linking-constraint tests | A005 |
| Printed future value | Expected revenue term as reported | `models/future_value.py` | \(P_k(x)\), fare, volume levels | Hand-calculated value test | A005 |
| Capped future value | Sensitivity alternative \(E[\min(X,j)]\) | `models/future_value.py` | Same probability data | Comparative value test | A005 |
| DCA | Current request only | `models/dca.py` | Current state | Hand-solvable baseline test | — |
| DCA-RM | Current plus future demand | `models/dca_rm.py` | Forecast data | Opportunity-cost decision test | A004, A005 |
| DCA-Reroute | Current plus unfinished past demands | `models/dca_reroute.py` | Demand fragments | Feasible-rerouting test | A003 |
| DCA-RRM | Past, current, and future integration | `models/dca_rrm.py` | Full policy input | Policy-reduction tests | A003–A005 |
| Rolling horizon | Re-solves sequentially as information arrives | `simulation/engine.py` | Demand and event sequence | Determinism and state-transition tests | A003 |
| Executed arcs | Irreversible historical movements | `simulation/state.py` | Recorded execution history | Fixed-history tests | A003 |
| Demand fragment | Remaining cargo at current state | `domain/fragment.py` | Execution state | Volume-accounting tests | A003 |
| Full-Reroute | Reoptimises after every new request | `simulation/policies.py` | Trigger configuration | Trigger-count tests | — |
| Partial-Reroute | Reoptimises at forecast intervals | `simulation/policies.py` | Forecast interval | Trigger-timing tests | — |
| Nominal capacity | Published service capacity | `domain/service.py` | Service configuration | Capacity-loading tests | A009 |
| Actual capacity | Water-adjusted capacity | `simulation/capacity.py` | Water factor | Transformation tests | A009 |
| Residual capacity | Capacity remaining after commitments | `simulation/state.py` | Executed and planned flows | Non-negativity and accounting tests | A003, A009 |
| Truck volume \(q_k^{truck}\) | Recourse for undeliverable barge volume | `models/recourse.py` | Truck penalty and availability | Balance and penalty tests | A008 |
| Truck penalty | Reduces objective for recourse use | `models/recourse.py` | Penalty per TEU | Objective-recalculation test | A008 |
| Demand generator | Produces synthetic experiment requests | `generation/demand.py` | Seeded YAML parameters | Seed reproducibility tests | A010 |
| Service-family generator | Produces the two frequency structures | `generation/services.py` | Exact or assumed schedules | Schedule-validation tests | A001 |
| AFR | Fill rate relative to actual capacity | `reporting/indicators.py` | Solution and capacity data | Independent formula test | A012 |
| NFR | Fill rate relative to nominal capacity | `reporting/indicators.py` | Solution and capacity data | \(NFR\approx\lambda AFR\) test | A009, A012 |
| VTR | Truck-transfer volume rate | `reporting/indicators.py` | Accepted and truck volumes | Numerator-denominator test | A012 |
| VFB | Final barge-volume rate | `reporting/indicators.py` | Final barge allocations | Accounting identity test | A012 |
| VOB | Originally barge-accepted rate | `reporting/indicators.py` | Original allocations | Accounting identity test | A012 |
| VOA | Overall originally accepted rate | `reporting/indicators.py` | Acceptance records | Acceptance-rate test | A012 |
| TR | Total revenue | `reporting/indicators.py` | Fare and penalty records | Independent objective recalculation | A008 |
| ST | Solving time | Solver metadata collector | CPLEX solve details | Nonnegative timing and metadata tests | A015 |
| Static experiments | Compare four mechanisms without external capacity change | `experiments/static.py` | Static configs and seeds | Experiment-count and output tests | A001, A010 |
| Dynamic experiments | Compare DCA, PR, and FR under capacity change | `experiments/dynamic.py` | Water and truck configs | Scenario-matrix tests | A008–A010 |
| Table reproduction | Produces comparable metrics and summaries | `reporting/tables.py` | Raw result files | Traceability and aggregation tests | A012, A013 |
| Figure reproduction | Displays behavioural patterns | `reporting/figures.py` | Processed results | Source-data consistency tests | A013 |

---

## 3. Policy composition

The four policies will share one modelling foundation.

| Component | DCA | DCA-RM | DCA-Reroute | DCA-RRM |
|---|---:|---:|---:|---:|
| Current demand | Yes | Yes | Yes | Yes |
| Unfinished past demands | No | No | Yes | Yes |
| Future probable demands | No | Yes | No | Yes |
| Past itinerary modification | No | No | Yes | Yes |
| Future capacity protection | No | Yes | No | Yes |

This composition will be validated through policy-reduction tests.

### Reduction test 1

If there are no future demands:

\[
K(\tilde{k})=\varnothing,
\]

then:

\[
DCA\text{-}RRM = DCA\text{-}Reroute.
\]

### Reduction test 2

If there are no unfinished past demands, then:

\[
DCA\text{-}RRM = DCA\text{-}RM.
\]

### Reduction test 3

If there are neither unfinished past demands nor future demands, then:

\[
DCA\text{-}RRM = DCA.
\]

---

## 4. Paper-to-result chain

Every final numerical result must follow this chain:

\[
\text{paper concept}
\rightarrow
\text{documented interpretation}
\rightarrow
\text{configuration}
\rightarrow
\text{code}
\rightarrow
\text{test}
\rightarrow
\text{raw result}
\rightarrow
\text{processed indicator}
\rightarrow
\text{table or figure}.
\]

A result that cannot be traced through this chain must not be presented as a
validated reproduction result.

---

## 5. Maintenance rule

Whenever a new module or modelling decision is introduced:

1. update this traceability matrix;
2. link any relevant assumption identifier;
3. add at least one validation mechanism;
4. identify the result or output affected;
5. record whether the component reproduces the paper or extends it.

---

## 6. Phase 7 implemented rerouting mapping

The initial matrix above contains planned package names. The following table is
the authoritative mapping for the implemented Phase 7 baseline.

| Phase 7 concept | Operational role | Implemented code location | Validation and output | Assumptions |
|---|---|---|---|---|
| Accepted-demand execution state | Reconstructs delivered, completed, in-transit, and future planned volume at a decision time | `src/barge_rerouting/rolling_horizon/execution.py` | Execution snapshots, path decomposition, volume-accounting tests | A003 |
| Demand fragment | Represents fixed remaining accepted volume associated with one unfinished path fragment | `src/barge_rerouting/domain/fragment.py` | Fragment identity, volume, and state validation | A003 |
| Rerouting eligibility | Selects accepted, unfinished, temporally feasible prior commitments | `src/barge_rerouting/rerouting/eligibility.py` | Inclusion and exclusion-reason tests | A003 |
| In-transit locking | Keeps a currently travelling service immutable and moves the effective rerouting source to its arrival node | `src/barge_rerouting/rerouting/in_transit.py` | Long-leg representation-gap fixture and lock tests | A003 |
| Released rerouting capacity | Releases only future bookable reservations belonging to eligible fragments | `src/barge_rerouting/rerouting/capacity.py` | Capacity identities and no-double-counting tests | A003, A009 |
| Fragment-specific future network | Builds and prunes a feasible future graph from the effective fragment source to eligible destination-time nodes | `src/barge_rerouting/rerouting/network.py` | Forward/backward reachability, deadline, auxiliary-sink tests | A002, A003 |
| Joint DCA-Reroute optimisation | Jointly routes the current request and fixed-volume unfinished fragments under shared capacity | `src/barge_rerouting/rerouting/optimization.py` | Ordinary-rejection/reroute-acceptance route-switching experiment | A003, A006 |
| Persistent rerouting transition | Preserves historical arcs, replaces future path flows, maps fragment sinks to original demand sinks, and appends the current event once | `src/barge_rerouting/rerouting/transition.py` | Metadata preservation, execution reconstruction, capacity and determinism tests | A003 |
| Single-event Full-Reroute orchestration | Builds execution, ordinary capacity, eligibility, released capacity, fragment networks, joint model, solution, and transition for one booking event | `src/barge_rerouting/rerouting/orchestration.py` | End-to-end controlled event diagnostic and tests | A003 |
| Complete Full-Reroute run | Invokes Full-Reroute at every incoming booking request and carries the revised state forward | `src/barge_rerouting/rerouting/run.py` | Complete-timeline, state-chain, failure-stop, and determinism tests | A003 |
| Canonical DCA comparison | Runs time-aware sequential DCA and Full-Reroute on the same seeded instance and timeline | `src/barge_rerouting/rerouting/evaluation.py` | Event CSV, structured JSON, Markdown report, deterministic rerun test | A003, A010, A013 |
| Canonical evaluation command | Reproduces and exports the Phase 7 canonical comparison | `scripts/evaluate_phase7_canonical.py` | `make evaluate-phase7-canonical` | A003, A010, A013 |
| Canonical raw results | Stores event-level comparison and structured summary data | `results/phase7/canonical_event_comparison.csv`, `results/phase7/canonical_evaluation.json` | Instance fingerprint and deterministic regeneration | A003, A013 |
| Canonical interpretation report | Records aggregate, common-prefix, continuation, and failure-point results | `docs/phase7_canonical_results.md` | Generated directly from evaluation results | A003, A013 |

### 6.1 Operational interpretation boundary

The fragment source is the cargo's execution-aware terminal-time position.

- Completed physical movement remains immutable.
- A currently in-transit service remains immutable.
- Only future bookable reservations may be released.
- Accepted prior volume remains mandatory.
- Prior booking sequence, decision time, acceptance, and demand metadata are
  preserved during commitment reconstruction.

This is the disclosed implementation governed by Assumption A003. It should
not be described as a verbatim transcription of printed Equation (5).

### 6.2 Meaning of a reoptimised prior commitment

Evaluation output lists prior commitments included in the joint model and
rebuilt in persistent state.

That list demonstrates participation in reoptimisation. It does not establish
that every listed commitment changed its physical itinerary. A physical route
change must be established by comparing the commitment's before-and-after
physical arc sequence.

### 6.3 Canonical Phase 7 result interpretation

On the canonical seeded instance:

- both mechanisms produce identical acceptance, accepted volume, and revenue
  over their common solved prefix of eight events;
- ordinary sequential DCA becomes infeasible at
  `booking::0009::K0011`;
- Full-Reroute recovers that event and processes three additional events;
- Full-Reroute becomes infeasible at `booking::0012::K0017`;
- the failure point therefore shifts forward by three booking events;
- the reported `+5.00` TEU and `+155.01` revenue are continuation gains after
  ordinary DCA terminates;
- they are not paired improvements across all twenty booking events.

The canonical Phase 7 results are synthetic implementation-validation results.
They are not claimed to reproduce a numerical table from the paper.

### 6.4 Phase 7 scope boundary

Phase 7 implements:

- operational DCA-Reroute;
- Full-Reroute at every incoming request;
- persistent execution-aware state transitions;
- canonical comparison with time-aware sequential DCA.

Phase 7 does **not** yet implement:

- future-demand capacity protection;
- the printed future expected-revenue term;
- DCA-RM;
- DCA-RRM;
- Partial-Reroute forecast-interval triggering;
- truck recourse and truck penalties;
- the paper's complete static or dynamic experiment matrix.

Those components belong to subsequent phases and must not be implied by the
Phase 7 results.

---

## 7. Phase 8 implemented revenue-management mapping

The initial matrix contains planned package names. The following table is the
authoritative mapping for the implemented Phase 8 architecture.

| Phase 8 concept | Operational role | Implemented code location | Validation and output | Assumptions |
|---|---|---|---|---|
| Future-volume probability distribution | Represents discrete uncertain future volume over \(0,\ldots,VMAX\) | `src/barge_rerouting/domain/forecast.py` | Probability validation, expected-volume and value-table tests | A005, A010 |
| Printed future value | Implements \(f_k\sum_{x=0}^{j}xP_k(x)\) | `src/barge_rerouting/domain/forecast.py` | Hand-calculated value tests and opportunity-cost gate | A005 |
| Capped future-value sensitivity | Implements \(f_kE[\min(X_k,j)]\) | `src/barge_rerouting/domain/forecast.py` | Printed-versus-capped decision test | A005 |
| Future set \(K(\tilde{k})\) | Selects feasible future forecasts explicitly or through shared transport-arc interaction | `src/barge_rerouting/revenue_management/future_set.py` | Explicit and A004 membership diagnostics | A004 |
| Future selector \(y_{kj}\) | Selects at most one positive protected-volume level | `src/barge_rerouting/optimization/dca_rm.py` | Binary-domain and exclusivity tests | A005, A016 |
| `maxvol(k)` | Links the selected level to tentatively routable future volume | `src/barge_rerouting/optimization/dca_rm.py` | Linking-constraint and protected-flow tests | A005, A016 |
| Tentative future flow | Routes selected protected future volume through shared capacity | `src/barge_rerouting/optimization/dca_rm.py` | Flow-conservation and bottleneck-capacity tests | A004, A005 |
| DCA-RM objective | Combines current realised revenue with expected future contribution | `src/barge_rerouting/optimization/dca_rm.py` | Independent objective validation and probability-reversal gate | A005 |
| DCA-RM state transition | Persists only the realised current acceptance and current route | `src/barge_rerouting/revenue_management/transition.py` | No-persistence tests for selectors and tentative future flows | A004, A005 |
| Time-aware sequential DCA-RM | Rebuilds forecasts and protection decisions at every booking event | `src/barge_rerouting/revenue_management/run.py` | Complete two-event opportunity-cost experiment and determinism tests | A004, A005 |
| Canonical synthetic sensitivity evaluation | Compares DCA with printed and capped DCA-RM under low, central, and high occurrence probabilities | `src/barge_rerouting/revenue_management/evaluation.py` | Summary CSV, event CSV, JSON, Markdown and deterministic rerun | A004, A005, A010, A016 |
| Canonical evaluation command | Generates all Phase 8 canonical outputs | `scripts/evaluate_phase8_canonical.py` | `make evaluate-phase8-canonical` | A004, A005, A010, A016 |
| Canonical raw outputs | Stores policy summaries and event-level decisions | `results/phase8/` | Deterministic instance fingerprint and regeneration | A004, A005, A010 |
| Canonical interpretation report | Separates realised revenue from forecast-based objective contributions | `docs/phase8_canonical_results.md` | Generated directly from evaluation data | A004, A005, A010, A016 |

### 7.1 Phase 8 evaluation boundary

The canonical Phase 8 forecast regime is attribute-conditioned:

- future origin;
- future destination;
- future availability time;
- future deadline;
- future customer category;
- future fare;

are used as diagnostic forecast attributes.

The realised future request volume is not used. It is replaced by a configured
zero-inflated discrete probability distribution over
\(0,\ldots,VMAX\).

Because the paper does not report its complete forecast distributions,
generation parameters, random seeds, or exact operational construction of
\(K(\tilde{k})\), Phase 8 results are synthetic mechanism and sensitivity
results. They are not claimed to reproduce a numerical table from the paper.

### 7.2 Revenue-accounting boundary

For each DCA-RM event:

\[
\text{optimisation objective}
=
\text{current realised revenue}
+
\text{expected future contribution}.
\]

Only current realised revenue is accumulated as earned revenue.

Expected future contribution may overlap with revenue earned when later demand
actually arrives and therefore must not be added to realised revenue.

### 7.3 Persistent-state boundary

After every decision, the implementation persists:

- the current acceptance or rejection;
- the accepted current volume;
- the realised current route.

It discards:

- \(y_{kj}\);
- `maxvol(k)`;
- tentative future flows.

Future protection is reconstructed at the next event from the new state and
the current forecast information.

### 7.4 Phase 8 scope boundary

Phase 8 implements DCA-RM without rerouting accepted unfinished demand.

It does not yet implement the combined DCA-RRM model. Integration of:

- accepted unfinished fragments;
- rerouting;
- future selectors;
- tentative future flows;
- shared released capacity;

belongs to Phase 9.

---

## 8. Phase 9 implemented combined DCA-RRM mapping

The following table is the authoritative mapping for the implemented
combined rerouting and revenue-management mechanism.

| Phase 9 concept | Operational role | Implemented code location | Validation and output | Assumptions |
|---|---|---|---|---|
| Combined DCA-RRM model | Jointly models accepted unfinished fragments, the current request, and tentative future demand | `src/barge_rerouting/optimization/dca_rrm.py` | Variable-index, objective, flow, sink, selector, and combined-capacity tests | A003, A004, A005, A016, A020 |
| Independent DCA-RRM validator | Recalculates domains, selector linking, balances, sinks, combined capacity, and objective independently of model construction | `src/barge_rerouting/optimization/dca_rrm.py` | Valid-solution and deliberate-tampering tests | A003, A004, A005, A016 |
| Persistent DCA-RRM transition | Reconstructs prior accepted commitments, persists the current decision, and discards all tentative future decisions | `src/barge_rerouting/revenue_management/rrm_transition.py` | Persistence, invalid-solution rejection, and empty-future reduction tests | A003, A004, A020 |
| Single-event DCA-RRM orchestration | Builds execution state, eligible fragments, released capacity, future set, combined model, validation, and transition | `src/barge_rerouting/revenue_management/rrm_orchestration.py` | Controlled three-commodity event tests and capacity-transition diagnostics | A003, A004, A020, A021 |
| Rerouting-aware capacity transition | Records net capacity reservation or release without weakening the original myopic invariant | `src/barge_rerouting/revenue_management/rrm_orchestration.py` | Explicit net-release test | A021 |
| Time-aware sequential DCA-RRM | Applies the combined mechanism at every incoming booking request and carries reconstructed state forward | `src/barge_rerouting/revenue_management/rrm_run.py` | State-chain, accounting, infeasibility-stop, reduction, and determinism tests | A003, A004, A020 |
| Canonical four-mechanism evaluation | Compares DCA, DCA-R, DCA-RM, and DCA-RRM under identical timelines and matching forecast regimes | `src/barge_rerouting/revenue_management/rrm_evaluation.py` | Headline regression locks, eventwise RM/RRM comparison, exports, and deterministic rerun | A003, A004, A005, A016, A018, A020 |
| Canonical evaluation command | Regenerates Phase 9 policy summaries, event data, structured JSON, and interpretation report | `scripts/evaluate_phase9_canonical.py` | `make evaluate-phase9-canonical` | A003, A004, A020 |
| Sequential diagnostic command | Demonstrates current, past-fragment, and future commodities in a controlled run | `scripts/inspect_sequential_dca_rrm.py` | `make inspect-sequential-dca-rrm` | A003, A004 |
| Canonical raw outputs | Stores complete policy and event-level machine-readable results | `results/phase9/` | Fingerprinted CSV and JSON outputs | A003, A004, A020 |
| Canonical interpretation report | Separates realised revenue from expected-future objective contribution and documents the comparison boundary | `docs/phase9_canonical_results.md` | Generated directly from the deterministic evaluator | A003, A004, A018, A020, A021 |

### 8.1 Combined-model contract

At each current booking request \(\tilde{k}\), DCA-RRM jointly considers:

\[
D(\tilde{k})
\cup
\{\tilde{k}\}
\cup
K(\tilde{k}).
\]

The three commodity classes have different persistence and decision semantics:

- accepted unfinished fragments are mandatory;
- the current request is accepted according to its customer-category domain;
- future forecasts are tentative capacity-protection commodities.

All three share the released transport capacity.

### 8.2 Persistence boundary

After each event, the implementation persists:

- fixed historical execution;
- reconstructed future paths for accepted unfinished fragments;
- the current acceptance decision;
- the current realised route.

It discards:

- future selectors;
- protected-volume variables;
- tentative future flows;
- expected-future objective contribution.

The next decision rebuilds future protection from the new state.

### 8.3 Reduction validation

The Phase 9 implementation verifies:

- empty future set: DCA-RRM reduces to DCA-R;
- empty unfinished-fragment set: DCA-RRM reduces to DCA-RM;
- both sets empty: DCA-RRM reduces to DCA.

These are structural implementation checks, not merely expected qualitative
behaviour.

### 8.4 Canonical Phase 9 findings

The canonical evaluator runs:

- Sequential DCA;
- DCA-R / Full-Reroute;
- six DCA-RM forecast regimes;
- six corresponding DCA-RRM forecast regimes.

The forecast regimes combine:

- occurrence probabilities \(0.20\), \(0.50\), and \(0.80\);
- the printed future-value expression;
- the capped-value sensitivity.

For every regime, DCA-RRM and its corresponding DCA-RM policy have identical:

- processed-event count;
- current acceptance decisions;
- accepted volume;
- realised revenue;
- accepted-demand set;
- failure event.

Their optimisation-objective sums and expected-future contributions differ.

This equality is an observed result on the canonical seeded instance. It must
not be represented as a general equivalence between DCA-RM and DCA-RRM.

### 8.5 Meaning of prior-reoptimising events

The canonical `events_reoptimising_prior_commitments` field counts solved
events where accepted unfinished commitments participate in the combined
model.

It does not count confirmed physical itinerary changes.

A physical itinerary change requires explicit before-and-after comparison of
the commitment's scheduled transport-arc sequence.

### 8.6 Future-set boundary

Phase 9 retains the A004 current-request shared-arc rule used in Phase 8.

Forecasts interacting only with a prior fragment network are not added to the
baseline combined model. Expanding future-set membership to fragment-only
interactions would be a separate sensitivity under Assumption A020.

### 8.7 Phase 9 scope boundary

Phase 9 implements:

- combined DCA-RRM optimisation;
- independent numerical validation;
- execution-aware persistent transitions;
- full sequential DCA-RRM;
- deterministic four-mechanism canonical evaluation;
- machine-readable and human-readable result exports.

Phase 9 does not yet implement:

- Partial-Reroute forecast-interval triggering;
- water-level disruption scenarios;
- truck recourse and truck penalties;
- order-randomisation sensitivity;
- fragment-expanded future-set selection;
- the paper's complete experiment matrix;
- exact numerical reproduction of unreported paper inputs.

Those components belong to later experimental phases.

### 8.8 Stable-capacity and truck-disabled boundary

Phase 9 implements the combined DCA-RRM mechanism with:

- unchanged nominal service capacities;
- no forecast-driven service-status events;
- no truck-flow variable;
- no truck transfer;
- no truck penalty.

This is consistent with the paper's stable-capacity experiment in which
Full-Reroute is applied without shifting demand volume to another transport
mode.

The general printed objective refers to truck penalties, but the publication
does not define the corresponding truck decision variables or flow
constraints. These missing operational details are not guessed inside the
Phase 9 model.

Explicit truck recourse, actual capacity, water-level updates, PR triggers and
disruption-aware FR are assigned to Phase 10 under Assumption A022.

---

## 9. Phase 10 service-disruption and truck-recourse mapping

| Phase 10 concept | Operational role | Implemented code location | Validation | Assumptions |
|---|---|---|---|---|
| Service-status update | Represents publication of new water/service information | `src/barge_rerouting/disruption/status.py` | Status-domain and validity-window tests | A023, A024 |
| Actual capacity profile | Converts nominal service capacity into current water-adjusted capacity | `src/barge_rerouting/disruption/capacity.py` | Nominal, reduced-water, service-specific and historical-leg tests | A023 |
| Disruption assessment | Detects future reservations exceeding actual capacity | `src/barge_rerouting/disruption/assessment.py` | Nominal-feasible and reduced-capacity overload tests | A023 |
| Operational timeline | Merges forecast/status and booking events with deterministic status-first ties | `src/barge_rerouting/disruption/timeline.py` | Ordering, sequence and same-time tests | A024 |
| Recovery fragments | Reconstructs unfinished execution-aware accepted cargo at status or booking recovery triggers | `src/barge_rerouting/disruption/recovery.py` | Status-triggered and booking-triggered fragment tests | A024, A027 |
| Recovery capacity | Releases flexible prior reservations and computes actual capacity available to recovery | `src/barge_rerouting/disruption/recovery_capacity.py` | Release, fixed-reservation and overload tests | A023, A024 |
| Recovery networks | Builds feasible networks from each fragment's effective rerouting source | `src/barge_rerouting/disruption/recovery_network.py` | Fragment-network and available-arc tests | A024 |
| Explicit truck recourse | Minimises truck penalty while maintaining barge-plus-truck delivery balance | `src/barge_rerouting/disruption/truck_recourse.py` | Independent balance, capacity and objective validation | A025 |
| Recovery persistence | Stores new barge plans and terminal truck transfers without rewriting contractual booking history | `src/barge_rerouting/disruption/recovery_transition.py` | Persistence and truck-accounting tests | A025, A027 |
| Operational execution overlay | Reconstructs execution from latest recovery generation plus cumulative truck history | `src/barge_rerouting/disruption/operational_execution.py` | 7+3, repeated-recovery 6+4 and final-delivery tests | A024, A027 |
| Actual booking capacity | Prevents bookings from using nominal residual capacity after a water reduction | `src/barge_rerouting/disruption/booking_capacity.py` and `rolling_horizon/sequential.py` | Nominal-residual versus actual-residual tests | A023 |
| Dynamic Partial-Reroute | Reroutes at status updates; ordinary bookings do not reroute prior cargo | `src/barge_rerouting/disruption/partial_reroute.py` | End-to-end PR tests | A023, A024, A025 |
| Dynamic Full-Reroute model | Jointly optimises current acceptance, unfinished prior fragments and truck recourse | `src/barge_rerouting/disruption/dynamic_full_reroute.py` | Independent objective, flow, delivery and capacity validation | A023, A025, A026 |
| Dynamic Full-Reroute transition | Persists booking-triggered rerouting and only newly created truck transfers | `src/barge_rerouting/disruption/dynamic_full_reroute_transition.py` | Incremental 3+1=4 truck-history tests | A026, A027 |
| Dynamic Full-Reroute run | Applies recovery at status updates and rerouting at every incoming request | `src/barge_rerouting/disruption/dynamic_full_reroute_run.py` | PR/FR end-to-end policy differentiation | A023–A027 |
| Forced-reduction gate | Demonstrates alternative barge rerouting before residual truck recourse | `tests/unit/test_phase10_forced_reduction_gate.py` | 7 primary + 1 alternate + 2 truck = 10 | A023, A025 |

### 9.1 Policy boundary

The implementation maintains three distinct policy contexts.

**Stable Full-Reroute**

- Phase 7/9;
- booking-triggered rerouting;
- nominal capacity;
- truck disabled.

**Dynamic Partial-Reroute**

- service-status recovery at forecast updates;
- ordinary booking decisions between updates;
- actual capacity;
- truck recourse for unfinished accepted cargo.

**Dynamic Full-Reroute**

- service-status recovery at forecast updates;
- additional rerouting at every incoming booking;
- actual capacity;
- truck recourse for unfinished accepted cargo.

These mechanisms must not be merged in reporting.

### 9.2 Explicit truck interpretation

The publication's printed penalty expression motivates truck recourse but does
not uniquely define the truck submodel.

The implementation therefore records explicit truck quantities and their
constraints under A025 rather than presenting them as a verbatim copy of the
printed formulation.

### 9.3 Remaining numerical-reproduction boundary

Exact numerical reproduction of the publication's dynamic tables remains
blocked by unresolved inputs including:

- truck penalty values;
- complete service schedules;
- exact demand generation and seeds;
- exact realised water sequence;
- capacity rounding;
- some indicator definitions and denominators.

Phase 10 validates mechanisms despite these missing numerical inputs.
