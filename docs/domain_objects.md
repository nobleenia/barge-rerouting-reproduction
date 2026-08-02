# Domain Objects

## 1. Purpose

Domain objects represent validated transportation data before an optimisation
model is constructed.

They prevent malformed requests from reaching the CPLEX formulation.

## 2. Demand input parameters

Each demand contains:

\[
q_k,o_k,d_k,t_k^{res},t_k^{avl},t_k^{due},c_k,f_k.
\]

The Python `Demand` object maps these parameters as follows:

| Mathematical symbol | Python field | Meaning |
|---|---|---|
| \(k\) | `demand_id` | Unique demand identifier |
| \(q_k\) | `volume` | Requested TEU |
| \(o_k\) | `origin` | Physical origin |
| \(d_k\) | `destination` | Physical destination |
| \(t_k^{res}\) | `reservation_time` | Booking time |
| \(t_k^{avl}\) | `availability_time` | Cargo availability |
| \(t_k^{due}\) | `due_time` | Latest arrival |
| \(c_k\) | `category` | Customer category |
| \(f_k\) | `fare_per_teu` | Revenue per accepted TEU |

## 3. Customer categories

### Regular customer

\[
c_k=R
\]

Acceptance is fixed:

\[
\xi_k=1.
\]

### Partially-spot customer

\[
c_k=P
\]

Acceptance is continuous:

\[
0\leq\xi_k\leq1.
\]

### Fully-spot customer

\[
c_k=F
\]

Acceptance is binary:

\[
\xi_k\in\{0,1\}.
\]

## 4. Input parameters versus decision variables

The `Demand` object stores the customer's request.

It does not store the acceptance decision \(\xi_k\), because acceptance is
created later as a DOcplex decision variable.

This separation distinguishes:

- immutable input data;
- optimisation decisions;
- rolling-horizon system state;
- final solution results.

## 5. Immutability

`Demand` is implemented as a frozen dataclass.

Once a request has been validated, its original attributes cannot be changed
accidentally.

Later operational developments, such as accepted volume, routing, execution,
and remaining fragments, will be represented by separate objects.

## 6. Validation rules

A valid realised demand requires:

\[
q_k>0,
\]

\[
t_k^{res}\leq t_k^{avl}\leq t_k^{due},
\]

\[
o_k\neq d_k,
\]

and:

\[
f_k\geq0.
\]

Identifiers and terminal names must be nonempty.

Numerical values must be finite.

A future probability distribution may include zero realised volume, but that
will be represented by a future-demand forecast object rather than a realised
`Demand` with zero volume.

## 7. Scheduled transport legs

A `ScheduledTransportLeg` represents input supplied to the time-space-network
builder.

It contains:

- service identifier;
- physical origin and destination;
- departure and arrival times;
- nominal capacity;
- direction.

It provides the terminal-time endpoints:

\[
tail(a)=(o_a,t_a^{dep})
\]

and:

\[
head(a)=(d_a,t_a^{arr}).
\]

## 8. Solver-ready time-space arcs

NetworkX stores edge information in flexible dictionaries.

Before optimisation, each edge is converted to an immutable `TimeSpaceArc`
containing:

- unique `arc_id`;
- tail node;
- head node;
- arc type;
- nominal capacity;
- service identifier;
- direction.

This provides a stable index for future flow variables:

\[
v_{ka}.
\]

## 9. Holding and transport arcs

A holding arc:

- remains at the same physical terminal;
- moves forward in time;
- has no service identifier;
- is not capacity-constrained in the baseline model.

A transport arc:

- connects different terminals;
- moves forward in time;
- belongs to a scheduled service;
- has nominal capacity.

## 10. Why graph edges are not used directly by CPLEX

NetworkX is designed for graph construction, reachability, traversal, and
visualisation.

The optimisation model instead needs:

- deterministic identifiers;
- immutable typed values;
- direct dictionaries for variable indexing;
- explicit capacity and arc-type validation.

The project therefore converts graph edges into solver-ready domain objects
before creating the CPLEX model.

## 11. Accepted-demand state

The original `Demand` object remains unchanged after the booking decision.

A separate `AcceptedDemandState` records the operational commitment:

- accepted fraction;
- accepted volume;
- unfinished cargo fragments;
- volume delivered by barge;
- volume delivered by truck.

The accounting identity is:

\[
Q_k^{accepted}
=
Q_k^{remaining}
+
Q_k^{barge-delivered}
+
Q_k^{truck-delivered}.
\]

## 12. Demand fragments

A `DemandFragment` represents one unfinished portion of accepted cargo.

It contains:

- fragment identifier;
- original demand identifier;
- remaining fragment volume;
- current terminal-time node;
- executed arc history.

If an accepted demand is split, it may have several fragments at different
terminal-time positions.

## 13. Executed versus planned arcs

`executed_arc_ids` records movements that have already occurred.

Those arcs are historical and irreversible.

Future planned arcs are not stored as executed history. They will be stored
separately in rolling-horizon solution state and may be modified during
rerouting.

## 14. Immutable movement

Calling `move_along(arc)` does not modify the existing fragment.

It creates a new fragment at the arc head and appends the arc identifier to the
executed history.

This provides an auditable state-transition history.

## 15. Future-demand forecasts

A `FutureDemandForecast` represents a future demand class whose exact realised
volume is unknown.

The random volume is represented by a discrete probability distribution:

\[
P_k(x)=P(X_k=x).
\]

Unlike a realised `Demand`, a future forecast may contain:

\[
x=0,
\]

because no future request may materialise.

The distribution must satisfy:

\[
P_k(x)\geq0
\]

and:

\[
\sum_xP_k(x)=1.
\]

## 16. Candidate protection levels

For maximum future volume:

\[
\operatorname{maxvol}_k,
\]

the candidate protection levels are:

\[
j\in\{0,\ldots,\operatorname{maxvol}_k\}.
\]

These levels will later be associated with selector variables:

\[
y_{kj}.
\]

## 17. Printed future-value expression

The paper prints the expression:

\[
\sum_{x=0}^{j}xP_k(x).
\]

The implementation exposes this as:

`paper_prefix_expected_volume(j)`.

Outcomes above \(j\) contribute zero to that expression.

## 18. Capped expected volume

A common alternative interpretation is:

\[
E[\min(X_k,j)].
\]

This is exposed separately as:

`expected_capped_volume(j)`.

The two expressions are generally not equal when:

\[
j<\operatorname{maxvol}_k.
\]

They are deliberately kept separate so that the baseline reproduction can
follow the printed formulation while a sensitivity experiment can test the
capped interpretation.
