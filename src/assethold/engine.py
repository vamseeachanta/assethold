# Standard library imports
import logging
import os
import sys

# Third party imports
from assetutilities.common.ApplicationManager import ConfigureApplicationInputs
from assetutilities.common.data import SaveData
from assetutilities.common.file_management import FileManagement
from assetutilities.common.update_deep import AttributeDict
from assetutilities.common.utilities import save_application_cfg
from assetutilities.common.yml_utilities import ymlInput

# Reader imports
from assethold.modules.stocks.stocks import Stocks

library_name = "assethold"

stks = Stocks()
fm = FileManagement()
save_data = SaveData()

def engine(inputfile: str = None, cfg: dict = None, config_flag: bool = True) -> dict:

    if cfg is None:
        inputfile = validate_arguments_run_methods(inputfile)
        cfg = ymlInput(inputfile, updateYml=None)
        cfg = AttributeDict(cfg)
        if cfg is None:
            raise ValueError("cfg is None")

    basename = cfg["basename"]

    if config_flag:
        cfg_base = cfg
        cfg_base = fm.router(cfg_base)
    else:
        cfg_base = cfg

    logging.info(f"{basename}, application ... START")

    if basename in "stocks":
        cfg_base = stks.router(cfg_base)
    else:
        raise Exception(f"Analysis for basename: {basename} not found. ... FAIL")

    save_application_cfg(cfg_base=cfg_base)
    logging.info(f"{basename}, application ... END")

    return cfg_base


def validate_arguments_run_methods(inputfile):
    """
    Validate inputs for following run methods:
    - module (i.e. python -m digitalmodel input.yml)
    - from python file (i.e. )
    """

    if len(sys.argv) > 1 and inputfile is not None:
        raise Exception(
            "2 Input files provided via arguments & function. Please provide only 1 file ... FAIL"
        )

    if len(sys.argv) > 1:
        if not os.path.isfile(sys.argv[1]):
            raise FileNotFoundError(f"Input file {sys.argv[1]} not found ... FAIL")
        else:
            inputfile = sys.argv[1]

    if len(sys.argv) <= 1:
        if not os.path.isfile(inputfile):
            raise FileNotFoundError(f"Input file {inputfile} not found ... FAIL")
        else:
            sys.argv.append(inputfile)

    return inputfile
