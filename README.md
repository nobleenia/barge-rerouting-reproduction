# Demand Rerouting for Intermodal Barge Networks

Python implementation of the demand-allocation, revenue-management, and
rerouting models described in:

> Y. Cui, I. C. Bilegan, E. Duchenne, and D. Duvivier,
> “Demand rerouting mechanisms with revenue management for intermodal barge
> transportation networks,” *Transportmetrica B: Transport Dynamics*, 12(1),
> 2024, Article 2416182.
> https://doi.org/10.1080/21680566.2024.2416182

## Scope

The repository implements:

- Dynamic Capacity Allocation (DCA);
- DCA with revenue management (DCA-RM);
- DCA with rerouting (DCA-R);
- DCA with revenue management and rerouting (DCA-RRM);
- Partial Rerouting and Full Rerouting;
- time-space network construction;
- rolling-horizon booking and execution;
- water-level capacity changes and truck recourse.

The paper does not provide all demand instances, random seeds, service
schedules, forecast realisations, indicator definitions, or solver settings.
The experiments therefore use documented substitute inputs. They reproduce the
model behaviour but not the published table values exactly.

## Repository layout

```text
configs/   Experiment configuration
data/      Controlled input data
docs/      Model, assumptions, and validation notes
results/   Selected outputs and audit records
scripts/   Command-line experiment and inspection scripts
src/       Python package
tests/     Unit and integration tests
```

## Installation

Python 3.12 is required. The optimisation code uses DOcplex with either CPLEX
or HiGHS.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The main dependencies are also listed in `requirements.lock.txt`.

## Checks

Run the complete local check with:

```bash
make check
```

This runs Ruff, mypy, and pytest. Individual checks are available through
`make lint`, `make type-check`, and `make test`.

## Small examples

```bash
make solve-tiny-dca
make solve-sequential-dca
make inspect-dca-rm
make inspect-full-reroute-run
```

The full campaign scripts are more expensive than the examples and tests.
Existing compact results are stored under `results/`.

## Experiment records

The final experiment notes are:

- `docs/phase11_table4_validation.md`
- `docs/phase11_table5_validation.md`
- `docs/phase11_table6_validation.md`
- `docs/phase11_validation_synthesis.md`

The main model description is in `docs/mathematical_model.md`. Assumptions and
unresolved source details are recorded in `docs/assumptions_register.md`.

## Results and limitations

The controlled experiments reproduce the expected qualitative effects:

- rerouting is most useful when barge capacity is scarce;
- lower water levels reduce available barge capacity;
- constrained cases transfer some cargo to truck;
- rerouting increases solve time;
- network structure affects policy performance.

The numerical values differ from the publication because several experimental
inputs are unavailable. No parameters were fitted to force agreement with the
reported tables.

Two apparent source-table anomalies are retained as printed in the comparison
data: the Table 5 AFR value `855` and the Table 6 NFR value `8` for Service 1,
capacity 40, and water factor 0.9.

## Licence and citation

The repository code is released under the MIT License. Citation metadata are
provided in `CITATION.cff`. Cite the Cui et al. paper when discussing the
underlying model.
