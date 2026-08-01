# Phase 0 Validation

## Purpose

Phase 0 verifies that the repository, Python environment, DOcplex modelling layer,
and local CPLEX solver are working correctly before the transportation model is built.

## Validation model

The test model is:

\[
\max 3x + 2y
\]

subject to:

\[
x + y \leq 4
\]

\[
x, y \geq 0
\]

Because one unit of \(x\) contributes more than one unit of \(y\), the analytically
known optimum is:

\[
x^* = 4,\qquad y^* = 0,\qquad z^* = 12.
\]

## CPLEX result

The implemented DOcplex model returned:

- status: optimal;
- \(x=4\);
- \(y=0\);
- objective value \(=12\).

The exported LP formulation was:

```text
Maximize
 obj: 3 x + 2 y
Subject To
 shared_capacity: x + y <= 4
Bounds
End
```

## Automated validation

The pytest test confirms:

- the model solves to optimality;
- the returned variable values match the analytical solution;
- the objective value is correct;
- the LP export is created;
- the solver log is created;

## Environmentdifference from the paper

The source paper reports Python 3.8 and CPLEX 22.1.1.

This reproduction currently uses:

- Python 3.12.3;
- CPLEX API/engine 22.2.0.0;
- CPLEX Python package 22.2.0.1;
- DOcplex 2.32.264.

This difference is documented and will be considered when interpreting numerical or computational time differences