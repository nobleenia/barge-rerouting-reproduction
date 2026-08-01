# Graph and Network Foundations

## 1. Graph

A graph is a mathematical structure consisting of nodes and connections.

\[
G=(N,A)
\]

where:

- \(N\) is the set of nodes or vertices;
- \(A\) is the set of directed arcs.

## 2. Node

A node represents an entity or state.

In the physical barge network, a node represents a terminal:

\[
N^P=\{A,B,C,D,E\}.
\]

Later, in the time-space network, a node will represent a terminal at a
specific time:

\[
n(i,t).
\]

Therefore:

- \(A\) is a physical terminal;
- \(n(A,4)\) is terminal \(A\) at time period 4.

## 3. Edge versus arc

An edge is normally undirected:

\[
\{A,B\}.
\]

It means that \(A\) and \(B\) are connected without specifying direction.

An arc is directed:

\[
(A,B).
\]

It represents movement from \(A\) to \(B\).

The reverse movement requires a separate arc:

\[
(B,A).
\]

The barge network is represented as a directed graph because services have
specific travel directions and schedules.

## 4. Tail and head

For arc:

\[
a=(i,j),
\]

\(i\) is the tail and \(j\) is the head.

The arc leaves \(i\) and enters \(j\).

## 5. Path

A directed path is a sequence of compatible arcs.

For example:

\[
A\rightarrow B\rightarrow C\rightarrow D
\]

is a path from \(A\) to \(D\).

The head of each arc must equal the tail of the next arc.

## 6. Cycle

A cycle is a path that returns to its starting node:

\[
A\rightarrow B\rightarrow C\rightarrow A.
\]

A physical bidirectional network may contain cycles.

A finite forward-moving time-space network is normally acyclic because time
cannot move backwards.

## 7. Source and destination

For a demand:

- the origin is its source;
- the destination is its sink.

Flow is introduced at the source and removed at the sink.

## 8. Incoming and outgoing arcs

For node \(n\):

\[
A^+(n)
\]

is the set of outgoing arcs, and:

\[
A^-(n)
\]

is the set of incoming arcs.

Flow conservation at an intermediate node requires:

\[
\sum_{a\in A^-(n)}v_a
=
\sum_{a\in A^+(n)}v_a.
\]

## 9. Capacity

An arc capacity limits the total flow that may use the arc:

\[
\sum_k v_{ka}\leq C_a.
\]

In the barge model, transport arcs represent service legs and \(C_a\)
represents available vessel capacity on that leg.

## 10. Multi-commodity flow

Each demand is a separate commodity.

Demand \(k\) has its own flow:

\[
v_{ka}.
\]

Different commodities are coupled because they share service capacity:

\[
\sum_k v_{ka}\leq C_a.
\]

This is why the problem is not simply a collection of independent shortest
paths.

## 11. Physical versus time-space network

The physical network answers:

> Which terminals are geographically connected?

The time-space network answers:

> Which scheduled movement or waiting opportunities are available at each
> particular time?

A physical terminal may therefore appear many times in the time-space graph:

\[
n(A,0),n(A,1),n(A,2),\ldots
\]

## 12. NetworkX

NetworkX is the Python library used to construct, inspect, and visualise graph
structures.

CPLEX will later optimise decisions over the resulting network.

NetworkX represents the network; CPLEX solves the mathematical optimisation
problem built on that network.

## 13. Time-space network

A time-space network expands each physical terminal across time.

If \(I\) is the set of physical terminals and \(\mathcal{T}\) is the set of
time periods, then the time-space node set is:

\[
N^{IT}=\{n(i,t): i\in I,\ t\in\mathcal{T}\}.
\]

A node \(n(i,t)\) means:

> terminal \(i\) at time \(t\).

Thus, one physical terminal appears many times in the time-space graph.

## 14. Holding arc

A holding arc allows cargo to stay at the same terminal and move forward in time:

\[
(n(i,t),n(i,t+1)).
\]

Holding arcs represent waiting, storage, or postponement.

## 15. Transport arc

A transport arc represents a scheduled service movement:

\[
(n(i,t),n(j,t')),\qquad t' > t.
\]

It connects the departure terminal-time node to the arrival terminal-time node.

## 16. Acyclicity

If every arc moves strictly forward in time, then the time-space graph is a
directed acyclic graph over a finite horizon.

This is important because:

- a cargo cannot move backward in time;
- a path is automatically time-feasible if every selected arc goes forward;
- infeasible loops are naturally avoided.

## 17. Path feasibility in time-space networks

A path is feasible only if:

1. the arcs connect properly;
2. time always increases;
3. any transport arc matches a scheduled service;
4. the destination is reached by the required deadline.

## 18. Why time-space networks are necessary here

The physical graph only tells us that terminal \(A\) is connected to terminal
\(B\).

The time-space graph tells us whether a demand can go from \(A\) to \(B\)
at the right time, and whether it can continue to another terminal or must
wait using a holding arc.

That is why the optimisation model is built on the time-space network rather
than only the physical network.

## 19. Directed multigraph

A directed multigraph permits more than one directed arc between the same pair
of nodes.

This is necessary when two scheduled services both travel from:

\[
n(A,0)
\]

to:

\[
n(B,1).
\]

Although their tail and head nodes are identical, they may have different:

- service identifiers;
- capacities;
- costs;
- operational statuses.

A simple directed graph would overwrite one arc. A directed multigraph
preserves both.

## 20. Demand-specific pruning

For a demand source \(s_k\) and acceptable destination-time nodes
\(N_k^{dest}\), a node is potentially useful only if it is:

1. reachable from \(s_k\); and
2. capable of reaching at least one node in \(N_k^{dest}\).

Therefore, the retained set is:

\[
N_k^{feasible}
=
ReachableFrom(s_k)
\cap
CanReach(N_k^{dest}).
\]

Pruning reduces unnecessary flow variables and flow-conservation constraints
before the CPLEX model is built.
