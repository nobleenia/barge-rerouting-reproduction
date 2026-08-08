# Questions for the Authors and Interview Panel

## 1. Purpose

This document records clarifications that would improve the accuracy of the
reproduction and research questions that demonstrate careful study of the
paper.

The questions are divided into four groups:

1. implementation-blocking questions;
2. mathematical-formulation questions;
3. experimental and numerical questions;
4. broader research questions.

Lack of an answer will not stop the reproduction. Where clarification is
unavailable, the implementation will follow the documented baseline decision
in `assumptions_register.md`.

---

# 2. Priority questions for early clarification

These questions affect the expected scope of the reproduction.

## Q001 — Expected reproduction level

Is the objective to reproduce the exact numerical results reported in the
paper, or to reproduce the methodology and principal behavioural patterns using
appropriately documented synthetic data?

**Related assumptions:** A001, A010, A013

---

## Q002 — Supplementary materials

Are any of the following available?

- original source code;
- generated demand instances;
- parameter files;
- service schedules;
- water-level scenarios;
- experiment configurations;
- supplementary documentation.

**Related assumptions:** A001, A010

---

## Q003 — Exact service-family schedules

Can the exact arrival and departure schedules for Service Families 1 and 2 be
provided, including:

- direction;
- terminal sequence;
- departure times;
- arrival times;
- periodic offsets;
- capacities.

**Related assumption:** A001

---

# 3. Mathematical-formulation questions

## Q004 — Future-demand revenue expression

For protected future-demand level \(j\), the printed model uses:

\[
\sum_{x=0}^{j} xP_k(x).
\]

This does not generally equal:

\[
E[\min(X_k,j)].
\]

When realised demand exceeds \(j\), is the entire request assumed to be rejected,
or was a capped expectation intended?

**Related assumption:** A005

---

## Q005 — Previously executed demand movements

When an already accepted demand is rerouted, are all previously executed arcs
fixed while only the unfinished portion is reoptimised from its current
terminal-time location?

**Related assumption:** A003

---

## Q006 — Destination-time definition

Does a demand satisfy its delivery requirement by reaching:

1. the destination exactly at \(t^{due}(k)\); or
2. any destination-time node no later than \(t^{due}(k)\)?

**Related assumption:** A002

---

## Q007 — Construction of \(K(\tilde{k})\)

How is the statement that future demands have “direct possible interactions in
time” operationally evaluated?

Possible interpretations include:

- overlapping time windows;
- common service legs;
- shared feasible transport arcs;
- common origin-destination corridors;
- a fixed forecast horizon.

**Related assumption:** A004

---

## Q008 — Demand divisibility

Are demand volumes intentionally modelled as divisible TEU flows that may use
multiple itineraries, or were additional restrictions used to keep each
request on a single itinerary?

**Related assumption:** A006

---

## Q009 — Holding arcs

Were holding arcs treated as:

- unlimited;
- costless;
- unconstrained by terminal capacity?

Were any waiting or storage penalties used?

**Related assumption:** A007

---

## Q010 — Truck recourse variables

How were truck transfers represented in the implementation?

In particular:

- Was there an explicit truck-volume variable?
- Were truck arcs included in the network?
- Was truck capacity unlimited?
- Was the penalty defined per TEU?
- Could every customer category be transferred?

**Related assumption:** A008

---

## Q011 — Previously accepted revenue

Was revenue from past accepted demand omitted from the rolling-horizon objective
because its accepted quantity and revenue were already fixed?

If rerouting causes truck penalties, was only the incremental recourse cost
included for those past demands?

---

## Q012 — Future-demand feasibility

When a future volume level \(j\) is selected, must the full value \(j\) be
routed feasibly through the time-space network at the current decision epoch?

Or is it treated only as reserved capacity without a complete tentative route?

---

# 4. Experimental questions

## Q013 — Demand generation

Can the following original values be provided?

- \(VMAX\);
- volume distributions;
- random seeds;
- demand counts;
- anticipation-time pools;
- delivery-time pools;
- base fares;
- fare multipliers;
- customer-category probabilities.

**Related assumption:** A010

---

