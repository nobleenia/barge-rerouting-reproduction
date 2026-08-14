# Phase 11B — Table 5 Reproduction Validation

## 1. Status

Phase 11B reproduces the computational structure of Table 5 from:

Cui, Y., Bilegan, I. C., Duchenne, E., and Duvivier, D. (2024),
"Demand rerouting mechanisms with revenue management for intermodal
barge transportation networks."

The completed controlled experiment contains:

- 2 service families;
- 4 nominal capacities: 10, 20, 30, and 40 TEU;
- 3 policies: DCA, Partial-Reroute (PR), and Full-Reroute (FR);
- one frozen 800-request demand realisation;
- 1076 TEU total requested volume;
- 8 structural service/capacity cells;
- 24 policy runs.

All 24 policy runs completed successfully.

No solver failure occurred.

The experiment is classified as:

`controlled_substitute_input`

It is not claimed to be an exact numerical reconstruction of the authors'
unpublished Table-5 simulation instance.

---

## 2. Reproduction level

The project reproduction protocol distinguishes:

1. conceptual reproduction;
2. mathematical reproduction;
3. computational reproduction;
4. numerical reproduction.

For Table 5:

- conceptual reproduction: achieved;
- mathematical reproduction: achieved subject to documented assumptions;
- computational reproduction: achieved;
- numerical reproduction: not achieved.

The following publication mechanisms are represented:

- sequential DCA booking;
- Partial-Reroute at forecast-update epochs;
- Full-Reroute at every incoming booking;
- standard-water service capacities;
- rerouting of unfinished accepted demand;
- truck recourse;
- rolling operational state;
- AFR/NFR reporting candidates;
- VTR, VFB, VOB, and VOA reporting candidates;
- revenue and solving-time evidence.

Exact numerical replication is not claimed because several source-level
experimental details remain unpublished or incompletely specified.

---

## 3. Frozen experiment identity

All 24 policy/scenario combinations use the same realised demand instance.

Demand fingerprint:

`9987096abb4c217cd2dca3c307599e4d231c47a2e02c416a6b0ee28128626944`

The frozen population contains:

\[
N^{req}=800
\]

requests and:

\[
Q^{req}=1076\ {\rm TEU}.
\]

The demand instance, truck-penalty interpretation, trigger conventions,
capacity rules, and indicator definitions were frozen before the final
24-run production campaign.

They were not modified after observing the campaign results.

---

## 4. Campaign integrity

The global campaign audit verifies:

\[
2
\times
4
\times
3
=
24
\]

unique policy runs.

The checkpoint contains:

- 24 unique run keys;
- 8 structural cells;
- no duplicate experiment row;
- no missing experiment row;
- no solver failure.

For every policy record, the audit verifies:

\[
Q^{acc}
=
Q^{final,barge}
+
Q^{truck}
\]

within numerical tolerance.

It also verifies:

\[
TR^{gross}
-
C^{truck}
=
TR^{net}.
\]

Allocation-level evidence and aggregate-ledger evidence reconcile
independently.

No final service arc exceeds actual capacity.

---

## 5. Prevalidation and raw-evidence durability

The final campaign contains 22 prevalidation artifacts.

The two runs without prevalidation artifacts are:

- `service_family_1__capacity_10__dca`;
- `service_family_1__capacity_10__pr`.

These two runs were completed before the prevalidation durability mechanism
was introduced.

They are retained as historical production records and are not rerun merely
to make the artifact structure cosmetically uniform.

The remaining 22 runs contain persisted prevalidation evidence.

The completed campaign checkpoint and prevalidation artifacts are bound by a
SHA-256 evidence manifest.

The completed campaign checkpoint SHA-256 is:

`a646c5e4e58e153f190e7737fc033f9b32d593c59335ad5e118c8f1711883f61`

---

## 6. Standard-water invariant

Table 5 is a standard-water experiment.

Therefore:

\[
C_a^{actual}
=
C_a^{nominal}.
\]

All three retained fill-rate candidate pairs satisfy:

\[
AFR=NFR
\]

within numerical tolerance for every completed policy run.

This invariant passes globally.

---

## 7. Controlled Table-5 indicator interpretation

The publication does not fully disclose all performance-indicator equations.

