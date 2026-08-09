# Phase 11B — Table 5 Experimental Contract

## 1. Purpose

Phase 11B reproduces the computational structure of Table 5 in:

Cui, Y., Bilegan, I. C., Duchenne, E., and Duvivier, D. (2024),
"Demand rerouting mechanisms with revenue management for intermodal
barge transportation networks."

The experiment compares:

- DCA;
- Partial-Reroute (PR);
- Full-Reroute (FR);

under standard water-level conditions.

This phase reuses the disruption, rerouting, recovery, and truck-recourse
mechanisms validated in Phase 10.

---

## 2. Paper-specified experiment dimensions

The publication states that the experiment uses:

- two service families;
- four nominal capacities:
  - 10 TEU;
  - 20 TEU;
  - 30 TEU;
  - 40 TEU;
- a set of 800 demands;
- origin-destination requests distributed over the five-terminal network;
- standard water-level conditions;
- DCA, PR, and FR.

The resulting publication matrix contains:

\[
2 \times 4 \times 3 = 24
\]

policy/scenario rows before replication or sensitivity analysis.

---

## 3. Standard-water condition

For Table 5:

\[
C^{actual}_{a,t}=C^{nominal}_{a}
\]

for every scheduled service arc.

Therefore:

\[
AFR=NFR
\]

up to numerical tolerance.

No reduced-water capacity factor is introduced in Phase 11B.

Reduced water levels belong to Phase 11C / Table 6.

---

## 4. Rerouting triggers

### Partial-Reroute

The paper states that PR is triggered at each forecast update.

The baseline forecast interval is:

\[
2\text{ days}
=
4\text{ half-day periods}.
\]

The paper further states that 40 requests occur during those four periods.

Therefore the implied booking intensity is:

\[
10\text{ requests per half-day period}.
\]

PR recovery/rerouting triggers are therefore separated by four model periods.

### Full-Reroute

FR triggers the rerouting procedure at every incoming booking request.

Thus FR has substantially more rerouting solves than PR.

---

## 5. Demand-count interpretation

The paper specifies:

\[
800\text{ demands}.
\]

It also states:

\[
40\text{ demands per 4 periods}.
\]

Hence the corresponding implied experiment duration is:

\[
800 / 10 = 80\text{ half-day request periods}.
\]

This 80-period horizon is an inferred controlled interpretation, not an
explicitly printed horizon endpoint.

It must be recorded as an assumption before campaign execution.

The original demand-generation distributions and random seeds remain
unavailable.

No demand parameters will be tuned after observing results merely to force
agreement with Table 5.

---

## 6. Truck recourse

Truck transport is available as an alternative mode for rerouting policies.

For recovered accepted cargo:

\[
Q^{remaining}
=
Q^{barge}
+
Q^{truck}.
\]

Truck use incurs a penalty.

The exact truck penalty used by the publication is not fully disclosed.

Phase 11B must therefore use the already documented controlled Phase-10 truck
penalty interpretation unless stronger source evidence becomes available.

DCA does not invoke rerouting truck recourse.

---

## 7. Policies

### DCA

Sequential booking using currently available barge capacity.

No rerouting operation is performed.

### Partial-Reroute

Sequential booking plus rerouting/recovery at forecast-update epochs:

\[
t = 0,4,8,\ldots
\]

subject to the exact trigger convention documented by the implementation.

### Full-Reroute

Sequential booking plus rerouting/recovery at every incoming demand.

---

## 8. Required performance indicators

The publication reports:

1. AFR — Actual Fill Rate;
2. NFR — Nominal Fill Rate;
3. VTR — Volume rate of demand on Truck due to Reroute;
4. VFB — Volume rate of demand Finally allocated on Barge;
5. VOB — Volume rate of demand Originally accepted on Barge;
6. VOA — Volume rate of demand Originally Accepted;
7. TR — Total Revenue;
8. ST — Solving Time.

The paper gives indicator names but does not completely disclose all
numerator/denominator definitions.

Therefore Phase 11B will not silently invent indicator formulas.

For each percentage indicator, the implementation must explicitly record:

- numerator;
- denominator;
- unit;
- physical-time horizon;
- whether the denominator refers to:
  - generated demand volume;
  - accepted demand volume;
  - original barge allocation;
  - nominal vessel capacity;
  - actual vessel capacity.

This is governed by Assumption A012.

---

## 9. Table 5 published values

The published table contains one row for each:

\[
(\text{service family},
\text{capacity},
\text{policy}).
\]

The table reports AFR, VTR, VFB, VOB, VOA, TR, and ST.

At standard water:

\[
AFR=NFR.
\]

The publication contains an apparent value `855` for one PR AFR entry
(Service 1, capacity 40). This value will remain recorded as printed and will
not be silently corrected.

---

## 10. Reproduction classification

Exact numerical reproduction is not currently possible because the
publication does not provide the complete original:

- demand-generation distributions;
- exact generated 800-demand instance;
- random seeds;
- precise service schedules;
- truck penalty calibration;
- all performance-indicator denominators;
- solver configuration.

Phase 11B is therefore initially classified as:

`controlled_substitute_input`

until experimental validation is completed.

---

## 11. Validation gates

Before running the 24-row Table 5 campaign:

1. the 800-demand controlled instance must be deterministic;
2. OD balance must be verified;
3. PR triggers must occur every four model periods;
4. FR must trigger at every incoming request;
5. standard water must satisfy actual capacity = nominal capacity;
6. AFR and NFR must therefore agree within tolerance;
7. every accepted remaining cargo fragment must satisfy:

\[
Q^{remaining}
=
Q^{barge}
+
Q^{truck};
\]

8. truck penalties must reconcile independently;
9. repeated recovery at later physical times must preserve executed history;
10. all indicator denominators must be documented before publication-facing
    numbers are generated;
11. raw results must be checkpointed before aggregation.

---

## 12. Scope boundary

Phase 11B does not vary water level.

Water factors:

\[
1.0,\ 0.9,\ 0.8,\ 0.7
\]

belong to Phase 11C / Table 6.

Full-Reroute under reduced water levels remains a separately labelled
extension unless directly supported by the publication experiment.
