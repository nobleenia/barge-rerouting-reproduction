# Phase 10 Controlled Mechanism-Validation Results

## 1. Scope

Phase 10 validates the service-disruption, actual-capacity, truck-recourse,
Partial-Reroute and dynamic Full-Reroute mechanisms.

These results are **controlled synthetic mechanism-validation results**.

They are not presented as exact numerical reproduction of the paper's
Tables 5 or 6 because several required experimental inputs are not disclosed.

## 2. Implemented mechanisms

Phase 10 adds:

- water/service-status update events;
- nominal versus actual transport capacity;
- proportional water-adjusted future capacity;
- disruption detection;
- execution-aware recovery fragments;
- recovery-capacity release;
- explicit truck-volume variables;
- independent truck-recourse validation;
- persistent truck-transfer history;
- operational execution reconstruction;
- actual-capacity booking;
- dynamic Partial-Reroute;
- dynamic Full-Reroute;
- repeated-recovery accounting.

The stable-capacity Phase 7 and Phase 9 mechanisms remain unchanged and
truck-disabled.

## 3. Controlled PR versus FR diagnostic

The controlled test uses:

\[
C^{nominal}=10,
\qquad
\lambda=0.7,
\qquad
C^{actual}=7.
\]

Demand K1:

- accepted volume: 10 TEU;
- revenue: 100 in the controlled fixture.

After the status update:

\[
K1
=
7\text{ barge}
+
3\text{ truck}.
\]

The test truck penalty for K1 is 25 per TEU, giving:

\[
Penalty_{status}
=
3\times25
=
75.
\]

A later one-TEU request K2 has controlled revenue 100.

### Partial-Reroute

PR does not reroute prior cargo at the K2 booking event.

Result:

\[
K1
=
7\text{ barge}
+
3\text{ truck},
\]

and K2 is rejected.

Controlled accounting:

- accepted volume: 10 TEU;
- realised booking revenue: 100;
- cumulative truck volume: 3 TEU;
- cumulative truck penalty: 75.

### Dynamic Full-Reroute

At the K2 booking event, FR reconstructs the seven TEU of K1 that remain
operational after the earlier terminal truck transfer.

The booking-triggered optimisation moves one additional K1 TEU to truck and
admits K2 on barge.

Result:

\[
K1
=
6\text{ barge}
+
4\text{ cumulative truck},
\]

\[
K2
=
1\text{ barge}.
\]

The second recovery creates only one **new** truck TEU:

\[
3+1=4.
\]

Controlled accounting:

- accepted volume: 11 TEU;
- realised booking revenue: 200;
- cumulative truck volume: 4 TEU;
- cumulative truck penalty: 100;
- net realised value: 100.

This difference demonstrates the implemented policy distinction:

\[
PR:
\text{reroute at status updates only},
\]

\[
FR:
\text{reroute at status updates and incoming bookings}.
\]

## 4. Forced-reduction gate

The stronger final Phase 10 gate contains:

- a primary service with nominal capacity 10;
- a status reduction factor 0.7;
- primary actual capacity 7;
- an unused alternative barge route with capacity 1;
- one previously accepted 10-TEU demand.

The original plan has a primary-route overload of:

\[
10-7=3.
\]

Recovery produces:

\[
7\text{ primary barge}
+
1\text{ alternative barge}
+
2\text{ truck}
=
10.
\]

At the controlled truck penalty of 25 per TEU:

\[
Penalty
=
2\times25
=
50.
\]

The independent validator confirms:

- flow conservation;
- barge-plus-truck delivery balance;
- actual-capacity compliance;
- objective reconstruction.

The critical interpretation is:

\[
q^{truck}=2
<
3=\text{raw primary overload}.
\]

Thus raw capacity overload is not itself truck demand. Alternative barge
rerouting absorbs part of the disruption before truck recourse is used.

## 5. Repeated-recovery regression findings

Development of the dynamic FR persistence layer exposed two repeated-recovery
failure modes that are now locked by regression tests.

### Recovery-generation ordering

Two recovery triggers can occur at the same physical time.

The latest generation must therefore be selected from persisted recovery
chronology, not lexicographic ordering of event identifiers.

### Nested recovered-fragment identity

A fragment may itself be produced by an earlier recovery.

A later recovery must reconstruct the immediately preceding fragment identity
when rebuilding its logical delivery arc.

Both behaviours are covered by the final Phase 10 test suite.

## 6. Validation status

At Phase 10 completion:

- forced-reduction gate: 3 tests passed;
- focused Phase 10 dynamic stack: 69 tests passed;
- complete repository: 358 tests passed;
- Ruff: passed;
- formatting check: passed;
- Mypy: passed;
- `git diff --check`: passed.

These counts describe the Phase 10 completion checkpoint and may increase in
later phases.

## 7. Reproduction limitations

Phase 10 does not fabricate missing paper inputs.

Exact reproduction of the publication's dynamic experiment numbers remains
limited by unavailable or insufficiently specified information including:

- exact truck-penalty values;
- whether truck costs vary by demand;
- truck travel time and capacity;
- exact water-level sequence;
- exact service schedules;
- capacity-rounding conventions;
- complete demand-generation distributions and seeds;
- exact indicator formulas/denominators for AFR, NFR, VTR, VFB, VOB and VOA.

Any Phase 11 substitute for these missing inputs must be explicit,
configuration-driven and labelled as an assumption or sensitivity.

## 8. Phase 10 conclusion

Phase 10 establishes the operational machinery required for the paper's
changing-service-status setting.

The strongest controlled gate demonstrates that:

\[
\boxed{
\text{reroute by barge first, then truck only the residual shortfall}
}
\]

while preserving:

- accepted-volume accounting;
- immutable historical execution;
- actual service capacity;
- terminal truck history;
- distinct PR and FR triggering policies.
