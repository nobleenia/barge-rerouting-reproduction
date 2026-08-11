# Phase 11 Table 5 Indicator Contract

## 1. Purpose

This document freezes the Phase-11B reporting contract used to reconstruct
Table-5 performance indicators from controlled computational evidence.

The publication reports:

- AFR — Actual Fill Rate;
- NFR — Nominal Fill Rate;
- VTR — Volume rate of demand on Truck due to Reroute;
- VFB — Volume rate of demand Finally allocated on Barge;
- VOB — Volume rate of demand Originally accepted on Barge;
- VOA — Volume rate of demand Originally Accepted;
- TR — Total Revenue;
- ST — Solving Time.

The publication provides abbreviated verbal definitions but does not disclose
complete mathematical numerator, denominator, aggregation, or accounting
definitions for all indicators.

A012 therefore remains unresolved at source level.

Phase 11B does not silently replace that missing information. It stores raw
evidence first and derives explicitly named controlled candidate indicators
from that evidence.

No indicator definition may be changed after observing campaign results merely
to improve agreement with the publication.

---

## 2. Frozen Table-5 population

The controlled Table-5 demand realisation contains:

- 800 requests;
- 1076 TEU requested in total.

Define:

\[
Q^{req}
=
\sum_k q_k^{req}.
\]

For the frozen instance:

\[
Q^{req}=1076\ {\rm TEU}.
\]

All service-family, capacity and policy combinations use the same realised
demand instance.

---

## 3. Authoritative raw demand quantities

For every booking request \(k\), the reporting state preserves:

- requested volume;
- acceptance fraction;
- accepted volume;
- booking decision time and sequence;
- original planned barge allocations.

Define:

\[
q_k^{acc}
=
q_k^{req}e_k
\]

and:

\[
Q^{acc}
=
\sum_k q_k^{acc}.
\]

The raw ledger also preserves:

\[
N^{req}
\]

and:

\[
N^{acc},
\]

where \(N^{acc}\) counts positively accepted requests.

These raw values remain authoritative even when PR or FR subsequently changes
the physical transport plan.

---

## 4. Truck and final-barge accounting

For PR and FR, cumulative truck allocations are reconstructed from the
persisted operational recovery state.

Define:

\[
Q^{truck}
=
\sum_\tau q_\tau^{truck}.
\]

Accepted-volume conservation is enforced independently of reporting labels.

At the final reporting horizon:

\[
Q^{final,barge}
=
Q^{acc}
-
Q^{truck}.
\]

Therefore:

\[
Q^{acc}
=
Q^{final,barge}
+
Q^{truck}.
\]

This is an implementation accounting identity.

It is not presented as an equation explicitly disclosed by the publication.

---

## 5. Original barge allocation

The original booking commitment is preserved separately from later recovery
decisions.

Within the Phase-11B Table-5 execution contract, truck recourse occurs after a
booking has been accepted into the barge transportation plan.

Therefore the controlled original-barge cargo quantity is:

\[
Q^{original,barge}
=
Q^{acc}.
\]

Original physical arc allocations are nevertheless persisted independently in
the allocation snapshot so that this relationship is auditable rather than
inferred from the final recovered state.

Transport-arc flow sums must not be confused with cargo TEU because one cargo
unit may occupy several successive service legs.

---

## 6. Controlled VTR, VFB and VOB candidates

For Phase 11B, the common requested-volume denominator candidate is frozen as:

\[
VTR_c
=
100
\frac{Q^{truck}}
     {Q^{req}},
\]

\[
VFB_c
=
100
\frac{Q^{final,barge}}
     {Q^{req}},
\]

and:

\[
VOB_c
=
100
\frac{Q^{original,barge}}
     {Q^{req}}
=
100
\frac{Q^{acc}}
     {Q^{req}}.
\]

These definitions imply:

\[
VOB_c
=
VFB_c
+
VTR_c
\]

up to floating-point tolerance.

This identity is also strongly consistent with the numerical structure visible
in the publication's Table 5, but it remains a controlled reconstruction
because the publication does not give the underlying equations.

No denominator will be tuned after the campaign.

---

## 7. VOA ambiguity and controlled comparison candidates

The publication distinguishes original barge acceptance from overall
acceptance but does not disclose the exact VOA equation.

Phase 11B therefore preserves two candidates.

### Request-count candidate

\[
VOA_{count,c}
=
100
\frac{N^{acc}}
     {N^{req}}.
\]

### Requested-volume candidate

\[
VOA_{volume,c}
=
100
\frac{Q^{acc}}
     {Q^{req}}.
\]

The request-count candidate is the primary Phase-11B comparison candidate for
"overall acceptance" because it provides a conceptually distinct acceptance
measure from VOB.

However, this choice is a controlled interpretation and is not claimed to be
the publication's undisclosed formula.

The volume-based alternative remains persisted and reportable.

A012 therefore remains unresolved.

---

