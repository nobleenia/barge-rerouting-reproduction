# Phase 8 Canonical Synthetic DCA-RM Evaluation

## Scientific status

This is a deterministic mechanism and sensitivity evaluation using an attribute-conditioned synthetic forecast regime.

The forecast provider uses the origin, destination, availability time, deadline, customer category, and fare of later timeline requests, but deliberately replaces their realised volumes with a configured probability distribution.

Because the paper does not report the complete forecast generation parameters, probability distributions, seeds, or exact construction of the future-demand set, these results are not an exact numerical reproduction of the paper's experimental tables.

Future-set membership follows the disclosed operational interpretation in Assumption A004. The printed expected-revenue expression is the baseline under Assumption A005; the capped expectation is reported as a sensitivity.

Zero protected volume is represented by setting all positive-level selectors to zero, as documented in Assumption A016.

Realised revenue is the primary financial result. Summed optimisation objectives and expected future contributions are diagnostic quantities and must not be interpreted as earned revenue.

## Evaluation configuration

- Instance fingerprint: `8a4b689e039dab9337ea335a62d79c57abe1ace9dfb48d431154eb9aca72abfc`
- Booking events: 20
- Maximum synthetic forecast volume: 8
- Look-ahead periods: —
- Forecast volume distribution: zero-inflated uniform over positive volumes

## Policy summary

| Policy | Mechanism | Interpretation | Probability | Completed | Processed | Accepted volume | Realised revenue | Objective sum | Expected-future sum | Forecast candidates | Positive protections | Protected volume | Failure event |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Sequential DCA | DCA | — | — | False | 8 | 26.0000 | 823.9000 | 823.9000 | 0.0000 | 0 | 0 | 0.0000 | booking::0009::K0011 |
| DCA-RM printed p=0.20 | DCA-RM | printed | 0.2000 | False | 11 | 31.0000 | 978.9100 | 1437.9418 | 459.0318 | 42 | 19 | 113.0000 | booking::0012::K0017 |
| DCA-RM printed p=0.50 | DCA-RM | printed | 0.5000 | False | 11 | 28.0000 | 913.0600 | 2354.3725 | 1441.3125 | 42 | 20 | 131.0000 | booking::0012::K0017 |
| DCA-RM printed p=0.80 | DCA-RM | printed | 0.8000 | False | 15 | 36.0000 | 1324.8600 | 3835.1490 | 2510.2890 | 56 | 24 | 145.0000 | booking::0016::K0013 |
| DCA-RM capped p=0.20 | DCA-RM | capped | 0.2000 | False | 11 | 31.0000 | 978.9100 | 1634.2280 | 655.3180 | 42 | 29 | 113.0000 | booking::0012::K0017 |
| DCA-RM capped p=0.50 | DCA-RM | capped | 0.5000 | False | 11 | 31.0000 | 978.9100 | 2617.2050 | 1638.2950 | 42 | 29 | 113.0000 | booking::0012::K0017 |
| DCA-RM capped p=0.80 | DCA-RM | capped | 0.8000 | False | 11 | 29.0000 | 935.0100 | 3785.4900 | 2850.4800 | 42 | 30 | 125.0000 | booking::0012::K0017 |

## Comparison with sequential DCA

| Policy | Processed-event delta | Volume delta | Realised-revenue delta | Common-prefix volume delta | Common-prefix revenue delta | Continuation volume | Continuation revenue | Paired acceptance gains |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Sequential DCA | +0 | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0.0000 | 0 |
| DCA-RM printed p=0.20 | +3 | +5.0000 | +155.0100 | +0.0000 | +0.0000 | +5.0000 | +155.0100 | 0 |
| DCA-RM printed p=0.50 | +3 | +2.0000 | +89.1600 | -3.0000 | -65.8500 | +5.0000 | +155.0100 | 0 |
| DCA-RM printed p=0.80 | +7 | +10.0000 | +500.9600 | -5.0000 | -133.6900 | +15.0000 | +634.6500 | 0 |
| DCA-RM capped p=0.20 | +3 | +5.0000 | +155.0100 | +0.0000 | +0.0000 | +5.0000 | +155.0100 | 0 |
| DCA-RM capped p=0.50 | +3 | +5.0000 | +155.0100 | +0.0000 | +0.0000 | +5.0000 | +155.0100 | 0 |
| DCA-RM capped p=0.80 | +3 | +3.0000 | +111.1100 | -2.0000 | -43.9000 | +5.0000 | +155.0100 | 0 |

