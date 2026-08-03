# Deterministic Current-Demand Allocation Model

## 1. Purpose

The DCA model allocates currently known demand over the available time-space
network.

It does not yet include:

- future-demand protection;
- rerouting of prior commitments;
- water-level disruptions;
- truck fallback.

## 2. Acceptance variables

For demand \(k\), let:

\[
\xi_k
\]

denote the accepted proportion.

Regular demand:

\[
\xi_k=1.
\]

Partially-spot demand:

\[
0\leq\xi_k\leq1.
\]

Fully-spot demand:

\[
\xi_k\in\{0,1\}.
\]

## 3. Flow variables

For each feasible demand-arc combination:

\[
v_{ka}\geq0.
\]

Flow variables are created only when:

\[
a\in A_k^{feasible}.
\]

They are also created for the demand-specific auxiliary delivery arcs.

## 4. Objective

The current-demand revenue objective is:

\[
\max
\sum_{k\in K}f_kq_k\xi_k.
\]

## 5. Source balance

At demand source \(s_k\):

\[
\sum_{a\in\delta_k^+(s_k)}v_{ka}
-
\sum_{a\in\delta_k^-(s_k)}v_{ka}
=
q_k\xi_k.
\]

## 6. Intermediate-node balance

At every other physical terminal-time node:

\[
\sum_{a\in\delta_k^+(n)}v_{ka}
-
\sum_{a\in\delta_k^-(n)}v_{ka}
=
0.
\]

Delivery arcs are included in the outgoing set of eligible destination-time
nodes.

## 7. Auxiliary-sink balance

For the demand-specific logical sink:

\[
\sum_{a\in\delta^-(sink_k)}v_{ka}
=
q_k\xi_k.
\]

This ensures that accepted cargo is delivered exactly once.

## 8. Transport capacity

For each scheduled transport arc:

\[
\sum_{k:a\in A_k^{feasible}}v_{ka}
\leq C_a.
\]

Holding and auxiliary delivery arcs are uncapacitated in the baseline model.

## 9. Controlled example

A ten-TEU service carries:

- four mandatory regular TEU;
- six partially-spot TEU;
- an eight-TEU fully-spot request.

The fully-spot request cannot fit after the mandatory regular request and
cannot be accepted fractionally.

The optimal decision is therefore:

\[
\xi_R=1,\qquad
\xi_P=1,\qquad
\xi_F=0.
\]

The resulting objective is:

\[
4(10)+6(20)=160.
\]

## 10. Independent solution validation

A solver status alone is not treated as sufficient evidence of correctness.

After extraction, the DCA solution is independently checked for:

- customer-category acceptance domains;
- flow nonnegativity;
- source and intermediate-node conservation;
- auxiliary-sink delivery balance;
- scheduled transport capacity;
- objective reconstruction.

The validation layer uses the assembled instance and extracted numerical
solution rather than relying on DOcplex constraint objects.

This provides an independent check of both model construction and solution
extraction.

## 11. Model export

The canonical DCA model is exported in LP format.

The LP file provides a human-readable record of:

- objective coefficients;
- variable domains;
- flow-balance equations;
- sink equations;
- capacity constraints.

It can be inspected directly during model debugging and included in the
technical reproduction archive.