## 8. Service-capacity evidence

Every completed campaign record preserves transport-arc evidence containing:

- transport arc identifier;
- recurring service identifier;
- terminal pair;
- departure and arrival time;
- nominal capacity;
- actual capacity;
- original load;
- final operational load;
- source status-update identifier where applicable.

For the frozen Table-5 network:

- 112 physical transport arcs are present;
- they reconstruct into 28 physical sailing occurrences;
- every occurrence contains four connected transport legs.

A recurring `service_id` therefore identifies a periodic service pattern and
must not be treated as one unique physical sailing.

---

## 9. AFR and NFR candidates

The publication describes AFR and NFR as average service fill rates but does
not provide the aggregation equation.

Phase 11B therefore preserves three explicit candidate pairs.

### Candidate 1 — mean transport-leg utilisation

\[
AFR_{arc}
=
100
\frac{1}{|A_L|}
\sum_{a\in A_L}
\frac{L_a^{final}}
     {C_a^{actual}},
\]

\[
NFR_{arc}
=
100
\frac{1}{|A_L|}
\sum_{a\in A_L}
\frac{L_a^{final}}
     {C_a^{nominal}}.
\]

This is the primary Phase-11B Table-5 comparison candidate.

Because every reconstructed sailing occurrence contains the same four
transport legs, it is also equivalent to taking the mean leg utilisation
within each sailing and then averaging those sailing means.

### Candidate 2 — capacity-weighted utilisation

\[
AFR_{weighted}
=
100
\frac{\sum_a L_a^{final}}
     {\sum_a C_a^{actual}},
\]

\[
NFR_{weighted}
=
100
\frac{\sum_a L_a^{final}}
     {\sum_a C_a^{nominal}}.
\]

### Candidate 3 — mean sailing peak utilisation

For sailing occurrence \(s\):

\[
u_s^{actual}
=
\max_{a\in s}
\frac{L_a^{final}}
     {C_a^{actual}},
\]

with an analogous nominal-capacity definition.

The candidate indicator is the arithmetic mean of these occurrence-level
peak utilisations.

No candidate is selected because it numerically fits the published table
better.

---

## 10. Standard-water invariant

Table 5 uses standard water conditions.

Therefore:

\[
C_a^{actual}
=
C_a^{nominal}
\]

for every transport arc.

Every retained AFR/NFR candidate must consequently satisfy:

\[
AFR=NFR
\]

within numerical tolerance.

A candidate violating this invariant is invalid for the standard-water
campaign.

---

## 11. Revenue

The reporting ledger preserves separately:

\[
TR^{gross}
=
\sum_k r_k^{booking},
\]

truck penalty:

\[
C^{truck},
\]

and:

\[
TR^{net}
=
TR^{gross}
-
C^{truck}.
\]

The publication reports `TR` but the available source does not unambiguously
establish whether the reported quantity corresponds exactly to the controlled
gross or net accounting quantity.

Phase 11B therefore preserves both.

Neither is silently renamed as the publication's exact TR until the
comparison evidence is evaluated.

---

## 12. Solving time

`ST` is represented in the reproduction by measured wall-clock runtime for the
complete policy execution.

Runtime is:

- finite;
- non-negative;
- persisted with each policy result.

Because the reproduction uses different hardware and a CE-aware
CPLEX/HiGHS backend strategy, its runtime is not claimed to numerically
replicate the publication's solving times.

---

## 13. Indicator snapshot

The reporting layer constructs:

`Table5IndicatorSnapshot`

from:

- `Table5VolumeLedger`;
- `Table5ServiceCapacitySnapshot`;
- policy wall-clock runtime.

The snapshot contains:

- all AFR/NFR candidates;
- all VTR/VFB/VOB/VOA candidates;
- gross revenue;
- truck penalty;
- net realised value;
- solving time;
- standard-water status.

The raw evidence remains authoritative.

---

## 14. Checkpoint integrity

Campaign checkpoint schema `table5-rich-v2` persists both:

1. raw reporting evidence; and
2. the derived indicator snapshot.

On reload, the indicator snapshot is independently reconstructed from the raw
evidence.

The checkpoint is rejected when:

\[
I^{persisted}
\neq
f(
\text{ledger},
\text{service-capacity evidence},
ST
).
\]

This prevents derived percentages from silently drifting away from their raw
computational evidence.

---

## 15. Publication-comparison rule

The publication-facing comparison must distinguish three categories:

1. **raw reproduced quantities** — directly reconstructed from computational
   state;
2. **controlled indicator interpretations** — equations frozen in this
   document before the production campaign;
3. **publication values** — reproduced exactly as printed, including apparent
   inconsistencies such as the Table-5 `855` AFR entry.

No controlled parameter, denominator, demand realisation, truck penalty,
capacity rule or indicator definition may be retrospectively modified merely
to improve numerical agreement with Table 5.

A012 and A013 remain active source-level limitations.
