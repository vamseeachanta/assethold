# Standard library imports
import os
import sys

# Third party imports
from assetutilities.common.utilities import is_file_valid_func
from assetutilities.common.yml_utilities import ymlInput

# Reader imports
from assethold.engine import engine


def run_process(input_file, expected_result={}):
    if input_file is not None and not os.path.isfile(input_file):
        input_file = os.path.join(os.path.dirname(__file__), input_file)
    cfg = engine(input_file)
    #assert(cfg[cfg['basename']] == expected_result[expected_result['basename']])

def test_run_process():
    input_file = 'breakout_TSLA.yml'
    pytest_output_file = 'results/pytest_breakout_TSLA.yml'

    file_is_valid, pytest_output_file = is_file_valid_func(pytest_output_file, os.path.dirname(__file__))

    if file_is_valid:
        expected_result = ymlInput(pytest_output_file, updateYml=None)

        if len(sys.argv) > 1:
            sys.argv.pop()

        run_process(input_file, expected_result)
    else:
        print(f"File {pytest_output_file} is not valid")
        run_process(input_file, expected_result={})

test_run_process()
