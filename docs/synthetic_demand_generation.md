# Synthetic Demand Generation

## 1. Reproducibility objective

Synthetic instances are deterministic functions of:

\[
(\text{configuration},\text{random seed}).
\]

The same configuration and seed must reproduce the same:

- demand identifiers;
- customer categories;
- volumes;
- fares;
- origins and destinations;
- reservation times;
- availability times;
- due times.

## 2. Feasible demand templates

The generator first enumerates candidate combinations of:

\[
(o_k,d_k,t_k^{res},t_k^{avl},t_k^{due}).
\]

A candidate is retained only when the time-space network contains a path from:

\[
(o_k,t_k^{avl})
\]

to the destination no later than:

\[
t_k^{due}.
\]

This prevents structurally infeasible requests from entering the baseline
synthetic instance.

## 3. Random seed

The generator uses a local deterministic random-number generator.

It does not use global random state.

Therefore, other code calling Python's random module does not alter the
generated instance.

## 4. Sampling order

For each demand, the generator samples in this order:

1. feasible OD and timing template;
2. requested volume;
3. fare per TEU;
4. customer category.

Changing this order changes the generated sequence, even with the same seed.
The implementation order is therefore part of the reproduction protocol.

## 5. Instance fingerprint

The generated demand records are serialised deterministically and hashed using
SHA-256.

The fingerprint provides a concise identity for the complete generated
instance.

Two experiments claiming to use the same demand instance should report the
same fingerprint.

## 6. Comparison across policies

DCA, DCA-R, DCA-RM, and DCA-RRM must use the same generated demand instance
when compared in one experiment.

The random seed must not be reset differently for each policy.

Otherwise, policy effects would be confounded with differences in the sampled
demand data.

## 7. Relationship to the paper

The exact empirical demand-generation parameters used by the paper have not
yet been fully recovered from the available description.

The current generator is therefore a transparent deterministic synthetic
baseline.

Paper-specific parameter values will replace or extend the toy configuration
when they become available.
