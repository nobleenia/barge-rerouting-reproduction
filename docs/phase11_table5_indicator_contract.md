# Phase 11 Table 5 Indicator Contract

## 1. Purpose

This document defines the raw quantities from which the Phase-11 Table-5
performance indicators will be reconstructed.

The publication reports:

- AFR — Actual Fill Rate;
- NFR — Nominal Fill Rate;
- VTR — Volume rate of demand on Truck due to Reroute;
- VFB — Volume rate of demand Finally allocated on Barge;
- VOB — Volume rate of demand Originally accepted on Barge;
- VOA — Volume rate of demand Originally Accepted;
- TR — Total Revenue;
- ST — Solving Time.

The publication does not disclose complete mathematical numerator and
denominator definitions for all volume-rate indicators.

Therefore the implementation first records raw physical quantities and only
then constructs candidate percentage definitions.

No denominator is selected merely to improve agreement with the published
table.

---

## 2. Frozen Table-5 demand population

The controlled Table-5 demand realisation contains:

- 800 requests;
- 1076 TEU requested in total.

Define

\[
Q^{req} = \sum_k q_k^{req}.
\]

For the frozen instance:

\[
Q^{req}=1076\ {\rm TEU}.
\]

---

## 3. Contractual acceptance quantities

For every demand \(k\), the original booking decision records:

- requested volume;
- acceptance fraction;
- accepted volume;
- original planned arc flows.

Define

\[
q_k^{acc}
=
q_k^{req} e_k
\]

and

\[
Q^{acc}
=
\sum_k q_k^{acc}.
\]

This quantity is retained independently of subsequent PR/FR recovery
decisions.

The raw ledger also records:

- total request count;
- positively accepted request count;
- rejected request count.

These quantities permit both volume-based and request-count-based candidate
interpretations of VOA to be evaluated without changing the underlying
experiment.

---

## 4. Truck and final-barge quantities

For PR and FR, cumulative truck allocations are persisted in
`RecoveryOperationalState.truck_transfer_history`.

Define:

\[
Q^{truck}
=
\sum_{\tau \in H^{truck}} q_\tau.
\]

The contractual accepted-volume conservation identity is:

\[
Q^{acc}
=
Q^{barge,remaining}
+
Q^{truck,pending}
+
Q^{barge,delivered}
+
Q^{truck,delivered}.
\]

At the terminal reporting horizon, define total cargo that remains allocated
to barge as:

\[
Q^{final,barge}
=
Q^{acc}
-
Q^{truck}.
\]

This identity is an implementation accounting relationship.

It must not by itself be presented as the publication's undisclosed VFB
formula until the denominator interpretation is frozen.

---

## 5. Original-barge quantity

The booking state preserves the original `DemandCommitment` and its
`planned_arc_flows`.

A separate raw quantity will therefore be reconstructed from the booking-time
commitments:

\[
Q^{original,barge}.
\]

This quantity must be measured from the original commitments rather than
inferred from the final recovered state.

This distinction matters because Full-Reroute may subsequently replace
future barge movements and create truck allocations.

---

## 6. Published conservation clue

The published Table-5 and Table-6 values strongly support the relationship:

\[
VOB \approx VFB + VTR
\]

up to published integer rounding.

Therefore the reproduction will require the corresponding raw-volume
relationship:

\[
Q^{original,barge}
\approx
Q^{final,barge}
+
Q^{rerouted,truck}
\]

under whichever common denominator is eventually adopted.

Failure of this relationship is a reporting-contract failure and must not be
hidden through denominator tuning.

---

## 7. VOA ambiguity

The publication defines VOA verbally as "Volume rate of demand Originally
Accepted" but does not disclose the denominator.

The reproduction will retain at least:

\[
VOA_{volume,candidate}
=
100 \frac{Q^{acc}}{Q^{req}}
\]

and

\[
VOA_{request,candidate}
=
100
\frac{N^{accepted}}{N^{requested}}.
\]

Neither candidate is labelled as the reproduced publication indicator until
the published table structure and implementation evidence support that
choice.

---

## 8. Revenue

The raw economic quantities are:

\[
TR^{gross}
=
\sum_k r_k^{booking}
\]

and, for PR/FR,

\[
C^{truck}
=
\sum_\tau c_\tau^{truck}.
\]

The controlled implementation additionally records:

\[
TR^{net}
=
TR^{gross}
-
C^{truck}.
\]

The publication's `TR` must be compared against the appropriate gross/net
interpretation only after its treatment of truck penalties is established.

---

## 9. Solving time

The implementation records wall-clock runtime for each policy experiment.

Runtime is useful for within-reproduction comparison but is not claimed to
replicate the paper's hardware-specific solving times.

---

## 10. AFR and NFR

The frozen pilot network contains:

- 112 transport arcs;
- four recurring service-pattern identifiers;
- 28 transport arcs associated with each recurring service pattern.

The recurring `service_id` is therefore not treated automatically as one
unique physical sailing.

AFR and NFR will be constructed only after the unique scheduled-sailing
aggregation is identified.

At standard water level the mandatory validation invariant is:

\[
AFR=NFR.
\]

No fill-rate implementation will be accepted unless this invariant holds on
the standard-water experiment.

---

## 11. Reporting principle

Raw quantities are authoritative.

Published indicator labels are attached only after numerator and denominator
interpretations have been explicitly documented.

No indicator denominator, truck penalty, demand realisation, or capacity
definition may be retrospectively changed merely to improve numerical
agreement with the publication.
