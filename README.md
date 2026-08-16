# Demand Rerouting and Revenue Management for Intermodal Barge Networks — Computational Reproduction

A tested computational reproduction of the demand-rerouting and revenue-management mechanisms presented in:

> Yaheng Cui, Ioana C. Bilegan, Eric Duchenne, and David Duvivier,  
> **“Demand rerouting mechanisms with revenue management for intermodal barge transportation networks.”**  
> *Transportmetrica B: Transport Dynamics*, 12(1), 2024, Article 2416182.  
> DOI: https://doi.org/10.1080/21680566.2024.2416182

## Reproduction status

**Phase 11 experimental reproduction is complete.**

This repository provides a:

> **Validated computational and behavioural reproduction of the published mechanisms using controlled substitute inputs, with unsuccessful exact numerical replication of the reported experimental values.**

The distinction is deliberate. The publication does not disclose all original generated instances, random seeds, service schedules, forecast realisations, indicator aggregation rules, implementation details, or solver configuration needed for exact numerical reconstruction.

The project therefore freezes explicit controlled assumptions and tests the behaviour of the published mechanisms without calibrating parameters after observing the paper's results.

## What is reproduced

The implementation covers the principal modelling and experimental components of the paper:

- physical and time-space intermodal transportation networks;
- sequential booking and accept/reject decisions;
- Dynamic Capacity Allocation (DCA);
- revenue-management capacity protection;
- Partial Rerouting (PR);
- Full Rerouting (FR);
- changing barge capacities caused by water-level reductions;
- truck recourse;
- rolling-horizon operational execution;
- publication-facing indicators and alternative indicator reconstructions;
- controlled reproductions corresponding to Tables 4, 5, and 6.

## Experimental reproduction

### Table 4

Stable-network experiments establish the controlled computational baseline and behaviour of the demand-allocation and revenue-management mechanisms.

### Table 5

The standard-water experiment evaluates:

- 2 service families;
- capacities of 10, 20, 30, and 40 TEU;
- DCA, Partial Reroute, and Full Reroute;
- one frozen 800-request realised demand set.

The controlled reproduction demonstrates that rerouting flexibility provides its strongest benefit under capacity scarcity, while the benefit diminishes as capacity becomes abundant.

### Table 6

The water-change experiment evaluates Partial Reroute for:

- 2 service families;
- capacities of 10, 20, 30, and 40 TEU;
- water factors 1.0, 0.9, 0.8, and 0.7.

The complete controlled comparison contains 32 rows.

The 24 newly solved reduced-water runs were independently audited for physical capacity, volume conservation, economic conservation, event completion, and reporting consistency.

## Important reproducibility result

The project reproduces important **behavioural mechanisms** from the paper but does not reproduce the published numerical tables exactly.

Examples of reproduced behaviour include:

- capacity scarcity increases the value of rerouting flexibility;
- reduced water increases pressure on remaining barge capacity;
- constrained cases shift cargo from barge to truck;
- additional rerouting flexibility carries substantial computational cost;
- network structure materially changes policy performance.

Systematic numerical discrepancies are preserved and documented rather than removed by post-hoc tuning.

## Validation philosophy

A successful solver termination is **not** treated as sufficient validation.

The project independently checks, where applicable:

- solver status;
- booking-event completion;
- status-update completion;
- configuration fingerprints;
- demand fingerprints;
- volume conservation;
- capacity feasibility;
- accepted-volume decomposition;
- truck recourse accounting;
- revenue accounting;
- reporting consistency;
- AFR/NFR reconstruction;
- experimental coverage;
- persisted prevalidation evidence;
- SHA-256 evidence manifests.

The full repository validation gate currently contains 577 passing tests.

## Repository structure

