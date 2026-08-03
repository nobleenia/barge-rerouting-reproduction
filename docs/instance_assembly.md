# Optimisation Instance Assembly

## 1. Purpose

The assembly layer combines validated configuration, network, arc, and demand
objects into one canonical optimisation instance.

All policy models must receive the same instance when their performance is
compared.

## 2. Canonical experiment instance

An `ExperimentInstance` contains:

- validated experiment configuration;
- complete time-space multigraph;
- global solver-ready arc collection;
- realised demand collection;
- demand-instance fingerprint;
- one feasible-network index per demand.

The instance is the boundary between data preparation and mathematical-model
construction.

## 3. Demand-specific feasible arc set

For each demand \(k\), the assembly process constructs:

\[
A_k^{feasible}\subseteq A.
\]

Only arcs belonging to a path from the demand source to an eligible
destination-time node are retained.

A future flow variable is therefore required only when:

\[
a\in A_k^{feasible}.
\]

## 4. Node flow indexes

For every feasible node \(n\), the assembly process records:

\[
\delta_k^-(n)
=
\{a\in A_k^{feasible}: head(a)=n\},
\]

and:

\[
\delta_k^+(n)
=
\{a\in A_k^{feasible}: tail(a)=n\}.
\]

These indexes will be used directly in flow-conservation constraints.

## 5. Flow conservation

For an intermediate node:

\[
\sum_{a\in\delta_k^+(n)}v_{ka}
-
\sum_{a\in\delta_k^-(n)}v_{ka}
=
0.
\]

The source and destination balances will be connected to the demand acceptance
decision in the optimisation-model layer.

## 6. Why indexes are prepared before CPLEX

Preparing indexes in advance:

- avoids repeated graph traversal during model construction;
- ensures every policy uses identical feasible arc sets;
- reduces flow-variable and constraint counts;
- provides deterministic variable indexing;
- makes model-validation tests easier.

## 7. Frozen graph

After assembly, the NetworkX graph is frozen.

This prevents accidental addition or removal of nodes and arcs after:

- global arc objects have been extracted;
- demand-specific feasible networks have been constructed;
- flow indexes have been prepared.

Changing the graph after that point would invalidate the prepared indexes.

## 8. Destination handling

A demand may reach its destination at any permitted time no later than its due
time.

The current assembly layer retains all eligible destination-time nodes.

Before the first CPLEX model is built, these nodes will be connected to a
demand-specific auxiliary sink so that delivery can occur at any eligible
arrival time without duplicating demand volume.
