# Test using package
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