The production campaign therefore uses the definitions frozen in:

`docs/phase11_table5_indicator_contract.md`

before campaign execution.

The primary controlled fill-rate comparison is mean transport-leg
utilisation.

For volume indicators:

\[
VTR_c
=
100
\frac{Q^{truck}}{Q^{req}},
\]

\[
VFB_c
=
100
\frac{Q^{final,barge}}{Q^{req}},
\]

and:

\[
VOB_c
=
100
\frac{Q^{acc}}{Q^{req}}.
\]

Therefore:

\[
VOB_c
=
VFB_c
+
VTR_c.
\]

The primary controlled VOA comparison candidate is:

\[
VOA_{count,c}
=
100
\frac{N^{acc}}{N^{req}}.
\]

Alternative indicator candidates remain persisted and are not discarded.

No denominator or aggregation rule was selected after observing which one
best matched the publication.

A012 therefore remains unresolved at source level.

---

## 8. DCA-relative revenue behaviour

Absolute controlled revenue is not directly comparable with the published
TR scale because the exact original fare generation, accounting convention,
truck-cost treatment, and simulation instance are unavailable.

A more informative comparison is therefore the within-cell percentage change
relative to DCA.

The controlled experiment preserves both gross and net realised revenue.

| Service | Capacity | Paper PR TR vs DCA (%) | Controlled PR Net vs DCA (%) | Paper FR TR vs DCA (%) | Controlled FR Gross vs DCA (%) | Controlled FR Net vs DCA (%) |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 10 | +4.190 | +0.200 | +142.318 | +100.496 | +14.197 |
| 1 | 20 | +6.227 | -1.617 | +68.544 | +24.392 | +6.672 |
| 1 | 30 | +2.493 | -1.560 | +45.406 | +4.139 | +2.127 |
| 1 | 40 | +4.457 | -1.792 | +30.962 | 0.000 | 0.000 |
| 2 | 10 | +25.219 | -1.174 | +105.015 | +23.489 | +6.446 |
| 2 | 20 | +9.098 | -0.049 | +53.278 | 0.000 | 0.000 |
| 2 | 30 | +4.515 | 0.000 | +24.355 | 0.000 | 0.000 |
| 2 | 40 | +0.764 | 0.000 | +8.857 | 0.000 | 0.000 |

The publication reports positive improvements for PR and FR throughout the
Table-5 experiment.

The controlled experiment does not reproduce that universal dominance.

---

## 9. Full-Reroute reproduces the scarcity mechanism qualitatively

Full-Reroute has its largest controlled benefit when barge capacity is
scarce.

For Service Family 1 at 10 TEU:

- DCA accepts 447 TEU;
- FR accepts approximately 818.980 TEU;
- FR finally carries approximately 379.023 TEU on barge;
- approximately 439.958 TEU is transferred to truck.

At 20 TEU:

- FR accepts 989 TEU;
- truck recourse falls to 212 TEU.

At 30 TEU:

- FR accepts 1073 TEU;
- truck recourse falls to 34 TEU.

At 40 TEU:

- DCA and FR both accept the complete 1076 TEU;
- FR uses no truck.

The controlled result therefore supports the qualitative mechanism that
rerouting flexibility has greater value under capacity scarcity.

Its numerical magnitude does not reproduce the publication.

---

## 10. Service Family 2 saturates substantially earlier

The strongest controlled-versus-published discrepancy occurs in Service
Family 2.

At 10 TEU:

- DCA accepts 798 TEU;
- PR accepts 794 TEU;
- FR accepts approximately 1006.031 TEU.

At 20 TEU:

- DCA accepts all 1076 TEU;
- PR accepts 1075 TEU;
- FR accepts all 1076 TEU.

At 30 and 40 TEU:

- all three policies accept all 1076 TEU.

Thus the controlled Service-Family-2 network becomes effectively
demand-saturated from approximately the 20-TEU setting.

The published experiment continues to show material advantages for advanced
policies at higher capacities.

This indicates that the controlled service-demand interaction does not
reconstruct the same scarcity regime as the authors' original simulation
instance.

It does not, by itself, establish an implementation error.

---

## 11. Partial-Reroute does not dominate DCA

