# Reproduction Protocol

## Source

Cui, Y., Bilegan, I. C., Duchenne, E., and Duvivier, D., “Demand
rerouting mechanisms with revenue management for intermodal barge
transportation networks.”

## Objective

The project reconstructs the paper's rolling-horizon models for demand
acceptance, revenue management, rerouting, and capacity disruption.

Each modelling choice is linked either to the paper or to a recorded
assumption. The main references are:

- `docs/mathematical_model.md`
- `docs/assumptions_register.md`
- `docs/paper_to_code_mapping.md`

## Reproduction boundary

The work covers four levels:

1. the problem, demand categories, policy hierarchy, and time-space network;
2. the mathematical variables, objective terms, and constraints;
3. a tested Python implementation and controlled experiments;
4. comparison with the numerical results in the paper.

Exact numerical reproduction is limited by missing service schedules, demand
instances, random seeds, fare parameters, truck costs, water-level sequences,
and some indicator definitions. Substitute values are recorded before their
results are evaluated.

## Policies

The implementation includes:

- **DCA:** current-demand allocation;
- **DCA-RM:** DCA with future-demand protection;
- **DCA-R:** DCA with rerouting of unfinished commitments;
- **DCA-RRM:** joint future-demand protection and rerouting;
- **Partial Rerouting:** recovery at status-update events;
- **Full Rerouting:** recovery at status updates and later booking events.

Truck recourse is available in the disruption experiments.

## Network model

The time-space network is

\[
G=(N^{IT},A_L\cup A_H),
\]

where (N^{IT}) is the set of terminal-time nodes, (A_L) contains scheduled
transport arcs, and (A_H) contains holding arcs. Each demand has its own flow
variables. Transport capacity couples the demand flows.

## Rolling-horizon sequence

At each booking time the program:

1. advances physical execution;
2. applies available service-status updates;
3. calculates remaining capacity;
4. constructs the selected optimisation model;
5. solves and validates the model;
6. stores the acceptance and routing decision.

Completed and in-transit movements remain fixed. Only future movements may be
rerouted.

## Source classification

| Status | Meaning |
|---|---|
| Explicit | Stated in the paper |
| Derived | Follows from stated information |
| Assumed | Needed for implementation but not fully specified |
| Sensitivity | Alternative interpretation evaluated separately |
| Unresolved | Requires further source information |

## Validation

Validation uses:

- hand-solvable instances;
- LP exports;
- unit and integration tests;
- flow and capacity residuals;
- independent objective reconstruction;
- policy-reduction tests;
- fixed random seeds;
- repeated-run checks;
- comparison with the paper's qualitative findings.

## Reporting

Published values, reproduced values, controlled assumptions, and extensions are
reported separately. Apparent source-table errors are retained as printed and
noted in the comparison files.
