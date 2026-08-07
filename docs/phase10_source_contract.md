# Phase 10 Source Contract: Service Disruption and Truck Recourse

## 1. Purpose

Phase 10 implements the operational mechanisms required for service-status
changes:

- nominal and actual transport capacity;
- water-level forecast updates;
- disruption detection;
- explicit truck recourse;
- truck penalties;
- Partial-Reroute;
- disruption-aware Full-Reroute.

It does not run the paper's full experiment matrix. That belongs to Phase 11.

## 2. Explicitly supported by the paper

The paper explicitly states that:

1. scheduled services and their nominal capacities are predefined;
2. actual service capacity may vary because of water-level changes;
3. water-level changes modify vessel capacities proportionally;
4. water forecasts are updated every `n` days;
5. forecast accuracy is assumed to hold for `m` days;
6. the reported baseline uses `n = m = 2` days;
7. one model period is half a day, so two days equal four periods;
8. rerouting is performed at every new forecast update;
9. Partial-Reroute triggers at the forecast-update interval;
10. Full-Reroute triggers at every incoming request;
11. trucks may carry barge shortfalls;
12. truck use incurs a carrier penalty;
13. RM policies are excluded from the paper's service-status-change experiment.

## 3. Stable and dynamic policy boundaries

### Stable Table 4-style mechanism

- unchanged service status;
- DCA, DCA-RM, DCA-Reroute and DCA-RRM;
- Full-Reroute at each incoming request;
- truck recourse disabled.

### Standard-water Table 5-style mechanism

- nominal equals actual capacity;
- DCA, Partial-Reroute and Full-Reroute;
- truck recourse available to rerouting mechanisms.

### Water-change Table 6-style mechanism

- Partial-Reroute;
- water factors `1.0`, `0.9`, `0.8`, `0.7`;
- actual capacities derived from nominal capacities;
- truck recourse available.

Full-Reroute under reduced water levels may be evaluated later as an
explicitly labelled extension.

## 4. Unresolved publication details

The paper does not disclose:

- the truck penalty value;
- whether truck penalties differ by demand;
- truck travel times;
- truck capacity;
- truck route structure;
- the terminal from which truck recourse begins;
- whether current requests may be initially assigned to truck;
- the precise water-level sequence;
- whether water factors apply uniformly to all service legs;
- capacity rounding rules;
- event ordering when a booking and status update have the same timestamp;
- the exact formulas and denominators for AFR, NFR, VTR, VFB, VOB and VOA.

No implementation choice for these points may remain undocumented.

## 5. Baseline operational assumptions

The Phase 10 controlled baseline will use:

1. `actual_capacity = water_factor * nominal_capacity`;
2. no integer rounding of actual TEU capacity;
3. only future, unexecuted service legs are affected by an update;
4. completed and currently in-transit movements remain immutable;
5. status updates are processed before bookings at the same timestamp;
6. truck recourse is unlimited in capacity;
7. truck recourse starts at the fragment's execution-aware location;
8. truck delivery is assumed capable of meeting the existing deadline;
9. truck penalty is linear per trucked TEU;
10. trucked volume is terminal and cannot return to barge in a later epoch;
11. truck use is configurable and disabled for Table 4-style experiments;
12. at status-only events, previously accepted revenue is constant and the
    recovery objective minimises truck penalty while preserving all accepted
    cargo.

These are reproduction assumptions, not claims about the authors' unpublished
implementation.

## 6. Required accounting identity

For every unfinished accepted fragment:

\[
q_d^{remaining}
=
q_d^{barge}
+
q_d^{truck}.
\]

For every future transport arc:

\[
\sum_d v_{da}
\leq C_{a,\tau}^{actual}.
\]

The truck penalty is:

\[
Penalty
=
\sum_d c_d^{truck}q_d^{truck}.
\]

At a booking-triggered rerouting epoch:

\[
NetObjective
=
CurrentRevenue
-
Penalty.
\]

