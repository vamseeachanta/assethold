"""Leveraged Multi Family Real Estate Analysis.

Usage:
------

import pathlib
import os
from lmfa import multifamily
from lmfa.utilities import get_config_files

config_files = ['2022_06_qinn_at_westchase.yaml']
parent_path = pathlib.Path(__file__).resolve().parent

if len(config_files) == 0:
    config_files = get_config_files()

config_files = [
    os.path.join(parent_path, config_file) for config_file in config_files
]

multifamily.run_analysis(config_files)


Contact:
--------

More information is available at:

- https://pypi.org/project/leveraged-multi-family-analysis/
- https://github.com/vamseeachanta/leveraged-multi-family-analysis


Version:
--------

- leveraged-multi-family-analysis v0.1.5
"""
import os
import pathlib
from lmfa import multifamily
from lmfa.utilities import get_config_files


def main() -> None:
    #TODO Fix python parent path to terminal window for running package as module
    parent_path = pathlib.Path(__file__).resolve().parent
    config_files = get_config_files()

    config_files = [
        os.path.join(parent_path, config_file) for config_file in config_files
    ]

    multifamily.run_analysis()


if __name__ == "__main__":
    main()
