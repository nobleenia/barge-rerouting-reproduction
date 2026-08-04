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
