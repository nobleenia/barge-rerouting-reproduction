# Mathematical Model Specification

## 1. Purpose

This document is the mathematical contract for the CPLEX implementation.

It distinguishes:

1. the formulation printed in the source paper;
2. the precise baseline interpretation used in this reproduction;
3. sensitivity formulations and later research extensions.

The software must not contain a scientifically consequential variable,
constraint, coefficient, or state transition that cannot be traced to this
document or to the assumptions register.

---

# 2. Decision epoch and notation

Let:

\[
\tau = t^{res}(\tilde{k})
\]

denote the current booking decision epoch, corresponding to the reservation
time of the incoming request \(\tilde{k}\).

At decision epoch \(\tau\), the optimiser may consider:

\[
D(\tilde{k})
\]

the set of already accepted but unfinished demands;

\[
\{\tilde{k}\}
\]

the current incoming request; and

\[
K(\tilde{k})
\]

the set of relevant potential future demands.

For compactness, define:

\[
\mathcal{K}_{\tau}
=
D(\tilde{k})\cup\{\tilde{k}\}\cup K(\tilde{k}).
\]

The exact composition of \(\mathcal{K}_{\tau}\) depends on the selected policy.

---

# 3. Time-space network

## 3.1 Sets

\[
I
\]

set of physical terminals.

\[
\mathcal{T}=\{0,\ldots,T\}
\]

set of discrete time periods.

\[
N^{IT}
=
\{n(i,t):i\in I,\ t\in\mathcal{T}\}
\]

set of terminal-time nodes.

\[
A_L
\]

set of scheduled transport arcs.

\[
A_H
\]

set of holding or waiting arcs.

\[
A=A_L\cup A_H.
\]

For a node \(n\in N^{IT}\):

\[
A^+(n)
\]

is the set of arcs leaving \(n\), and:

\[
A^-(n)
\]

is the set of arcs entering \(n\).

The paper defines the transport system as a directed time-space graph:

\[
G=(N^{IT},A).
\]

## 3.2 Arc structure

A transport arc:

\[
a=(n(i,t),n(j,t'))
\in A_L
\]

represents a scheduled movement from terminal \(i\) at time \(t\) to terminal
\(j\) at time \(t'>t\).

A holding arc:

\[
a=(n(i,t),n(i,t+1))
\in A_H
\]

represents cargo waiting at terminal \(i\) for one time period.

All baseline arcs move forward in time. Therefore, the time-space graph should
normally be a directed acyclic graph over one finite planning horizon.

---

# 4. Demand data

For each demand \(k\), define:

\[
q_k = vol(k)
\]

requested volume in TEU;

\[
o_k=o(k)
\]

physical origin terminal;

\[
d_k=d(k)
\]

physical destination terminal;

\[
r_k=t^{res}(k)
\]

reservation time;

\[
a_k=t^{avl}(k)
\]

availability time at origin;

\[
b_k=t^{due}(k)
\]

latest permitted destination arrival time;

\[
c_k=cat(k)\in\{R,P,F\}
\]

customer category; and:

\[
f_k=f(k)
\]

unit fare per accepted TEU.

For future demand \(k\in K(\tilde{k})\), define:

\[
VMAX_k
\]

as the maximum possible request volume and:

\[
P_k(x)=\Pr(X_k=x),
\qquad
x\in\{0,\ldots,VMAX_k\}.
\]

The probability distribution must satisfy:

\[
P_k(x)\geq0
\]

and:

\[
\sum_{x=0}^{VMAX_k}P_k(x)=1.
\]

---

# 5. Capacity parameters

For transport arc \(a\in A_L\), define:

\[
C_a^{nom}
\]

nominal scheduled capacity;

\[
\lambda_{a,\tau}
\]

water-level or service-status capacity multiplier at epoch \(\tau\);

\[
C_{a,\tau}^{actual}
=
\lambda_{a,\tau}C_a^{nom}
\]

actual usable capacity; and:

\[
C_{a,\tau}^{avl}
\]

capacity available to the optimisation model.

The available capacity must exclude only allocations that are already
irreversible or external to the current reoptimisation.

Reroutable planned flows must not be subtracted from capacity before being
included again as decision variables. Otherwise, capacity would be counted
twice.

For holding arcs \(a\in A_H\), the baseline assumes no binding capacity.

---

# 6. Decision variables

## 6.1 Current-demand acceptance

For the current request \(\tilde{k}\):

\[
\xi_{\tilde{k}}
\]

is the accepted fraction.

Its domain depends on customer category:

\[
\xi_{\tilde{k}}=1
\qquad
\text{if }c_{\tilde{k}}=R,
\]

\[
0\leq\xi_{\tilde{k}}\leq1
\qquad
\text{if }c_{\tilde{k}}=P,
\]

\[
\xi_{\tilde{k}}\in\{0,1\}
\qquad
\text{if }c_{\tilde{k}}=F.
\]

The accepted volume is:

\[
Q_{\tilde{k}}^{accepted}
=
q_{\tilde{k}}\xi_{\tilde{k}}.
\]

For every past demand \(k\in D(\tilde{k})\), its previously committed accepted
volume is fixed and cannot be reduced during rerouting.

---

## 6.2 Arc-flow variables

For demand \(k\) and arc \(a\):

\[
v_{ka}\geq0
\]

is the volume of demand \(k\) assigned to arc \(a\).

Because these variables are continuous, the baseline formulation permits
splitting a demand across several feasible itineraries.

---

## 6.3 Future-demand selectors

For each future demand \(k\in K(\tilde{k})\), define candidate protected-volume
levels:

\[
J_k=\{1,\ldots,VMAX_k\}.
\]

For \(j\in J_k\):

\[
y_{kj}\in\{0,1\}
\]

equals one when protected level \(j\) is selected.

Define:

\[
m_k=maxvol(k)
\]

as the future volume tentatively accommodated in the current capacity plan.

The linking constraint is:

\[
m_k
=
\sum_{j\in J_k}j\,y_{kj}.
\]

At most one positive level may be selected:

\[
\sum_{j\in J_k}y_{kj}\leq1.
\]

If all selectors equal zero, then:

\[
m_k=0.
\]

This implementation omits a separate variable \(y_{k0}\), because the all-zero
selector vector already represents zero protected volume.

---

## 6.4 Explicit truck recourse

For accepted current or past demand \(k\), define:

\[
q_k^{truck}\geq0
\]

as the volume transferred from barge transport to truck during a recourse or
disruption decision.

Let:

\[
c_k^{truck}\geq0
\]

be the penalty or cost per TEU transferred to truck.

Truck recourse is disabled in the initial stable-capacity baseline and enabled
only for experiments in which alternative-mode recourse is permitted.

---

# 7. Published objective

The paper's printed DCA-RRM objective contains:

1. revenue from the current request;
2. expected contribution from future requests;
3. a penalty term related to past and current demands.

The current-request contribution is:

\[
f_{\tilde{k}}
q_{\tilde{k}}
\xi_{\tilde{k}}.
\]

For future request \(k\), the printed contribution for selected level \(j\) is:

\[
R_{kj}^{printed}
=
f_k
\sum_{x=0}^{j}xP_k(x).
\]

Therefore, the printed future contribution is:

\[
\sum_{k\in K(\tilde{k})}
\sum_{j\in J_k}
R_{kj}^{printed}y_{kj}.
\]

Revenue already earned or contractually committed for past accepted requests
does not need to be added again when it is constant with respect to the current
decision.

---

# 8. Baseline implementation objective

For the stable-capacity model without truck recourse:

\[
\max
\quad
f_{\tilde{k}}
q_{\tilde{k}}
\xi_{\tilde{k}}
+
\sum_{k\in K(\tilde{k})}
\sum_{j\in J_k}
R_{kj}^{printed}y_{kj}.
\]

For a recourse model with explicit truck transfers:

\[
\max
\quad
f_{\tilde{k}}
q_{\tilde{k}}
\xi_{\tilde{k}}
+
\sum_{k\in K(\tilde{k})}
\sum_{j\in J_k}
R_{kj}^{printed}y_{kj}
-
\sum_{k\in D(\tilde{k})\cup\{\tilde{k}\}}
c_k^{truck}q_k^{truck}.
\]

Past accepted revenue is omitted because it is constant, but any new truck
penalty caused by the current reoptimisation remains decision-dependent and is
included.

---

# 9. Sensitivity future-value function

The alternative capped-demand value is:

\[
R_{kj}^{capped}
=
f_kE[\min(X_k,j)].
\]

For a discrete distribution:

\[
R_{kj}^{capped}
=
f_k
\left[
\sum_{x=0}^{j}xP_k(x)
+
j\sum_{x=j+1}^{VMAX_k}P_k(x)
\right].
\]

This alternative credits outcomes where realised future demand exceeds the
protected level \(j\).

It will be implemented as a sensitivity variant and will not be described as
the paper's printed baseline.

---

# 10. Shared transport-arc capacity

For every transport arc \(a\in A_L\):

\[
\sum_{k\in\mathcal{K}_{\tau}}v_{ka}
\leq
C_{a,\tau}^{avl}.
\]

This is the principal coupling constraint.

Each demand has its own commodity flow, but all demands compete for the same
service-leg capacity.

Holding arcs are excluded from this constraint in the baseline model.

---

# 11. Generalised flow conservation

## 11.1 Balance representation

For each modelled demand \(k\), define a node-balance parameter:

\[
b_{kn}.
\]

The general conservation equation is:

\[
\sum_{a\in A^+(n)}v_{ka}
-
\sum_{a\in A^-(n)}v_{ka}
=
b_{kn}
\qquad
\forall k,\forall n.
\]

At ordinary intermediate nodes:

\[
b_{kn}=0.
\]

This means that flow cannot be created or destroyed inside the transportation
network.

---

## 11.2 Current demand

Create a source node:

\[
s_{\tilde{k}}
=
n(o_{\tilde{k}},a_{\tilde{k}})
\]

or the earliest feasible origin-time node after the current booking epoch.

For the current request:

\[
b_{\tilde{k},s_{\tilde{k}}}
=
q_{\tilde{k}}\xi_{\tilde{k}}.
\]

The same accepted quantity must be absorbed at the demand's destination
super-sink:

\[
b_{\tilde{k},\hat{d}_{\tilde{k}}}
=
-q_{\tilde{k}}\xi_{\tilde{k}}.
\]

---

## 11.3 Future demand

For future demand \(k\in K(\tilde{k})\):

\[
b_{k,s_k}=m_k
\]

and:

\[
b_{k,\hat{d}_k}=-m_k.
\]

Thus, selecting future level \(j\) is not merely an accounting reservation.

The complete protected volume must be routable through the current time-space
capacity plan.

---

## 11.4 Past unfinished demand

A past demand may have remaining fragments at several current terminal-time
positions.

Let:

\[
F_k^\tau
\]

be the set of unfinished fragments of demand \(k\) at epoch \(\tau\).

For fragment \(h\in F_k^\tau\), let:

\[
\ell_{kh}^{\tau}
\]

be its current terminal-time node and:

\[
q_{kh}^{rem}
\]

its remaining undelivered volume.

Set:

\[
b_{k,\ell_{kh}^{\tau}}
\mathrel{+}=
q_{kh}^{rem}.
\]

At the destination super-sink:

\[
b_{k,\hat{d}_k}
=
-
\sum_{h\in F_k^\tau}q_{kh}^{rem}.
\]

This prevents previously transported cargo from restarting at its original
source.

Executed historical arcs are stored in simulation state and are not decision
variables in the new rerouting model.

---

# 12. Destination deadline using a super-sink

For demand \(k\), define eligible destination-time nodes:

\[
N_k^{dest}
=
\{
n(d_k,t):
t\leq b_k
\}.
\]

Create a demand-specific super-sink:

\[
\hat{d}_k.
\]

For every eligible destination-time node \(n(d_k,t)\in N_k^{dest}\), add a
zero-capacity-free connector arc:

\[
(n(d_k,t),\hat{d}_k).
\]

No connector is added from a destination-time node after the due time.

Therefore, delivery is feasible only when:

\[
t^{arrival}_k\leq b_k.
\]

The super-sink converts several acceptable arrival times into one unique sink
for flow conservation.

---

# 13. Truck-recourse balance

When truck recourse is enabled, barge delivery plus truck delivery must equal
the remaining contractual volume.

For a past accepted demand:

\[
Q_k^{remaining}
=
Q_k^{barge}
+
q_k^{truck}.
\]

For an accepted current request:

\[
q_{\tilde{k}}\xi_{\tilde{k}}
=
Q_{\tilde{k}}^{barge}
+
q_{\tilde{k}}^{truck}.
\]

In implementation, this may be represented either by:

1. an explicit truck variable in the commodity balance; or
2. a truck connector from the demand source state directly to its super-sink.

The first baseline implementation will use an explicit quantity variable,
because it is easier to audit and report.

---

# 14. Policy-specific model composition

## 14.1 DCA

Modelled decisions:

\[
\{\tilde{k}\}.
\]

Past accepted itineraries remain fixed outside the optimisation model and
consume residual capacity.

No future-demand selectors are included.

No past-demand rerouting is permitted.

---

## 14.2 DCA-RM

Modelled demands:

\[
\{\tilde{k}\}\cup K(\tilde{k}).
\]

Past accepted itineraries remain fixed and consume residual capacity.

Future selectors and tentative future flows are included.

---

## 14.3 DCA-Reroute

Modelled demands:

\[
D(\tilde{k})\cup\{\tilde{k}\}.
\]

Past unfinished flows may be reoptimised from their current state.

No future-demand selectors are included:

\[
K(\tilde{k})=\varnothing.
\]

---

## 14.4 DCA-RRM

Modelled demands:

\[
D(\tilde{k})
\cup
\{\tilde{k}\}
\cup
K(\tilde{k}).
\]

It combines:

- current acceptance;
- past unfinished-demand rerouting;
- future-demand capacity protection.

---

# 15. Partial- and Full-Reroute triggers

The mathematical rerouting model may be identical while the triggering policy
changes.

## Full-Reroute

Reoptimise eligible unfinished demands after every new incoming request.

## Partial-Reroute

Reoptimise only at configured forecast-update or disruption epochs.

Therefore, Partial- and Full-Reroute differ primarily in the simulation control
logic rather than in the core flow-conservation equations.

---

# 16. Variable domains

For all modelled demands and feasible arcs:

\[
v_{ka}\geq0.
\]

For all future selectors:

\[
y_{kj}\in\{0,1\}.
\]

For future protected volume:

\[
m_k\geq0.
\]

For truck transfer:

\[
q_k^{truck}\geq0.
\]

The current acceptance domain is determined by customer category.

Past accepted quantities are parameters during reoptimisation, not new
acceptance decisions.

---

# 17. Model classification

The model is a linear programme when all decision variables are continuous.

It becomes a mixed-integer linear programme when it contains at least one of:

- fully-spot binary acceptance variable;
- future-volume selector \(y_{kj}\);
- later unsplittable-routing variables.

The baseline models are therefore generally MILPs.

The formulation is also a capacitated multi-commodity flow model because:

- every demand has its own flow;
- multiple demand flows share service-leg capacities.

---

# 18. CPLEX and DOcplex translation

| Mathematical concept | Planned DOcplex construction |
|---|---|
| Continuous acceptance | `model.continuous_var(lb=0, ub=1)` |
| Binary acceptance | `model.binary_var()` |
| Continuous arc flow | `model.continuous_var(lb=0)` |
| Future selector | `model.binary_var()` |
| Protected volume | `model.continuous_var(lb=0)` or linear expression |
| Truck quantity | `model.continuous_var(lb=0)` |
| Linear sum | `model.sum(...)` |
| Capacity constraint | `model.add_constraint(...)` |
| Flow balance | named `model.add_constraint(...)` |
| Objective | `model.maximize(...)` |
| LP inspection | `model.export_as_lp(...)` |
| Solve | `model.solve(...)` |
| Status and time | `model.solve_details` |

Every major constraint will receive a deterministic name such as:

```text
capacity__arc_<arc_id>
flow__demand_<demand_id>__node_<node_id>
future_level__demand_<demand_id>
truck_balance__demand_<demand_id>
```

Named constraints make LP exports and infeasibility diagnosis easier.

# 19. Model-size drivers

Approximate flow-variable count:

O(∣K
τ
	​

∣∣A∣).

Approximate flow-balance constraint count:

O(∣K
τ
	​

∣∣N
IT
∣).

Future binary count:

O
	​

k∈K(
k
~
)
∑
	​

∣J
k
	​

∣
	​

.

The main computational drivers are expected to include:

number of time periods;
number of services and transport arcs;
number of active demand commodities;
number of future protected-volume levels;
rerouting frequency;
number of binary acceptance and selector variables.

Demand-specific network pruning should reduce the number of unnecessary
variables and constraints.

# 20. Required mathematical invariants

Every feasible solution must satisfy the following checks.

Volume conservation

For each modelled demand:

total source supply=total destination delivery+authorised truck delivery.
Transport capacity

For every transport arc:

k
∑
	​

v
ka
	​

≤C
a,τ
avl
	​

+ϵ.
Nonnegative residual capacity
C
a,τ
avl
	​

−
k
∑
	​

v
ka
	​

≥−ϵ.
Deadline compliance

Any positive barge delivery must reach the destination at:

t≤b
k
	​

.
Commitment preservation

For every past accepted demand:

Q
k
remaining
	​


cannot be rejected or reduced.

Fixed-history preservation

No executed arc may be removed, changed, or traversed again by the same
historical cargo fragment.

Future-selection consistency
m
k
	​

=
j
∑
	​

jy
kj
	​

.
Selector exclusivity
j
∑
	​

y
kj
	​

≤1.
Objective reconciliation

The objective reported by CPLEX must equal an independently recalculated value
within numerical tolerance.

# 21. Numerical tolerance

Use a common feasibility tolerance in validation code:

ϵ=10
−6

unless solver behaviour requires another documented value.

Floating-point values should not be compared using exact equality.

For example, test:

∣x−y∣≤ϵ

rather than:

x=y

in raw Python arithmetic.

# 22. Known unresolved points

The following remain dependent on author clarification or documented
assumption:

exact service schedules;
exact definition of K(
k
~
);
exact truck penalty formulation;
precise performance-indicator denominators;
original demand distributions;
interpretation of the printed future-revenue term;
whether y
k0
	​

 was explicitly created;
exact handling of partially transported fragments in the original code;
solver parameter settings.

The implementation will continue using the decisions recorded in
assumptions_register.md.

23. Implementation order

The mathematical components will be implemented in this order:

graph and network objects;
current-demand flow conservation;
shared transport capacity;
customer-category acceptance domains;
DCA baseline;
rolling-horizon state;
past-demand fragment rerouting;
future-demand selectors and expected value;
combined DCA-RRM;
water-level capacity changes;
truck recourse;
experiment indicators.

This order allows every new capability to be validated against a simpler
working model.

# 24. Phase 9 combined DCA-RRM formulation

## 24.1 Decision epoch and commodity sets

At the booking epoch of current request \(\tilde{k}\), the combined
DCA-RRM model contains three commodity groups:

\[
D(\tilde{k})
\cup
\{\tilde{k}\}
\cup
K(\tilde{k}),
\]

where:

- \(D(\tilde{k})\) is the set of accepted unfinished demand fragments
  eligible for rerouting;
- \(\tilde{k}\) is the current booking request;
- \(K(\tilde{k})\) is the selected future-demand forecast set.

The fragment construction follows the execution-aware interpretation in
Assumption A003. The future-set construction follows Assumptions A004 and
A020.

## 24.2 Current-request variables

For the current request \(\tilde{k}\), let:

\[
e_{\tilde{k}}
\]

be its acceptance variable and let:

\[
v_{\tilde{k}a}
\]

be its flow on feasible arc \(a\).

The domain of \(e_{\tilde{k}}\) depends on the customer category:

- regular demand is mandatory;
- fully spot demand is binary;
- partially spot demand may be fractionally accepted.

Its realised revenue contribution is:

\[
f_{\tilde{k}}
Q_{\tilde{k}}
e_{\tilde{k}}.
\]

## 24.3 Accepted unfinished fragments

For every fragment \(d\in D(\tilde{k})\), let:

\[
q_d^{rem}
\]

be its fixed unfinished accepted volume and:

\[
w_{da}
\]

its reconstructed future flow on arc \(a\).

A fragment has no acceptance variable. Its remaining accepted quantity is
mandatory and cannot be reduced or rejected.

Its flow originates from the fragment's execution-aware effective source
node and terminates at an eligible sink for the original demand.

Executed movement and immutable in-transit movement remain outside the
released rerouting decision.

## 24.4 Future-demand protection variables

For each forecast \(k\in K(\tilde{k})\), let:

\[
y_{kj}\in\{0,1\}
\]

select positive protected-volume level \(j\), subject to:

\[
\sum_{j=1}^{VMAX_k}y_{kj}\leq 1.
\]

The protected volume is:

\[
maxvol(k)
=
\sum_{j=1}^{VMAX_k}j y_{kj}.
\]

Zero protected volume is represented by selecting no positive level, under
Assumption A016.

Let:

\[
z_{ka}
\]

denote tentative future flow. Future flow conservation routes exactly
\(maxvol(k)\) units through the selected forecast network.

## 24.5 Combined objective

The Phase 9 objective is:

\[
\max
\left[
f_{\tilde{k}}
Q_{\tilde{k}}
e_{\tilde{k}}
+
\sum_{k\in K(\tilde{k})}
\sum_{j=1}^{VMAX_k}
V_{kj}y_{kj}
\right],
\]

where \(V_{kj}\) is either:

1. the printed future-value expression used as the reproduction baseline; or
2. the explicitly labelled capped-value sensitivity.

Revenue from earlier accepted demands is omitted because their acceptance is
already fixed. Their unfinished volume remains mandatory through fragment
flow constraints.

## 24.6 Combined transport capacity

For every scheduled transport arc \(a\), current flow, reconstructed fragment
flow, and tentative future flow share the released rerouting capacity:

\[
v_{\tilde{k}a}
+
\sum_{d\in D(\tilde{k})}w_{da}
+
\sum_{k\in K(\tilde{k})}z_{ka}
\leq
C^{release}_{a,\tilde{k}}.
\]

The released capacity includes:

- ordinary currently bookable capacity; and
- future reservations released from eligible unfinished fragments.

It excludes:

- completed movement;
- immutable in-transit movement;
- reservations belonging to ineligible commitments.

The validator independently recalculates this inequality for every modelled
transport arc.

## 24.7 Flow conservation

The current request satisfies acceptance-scaled flow conservation.

Every unfinished fragment satisfies fixed-volume flow conservation using
\(q_d^{rem}\).

Every future forecast satisfies tentative flow conservation using
\(maxvol(k)\).

Auxiliary sinks retain the original demand's destination and deadline
semantics.

## 24.8 Persistent transition

After a solved DCA-RRM event, persistent state contains:

- reconstructed prior accepted commitments;
- the realised current acceptance decision;
- the realised current route when accepted;
- preserved booking and execution metadata.

Persistent state does not contain:

- future selectors \(y_{kj}\);
- `maxvol(k)`;
- tentative future flows \(z_{ka}\);
- expected-future objective value.

Those future-planning quantities are discarded and reconstructed at the next
booking event.

## 24.9 Reduction properties

The implementation must satisfy the following structural reductions.

### No future forecasts

When:

\[
K(\tilde{k})=\varnothing,
\]

the combined model reduces to DCA-R.

### No unfinished accepted fragments

When:

\[
D(\tilde{k})=\varnothing,
\]

the combined model reduces to DCA-RM.

### Neither fragments nor forecasts

When:

\[
D(\tilde{k})=\varnothing
\quad\text{and}\quad
K(\tilde{k})=\varnothing,
\]

the model reduces to ordinary DCA.

These reductions are enforced through controlled unit and integration tests.

## 24.10 Evaluation accounting

For each event:

\[
Objective_{\tilde{k}}
=
RealisedCurrentRevenue_{\tilde{k}}
+
ExpectedFutureContribution_{\tilde{k}}.
\]

Only realised current-request revenue is accumulated as earned revenue.

Expected-future contributions are diagnostic opportunity values. They may
overlap with revenue subsequently earned when a forecasted demand actually
arrives and therefore cannot be added to realised revenue.

## 24.11 Canonical Phase 9 finding

On the canonical seeded instance, each DCA-RRM forecast regime produces the
same:

- current acceptance sequence;
- accepted volume;
- realised revenue;
- processed-event count;
- failure event;
- final accepted-demand set;

as the corresponding DCA-RM regime.

DCA-RRM nevertheless produces a different and generally larger
expected-future objective contribution because tentative future flow is
optimised jointly with mandatory unfinished fragments.

This is an observed property of the canonical instance, not a proof that
DCA-RM and DCA-RRM are generally equivalent.

## 24.12 Phase 9 truck-disabled scope

The implemented Phase 9 combined objective is conditional on:

\[
q_k^{truck}=0
\qquad
\forall k.
\]

Consequently, the truck-penalty component mentioned in the paper's general
objective vanishes.

The Phase 9 model should therefore be interpreted as the stable-capacity,
truck-disabled DCA-RRM core. It is not yet the complete disruption-recovery
formulation.

Phase 10 introduces explicit truck recourse:

\[
q_k^{truck}\geq 0,
\]

together with actual water-adjusted capacities and a penalty proportional to
the trucked volume.

This separation prevents an unreported truck formulation from being hidden
inside the Phase 9 model.