```text
.
├── configs/       Experiment and model configuration
├── data/          Controlled input data
├── docs/          Mathematical, methodological, assumption, and validation documentation
├── notebooks/     Analysis notebooks
├── presentation/  Presentation material
├── results/       Compact version-controlled reproduction evidence
├── scripts/       Experiment, audit, export, and plotting entry points
├── src/           Reproduction implementation
├── tests/         Unit and integration validation
├── Makefile
├── pyproject.toml
└── requirements.lock.txt
```

## Environment

The project targets Python 3.12 and uses:

- IBM CPLEX / DOcplex;
- HiGHS;
- NetworkX;
- NumPy;
- pandas;
- matplotlib;
- pytest;
- Ruff;
- mypy.

Create an environment and install the project with development dependencies:

```bash
python3.12 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

A frozen dependency snapshot is also retained in `requirements.lock.txt.`

## Validate the repository

Run:

```bash
make check
```

This executes formatting/lint checks, static typing, and the complete pytest suite.

At the Phase-11 closure point:

```bash
Ruff:   PASS
Format: PASS
mypy:   PASS
pytest: 577 passed
```

## Expensive experiment warning

The production campaigns are computationally expensive.

Normal verification of the repository should use the test suite and persisted audit evidence rather than rerunning every production campaign.

Heavy operational records, prevalidation payloads, solver logs, and resumable campaign state are deliberately excluded from Git where they are not necessary for compact reproducibility.

The version-controlled `results/` tree retains compact tables, manifests, audit transcripts, publication comparisons, and evidence hashes.

## Phase-11 evidence

The principal final validation documents are:

```bash
docs/phase11_table5_validation.md
docs/phase11_table6_validation.md
docs/phase11_validation_synthesis.md
```

Table-6 compact evidence includes:

```bash
results/phase11/table6/campaign/table6_policy_rows.csv
results/phase11/table6/campaign/table6_published_comparison.csv
results/phase11/table6/campaign/table6_water_effects.csv
results/phase11/table6/campaign/campaign_manifest.json
results/phase11/table6/campaign/audit/global_campaign_audit.txt
results/phase11/table6/campaign/audit/evidence_sha256.txt
```

## Controlled assumptions and limitations

Where the source paper does not uniquely determine an implementation detail, the interpretation is recorded explicitly before evaluating the corresponding results.

Assumptions are maintained in:

```bash
docs/assumptions_register.md
```

The repository distinguishes between:

1. source-supported behaviour;
2. controlled reconstruction assumptions;
3. implementation choices;
4. numerical discrepancies;
5. optional extensions.

Undisclosed source information is not silently inferred from the target results.

## Known publication-data anomalies

Apparent anomalies in the publication are retained literally in source-comparison evidence instead of silently corrected.

Examples include the printed Table-5 AFR value `855` and the Table-6 Service-1 / capacity-40 / water-0.9 NFR value `8`.

Their apparent inconsistency is documented separately from the literal published values.

## Scope boundary

The strict reproduction campaign ends with the Table-6 experiment.

Reduced-water Full-Reroute, DCA-under-disruption, broader stochastic water trajectories, additional demand realisations, and larger sensitivity analyses are treated as future extensions, not requirements for claiming completion of the reproduction.

## Original article and copyright

This repository does not claim ownership of the reproduced article.

The original publication remains the intellectual property of its authors and publisher. The repository contains an independent implementation, controlled data, documentation, and reproduction evidence.

The original publisher PDF should not be redistributed through this repository unless its licence explicitly permits redistribution.

## Software licence

The independently developed code and associated repository documentation are released under the MIT License. See `LICENSE`.

## Citation

Software citation metadata are provided in `CITATION.cff`.

For academic discussion of the underlying model and mechanisms, cite the original Cui et al. publication in addition to this reproduction repository.

## Reproduction integrity

The final Phase-11 closure commit records a clean validation state in which:

```bash
577 tests passed
Table 5 global audit: PASS
Table 6 global audit: PASS
Phase 11 experimental reproduction: COMPLETE
```

The objective of this repository is not to make the published numbers appear reproducible at all costs.

The objective is to make every reproduced result traceable, testable, explainable, and scientifically defensible.
