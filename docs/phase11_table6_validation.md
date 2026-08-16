# Phase 11C — Table 6 Reproduction Validation

## 1. Status

Phase 11C reconstructs the publication's Table-6 Partial-Reroute
water-change experiment under controlled substitute inputs.

The complete controlled comparison contains:

- 2 service families;
- nominal capacities 10, 20, 30 and 40 TEU;
- water factors 1.0, 0.9, 0.8 and 0.7;
- Partial-Reroute only;
- 800 requests;
- 1076 TEU requested volume;
- 32 publication-facing rows.

Eight standard-water rows are reused directly from the validated
Phase-11B Table-5 PR campaign.

The remaining 24 reduced-water rows were newly solved in Phase 11C.

All 24 new runs completed.

No solver failure occurred.

The reproduction classification is:

`controlled_substitute_input`

Exact numerical replication of the published Table 6 is not claimed.

---

## 2. Frozen experiment identity

All Table-6 rows use the same frozen realised demand set as Table 5.

Demand fingerprint:

`9987096abb4c217cd2dca3c307599e4d231c47a2e02c416a6b0ee28128626944`

The reduced-water production campaign was generated from source commit:

`01f7b80e4104b5c3fda2b06f7be65fe9033d9cc9`

The experiment contains:

\[
N^{req}=800
\]

requests and:

\[
Q^{req}=1076\ {\rm TEU}.
\]

---

## 3. Table-6 water interpretation

Under frozen assumption A052, one scenario uses one constant water factor:

\[
\lambda\in\{1.0,0.9,0.8,0.7\}.
\]

For reduced-water scenarios, the same factor is issued at the 20 PR
forecast epochs:

\[
0,4,8,\ldots,76.
\]

Forecast validity windows are:

\[
[0,4),[4,8),\ldots,[72,76),[76,99).
\]

The final interval therefore covers the complete controlled horizon.

Updates are global across services.

Actual capacity is:

\[
C_a^{actual}
=
\lambda C_a^{nominal}.
\]

No integer rounding is applied.

---

## 4. Historical actual-capacity reporting

Operational capacity reconstruction intentionally leaves already-departed
movements immutable.

That behaviour is correct for execution but would be inappropriate for
final reduced-water reporting if historical sailings were subsequently
assigned nominal capacity.

Phase 11C therefore reconstructs each transport arc's reporting capacity
at its own departure time.

This ensures that an arc which departed under reduced water retains:

\[
C_a^{actual}
=
\lambda C_a^{nominal}
\]

in the final Table-6 evidence.

This reporting change is opt-in and does not alter the closed Table-5
standard-water reporting path.

---

## 5. Global campaign validation

The completed reduced-water campaign contains:

\[
2\times4\times3=24
\]

new PR runs.

The global audit verifies:

- 24 unique rich records;
- 24 validated prevalidation artifacts;
- complete 2 x 4 x 3 reduced-water coverage;
- one campaign source commit;
- one frozen demand fingerprint;
- 800 processed booking events per run;
- 20 processed status events per run;
- zero solver failures;
- accepted-volume conservation;
- economic conservation;
- historical actual-capacity reconstruction;
- no material actual-capacity violations;
- independent AFR/NFR reconstruction.

For every reduced-water run:

\[
Q^{acc}
=
Q^{final,barge}
+
Q^{truck}.
\]

Economic accounting satisfies:

\[
TR^{gross}
-
C^{truck}
=
TR^{net}.
\]

---

## 6. AFR/NFR invariant

For the controlled uniform-factor experiment:

\[
AFR
=
100\frac{L}{\lambda C^{nominal}}
\]

and:

\[
NFR
=
100\frac{L}{C^{nominal}}.
\]

Therefore:

\[
\boxed{NFR=\lambda AFR}.
\]

The global audit verifies this identity for all 24 reduced-water runs and
for all three retained fill-rate candidates:

- mean transport-arc utilisation;
- capacity-weighted utilisation;
- mean sailing-peak utilisation.

This is independently reconstructed from raw arc evidence rather than
accepted solely from stored indicators.

---

## 7. Volume indicators

The controlled volume indicators remain those frozen before the production
campaign:

\[
VTR
=
100\frac{Q^{truck}}{Q^{req}},
\]

\[
VFB
=
100\frac{Q^{final,barge}}{Q^{req}},
\]

and:

\[
VOB
=
100\frac{Q^{acc}}{Q^{req}}.
\]

Thus:

\[
VOB=VFB+VTR.
\]

The identity passes globally.

The publication prints `VT` in Table 6. The reproduction retains the
publication-facing heading separately while interpreting the truck-volume
indicator internally as VTR.

---

## 8. Controlled response to declining water level

The controlled experiment reproduces an important qualitative mechanism:
lower water capacity can shift accepted cargo from barge to truck while
keeping much of the accepted demand served.

### Service Family 1

At capacity 10 TEU:

- water 1.0: 453 accepted, 0 truck TEU;
- water 0.9: 442 accepted, 46 truck TEU;
- water 0.8: 434 accepted, 91 truck TEU;
- water 0.7: 437 accepted, 138 truck TEU.

At capacity 20 TEU:

- water 1.0: 793 accepted, 0 truck TEU;
- water 0.7: 769 accepted, 193 truck TEU.

At capacity 30 TEU:

- water 1.0: 1018 accepted, 0 truck TEU;
- water 0.7: 986 accepted, 161 truck TEU.

At capacity 40 TEU:

- water 1.0: 1061 accepted, 0 truck TEU;
- water 0.8: 1061 accepted, 7 truck TEU;
- water 0.7: 1057 accepted, 55 truck TEU.

