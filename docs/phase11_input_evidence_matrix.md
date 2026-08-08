# Phase 11 Experimental Input Evidence Matrix

| Input | 2024 paper status | Numerical value available? | Phase 11 treatment |
|---|---|---:|---|
| Terminals | Explicit | Yes: A--E | Reproduce |
| Adjacent travel equality | Explicit | Structural only | Reproduce; duration under A028 |
| Time unit | Explicit | Half-day | Reproduce |
| Weekly period | Explicit | 14 periods | Reproduce |
| Service Family 1 frequency | Explicit | 2 services, both directions | Reproduce structure |
| Service Family 2 frequency | Explicit | 4 services, both directions | Reproduce structure |
| Exact departure offsets | Not disclosed | No | A028 controlled substitute |
| Table 4 capacities | Explicit | 10, 15, 20 TEU | Reproduce |
| Demand density | Explicit | 10 per half-day | Reproduce structurally |
| OD sampling | Explicit | Uniform | Reproduce |
| Customer categories | Explicit | Uniform R/P/F | Reproduce |
| Volume support | Explicit | 0..VMAX | Reproduce structure |
| Common experimental VMAX | Explicit structurally | No numerical value | A031 unresolved |
| Volume probability mass | Explicit structurally | No | A031 unresolved |
| Timing pools | Explicit structurally | No | A029/A031 unresolved |
| Timing thresholds | Explicit structurally | No | A031 unresolved |
| Fare equation | Explicit | `p * r_ant * r_del` | Reproduce |
| Early-reservation rate | Explicit | 1 | Reproduce |
| Standard-delivery rate | Explicit | 1 | Reproduce |
| Late-reservation rate | Explicit inequality | >1 only | A031 unresolved |
| Express-delivery rate | Explicit inequality | >1 only | A031 unresolved |
| Base fares | Explicit structurally | No | A031 unresolved |
| Random seeds | Not disclosed | No | Controlled fixed seeds |
| Horizon | Explicit but ambiguous | 400/800 instants | A030 unresolved mapping |
| Table 4 demand sets | Explicit | 5 sets | Reproduce |
| Table 4 mechanisms | Explicit | 4 | Reproduce |
| Table 4 instances | Explicit | 120 | Reproduce |
| Table 4 truck use | Explicit boundary | Disabled | Reproduce |
| Forecasts at simulation start | Explicit | Structural | Reproduce |
| Exact forecast construction | Not disclosed | No | Separate controlled input |
| Exact K(current) construction | Not disclosed | No | Existing A004/A020 |