PR does not consistently outperform DCA in the controlled experiment.

Examples include:

### Service Family 1 / 20 TEU

\[
803\ {\rm TEU}_{DCA}
>
793\ {\rm TEU}_{PR}.
\]

### Service Family 1 / 30 TEU

\[
1031\ {\rm TEU}_{DCA}
>
1018\ {\rm TEU}_{PR}.
\]

### Service Family 1 / 40 TEU

\[
1076\ {\rm TEU}_{DCA}
>
1061\ {\rm TEU}_{PR}.
\]

### Service Family 2 / 10 TEU

\[
798\ {\rm TEU}_{DCA}
>
794\ {\rm TEU}_{PR}.
\]

The publication reports positive PR improvements relative to DCA.

This discrepancy is retained.

The controlled result demonstrates that forecast-based capacity protection
need not improve the realised outcome for every demand sequence when the
protected future-demand opportunity differs from the realised demand.

No parameters are changed to remove this behaviour.

---

## 12. PR truck-recourse discrepancy

The publication reports non-zero PR VTR values throughout Table 5.

Published PR VTR values are:

### Service Family 1

- 10 TEU: 2%;
- 20 TEU: 3%;
- 30 TEU: 1%;
- 40 TEU: 1%.

### Service Family 2

- 10 TEU: 9%;
- 20 TEU: 6%;
- 30 TEU: 2%;
- 40 TEU: 1%.

In the controlled production campaign:

\[
VTR_{PR}=0
\]

for all eight PR cells.

This is a systematic numerical/behavioural discrepancy.

Possible contributing factors include differences in the unpublished service
schedule, demand realisation, recovery state, forecast construction, and
truck-cost interpretation.

The result is preserved rather than altered by calibration.

---

## 13. FR truck-recourse discrepancy

The publication reports FR VTR values:

### Service Family 1

- 10 TEU: 37%;
- 20 TEU: 35%;
- 30 TEU: 25%;
- 40 TEU: 13%.

The controlled values are approximately:

- 40.888%;
- 19.703%;
- 3.160%;
- 0.000%.

### Service Family 2

The publication reports:

- 46%;
- 29%;
- 17%;
- 6%.

The controlled values are approximately:

- 19.241%;
- 0.000%;
- 0.000%;
- 0.000%.

Thus truck dependence in the controlled experiment declines substantially
faster as nominal barge capacity increases.

This is consistent with the earlier saturation of the controlled network.

---

## 14. AFR discrepancy and source anomaly

The primary controlled AFR candidate is mean transport-leg utilisation.

Its absolute values differ substantially from the published AFR values.

This is not surprising because exact service schedules, sailing
construction, and the publication's precise AFR aggregation formula remain
unavailable.

The publication also contains an apparent anomalous Table-5 value:

- Service Family 1;
- capacity 40 TEU;
- PR;
- AFR printed as `855`.

The literal value is retained in:

`table5_published_comparison.csv`

and is not silently corrected.

A mechanical subtraction from the DCA AFR therefore produces a
772-percentage-point difference.

That arithmetic result must not be interpreted as a meaningful policy
effect.

Separate source evidence records a standard-water value of 85 for the
corresponding PR setting in Table 6, which is consistent with `855` being a
typographical error.

Nevertheless, Table 5 is preserved exactly as printed.

A013 remains active.

---

## 15. A036 feasibility continuation is material

The controlled production campaign records the A036 Regular-demand
feasibility continuation.

Across the eight DCA runs:

\[
316
\]

A036 feasibility-rejection events occur.

Across the eight PR runs:

\[
322
\]

A036 events occur.

Thus DCA and PR together contain:

\[
638
\]

A036 events.

FR contains zero A036 events under the frozen FR continuation contract.

A036 is therefore not a marginal implementation detail.

The publication does not fully disclose the corresponding simulation
transition when mandatory Regular demand is infeasible in the realised
rolling state.

Results depending on A036 cannot be presented as exact claims about the
authors' unpublished implementation.

---

## 16. Runtime and computational burden

Measured production runtime totals are approximately:

- DCA: 0.074 h;
- PR: 12.112 h;
- FR: 34.013 h.

The complete 24-run campaign therefore required approximately:

