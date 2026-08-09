# Phase 11A — Table 4 Reproduction Validation

## 1. Status

Phase 11A reproduces the computational structure of Table 4 from:

Cui, Y., Bilegan, I. C., Duchenne, E., and Duvivier, D. (2024),
"Demand rerouting mechanisms with revenue management for intermodal
barge transportation networks."

The completed controlled experiment contains:

- 2 service families;
- 3 nominal capacities: 10, 15, and 20 TEU;
- 5 paired demand sets;
- 4 policies: DCA, DCA-RM, DCA-Reroute, and DCA-RRM;
- 30 paired experimental cells;
- 120 policy runs.

All 120 policy runs completed successfully.

No solver failure occurred.

The experiment is classified as:

`controlled_substitute_input`

It is not claimed to be an exact numerical reconstruction of the
authors' unpublished simulation instances.

---

## 2. Reproduction level

The project reproduction protocol distinguishes:

1. conceptual reproduction;
2. mathematical reproduction;
3. computational reproduction;
4. numerical reproduction.

For Table 4:

- conceptual reproduction: achieved;
- mathematical reproduction: achieved subject to documented assumptions;
- computational reproduction: achieved;
- numerical reproduction: not achieved.

The distinction is important.

The booking-policy hierarchy, rolling-horizon logic, stable service-status
scenario, paired experimental structure, demand rerouting, future-demand
revenue management, and improvement-ratio calculations have been
implemented and executed.

However, the publication does not disclose enough information to uniquely
reconstruct the numerical simulation instances used to produce Table 4.

---

## 3. Paper experiment

The paper defines the Table 4 scenario as a stable service-status experiment.

The four policies are:

- DCA;
- DCA-RM;
- DCA-Reroute;
- DCA-RRM.

The improvement ratio is calculated relative to DCA for both total revenue
and total transported volume.

The paper reports 120 problem instances obtained from:

\[
2\text{ service families}
\times
3\text{ capacities}
\times
5\text{ demand sets}
\times
4\text{ policies}
=
120\text{ runs}.
\]

The reproduced campaign uses the same factorial structure.

---

## 4. Published versus controlled average improvement ratios

The following comparison uses the average improvement ratios reported in
Table 4 of the publication and the average ratios obtained from the frozen
controlled-substitute experiment.

### 4.1 Service Family 1

| Capacity | Policy | Paper Revenue IR (%) | Controlled Revenue IR (%) | Paper Volume IR (%) | Controlled Volume IR (%) |
|---:|---|---:|---:|---:|---:|
| 10 | DCA-RM | 15 | 3.833 | 1 | 4.632 |
| 10 | DCA-Reroute | 23 | 3.026 | 8 | 3.325 |
| 10 | DCA-RRM | 24 | 4.438 | 10 | 4.071 |
| 15 | DCA-RM | 7 | 3.445 | 1 | 2.817 |
| 15 | DCA-Reroute | 8 | 3.184 | 6 | 2.666 |
| 15 | DCA-RRM | 9 | 3.782 | 5 | 3.366 |
| 20 | DCA-RM | 6 | 0.703 | 2 | 0.635 |
| 20 | DCA-Reroute | 10 | 0.703 | 5 | 0.635 |
| 20 | DCA-RRM | 10 | 0.703 | 5 | 0.635 |

### 4.2 Service Family 2

| Capacity | Policy | Paper Revenue IR (%) | Controlled Revenue IR (%) | Paper Volume IR (%) | Controlled Volume IR (%) |
|---:|---|---:|---:|---:|---:|
| 10 | DCA-RM | 8 | 0.000 | 3 | 0.000 |
| 10 | DCA-Reroute | 16 | 0.000 | 9 | 0.000 |
| 10 | DCA-RRM | 18 | 0.000 | 11 | 0.000 |
| 15 | DCA-RM | 9 | 0.000 | 3 | 0.000 |
| 15 | DCA-Reroute | 15 | 0.000 | 10 | 0.000 |
| 15 | DCA-RRM | 15 | 0.000 | 10 | 0.000 |
| 20 | DCA-RM | 11 | 0.000 | 5 | 0.000 |
| 20 | DCA-Reroute | 15 | 0.000 | 10 | 0.000 |
| 20 | DCA-RRM | 15 | 0.000 | 9 | 0.000 |

Values numerically close to zero, such as `-2.95e-15`, are treated as
floating-point zero.

---

## 5. Main controlled-experiment findings

### 5.1 Scarcity creates value for advanced policies

For Service Family 1, advanced booking policies generally improve revenue
and transported volume when nominal capacity is relatively scarce.

At 10 TEU, average revenue improvements are:

- DCA-RM: +3.833%;
- DCA-Reroute: +3.026%;
- DCA-RRM: +4.438%.

At 15 TEU:

- DCA-RM: +3.445%;
- DCA-Reroute: +3.184%;
- DCA-RRM: +3.782%.

At 20 TEU all three mechanisms produce only approximately:

- +0.703% average revenue improvement;
- +0.635% average volume improvement.

The reduction in benefit as nominal capacity increases is consistent with
the mechanism having less scarce capacity to reorganise or protect.

### 5.2 DCA-RRM performs best on average under the two scarcer
Service-Family-1 settings

For Service Family 1:

- at 10 TEU, DCA-RRM has the highest average revenue IR;
- at 15 TEU, DCA-RRM again has the highest average revenue IR;
- at 20 TEU, all three advanced mechanisms are equal on average.

This provides qualitative support for the combined use of future-demand
information and rerouting, although the magnitude is much lower than that
reported in the publication.

### 5.3 Revenue improvement and volume improvement are not identical

