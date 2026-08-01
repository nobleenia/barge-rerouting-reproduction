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
