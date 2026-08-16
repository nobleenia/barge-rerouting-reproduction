# Phase 11 — Experimental Reproduction Synthesis

## 1. Scope

Phase 11 converts the paper-to-code reconstruction developed in earlier
phases into controlled computational experiments corresponding to the
publication's principal numerical studies.

The reproduced experimental layers are:

- Phase 11A — Table 4 stable-network experiments;
- Phase 11B — Table 5 standard-water DCA/PR/FR experiments;
- Phase 11C — Table 6 Partial-Reroute water-change experiments.

Reduced-water Full-Reroute and other sensitivity extensions were deliberately
not executed as part of the strict reproduction scope.

This decision prevents extension results from being confused with the
published experiment and avoids unnecessary post-hoc computation.

---

## 2. Scientific boundary

The project does not claim possession of the authors' original simulation
instance.

Important unpublished or incompletely specified inputs include:

- original generated demand sets;
- original random seeds;
- exact service schedules;
- complete fare-generation parameters;
- precise forecast sequences;
- some revenue-management distributions;
- truck-cost calibration;
- some operational transition details;
- several indicator denominators and aggregation rules;
- original implementation and solver configuration.

Therefore Phase 11 uses controlled substitute inputs whose assumptions,
seeds, fingerprints and interpretation rules are explicitly frozen.

Results are never tuned after observing the publication values.

---

## 3. Table 4 conclusion

The Table-4 work establishes the stable-network computational baseline and
the revenue-management/rerouting mechanisms required by the reproduction.

It is classified as a validated computational and behavioural reproduction
under controlled substitute inputs rather than an exact numerical
replication.

The Table-4 validation evidence is retained separately in the Phase-11A
result package.

---

## 4. Table 5 conclusion

Table 5 executes 24 standard-water policy runs:

\[
2\ {\rm service\ families}
\times
4\ {\rm capacities}
\times
3\ {\rm policies}.
\]

DCA, Partial-Reroute and Full-Reroute are evaluated on one frozen
800-request, 1076-TEU realised demand set.

The experiment reproduces the central qualitative mechanism that rerouting
flexibility is most valuable under capacity scarcity.

Full-Reroute produces substantial additional accepted demand in scarce
settings but incurs very high computational cost.

Important discrepancies include:

- earlier saturation of the controlled network;
- zero PR truck use throughout standard-water Table 5;
- PR not universally dominating DCA;
- different FR truck-use profiles;
- substantial absolute AFR differences;
- material dependence on A036;
- unresolved publication indicator definitions.

Exact numerical Table-5 replication is therefore unsuccessful.

---

## 5. Table 6 conclusion

Table 6 evaluates PR under water factors:

\[
1.0,\ 0.9,\ 0.8,\ 0.7.
\]

Eight standard-water rows are reused from Table 5 and 24 new reduced-water
runs are executed.

The reduced-water experiment validates:

\[
C^{actual}
=
\lambda C^{nominal}
\]

and independently verifies:

\[
NFR=\lambda AFR
\]

under the controlled uniform-factor reconstruction.

Lower water generally transfers cargo from barge to truck in constrained
cells while actual capacity utilization increases.

The controlled Service-Family-2 network remains substantially less scarce
than the published experiment, reaching complete-demand saturation at
medium and high nominal capacities even under reduced water.

Exact numerical Table-6 replication is therefore unsuccessful.

---

## 6. Cross-experiment findings

Across the Phase-11 experiments, several robust controlled findings emerge.

### Capacity scarcity determines the value of flexibility

Advanced rerouting mechanisms have their strongest economic and operational
effect when barge capacity is scarce.

As capacity becomes abundant, the marginal accepted-volume benefit shrinks
or disappears.

### Flexibility is computationally expensive

DCA is comparatively inexpensive.

PR introduces repeated recovery/reoptimisation at forecast epochs.

FR is substantially more expensive because it reroutes at every incoming
booking.

The controlled Table-5 campaign alone required approximately:

- 0.074 h DCA;
- 12.112 h PR;
- 34.013 h FR.

The additional reduced-water Table-6 PR campaign required approximately:

- 36.115 h.

Thus operational flexibility has a clearly measurable computational cost.

### Reduced water changes both capacity and allocation

As the water factor declines, actual capacity decreases proportionally.

In constrained cells, PR uses truck recourse to preserve accepted cargo.

In sufficiently unconstrained cells, reduced water may increase utilization
without causing truck use or lost acceptance.

### Network structure matters

The two controlled service families behave differently even though they use
the same realised demand set.

Service Family 2 reaches demand saturation much earlier than Service Family
1.

This demonstrates that policy performance cannot be interpreted from nominal
capacity alone; connectivity, schedule structure, timing and alternative
routing opportunities matter.

---

## 7. Important source discrepancies retained

The reproduction deliberately preserves publication and interpretation
problems rather than silently correcting them.

Examples include:

- Table 5 AFR value `855`;
- Table 6 Service-1 / capacity-40 / water-0.9 NFR value `8`;
- unresolved AFR/NFR aggregation details;
- unresolved volume-indicator denominators;
- unresolved TR accounting;
- unresolved original forecast sequence;
- unresolved behaviour corresponding to controlled continuation A036.

These issues form part of the reproducibility assessment.

---

## 8. Validation philosophy

Solver completion is not treated as sufficient evidence of correctness.

The reproduction independently validates, where applicable:

- solver status;
- booking/status-event completion;
- configuration fingerprints;
- demand fingerprints;
- flow and volume conservation;
- actual-capacity feasibility;
- accepted-volume decomposition;
- truck accounting;
- revenue accounting;
- reporting-ledger consistency;
- AFR/NFR reconstruction;
- deterministic scenario coverage;
- persisted raw/prevalidation evidence;
- SHA-256 evidence manifests.

Expensive production results are persisted before moving to subsequent runs.

---

## 9. Overall Phase-11 classification

Phase 11 achieves:

- conceptual reproduction;
- mathematical implementation;
- computational reproduction;
- controlled behavioural reproduction of the principal mechanisms.

It does not achieve exact numerical reproduction of the publication tables.

The overall scientific classification is therefore:

**validated computational and behavioural reproduction of the published
mechanisms using controlled substitute inputs, with unsuccessful exact
numerical replication of the reported experimental values.**

This is a scientifically meaningful reproduction outcome.

Failure to reproduce exact values is not hidden and is not repaired by
parameter tuning.

---

## 10. Experimental reproduction boundary

The strict reproduction campaign ends with Table 6.

The following remain optional extensions rather than requirements:

- Full-Reroute under reduced water;
- DCA under reduced water;
- complete policy x water-factor factorial experiments;
- alternative truck penalties;
- alternative forecast intervals;
- stochastic water trajectories;
- additional demand realisations;
- broader sensitivity analysis.

They are intentionally excluded from the completed Phase-11 reproduction.

---

## 11. Phase-11 completion

With Tables 4, 5 and 6 validated and documented, the Phase-11 experimental
reproduction is complete.

No further long-running optimisation campaign is required for the strict
paper reproduction.

Subsequent project work should focus on:

- final interpretation;
- presentation preparation;
- technical-interview defence;
- limitations and future-work positioning;
- optional extensions only where they add clear scientific value.
