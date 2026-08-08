# Phase 11 Experimental Reproduction Contract

## 1. Purpose

Phase 11 moves from mechanism validation to publication-oriented experiments.

Every experiment must be classified as one of:

1. strict publication-structure reproduction;
2. controlled substitute-input reproduction;
3. sensitivity analysis;
4. research extension.

Missing publication inputs must never be tuned simply to reproduce reported
numbers.

## 2. Shared published experimental structure

The source paper uses:

- five consecutive terminals A--E;
- equal travel times between consecutive terminals;
- half-day time periods;
- weekly service repetition every 14 periods;
- two service families;
- customer categories R, P and F;
- proportional water-level capacity reduction.

Service family 1 contains two services defined in both directions.

Service family 2 contains four services defined in both directions.

The exact unpublished schedules and demand-generation parameters remain
controlled assumptions where necessary.

## 3. Phase 11A — Table 4 stable-capacity experiment

### Publication structure

Service families:

- Service family 1;
- Service family 2.

Capacities:

- 10 TEU;
- 15 TEU;
- 20 TEU.

Policies:

- DCA;
- DCA-RM;
- DCA-Reroute;
- DCA-RRM.

Demand sets:

- five common demand sets.

Total experiment instances:

\[
2 \times 3 \times 4 \times 5 = 120.
\]

External service status remains unchanged.

Truck recourse is disabled.

### Raw records

For every run record at minimum:

- demand-set identifier;
- service-family identifier;
- capacity;
- policy;
- seed;
- total revenue;
- total transported barge volume;
- accepted volume;
- revenue per accepted TEU;
- processed demand count;
- solver status;
- solving time;
- MIP gap;
- variable count;
- constraint count;
- branch-and-bound node count where available;
- configuration fingerprint;
- demand-instance fingerprint;
- software/solver metadata.

### Table 4 derived quantities

For each demand set and each non-DCA policy:

\[
RevenueIR
=
100
\frac{TR_{policy}-TR_{DCA}}
     {TR_{DCA}}.
\]

For total transported volume:

\[
VolumeIR
=
100
\frac{V_{policy}-V_{DCA}}
     {V_{DCA}}.
\]

Aggregate across the five paired demand sets using:

- average;
- minimum;
- maximum.

The DCA reference row is zero by definition.

## 4. Phase 11B — Table 5 standard-water experiment

Use:

- two service families;
- capacities 10, 20, 30 and 40 TEU;
- standard water level only;
- DCA;
- Partial-Reroute;
- Full-Reroute.

The paper describes a set of 800 demands with origin-destination pairs evenly
distributed over the five-terminal network.

Partial-Reroute triggers at every water-forecast update:

\[
2\text{ days}=4\text{ half-day periods}.
\]

The publication states that 40 requests occur during those four periods.

Full-Reroute triggers at every incoming request.

Table-5-facing indicators:

- AFR;
- VTR;
- VFB;
- VOB;
- VOA;
- TR;
- ST.

At standard water level, AFR and NFR should coincide.

## 5. Phase 11C — Table 6 water-change experiment

Table 6 is a Partial-Reroute experiment.

Use:

- two service families;
- capacities 10, 20, 30 and 40 TEU;
- water factors 1.0, 0.9, 0.8 and 0.7;
- Partial-Reroute only.

Table-6-facing indicators:

- AFR;
- NFR;
- VTR;
- VFB;
- VOB.

The printed Table 6 heading uses `VT` while Table 7 defines the truck-volume
indicator as `VTR`. Internally the implementation will use `VTR`; source
comparison output must preserve the publication's printed heading separately.

## 6. Phase 11D — explicit extensions

The following are scientifically useful but are not strict Table 6
reproduction:

- Full-Reroute under reduced water factors;
- DCA under reduced water factors;
- complete DCA/PR/FR x water-factor comparison;
- alternative truck penalties;
- alternative forecast intervals;
- alternative water sequences;
- future-demand RM under predicted disruptions.

Every such result must be labelled `extension`.

## 7. Indicator rule

No percentage indicator may be reported until its definition contains:

- numerator;
- denominator;
- unit;
- time horizon;
- aggregation rule;
- treatment of trucked cargo;
- treatment of rejected demand.

Table 7 supplies indicator names but does not uniquely establish all required
denominators.

## 8. Validation protocol

Use:

- common random numbers;
- fixed explicit seeds;
- identical demand sets across paired policy comparisons;
- hand-solved controlled instances;
- unit tests;
- integration tests;
- regression locks;
- independent objective recalculation;
- node-flow residual checks;
- transport-capacity residual checks;
- accepted-volume accounting;
- solver-status and MIP-gap capture;
- confidence intervals where repeated synthetic runs permit them;
- explicit sensitivity analysis.

Confidence intervals are additional scientific analysis and must not be
described as reported by the source paper.

## 9. Traceability gate

Every final result must satisfy:

\[
paper
\rightarrow
interpretation
\rightarrow
configuration
\rightarrow
seed
\rightarrow
raw\ result
\rightarrow
indicator
\rightarrow
table/figure.
\]

No presentation table or figure is admissible unless:

- it is regenerated automatically from raw results;
- every denominator is defined;
- units are explicit;
- configuration and seed are recoverable;
- software and solver metadata are stored;
- reproduction and extension results are clearly separated.

## 10. Known publication limitations

Do not silently invent or correct:

- exact service schedules;
- original random seeds;
- exact demand-volume distributions;
- complete fare parameters;
- exact future-demand distributions;
- truck penalty values;
- exact water-level sequence;
- capacity rounding;
- several performance-indicator denominators.

Also preserve as printed when comparing with the paper:

- Table 5 apparent AFR value `855`;
- Table 6 apparent NFR value `8`.

Any mathematically plausible correction must be reported in a separate
diagnostic field rather than replacing the published value.

## 11. Controlled Table 4 demand-set seed registry

The original five random seeds are not disclosed by the publication.

The controlled substitute-input baseline therefore uses the explicit seeds:

- demand_set_01: 11001;
- demand_set_02: 11002;
- demand_set_03: 11003;
- demand_set_04: 11004;
- demand_set_05: 11005.

These values were selected before running the Phase 11 experimental matrix.

They must not be tuned in response to agreement or disagreement with the
publication's reported Table 4 values.

Within every service-family/capacity cell, the identical realised demand
instance and demand fingerprint must be supplied to:

- DCA;
- DCA-RM;
- DCA-Reroute;
- DCA-RRM.

The seed registry is therefore a common-random-number device for paired policy
comparison, not a claim about the authors' unpublished random seeds.

## 12. Table 4 periodic service-family reconstruction

The publication-facing network generator must preserve the reported structural
properties:

- terminals A--E;
- only consecutive-terminal service movement;
- equal adjacent travel times;
- half-day periods;
- 14-period weekly repetition;
- two service slots per direction for Service Family 1;
- four service slots per direction for Service Family 2.

Because the publication does not disclose exact departure offsets or the
numerical adjacent travel duration, the controlled baseline follows A028:

- Family 1 offsets: `0, 7`;
- Family 2 offsets: `0, 3, 7, 10`;
- adjacent travel duration: one half-day period.

These values are fixed before experimental solving and must not be tuned to
increase agreement with Table 4.

The experimental horizon remains a separate Phase 11 demand-generation
decision and is not fixed merely by the service-family generator.

## 13. Structural demand-generation boundary

Phase 11 separates the publication-supported request-arrival process from
undisclosed economic parameters.

The structural generator follows A029 and produces:

- ten requests for every configured half-day request period;
- uniformly sampled ordered OD pairs over A--E;
- uniformly sampled R/P/F customer categories;
- distance-dependent anticipation draws;
- distance-dependent delivery-slack draws.

The same structural request stream must be reused across service families,
capacities and policies whenever the experimental design requires the same
demand set.

The following are intentionally not assigned numerical baseline values in
the structural generator:

- realised-demand volume distribution;
- VMAX;
- base fare;
- anticipation fare multiplier;
- delivery-time fare multiplier.

Those values must be locked separately before the first Table 4 pilot solve.
