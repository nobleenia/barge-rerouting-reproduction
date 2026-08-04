.PHONY: inspect-rerouting-eligibility solve-time-aware-sequential-dca inspect-time-aware-capacity inspect-physical-execution solve-toy-sequential-dca solve-sequential-dca inspect-booking-commitments inspect-booking-timeline solve-toy-dca solve-tiny-dca inspect-toy-instance generate-toy-demands plot-time-space plot-physical install solve-toy test lint format type-check check versions environment clean

install:
	python -m pip install -e ".[dev]"

solve-toy:
	python -m barge_rerouting.models.toy_lp

plot-physical:
	python scripts/plot_physical_network.py

plot-time-space:
	python scripts/plot_time_space_network.py

test:
	pytest -q

lint:
	ruff check .

format:
	ruff check --fix .
	ruff format .

type-check:
	mypy src

check:
	ruff check .
	ruff format --check .
	mypy src
	pytest -q

environment:
	python scripts/check_environment.py

versions:
	python --version
	python -m pip --version
	python -c "import cplex; print('CPLEX:', cplex.__version__)"
	python -c "import docplex; print('DOcplex:', docplex.__version__)"
	python -c "import networkx; print('NetworkX:', networkx.__version__)"
	python -c "import numpy; print('NumPy:', numpy.__version__)"
	python -c "import pandas; print('pandas:', pandas.__version__)"
	git --version

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

generate-toy-demands:
	python scripts/generate_demands.py configs/toy_experiment.yaml --output data/generated/toy_demands.csv

inspect-toy-instance:
	python scripts/inspect_experiment_instance.py configs/toy_experiment.yaml

solve-tiny-dca:
	python scripts/solve_tiny_dca.py

solve-toy-dca:
	python scripts/solve_toy_dca.py

inspect-booking-timeline:
	python scripts/inspect_booking_timeline.py

inspect-booking-commitments:
	python scripts/inspect_booking_commitments.py

solve-sequential-dca:
	python scripts/solve_sequential_dca.py

solve-toy-sequential-dca:
	python scripts/solve_toy_sequential_dca.py

inspect-physical-execution:
	python scripts/inspect_physical_execution.py

inspect-time-aware-capacity:
	python scripts/inspect_time_aware_capacity.py

solve-time-aware-sequential-dca:
	python scripts/solve_time_aware_sequential_dca.py

inspect-rerouting-eligibility:
	python scripts/inspect_rerouting_eligibility.py

