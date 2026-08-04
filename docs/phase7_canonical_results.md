# Phase 7 Canonical Full-Reroute Evaluation

This report compares the operational Full-Reroute implementation under Assumption A003 with the time-aware sequential DCA baseline.

It does not yet include the paper's future-demand revenue-management component.

## Aggregate results

- Instance fingerprint: `8a4b689e039dab9337ea335a62d79c57abe1ace9dfb48d431154eb9aca72abfc`
- Total booking events: 20
- Ordinary run completed: False
- Full-Reroute run completed: False
- Ordinary processed events: 8
- Full-Reroute processed events: 11
- Ordinary accepted volume: 26.0000
- Full-Reroute accepted volume: 31.0000
- Accepted-volume delta: 5.0000
- Ordinary revenue: 823.9000
- Full-Reroute revenue: 978.9100
- Revenue delta: 155.0100
- Paired acceptance-improvement events: 0
- Ordinary failure recovered by Full-Reroute: True
- Additional processed events: 3
- Failure-sequence shift: 3
- Common-prefix ordinary revenue: 823.9000
- Common-prefix Full-Reroute revenue: 823.9000
- Common-prefix revenue delta: 0.0000
- Common-prefix accepted-volume delta: 0.0000
- Continuation revenue after ordinary failure: 155.0100
- Continuation volume after ordinary failure: 5.0000
- Events reoptimising prior commitments: 10
- Ordinary failure event: booking::0009::K0011
- Full-Reroute failure event: booking::0012::K0017

## Comparison interpretation

The aggregate revenue and volume deltas are continuation gains after the ordinary baseline terminates. They are not paired improvements across all twenty booking events.

On the common solved prefix, both mechanisms produce the same acceptance, accepted volume, and revenue. Full-Reroute then recovers the ordinary failure event and continues until its own later mandatory-demand infeasibility.

The listed prior commitments were included in joint reoptimisation. Their inclusion does not by itself prove that every physical route changed.

## Event-level comparison

| Seq. | Event | Time | Demand | Category | Volume | Ordinary acceptance | Full-Reroute acceptance | Ordinary revenue | Full-Reroute revenue | Prior commitments reoptimised | Released services |
|---:|---|---:|---|---|---:|---:|---:|---:|---:|---|---|
| 1 | booking::0001::K0001 | 0 | K0001 | P | 1.0000 | 1.0000 | 1.0000 | 27.9200 | 27.9200 | — | — |
| 2 | booking::0002::K0003 | 0 | K0003 | P | 6.0000 | 1.0000 | 1.0000 | 144.1800 | 144.1800 | K0001 | S6 |
| 3 | booking::0003::K0004 | 0 | K0004 | F | 3.0000 | 1.0000 | 1.0000 | 118.0800 | 118.0800 | K0001, K0003 | S5, S6 |
| 4 | booking::0004::K0005 | 0 | K0005 | P | 8.0000 | 0.3750 | 0.3750 | 89.0700 | 89.0700 | K0001, K0003, K0004 | S1, S5, S6 |
| 5 | booking::0005::K0006 | 0 | K0006 | P | 5.0000 | 1.0000 | 1.0000 | 109.7500 | 109.7500 | K0001, K0003, K0004, K0005 | S1, S5, S6 |
| 6 | booking::0006::K0007 | 0 | K0007 | R | 3.0000 | 1.0000 | 1.0000 | 140.9100 | 140.9100 | K0001, K0003, K0004, K0005, K0006 | S1, S2, S5, S6 |
| 7 | booking::0007::K0009 | 0 | K0009 | R | 3.0000 | 1.0000 | 1.0000 | 126.1500 | 126.1500 | K0001, K0003, K0004, K0005, K0006, K0007 | S1, S2, S5, S6 |
| 8 | booking::0008::K0010 | 0 | K0010 | F | 2.0000 | 1.0000 | 1.0000 | 67.8400 | 67.8400 | K0001, K0003, K0004, K0005, K0006, K0007, K0009 | S1, S2, S3, S4, S5, S6 |
| 9 | booking::0009::K0011 | 0 | K0011 | R | 2.0000 | — | 1.0000 | — | 67.4200 | K0001, K0003, K0004, K0005, K0006, K0007, K0009, K0010 | S1, S2, S3, S4, S5, S6 |
| 10 | booking::0010::K0012 | 0 | K0012 | P | 4.0000 | — | 0.2500 | — | 42.1900 | K0001, K0003, K0004, K0005, K0006, K0007, K0009, K0010, K0011 | S1, S2, S3, S4, S5, S6 |
| 11 | booking::0011::K0016 | 0 | K0016 | P | 2.0000 | — | 1.0000 | — | 45.4000 | K0001, K0003, K0004, K0005, K0006, K0007, K0009, K0010, K0011, K0012 | S1, S2, S3, S4, S5, S6 |
| 12 | booking::0012::K0017 | 0 | K0017 | R | 6.0000 | — | — | — | — | — | S1, S2, S3, S4, S5, S6 |
| 13 | booking::0013::K0019 | 0 | K0019 | F | 5.0000 | — | — | — | — | — | — |
| 14 | booking::0014::K0002 | 1 | K0002 | P | 5.0000 | — | — | — | — | — | — |
| 15 | booking::0015::K0008 | 1 | K0008 | F | 8.0000 | — | — | — | — | — | — |
| 16 | booking::0016::K0013 | 1 | K0013 | R | 5.0000 | — | — | — | — | — | — |
| 17 | booking::0017::K0014 | 1 | K0014 | F | 4.0000 | — | — | — | — | — | — |
| 18 | booking::0018::K0015 | 1 | K0015 | F | 1.0000 | — | — | — | — | — | — |
| 19 | booking::0019::K0018 | 1 | K0018 | F | 7.0000 | — | — | — | — | — | — |
| 20 | booking::0020::K0020 | 1 | K0020 | R | 1.0000 | — | — | — | — | — | — |

## Interpretation boundary

The fragment source is the cargo's execution-aware terminal-time position. Completed and in-transit movements remain immutable, while only future bookable reservations are released and reoptimised.

This is the disclosed operational interpretation in Assumption A003 and should not be presented as a verbatim implementation of printed Equation (5).