\[
46.20\ {\rm hours}
\]

of measured policy execution.

Within the controlled reproduction environment:

- DCA is computationally inexpensive;
- PR is much more expensive;
- FR is by far the most expensive policy.

The reproduction uses different hardware and a CE-aware CPLEX/HiGHS backend
strategy.

Consequently, absolute solving times are not claimed to numerically reproduce
the publication's ST values.

The within-environment computational hierarchy is nevertheless clear.

---

## 17. Important reporting distinction

A 100% VOB value does not imply a 100% AFR value.

VOB measures accepted cargo relative to requested cargo:

\[
VOB_c
=
100
\frac{Q^{acc}}{Q^{req}}.
\]

AFR measures utilisation of transport-service capacity.

Therefore a network may accept every requested TEU while operating
substantially below nominal service capacity.

This is visible particularly in Service Family 2 at capacities 20, 30, and
40 TEU.

---

## 18. Why exact Table 5 numerical reproduction is not claimed

Exact numerical reproduction would require the complete original simulation
instance and reporting definitions.

Important unavailable or incompletely specified elements include:

- original generated 800-demand instance;
- demand-generation distributions;
- random seeds;
- exact service schedules;
- complete fare-generation procedure;
- precise forecast construction;
- precise truck-cost calibration;
- exact PR/FR recovery transition details;
- exact AFR/NFR aggregation equations;
- exact VTR/VFB/VOB/VOA denominators;
- exact TR accounting convention;
- original source code and solver configuration.

The controlled experiment does not infer these quantities after observing
the published values.

---

## 19. Reproduction conclusion

Phase 11B establishes a successful methodological, computational, and
behavioural reproduction of the standard-water Table-5 experiment.

The following have been reproduced:

- DCA;
- Partial-Reroute;
- Full-Reroute;
- 800 sequential bookings;
- 20 PR forecast-update epochs;
- FR rerouting at every booking;
- two service families;
- capacities 10, 20, 30, and 40 TEU;
- standard-water capacities;
- truck recourse;
- accepted-volume conservation;
- revenue/truck-penalty accounting;
- service-capacity validation;
- AFR/NFR candidate reconstruction;
- VTR/VFB/VOB/VOA candidate reconstruction;
- checkpointed raw evidence;
- 24 policy/scenario runs.

The controlled experiment reproduces the central qualitative mechanism that
rerouting flexibility is most valuable under capacity scarcity.

However, exact Table-5 numerical replication is not achieved.

Major discrepancies include:

- substantially earlier saturation of the controlled network;
- systematic zero PR truck use;
- weaker or negative realised PR benefit relative to DCA;
- substantially different FR truck-use profiles;
- large absolute AFR differences;
- unresolved publication indicator denominators;
- unresolved TR accounting;
- material dependence on A036;
- non-comparable absolute solving times.

The proper scientific classification is therefore:

**validated computational and behavioural reproduction using controlled
substitute inputs, with unsuccessful exact numerical replication of the
published Table 5 values.**

The discrepancies are preserved as results rather than removed through
post-hoc calibration.

---

## 20. Traceability

Primary compact reproduced outputs:

- `results/phase11/table5/campaign/table5_policy_runs.csv`
- `results/phase11/table5/campaign/table5_published_comparison.csv`
- `results/phase11/table5/campaign/table5_policy_comparisons.csv`
- `results/phase11/table5/campaign/campaign_manifest.json`
- `results/phase11/table5/campaign/run_plan.json`
- `results/phase11/table5/campaign/audit/global_campaign_audit.txt`
- `results/phase11/table5/campaign/audit/evidence_sha256.txt`

Reproducibility scripts:

- `scripts/audit_phase11_table5_campaign.py`
- `scripts/export_phase11_table5_results.py`
- `scripts/analyze_phase11_table5_comparison.py`

Heavy operational evidence retained locally:

- `results/phase11/table5/campaign/campaign_checkpoint.json`
- `results/phase11/table5/campaign/prevalidation/`
- `results/phase11/table5/campaign/logs/`
- `results/phase11/table5/pilot/`

The heavy operational evidence is intentionally excluded from normal Git
history.

Relevant source-level limitations include A012, A013, and assumptions
A039 through A051.