At a status-only recovery epoch, current revenue is absent and the equivalent
objective is minimisation of truck penalty.

## 7. Phase 10 gate

A forced capacity reduction must demonstrate that:

1. the previously committed future plan violates new actual capacity;
2. completed and in-transit movement remains unchanged;
3. rerouting uses alternative barge capacity where available;
4. truck flow equals only the residual shortfall;
5. every accepted TEU is delivered;
6. actual capacity is respected;
7. truck penalties reconcile independently;
8. Partial-Reroute triggers only at configured status updates;
9. Full-Reroute triggers at every booking and every required status recovery;
10. disabling truck recourse reproduces the existing truck-disabled behaviour.

## 8. Implemented Phase 10 operational boundary

The completed Phase 10 baseline implements the service-status-change
mechanisms using the following explicit boundaries:

- water-adjusted actual capacity follows A023;
- same-time status precedence and immutable execution follow A024;
- explicit direct truck recourse follows A025;
- production dynamic Full-Reroute disables direct trucking of the newly
  arriving request under A026;
- repeated recoveries use incremental terminal truck history under A027.

The implemented dynamic policies are:

### Partial-Reroute

At a service-status update:

- reconstruct unfinished accepted cargo;
- release its future flexible reservations;
- reroute against current actual capacity;
- send only unavoidable residual volume to truck.

At an ordinary booking event:

- use the current actual residual capacity;
- process the request through ordinary DCA;
- do not reoptimise prior accepted cargo.

### Full-Reroute

At a service-status update:

- perform the same disruption recovery as Partial-Reroute.

At every incoming booking:

- reconstruct unfinished prior accepted fragments;
- release their flexible future barge reservations;
- jointly optimise those fragments with the current request;
- enforce current actual capacity;
- use explicit truck recourse for prior unfinished fragments;
- persist the new booking and operational recovery generation.

The stable-capacity Phase 7 and Phase 9 mechanisms remain unchanged and
truck-disabled.

## 9. Controlled Phase 10 mechanism-validation results

Phase 10 contains two principal controlled validation cases.

### 9.1 PR versus dynamic FR

With:

\[
C^{nominal}=10,\qquad
\lambda=0.7,\qquad
C^{actual}=7,
\]

a previously accepted 10-TEU demand is first recovered as:

\[
7\text{ barge}+3\text{ truck}.
\]

A later one-TEU high-value request produces:

- Partial-Reroute: prior cargo remains \(7+3\), current request rejected;
- Full-Reroute: prior cargo becomes \(6\) barge \(+4\) cumulative truck,
  and the current one-TEU request is accepted on barge.

This is a controlled mechanism test, not a numerical reproduction of a
published table.

### 9.2 Forced-reduction gate

A second controlled network starts with a 10-TEU plan on a primary service.
The primary service is reduced to seven TEU, while an unused one-TEU
alternative barge path remains available.

Recovery yields:

\[
7\text{ primary barge}
+
1\text{ alternative barge}
+
2\text{ truck}
=
10.
\]

Therefore the raw primary overload is:

\[
10-7=3,
\]

while unavoidable truck volume is only:

\[
q^{truck}=2.
\]

The gate verifies that truck volume is residual infeasibility after network
rerouting, not simply the magnitude of raw capacity overload.

## 10. Phase 10 completion boundary

Phase 10 completes the operational mechanism layer required before the paper's
larger experiments can be attempted.

Phase 10 does **not** claim exact numerical reproduction of Tables 5 or 6
because the publication does not disclose enough information to reconstruct
all experimental inputs uniquely.

Phase 11 is responsible for:

- stable Table 4-style experimental reconstruction;
- standard-water Table 5-style DCA/PR/FR experiments;
- water-factor Table 6-style PR experiments;
- indicator reconstruction;
- sensitivity analysis;
- explicit separation between publication reproduction and extensions.
