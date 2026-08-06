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
