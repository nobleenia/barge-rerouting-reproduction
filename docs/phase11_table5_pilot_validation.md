# Phase 11 Table 5 Pilot Validation

## 1. Scope

This document closes Phase 11B4c: full-horizon pilot execution for the frozen Table 5 demand instance.

The three policies are evaluated on the same 800-demand realisation.

The successful pilot policies are:

- DCA: 800 bookings;
- Partial-Reroute (PR): 800 bookings and 20 forecast updates;
- Full-Reroute (FR): 800 bookings with rerouting at each incoming request.

The pilots are computational validation runs under controlled reproduction assumptions.
They are not claimed to be exact numerical replication of the paper.

## 2. Frozen demand identity

`9987096abb4c217cd2dca3c307599e4d231c47a2e02c416a6b0ee28128626944`

All three successful policies use this same demand fingerprint.

## 3. Successful pilot results

| Policy | Completed | Accepted TEU | Revenue | Truck TEU | Truck penalty | Net value | Solver failures | Runtime s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DCA | True | 447.000000000 | 103237.500000000 | 0.000000000 | 0.000000000 | 103237.500000000 | 0 | 27.949841 |
| PR | True | 453.000000000 | 103443.750000000 | 0.000000000 | 0.000000000 | 103443.750000000 | 0 | 1956.534218 |
| FR | True | 818.980183373 | 206987.189352599 | 439.957580865 | 89093.231859798 | 117893.957492801 | 0 | 11419.597360 |

## 4. Raw-result integrity

| Policy | File | SHA-256 | Git commit recorded by run |
|---|---|---|---|
| DCA | `results/phase11/table5/pilot/dca_800.json` | `2d7039d2a7c5cc6e275842aac6ce9a00c52be645a6fefd79135a41b52fc17429` | `c1d449c0f0e8feedcdc68656755d568f5232ea56` |
| PR | `results/phase11/table5/pilot/pr_800.json` | `f8b8f013fc5ca4be05dbe9ebde92ac0ba9bfe20d32a541843141d2f4f8dd9d2e` | `c1d449c0f0e8feedcdc68656755d568f5232ea56` |
| FR | `results/phase11/table5/pilot/fr_800.json` | `cb493c3b62cbcac3e8e3c1b39ae8597a80057b2634e5e35abded45ed4fce9695` | `3d99bf8fae155a176cb8e9c09f129605cfa00fb3` |

## 5. Full-Reroute full-horizon validation

The final FR pilot processed all 800 booking events with zero solver failures.

The final FR trajectory passed the previously observed failure regions associated with:

- recovery-lineage accounting;
- pending truck commitments;
- HiGHS long variable-name round-tripping;
- solver-scale accepted-volume residuals;
- recovered-flow path decomposition;
- mass preservation when numerical recovery dust is terminalised.

The successful FR run therefore provides full-horizon computational validation of the Phase-11 operational execution machinery on the frozen pilot instance.

It does not establish exact numerical replication of Table 5.

## 6. Failed FR runs retained as diagnostic evidence

- `results/phase11/table5/pilot/fr_800_failure_booking414.json`
- `results/phase11/table5/pilot/fr_800_failure_booking417.json`
- `results/phase11/table5/pilot/fr_800_failure_booking426_after_decomposition_cleanup.json`
- `results/phase11/table5/pilot/fr_800_failure_booking428_diagnostic.json`
- `results/phase11/table5/pilot/fr_800_failure_booking428_undecomposed.json`

These failed trajectories are retained because they document the numerical and state-consistency problems exposed only by long-horizon repeated Full-Reroute execution.

## 7. Phase boundary

Phase 11B4c is closed. The next task is Phase 11B5: reconstruct, define, implement, and validate the Table 5 performance indicators.
