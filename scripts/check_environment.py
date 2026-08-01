"""Display the software environment used by the reproduction project."""

from __future__ import annotations

import platform
import sys
from importlib.metadata import version

import cplex
import docplex
import matplotlib
import networkx
import numpy
import pandas
import yaml


def main() -> None:
    """Print the principal environment and dependency versions."""
    print("Barge rerouting reproduction environment")
    print("=" * 42)
    print(f"Operating system:           {platform.platform()}")
    print(f"Python:                     {sys.version.split()[0]}")
    print(f"Python path:                {sys.executable}")
    print(f"CPLEX API/engine version:   {cplex.__version__}")
    print(f"CPLEX package version:      {version('cplex')}")
    print(f"DOcplex:                    {docplex.__version__}")
    print(f"NetworkX:                   {networkx.__version__}")
    print(f"NumPy:                      {numpy.__version__}")
    print(f"pandas:                     {pandas.__version__}")
    print(f"matplotlib:                 {matplotlib.__version__}")
    print(f"PyYAML:                     {yaml.__version__}")


if __name__ == "__main__":
    main()