## Event-level results

| Policy | Seq. | Event | Time | Demand | Category | Requested | Status | Acceptance | Accepted volume | Realised revenue | Objective | Future contribution | Forecasts | Protected forecasts | Protected volume |
|---|---:|---|---:|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Sequential DCA | 1 | booking::0001::K0001 | 0 | K0001 | P | 1.0000 | solved | 1.0000 | 1.0000 | 27.9200 | 27.9200 | 0.0000 | 0 | 0 | 0.0000 |
| Sequential DCA | 2 | booking::0002::K0003 | 0 | K0003 | P | 6.0000 | solved | 1.0000 | 6.0000 | 144.1800 | 144.1800 | 0.0000 | 0 | 0 | 0.0000 |
| Sequential DCA | 3 | booking::0003::K0004 | 0 | K0004 | F | 3.0000 | solved | 1.0000 | 3.0000 | 118.0800 | 118.0800 | 0.0000 | 0 | 0 | 0.0000 |
| Sequential DCA | 4 | booking::0004::K0005 | 0 | K0005 | P | 8.0000 | solved | 0.3750 | 3.0000 | 89.0700 | 89.0700 | 0.0000 | 0 | 0 | 0.0000 |
| Sequential DCA | 5 | booking::0005::K0006 | 0 | K0006 | P | 5.0000 | solved | 1.0000 | 5.0000 | 109.7500 | 109.7500 | 0.0000 | 0 | 0 | 0.0000 |
| Sequential DCA | 6 | booking::0006::K0007 | 0 | K0007 | R | 3.0000 | solved | 1.0000 | 3.0000 | 140.9100 | 140.9100 | 0.0000 | 0 | 0 | 0.0000 |
| Sequential DCA | 7 | booking::0007::K0009 | 0 | K0009 | R | 3.0000 | solved | 1.0000 | 3.0000 | 126.1500 | 126.1500 | 0.0000 | 0 | 0 | 0.0000 |
| Sequential DCA | 8 | booking::0008::K0010 | 0 | K0010 | F | 2.0000 | solved | 1.0000 | 2.0000 | 67.8400 | 67.8400 | 0.0000 | 0 | 0 | 0.0000 |
| Sequential DCA | 9 | booking::0009::K0011 | 0 | K0011 | R | 2.0000 | failed | — | — | — | — | — | 0 | 0 | 0.0000 |
| Sequential DCA | 10 | booking::0010::K0012 | 0 | K0012 | P | 4.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| Sequential DCA | 11 | booking::0011::K0016 | 0 | K0016 | P | 2.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| Sequential DCA | 12 | booking::0012::K0017 | 0 | K0017 | R | 6.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| Sequential DCA | 13 | booking::0013::K0019 | 0 | K0019 | F | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| Sequential DCA | 14 | booking::0014::K0002 | 1 | K0002 | P | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| Sequential DCA | 15 | booking::0015::K0008 | 1 | K0008 | F | 8.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| Sequential DCA | 16 | booking::0016::K0013 | 1 | K0013 | R | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| Sequential DCA | 17 | booking::0017::K0014 | 1 | K0014 | F | 4.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| Sequential DCA | 18 | booking::0018::K0015 | 1 | K0015 | F | 1.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| Sequential DCA | 19 | booking::0019::K0018 | 1 | K0018 | F | 7.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| Sequential DCA | 20 | booking::0020::K0020 | 1 | K0020 | R | 1.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.20 | 1 | booking::0001::K0001 | 0 | K0001 | P | 1.0000 | solved | 1.0000 | 1.0000 | 27.9200 | 129.8890 | 101.9690 | 4 | 4 | 25.0000 |
| DCA-RM printed p=0.20 | 2 | booking::0002::K0003 | 0 | K0003 | P | 6.0000 | solved | 1.0000 | 6.0000 | 144.1800 | 220.1175 | 75.9375 | 4 | 3 | 19.0000 |
| DCA-RM printed p=0.20 | 3 | booking::0003::K0004 | 0 | K0004 | F | 3.0000 | solved | 1.0000 | 3.0000 | 118.0800 | 118.0800 | 0.0000 | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.20 | 4 | booking::0004::K0005 | 0 | K0005 | P | 8.0000 | solved | 0.3750 | 3.0000 | 89.0700 | 159.9630 | 70.8930 | 4 | 2 | 16.0000 |
| DCA-RM printed p=0.20 | 5 | booking::0005::K0006 | 0 | K0006 | P | 5.0000 | solved | 1.0000 | 5.0000 | 109.7500 | 176.4355 | 66.6855 | 4 | 3 | 15.0000 |
| DCA-RM printed p=0.20 | 6 | booking::0006::K0007 | 0 | K0007 | R | 3.0000 | solved | 1.0000 | 3.0000 | 140.9100 | 205.5090 | 64.5990 | 11 | 2 | 12.0000 |
| DCA-RM printed p=0.20 | 7 | booking::0007::K0009 | 0 | K0009 | R | 3.0000 | solved | 1.0000 | 3.0000 | 126.1500 | 156.1565 | 30.0065 | 6 | 2 | 9.0000 |
| DCA-RM printed p=0.20 | 8 | booking::0008::K0010 | 0 | K0010 | F | 2.0000 | solved | 1.0000 | 2.0000 | 67.8400 | 90.1000 | 22.2600 | 2 | 1 | 7.0000 |
| DCA-RM printed p=0.20 | 9 | booking::0009::K0011 | 0 | K0011 | R | 2.0000 | solved | 1.0000 | 2.0000 | 67.4200 | 79.3450 | 11.9250 | 2 | 1 | 5.0000 |
| DCA-RM printed p=0.20 | 10 | booking::0010::K0012 | 0 | K0012 | P | 4.0000 | solved | 0.2500 | 1.0000 | 42.1900 | 42.1900 | 0.0000 | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.20 | 11 | booking::0011::K0016 | 0 | K0016 | P | 2.0000 | solved | 1.0000 | 2.0000 | 45.4000 | 60.1562 | 14.7563 | 4 | 1 | 5.0000 |
| DCA-RM printed p=0.20 | 12 | booking::0012::K0017 | 0 | K0017 | R | 6.0000 | failed | — | — | — | — | — | 1 | 0 | 0.0000 |
| DCA-RM printed p=0.20 | 13 | booking::0013::K0019 | 0 | K0019 | F | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.20 | 14 | booking::0014::K0002 | 1 | K0002 | P | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.20 | 15 | booking::0015::K0008 | 1 | K0008 | F | 8.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.20 | 16 | booking::0016::K0013 | 1 | K0013 | R | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.20 | 17 | booking::0017::K0014 | 1 | K0014 | F | 4.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.20 | 18 | booking::0018::K0015 | 1 | K0015 | F | 1.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.20 | 19 | booking::0019::K0018 | 1 | K0018 | F | 7.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.20 | 20 | booking::0020::K0020 | 1 | K0020 | R | 1.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.50 | 1 | booking::0001::K0001 | 0 | K0001 | P | 1.0000 | solved | 1.0000 | 1.0000 | 27.9200 | 282.8425 | 254.9225 | 4 | 4 | 25.0000 |
| DCA-RM printed p=0.50 | 2 | booking::0002::K0003 | 0 | K0003 | P | 6.0000 | solved | 1.0000 | 6.0000 | 144.1800 | 334.0238 | 189.8438 | 4 | 3 | 19.0000 |
| DCA-RM printed p=0.50 | 3 | booking::0003::K0004 | 0 | K0004 | F | 3.0000 | solved | 1.0000 | 3.0000 | 118.0800 | 118.0800 | 0.0000 | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.50 | 4 | booking::0004::K0005 | 0 | K0005 | P | 8.0000 | solved | 0.3750 | 3.0000 | 89.0700 | 266.3025 | 177.2325 | 4 | 2 | 16.0000 |
| DCA-RM printed p=0.50 | 5 | booking::0005::K0006 | 0 | K0006 | P | 5.0000 | solved | 0.4000 | 2.0000 | 43.9000 | 287.7100 | 243.8100 | 4 | 3 | 18.0000 |
| DCA-RM printed p=0.50 | 6 | booking::0006::K0007 | 0 | K0007 | R | 3.0000 | solved | 1.0000 | 3.0000 | 140.9100 | 370.1300 | 229.2200 | 11 | 2 | 15.0000 |
| DCA-RM printed p=0.50 | 7 | booking::0007::K0009 | 0 | K0009 | R | 3.0000 | solved | 1.0000 | 3.0000 | 126.1500 | 232.3625 | 106.2125 | 6 | 2 | 12.0000 |
| DCA-RM printed p=0.50 | 8 | booking::0008::K0010 | 0 | K0010 | F | 2.0000 | solved | 1.0000 | 2.0000 | 67.8400 | 164.8113 | 96.9712 | 2 | 2 | 10.0000 |
| DCA-RM printed p=0.50 | 9 | booking::0009::K0011 | 0 | K0011 | R | 2.0000 | solved | 1.0000 | 2.0000 | 67.4200 | 138.9700 | 71.5500 | 2 | 1 | 8.0000 |
| DCA-RM printed p=0.50 | 10 | booking::0010::K0012 | 0 | K0012 | P | 4.0000 | solved | 0.2500 | 1.0000 | 42.1900 | 42.1900 | 0.0000 | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.50 | 11 | booking::0011::K0016 | 0 | K0016 | P | 2.0000 | solved | 1.0000 | 2.0000 | 45.4000 | 116.9500 | 71.5500 | 4 | 1 | 8.0000 |
| DCA-RM printed p=0.50 | 12 | booking::0012::K0017 | 0 | K0017 | R | 6.0000 | failed | — | — | — | — | — | 1 | 0 | 0.0000 |
| DCA-RM printed p=0.50 | 13 | booking::0013::K0019 | 0 | K0019 | F | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.50 | 14 | booking::0014::K0002 | 1 | K0002 | P | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.50 | 15 | booking::0015::K0008 | 1 | K0008 | F | 8.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.50 | 16 | booking::0016::K0013 | 1 | K0013 | R | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.50 | 17 | booking::0017::K0014 | 1 | K0014 | F | 4.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.50 | 18 | booking::0018::K0015 | 1 | K0015 | F | 1.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.50 | 19 | booking::0019::K0018 | 1 | K0018 | F | 7.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.50 | 20 | booking::0020::K0020 | 1 | K0020 | R | 1.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.80 | 1 | booking::0001::K0001 | 0 | K0001 | P | 1.0000 | solved | 1.0000 | 1.0000 | 27.9200 | 435.7960 | 407.8760 | 4 | 4 | 25.0000 |
| DCA-RM printed p=0.80 | 2 | booking::0002::K0003 | 0 | K0003 | P | 6.0000 | solved | 1.0000 | 6.0000 | 144.1800 | 447.9300 | 303.7500 | 4 | 3 | 19.0000 |
| DCA-RM printed p=0.80 | 3 | booking::0003::K0004 | 0 | K0004 | F | 3.0000 | solved | 1.0000 | 3.0000 | 118.0800 | 118.0800 | 0.0000 | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.80 | 4 | booking::0004::K0005 | 0 | K0005 | P | 8.0000 | solved | 0.3750 | 3.0000 | 89.0700 | 372.6420 | 283.5720 | 4 | 2 | 16.0000 |
| DCA-RM printed p=0.80 | 5 | booking::0005::K0006 | 0 | K0006 | P | 5.0000 | solved | 0.4000 | 2.0000 | 43.9000 | 433.9960 | 390.0960 | 4 | 3 | 18.0000 |
| DCA-RM printed p=0.80 | 6 | booking::0006::K0007 | 0 | K0007 | R | 3.0000 | solved | 1.0000 | 3.0000 | 140.9100 | 507.6620 | 366.7520 | 11 | 2 | 15.0000 |
| DCA-RM printed p=0.80 | 7 | booking::0007::K0009 | 0 | K0009 | R | 3.0000 | solved | 1.0000 | 3.0000 | 126.1500 | 296.0900 | 169.9400 | 6 | 2 | 12.0000 |
| DCA-RM printed p=0.80 | 8 | booking::0008::K0010 | 0 | K0010 | F | 2.0000 | solved | 0.0000 | 0.0000 | 0.0000 | 243.2640 | 243.2640 | 2 | 2 | 12.0000 |
| DCA-RM printed p=0.80 | 9 | booking::0009::K0011 | 0 | K0011 | R | 2.0000 | solved | 1.0000 | 2.0000 | 67.4200 | 222.5740 | 155.1540 | 2 | 2 | 10.0000 |
| DCA-RM printed p=0.80 | 10 | booking::0010::K0012 | 0 | K0012 | P | 4.0000 | solved | 0.2500 | 1.0000 | 42.1900 | 42.1900 | 0.0000 | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.80 | 11 | booking::0011::K0016 | 0 | K0016 | P | 2.0000 | solved | 1.0000 | 2.0000 | 45.4000 | 171.6850 | 126.2850 | 4 | 2 | 10.0000 |
| DCA-RM printed p=0.80 | 12 | booking::0012::K0017 | 0 | K0017 | R | 6.0000 | solved | 1.0000 | 6.0000 | 352.4400 | 384.2400 | 31.8000 | 1 | 1 | 4.0000 |
| DCA-RM printed p=0.80 | 13 | booking::0013::K0019 | 0 | K0019 | F | 5.0000 | solved | 0.0000 | 0.0000 | 0.0000 | 31.8000 | 31.8000 | 2 | 1 | 4.0000 |
| DCA-RM printed p=0.80 | 14 | booking::0014::K0002 | 1 | K0002 | P | 5.0000 | solved | 0.8000 | 4.0000 | 127.2000 | 127.2000 | 0.0000 | 5 | 0 | 0.0000 |
| DCA-RM printed p=0.80 | 15 | booking::0015::K0008 | 1 | K0008 | F | 8.0000 | solved | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 4 | 0 | 0.0000 |
| DCA-RM printed p=0.80 | 16 | booking::0016::K0013 | 1 | K0013 | R | 5.0000 | failed | — | — | — | — | — | 3 | 0 | 0.0000 |
| DCA-RM printed p=0.80 | 17 | booking::0017::K0014 | 1 | K0014 | F | 4.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.80 | 18 | booking::0018::K0015 | 1 | K0015 | F | 1.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.80 | 19 | booking::0019::K0018 | 1 | K0018 | F | 7.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM printed p=0.80 | 20 | booking::0020::K0020 | 1 | K0020 | R | 1.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.20 | 1 | booking::0001::K0001 | 0 | K0001 | P | 1.0000 | solved | 1.0000 | 1.0000 | 27.9200 | 145.0695 | 117.1495 | 4 | 4 | 25.0000 |
| DCA-RM capped p=0.20 | 2 | booking::0002::K0003 | 0 | K0003 | P | 6.0000 | solved | 1.0000 | 6.0000 | 144.1800 | 234.1563 | 89.9763 | 4 | 4 | 19.0000 |
| DCA-RM capped p=0.20 | 3 | booking::0003::K0004 | 0 | K0004 | F | 3.0000 | solved | 1.0000 | 3.0000 | 118.0800 | 118.0800 | 0.0000 | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.20 | 4 | booking::0004::K0005 | 0 | K0005 | P | 8.0000 | solved | 0.3750 | 3.0000 | 89.0700 | 159.9630 | 70.8930 | 4 | 2 | 16.0000 |
| DCA-RM capped p=0.20 | 5 | booking::0005::K0006 | 0 | K0006 | P | 5.0000 | solved | 1.0000 | 5.0000 | 109.7500 | 214.1353 | 104.3853 | 4 | 4 | 15.0000 |
| DCA-RM capped p=0.20 | 6 | booking::0006::K0007 | 0 | K0007 | R | 3.0000 | solved | 1.0000 | 3.0000 | 140.9100 | 246.4023 | 105.4923 | 11 | 6 | 12.0000 |
| DCA-RM capped p=0.20 | 7 | booking::0007::K0009 | 0 | K0009 | R | 3.0000 | solved | 1.0000 | 3.0000 | 126.1500 | 191.2605 | 65.1105 | 6 | 4 | 9.0000 |
| DCA-RM capped p=0.20 | 8 | booking::0008::K0010 | 0 | K0010 | F | 2.0000 | solved | 1.0000 | 2.0000 | 67.8400 | 113.7175 | 45.8775 | 2 | 2 | 7.0000 |
| DCA-RM capped p=0.20 | 9 | booking::0009::K0011 | 0 | K0011 | R | 2.0000 | solved | 1.0000 | 2.0000 | 67.4200 | 91.2700 | 23.8500 | 2 | 1 | 5.0000 |
| DCA-RM capped p=0.20 | 10 | booking::0010::K0012 | 0 | K0012 | P | 4.0000 | solved | 0.2500 | 1.0000 | 42.1900 | 42.1900 | 0.0000 | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.20 | 11 | booking::0011::K0016 | 0 | K0016 | P | 2.0000 | solved | 1.0000 | 2.0000 | 45.4000 | 77.9838 | 32.5838 | 4 | 2 | 5.0000 |
| DCA-RM capped p=0.20 | 12 | booking::0012::K0017 | 0 | K0017 | R | 6.0000 | failed | — | — | — | — | — | 1 | 0 | 0.0000 |
| DCA-RM capped p=0.20 | 13 | booking::0013::K0019 | 0 | K0019 | F | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.20 | 14 | booking::0014::K0002 | 1 | K0002 | P | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.20 | 15 | booking::0015::K0008 | 1 | K0008 | F | 8.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.20 | 16 | booking::0016::K0013 | 1 | K0013 | R | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.20 | 17 | booking::0017::K0014 | 1 | K0014 | F | 4.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.20 | 18 | booking::0018::K0015 | 1 | K0015 | F | 1.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.20 | 19 | booking::0019::K0018 | 1 | K0018 | F | 7.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.20 | 20 | booking::0020::K0020 | 1 | K0020 | R | 1.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.50 | 1 | booking::0001::K0001 | 0 | K0001 | P | 1.0000 | solved | 1.0000 | 1.0000 | 27.9200 | 320.7937 | 292.8738 | 4 | 4 | 25.0000 |
| DCA-RM capped p=0.50 | 2 | booking::0002::K0003 | 0 | K0003 | P | 6.0000 | solved | 1.0000 | 6.0000 | 144.1800 | 369.1206 | 224.9406 | 4 | 4 | 19.0000 |
| DCA-RM capped p=0.50 | 3 | booking::0003::K0004 | 0 | K0004 | F | 3.0000 | solved | 1.0000 | 3.0000 | 118.0800 | 118.0800 | 0.0000 | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.50 | 4 | booking::0004::K0005 | 0 | K0005 | P | 8.0000 | solved | 0.3750 | 3.0000 | 89.0700 | 266.3025 | 177.2325 | 4 | 2 | 16.0000 |
| DCA-RM capped p=0.50 | 5 | booking::0005::K0006 | 0 | K0006 | P | 5.0000 | solved | 1.0000 | 5.0000 | 109.7500 | 370.7131 | 260.9631 | 4 | 4 | 15.0000 |
| DCA-RM capped p=0.50 | 6 | booking::0006::K0007 | 0 | K0007 | R | 3.0000 | solved | 1.0000 | 3.0000 | 140.9100 | 404.6406 | 263.7306 | 11 | 6 | 12.0000 |
| DCA-RM capped p=0.50 | 7 | booking::0007::K0009 | 0 | K0009 | R | 3.0000 | solved | 1.0000 | 3.0000 | 126.1500 | 288.9262 | 162.7763 | 6 | 4 | 9.0000 |
| DCA-RM capped p=0.50 | 8 | booking::0008::K0010 | 0 | K0010 | F | 2.0000 | solved | 1.0000 | 2.0000 | 67.8400 | 182.5337 | 114.6937 | 2 | 2 | 7.0000 |
| DCA-RM capped p=0.50 | 9 | booking::0009::K0011 | 0 | K0011 | R | 2.0000 | solved | 1.0000 | 2.0000 | 67.4200 | 127.0450 | 59.6250 | 2 | 1 | 5.0000 |
| DCA-RM capped p=0.50 | 10 | booking::0010::K0012 | 0 | K0012 | P | 4.0000 | solved | 0.2500 | 1.0000 | 42.1900 | 42.1900 | 0.0000 | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.50 | 11 | booking::0011::K0016 | 0 | K0016 | P | 2.0000 | solved | 1.0000 | 2.0000 | 45.4000 | 126.8594 | 81.4594 | 4 | 2 | 5.0000 |
| DCA-RM capped p=0.50 | 12 | booking::0012::K0017 | 0 | K0017 | R | 6.0000 | failed | — | — | — | — | — | 1 | 0 | 0.0000 |
| DCA-RM capped p=0.50 | 13 | booking::0013::K0019 | 0 | K0019 | F | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.50 | 14 | booking::0014::K0002 | 1 | K0002 | P | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.50 | 15 | booking::0015::K0008 | 1 | K0008 | F | 8.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.50 | 16 | booking::0016::K0013 | 1 | K0013 | R | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.50 | 17 | booking::0017::K0014 | 1 | K0014 | F | 4.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.50 | 18 | booking::0018::K0015 | 1 | K0015 | F | 1.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.50 | 19 | booking::0019::K0018 | 1 | K0018 | F | 7.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.50 | 20 | booking::0020::K0020 | 1 | K0020 | R | 1.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.80 | 1 | booking::0001::K0001 | 0 | K0001 | P | 1.0000 | solved | 1.0000 | 1.0000 | 27.9200 | 496.5180 | 468.5980 | 4 | 4 | 25.0000 |
| DCA-RM capped p=0.80 | 2 | booking::0002::K0003 | 0 | K0003 | P | 6.0000 | solved | 1.0000 | 6.0000 | 144.1800 | 504.0850 | 359.9050 | 4 | 4 | 19.0000 |
| DCA-RM capped p=0.80 | 3 | booking::0003::K0004 | 0 | K0004 | F | 3.0000 | solved | 1.0000 | 3.0000 | 118.0800 | 118.0800 | 0.0000 | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.80 | 4 | booking::0004::K0005 | 0 | K0005 | P | 8.0000 | solved | 0.3750 | 3.0000 | 89.0700 | 372.6420 | 283.5720 | 4 | 2 | 16.0000 |
| DCA-RM capped p=0.80 | 5 | booking::0005::K0006 | 0 | K0006 | P | 5.0000 | solved | 0.6000 | 3.0000 | 65.8500 | 530.6310 | 464.7810 | 4 | 4 | 17.0000 |
| DCA-RM capped p=0.80 | 6 | booking::0006::K0007 | 0 | K0007 | R | 3.0000 | solved | 1.0000 | 3.0000 | 140.9100 | 618.1540 | 477.2440 | 11 | 6 | 14.0000 |
| DCA-RM capped p=0.80 | 7 | booking::0007::K0009 | 0 | K0009 | R | 3.0000 | solved | 1.0000 | 3.0000 | 126.1500 | 442.7300 | 316.5800 | 6 | 5 | 11.0000 |
| DCA-RM capped p=0.80 | 8 | booking::0008::K0010 | 0 | K0010 | F | 2.0000 | solved | 1.0000 | 2.0000 | 67.8400 | 267.2500 | 199.4100 | 2 | 2 | 9.0000 |
| DCA-RM capped p=0.80 | 9 | booking::0009::K0011 | 0 | K0011 | R | 2.0000 | solved | 1.0000 | 2.0000 | 67.4200 | 178.7200 | 111.3000 | 2 | 1 | 7.0000 |
| DCA-RM capped p=0.80 | 10 | booking::0010::K0012 | 0 | K0012 | P | 4.0000 | solved | 0.2500 | 1.0000 | 42.1900 | 42.1900 | 0.0000 | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.80 | 11 | booking::0011::K0016 | 0 | K0016 | P | 2.0000 | solved | 1.0000 | 2.0000 | 45.4000 | 214.4900 | 169.0900 | 4 | 2 | 7.0000 |
| DCA-RM capped p=0.80 | 12 | booking::0012::K0017 | 0 | K0017 | R | 6.0000 | failed | — | — | — | — | — | 1 | 0 | 0.0000 |
| DCA-RM capped p=0.80 | 13 | booking::0013::K0019 | 0 | K0019 | F | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.80 | 14 | booking::0014::K0002 | 1 | K0002 | P | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.80 | 15 | booking::0015::K0008 | 1 | K0008 | F | 8.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.80 | 16 | booking::0016::K0013 | 1 | K0013 | R | 5.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.80 | 17 | booking::0017::K0014 | 1 | K0014 | F | 4.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.80 | 18 | booking::0018::K0015 | 1 | K0015 | F | 1.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.80 | 19 | booking::0019::K0018 | 1 | K0018 | F | 7.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |
| DCA-RM capped p=0.80 | 20 | booking::0020::K0020 | 1 | K0020 | R | 1.0000 | not-run | — | — | — | — | — | 0 | 0 | 0.0000 |

## Interpretation boundary

The probability regimes test whether the implemented DCA-RM mechanism responds coherently to changing future-demand opportunity cost. They do not establish that any one synthetic probability regime matches the paper's original experimental data.

Tentative future flows, protected-volume selectors, and forecast protection levels are discarded after each decision. Only the realised current acceptance and current route enter persistent booking state.

The capped-value formulation credits outcomes above the selected protection level and is an explicitly labelled sensitivity, not the printed baseline.
