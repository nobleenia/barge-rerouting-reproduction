# Reproduction Protocol

## 1. Project

This project studies and computationally reproduces:

> Cui, Y., Bilegan, I. C., Duchenne, E., and Duvivier, D.  
> "Demand rerouting mechanisms with revenue management for intermodal
> barge transportation networks."

## 2. Purpose

The purpose is to reconstruct, implement, validate, and explain the paper's
rolling-horizon optimisation framework for sequential demand acceptance,
revenue management, demand rerouting, and service-capacity disruption in an
intermodal barge transportation network.

The implementation must be sufficiently transparent that every important:

- set;
- parameter;
- decision variable;
- objective term;
- constraint;
- simulation-state transition;
- experimental indicator;

can be traced either to the paper or to a documented reproduction assumption.

## 3. Reproduction levels

The project distinguishes four reproduction levels.

### Level 1 — Conceptual reproduction

Reconstruct the research problem, demand categories, policy hierarchy,
time-space-network representation, rolling-horizon logic, and disruption
mechanism.

### Level 2 — Mathematical reproduction

Implement the reported decision variables, objective components, capacity
constraints, flow-conservation constraints, future-demand protection, and
rerouting logic.

### Level 3 — Computational reproduction

Develop tested Python and CPLEX software that generates instances, constructs
the optimisation models, solves sequential booking decisions, records results,
and reproduces the qualitative behaviour reported in the paper.

### Level 4 — Numerical reproduction

Attempt to reproduce the numerical values reported in the paper's tables and
figures.

Exact Level 4 reproduction is conditional on the availability of the original:

- service schedules;
- synthetic-demand distributions;
- parameter values;
- random seeds;
- truck penalties;
- water-level sequences;
- implementation details;
- source code or benchmark instances.

Without those inputs, the project will perform a documented methodological and
behavioural reproduction rather than claim exact numerical replication.

## 4. Primary mechanisms

The implementation will contain the following policies:

1. DCA:
   current-demand allocation without future-demand revenue management and
   without rerouting of previously accepted unfinished demand.

2. DCA-RM:
   current-demand allocation with protection for probable future demand but
   without rerouting of previously accepted unfinished demand.

3. DCA-Reroute:
   current-demand allocation with rerouting of previously accepted unfinished
   demand but without future-demand revenue management.

4. DCA-RRM:
   current-demand allocation combining future-demand revenue management and
   rerouting of previously accepted unfinished demand.

The disruption experiments will additionally distinguish:

- Partial-Reroute;
- Full-Reroute;
- truck recourse following reductions in available barge capacity.

## 5. Core modelling representation

The transportation system will be represented as a directed time-space network:

\[
G = (N^{IT}, A_L \cup A_H)
\]

where:

- \(N^{IT}\) contains terminal-time nodes;
- \(A_L\) contains scheduled transport arcs;
- \(A_H\) contains holding or waiting arcs.

Each demand is treated as a commodity with its own flow variables. Commodities
are coupled through shared transport-arc capacity constraints.

## 6. Rolling-horizon interpretation

Demand requests arrive sequentially.

At each booking decision epoch, the implementation will:

1. advance the simulation clock;
2. identify already executed movements;
3. update cargo locations and remaining demand fragments;
4. update nominal, actual, and residual capacities;
5. identify the current and relevant future demands;
6. construct the selected optimisation policy;
7. solve the model with CPLEX;
8. commit the current acceptance decision;
9. store planned itineraries;
10. proceed to the next event.

Executed movements are irreversible. Only unfinished future movements may be
rerouted.

## 7. Evidence classifications

Every reproduction choice will be assigned one of the following statuses:

| Status | Meaning |
|---|---|
| Explicit | Directly stated in the paper |
| Derived | Logically derived from information stated in the paper |
| Assumed | Required for implementation but not fully specified |
| Sensitivity | Alternative interpretation tested experimentally |
| Unresolved | Requires clarification from the authors |

No undocumented modelling assumption may be embedded silently in the code.

## 8. Validation strategy

The implementation will be validated using:

- hand-solvable examples;
- exported LP formulations;
- unit tests;
- flow-conservation checks;
- capacity-residual checks;
- objective-value recalculation;
- policy-equivalence tests;
- deterministic random seeds;
- regression tests;
- sensitivity analysis;
- comparison with the qualitative patterns reported in the paper.

For selected toy problems, results will be compared using:

1. manual calculation;
2. exhaustive enumeration where practical;
3. CPLEX optimisation.

## 9. Reproducibility requirements

The final project must provide:

- explicit software versions;
- fixed random seeds;
- configuration files for all experiments;
- automated model and data validation;
- traceable raw and processed results;
- automatically generated tables and figures;
- documented assumptions and limitations;
- one-command execution of the main reproduction workflow.

## 10. Scientific reporting rule

The project will distinguish clearly between:

- results reported by the paper;
- results reproduced by this implementation;
- results obtained under additional assumptions;
- proposed extensions beyond the paper.

Apparent inconsistencies will be reported as questions or possible
typographical errors rather than silently corrected.

## 11. Initial success criteria

The reproduction will be considered successful when it demonstrates that:

1. the four policy mechanisms are implemented consistently;
2. each policy behaves correctly on hand-constructed instances;
3. the rolling-horizon simulator preserves feasibility and commitments;
4. revenue management can change acceptance based on future opportunity cost;
5. rerouting can reorganise unfinished accepted demand;
6. reduced water levels modify actual service capacity;
7. truck recourse restores feasibility where required;
8. the broad behavioural patterns can be compared with those reported by the
   paper;
9. all deviations from the paper are documented;
10. the author can explain and defend every major modelling choice.