## Q014 — Demand density and 800-demand experiment

How should the stated demand density of ten demands per half-day be reconciled
with the separate reference to a set of 800 demands?

Were these descriptions associated with different experiments or horizons?

**Related assumption:** A013

---

## Q015 — Water-level sequence

Were water levels:

- constant throughout each scenario;
- changed according to a predefined sequence;
- generated stochastically;
- applied uniformly to every service leg?

**Related assumptions:** A009, A010

---

## Q016 — Forecast accuracy

How were the water-level forecast update interval and accuracy horizon
implemented?

Were forecast errors included, or were the updated capacity forecasts assumed
to be correct?

---

## Q017 — Truck penalty values

What truck penalty or cost values were used, and how were they calibrated
relative to barge fares?

**Related assumptions:** A008, A010

---

## Q018 — Performance-indicator denominators

What are the exact mathematical definitions of:

- VTR;
- VFB;
- VOB;
- VOA?

For each rate, what is the numerator and denominator?

**Related assumption:** A012

---

## Q019 — Apparent Table 5 AFR entry

Table 5 appears to contain an AFR value of \(855\%\).

Was \(85\%\) intended?

**Related assumption:** A013

---

## Q020 — Apparent Table 6 NFR entry

For Service Family 1, capacity 40 and water factor 0.9, Table 6 appears to report:

\[
NFR=8\%.
\]

Since the same row reports:

\[
AFR=89\%
\]

and:

\[
0.9\times89\%\approx80\%,
\]

was \(80\%\) intended?

**Related assumption:** A013

---

## Q021 — Statistical analysis

Were standard deviations, confidence intervals or statistical significance
tests calculated across the demand sets?

If not, were the reported average, minimum and maximum values considered
sufficient because the experiments were intended primarily as behavioural
demonstrations?

---

## Q022 — Solver parameters

Were default CPLEX parameters used?

If not, what values were used for:

- time limit;
- relative MIP gap;
- threads;
- presolve;
- emphasis;
- random seed;
- memory limits.

---

# 5. Research-level interview questions

## Q023 — Rerouting trigger as a decision

Could rerouting frequency itself become a decision rather than using only:

- Full-Reroute after every demand; or
- Partial-Reroute at fixed intervals?

For example, could rerouting be triggered only when predicted benefit exceeds
its computational and operational cost?

---

## Q024 — Forecast uncertainty

How sensitive are the revenue-management decisions to biased or inaccurate
future-demand forecasts?

Would robust or distributionally robust optimisation be appropriate?

---

## Q025 — Learning-guided optimisation

Which component is considered the most promising target for machine learning?

- warm-start generation;
- acceptance prediction;
- variable fixing;
- promising-arc prediction;
- future-demand selection;
- rerouting-trigger prediction;
- heuristic operator selection.

---

## Q026 — Principal scalability bottleneck

Which factor dominates computational growth in the present implementation?

- number of terminal-time nodes;
- number of transport arcs;
- number of demands or commodities;
- number of future-volume levels;
- number of binary acceptance variables;
- rerouting frequency.

---

## Q027 — Arc-flow versus path-flow formulation

Was an arc-flow formulation selected mainly for modelling convenience?

Could a path-flow or column-generation approach improve scalability on larger
service networks?

---

## Q028 — Sustainability objective

The study is motivated partly by the sustainability advantages of inland
waterway transport, but truck recourse can increase road transport.

Would a multi-objective formulation including:

- revenue;
- emissions;
- road congestion;
- service reliability;

change the preferred rerouting decisions?

**Related assumption:** A014

---

## Q029 — Tactical and operational integration

Could the operational booking-and-rerouting model be integrated with tactical
decisions such as:

- vessel assignment;
- frequency selection;
- timetable design;
- service-network design?

---

## Q030 — Real-world validation

What operational data would be most important for validating the model on a
real inland-waterway network?

Possible data include:

- actual bookings;
- vessel loads;
- service schedules;
- realised water levels;
- cancellations;
- truck-recouse costs;
- delay records.

---

# 6. Communication rule

When raising questions:

- distinguish clarification from criticism;
- cite the relevant equation, table, or modelling concept;
- explain why the answer affects implementation;
- state the current baseline assumption;
- avoid claiming that an apparent inconsistency is definitely an error.

The strongest questions should be used selectively rather than presented as a
long interrogation.

---

## Q031 — Zero future-volume selector

The linking and exclusivity constraints use positive protected-volume levels,
while the variable-domain statement appears to include \(j=0\).

Was an explicit variable \(y_{k0}\) created, or was zero protected volume
represented by setting all positive-level selectors to zero?

**Related assumption:** A016

---

## Q032 — Exact truck decision and penalty definition

In the general objective, the penalty term refers to demand volume shifted
from barges to trucks.

How was truck usage represented in the authors' implementation?

In particular:

- was there an explicit truck-volume decision variable;
- was truck represented by network arcs;
- was the penalty linear per TEU;
- could the penalty differ by demand?

**Implementation impact:** determines whether A025 matches the unpublished
operational formulation.

---

## Q033 — Truck origin, travel time and capacity

When barge cargo is transferred to truck after a disruption:

- from which terminal does the truck movement begin;
- is truck capacity unlimited;
- is truck travel time modelled;
- must truck delivery explicitly satisfy the original due time?

**Current baseline:** direct unlimited recourse from the fragment's
execution-aware rerouting source, assumed capable of meeting the deadline.

**Related assumption:** A025

---

## Q034 — May the newly arriving request be assigned directly to truck?

During Full-Reroute under changing service status, is truck recourse restricted
to already accepted demand that becomes infeasible, or may the current booking
request itself be accepted directly onto truck?

**Current production baseline:** the arriving request is not directly trucked.

**Related assumption:** A026

---

## Q035 — Water-adjusted capacity rounding and service scope

When vessel capacity is changed proportionally with water level:

- is the product rounded to an integer TEU capacity;
- if so, what rounding rule is used;
- does one water factor apply to every service or only selected services/legs?

**Current baseline:** no rounding; status events may target selected services.

**Related assumption:** A023

---

## Q036 — Ordering of status updates and bookings at the same time

If a water/service forecast update and a demand request occur in the same
half-day period, which is processed first?

**Current baseline:** status update first so the booking sees the newest
capacity information.

**Related assumption:** A024

---

## Q037 — Dynamic-experiment indicator formulas

Could the exact formulas and denominators used for the following indicators
be provided?

- AFR;
- NFR;
- VTR;
- VFB;
- VOB;
- VOA.

This is required for exact Table 5/6 numerical reproduction even when the
underlying routing decisions are reproduced correctly.

---

## Q038 — Relationship between 400/800 time instants and demand counts

Section 4.1 reports:

- a rolling-time horizon of 400/800 time instants;
- demand density 10 per half-day;
- while the dynamic experiment later refers to a set of 800 demands.

How exactly are these quantities related in the original simulation?

In particular, how many demand-generation opportunities and positive-volume
booking requests are used in the stable Table 4 instances?

**Related assumption:** A030

---

## Q039 — Complete numerical demand and fare generation parameters

Could the original numerical generation inputs be provided for:

- VMAX;
- the probability mass on `0..VMAX`;
- anticipation pools by OD distance;
- delivery-time pools by OD distance;
- early/late and standard/express thresholds;
- base fares by OD distance;
- late-reservation multiplier;
- express-delivery multiplier;
- random seeds?

These values are required for exact numerical reproduction of Table 4 rather
than only methodological reproduction.

**Related assumption:** A031

---

## Q040 — Construction and information content of future-demand forecasts

For the stable DCA-RM and DCA-RRM experiments, how was the potential future
set \(K(\tilde{k})\) generated?

In particular:

- were future OD pairs known or probabilistic?
- were future availability and due times known?
- were customer classes and fares known?
- how many potential future requests were represented per decision epoch?
- were requests later in the same half-day included?
- was there a finite forecast look-ahead horizon?
- were forecasts fixed at the beginning of the simulation or regenerated
  during the rolling horizon?

The Phase 11 baseline currently uses an independent ex-ante forecast catalogue
under A033 rather than unrevealed realised request attributes.

**Related assumptions:** A004, A033