Actual fill rate generally rises as water capacity falls because the
available-capacity denominator decreases.

---

## 9. Service Family 2 retains substantial capacity slack

Service Family 2 is substantially less constrained in the controlled
instance.

At capacity 10 TEU, reduced water produces material truck recourse:

- 0.9: 52 truck TEU;
- 0.8: 111 truck TEU;
- 0.7: 185 truck TEU.

At capacity 20 TEU:

- 0.9: 0 truck TEU;
- 0.8: 15 truck TEU;
- 0.7: 61 truck TEU.

However, at capacities 30 and 40 TEU:

\[
Q^{acc}=1076\ {\rm TEU}
\]

for every tested water factor, including 0.7, and:

\[
Q^{truck}=0.
\]

Thus the controlled Service-Family-2 network retains sufficient barge
capacity to accommodate the entire realised demand set even after a 30%
capacity reduction at those nominal capacities.

This differs materially from the published Table-6 behaviour and is
retained rather than calibrated away.

---

## 10. Non-monotonic realised effects

Not every realised PR result changes monotonically with the nominal water
factor.

For example, Service Family 1 at capacity 40 accepts:

- 1061 TEU at water 1.0;
- 1064 TEU at water 0.9;
- 1061 TEU at water 0.8;
- 1057 TEU at water 0.7.

The small increase at 0.9 is retained as a realised rolling-horizon outcome.

PR decisions depend on sequential booking, capacity protection and the
state exposed at each forecast epoch. A modest capacity reduction therefore
does not mathematically require the realised accepted-volume path to be
strictly monotonic.

No parameter is adjusted to remove this outcome.

---

## 11. Comparison with the publication

Exact numerical Table-6 values are not reproduced.

The main controlled differences include:

- substantially lower absolute AFR/NFR values in many cells;
- substantially higher VFB/VOB values at medium and high capacities;
- substantially less truck recourse in high-capacity Service Family 2;
- much earlier saturation of the controlled network.

Excluding the publication's anomalous Service-1 / capacity-40 / water-0.9
NFR entry, approximate mean absolute controlled-versus-published
differences across the comparison matrix are:

- AFR: 26.6 percentage points;
- NFR: 22.8 percentage points;
- truck-volume indicator: 6.8 percentage points;
- VFB: 19.9 percentage points;
- VOB: 12.9 percentage points.

These discrepancies are too large and too systematic to support a claim of
exact numerical replication.

They are consistent with the already documented differences in controlled
network scarcity, service construction, realised demand and unresolved
publication indicator definitions.

---

## 12. Publication anomaly

The publication prints the following Table-6 value:

- Service Family 1;
- capacity 40 TEU;
- water factor 0.9;
- NFR = `8`.

The value is preserved literally in the publication-comparison dataset.

It is not silently replaced with 80.

The controlled invariant:

\[
NFR=\lambda AFR
\]

and the surrounding published values make the printed value anomalous, but
the reproduction record distinguishes that inference from the literal
published source.

---

## 13. Computational cost

The 24 new reduced-water PR runs required:

\[
130014.910\ {\rm s}
\]

or approximately:

\[
36.115\ {\rm hours}.
\]

Runtime by water factor was remarkably similar:

- 0.9: 12.048 h;
- 0.8: 12.035 h;
- 0.7: 12.033 h.

By service family:

- Service Family 1: 16.017 h;
- Service Family 2: 20.098 h.

Absolute solving times are implementation- and hardware-dependent and are
not treated as numerical reproduction targets.

---

## 14. Evidence persistence

The Table-6 closure evidence contains 49 SHA-256 entries:

\[
24\ {\rm rich\ records}
+
24\ {\rm prevalidations}
+
1\ {\rm reused\ Table5\ source}
=
49.
\]

Heavy operational records and logs remain outside normal Git history.

Compact publication-facing outputs are version controlled.

---

## 15. Reproduction conclusion

Phase 11C successfully reproduces the computational structure and important
qualitative behaviour of the publication's PR water-change experiment.

The reproduction demonstrates:

- proportional reduction of actual service capacity;
- execution-aware status updates;
- Partial-Reroute at forecast epochs;
- explicit truck recourse;
- historical actual-capacity accounting;
- increasing pressure on barge capacity as water falls;
- transfer from barge to truck in constrained cells;
- preservation of accepted-volume and economic accounting;
- independently validated AFR/NFR relationships.

However, exact numerical replication is unsuccessful.

The proper classification is:

**validated computational and behavioural reproduction using controlled
substitute inputs, with unsuccessful exact numerical replication of the
published Table 6 values.**

The discrepancies are treated as scientific results rather than targets for
post-hoc calibration.

---

## 16. Traceability

Compact outputs:

- `results/phase11/table6/campaign/table6_policy_rows.csv`
- `results/phase11/table6/campaign/table6_published_comparison.csv`
- `results/phase11/table6/campaign/table6_water_effects.csv`
- `results/phase11/table6/campaign/campaign_manifest.json`
- `results/phase11/table6/campaign/run_plan.json`
- `results/phase11/table6/campaign/audit/global_campaign_audit.txt`
- `results/phase11/table6/campaign/audit/evidence_sha256.txt`

Post-processing:

- `scripts/audit_export_phase11_table6_results.py`

Heavy operational evidence retained locally:

- `results/phase11/table6/campaign/records/`
- `results/phase11/table6/campaign/prevalidation/`
- `results/phase11/table6/campaign/logs/`

Relevant frozen assumptions include A052 and the previously frozen
Phase-10/Phase-11 reporting contracts.