DCA-RM produces the largest average volume improvement for Service Family 1
at 10 TEU:

\[
4.632\%.
\]

DCA-RRM produces the largest average revenue improvement:

\[
4.438\%.
\]

The mechanisms can therefore alter the economic composition of accepted
cargo rather than merely maximise total transported TEU.

### 5.4 Rerouting does not dominate DCA in every controlled realisation

For Service Family 1 / 15 TEU, DCA-Reroute has:

\[
\text{minimum revenue IR}=-3.518\%
\]

and:

\[
\text{minimum volume IR}=-4.425\%.
\]

This negative realisation must not be hidden or replaced.

It demonstrates that, under the controlled substitute inputs and implemented
rolling-horizon decisions, rerouting alone does not necessarily dominate DCA
for every demand realisation.

The publication's reported Table 4 minima are non-negative.

This is therefore a substantive numerical discrepancy to retain in the
reproduction record.

---

## 6. Service Family 2 saturation

The most important discrepancy is Service Family 2.

Across all three nominal capacities and all five demand sets, DCA,
DCA-RM, DCA-Reroute, and DCA-RRM produce effectively identical realised
revenue and volume.

Consequently, all advanced-policy improvement ratios are approximately zero.

Moreover, the DCA outcome for each demand set remains unchanged when nominal
capacity increases from 10 to 15 and then to 20 TEU.

This is strong evidence that, under the frozen controlled demand process,
Service Family 2 already provides sufficient effective capacity at the
10-TEU setting.

There is therefore no scarce resource for revenue management or rerouting
to exploit.

This differs strongly from the published experiment, where Service Family 2
still exhibits substantial positive improvement ratios at all capacities.

The result indicates that the controlled service-demand interaction does not
reconstruct the scarcity regime of the authors' original instances.

It does not establish that the implemented mechanisms are incorrect.

---

## 7. A036 feasibility continuation

Across the 120 completed policy trajectories, the campaign recorded:

\[
110
\]

A036 Regular-demand feasibility-rejection events.

This value counts event-level feasibility continuations, not policy runs.

A036 is required because the publication simultaneously describes Regular
demand as mandatory and discusses feasibility-based admission, but does not
explicitly specify the simulation transition when a Regular request becomes
infeasible in the realised rolling state.

The campaign therefore records every such event rather than silently
terminating the trajectory or altering the input data.

The frequency is material and must be reported whenever Phase 11 Table 4
results are presented.

No numerical result relying on A036 may be presented as an exact claim about
the authors' unpublished implementation.

---

## 8. Solver environment

The publication reports Python 3.8 and CPLEX Optimizer 22.1.1.

The reproduction uses the local available environment and retains CPLEX
whenever the constructed model fits within the local Community Edition
limits.

When either:

\[
n_{\mathrm{variables}}>1000
\]

or:

\[
n_{\mathrm{constraints}}>1000,
\]

the already-constructed mathematical programme is solved with HiGHS through
the validated solver bridge.

Backend selection is deterministic and occurs before optimisation from model
dimensions only.

This computational substitution affects runtime comparability.

It does not intentionally modify the optimisation formulation.

Solver equivalence has been tested on controlled models for the RM, RRM, and
joint rerouting formulations.

---

## 9. Why exact Table 4 numerical reproduction is not claimed

Exact numerical reproduction would require the complete original simulation
instance.

Important unavailable or incompletely specified elements include, depending
on the experiment:

- exact original service schedules;
- complete synthetic-demand generation distributions;
- exact random seeds;
- all fare-generation details;
- complete future-demand forecast generation;
- exact implementation decisions around Regular-demand infeasibility;
- source code or benchmark instances used for the published runs.

The frozen Phase 11 inputs were selected before the final campaign and were
not modified after observing discrepancies.

No post-hoc parameter tuning was performed to force the results toward the
published Table 4 values.

---

## 10. Reproduction conclusion

Phase 11A establishes a successful methodological and computational
reproduction of the stable-capacity experiment.

The following have been reproduced:

- the four booking-policy families;
- rolling sequential demand processing;
- revenue-management future-capacity protection;
- rerouting of unfinished accepted demands;
- combined DCA-RRM behaviour;
- stable service capacities;
- five paired demand sets;
- two service families;
- capacities 10, 15, and 20 TEU;
- 30 paired cells;
- 120 policy runs;
- DCA-relative revenue and volume improvement ratios;
- average, minimum, and maximum aggregation.

The controlled experiment also reproduces an important qualitative mechanism:

advanced allocation and rerouting policies have greater value when network
capacity is scarce.

However, exact Table 4 numerical reproduction is not achieved.

The largest discrepancy is Service Family 2, where the controlled network is
already effectively non-binding at 10 TEU and therefore leaves no improvement
opportunity for the advanced policies.

The proper scientific classification is therefore:

**validated computational and behavioural reproduction using controlled
substitute inputs, with unsuccessful exact numerical replication of the
published Table 4 values.**

The discrepancy is preserved as a result rather than removed through
post-hoc calibration.

---

## 11. Traceability

Primary reproduced outputs:

- `results/phase11/table4/campaign/table4_policy_runs.csv`
- `results/phase11/table4/campaign/table4_paired_comparisons.csv`
- `results/phase11/table4/campaign/table4_aggregates.csv`
- `results/phase11/table4/campaign/campaign_manifest.json`
- `results/phase11/table4/campaign/run_plan.json`

Operational checkpoint:

- `results/phase11/table4/campaign/campaign_checkpoint.json`

The operational checkpoint is intentionally not treated as a publication
result.

Relevant assumptions include A032 through A037 and the A036 feasibility
continuation.
