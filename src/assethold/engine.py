# ABOUTME: Application engine that routes analysis requests to the appropriate module.
# ABOUTME: Reads YAML config and dispatches to stock analysis based on the `basename` key.

import logging
import os
import sys

from assetutilities.common.file_management import FileManagement
from assetutilities.common.update_deep import AttributeDict
from assetutilities.common.utilities import save_application_cfg
from assetutilities.common.yml_utilities import ymlInput

from assethold.modules.dividend_forecast.dividend_forecast import (
    DividendForecastWorkflow,
)
from assethold.modules.fundamentals.fundamentals import FundamentalsWorkflow
from assethold.modules.options.options import OptionsWorkflow
from assethold.modules.portfolio.portfolio import PortfolioWorkflow
from assethold.modules.property.property import PropertyWorkflow
from assethold.modules.risk_metrics.risk_metrics import RiskMetricsWorkflow
from assethold.modules.stocks.stocks import Stocks


def engine(inputfile: str = None, cfg: dict = None, config_flag: bool = True) -> dict:

    if cfg is None:
        inputfile = validate_arguments_run_methods(inputfile)
        cfg = ymlInput(inputfile, updateYml=None)
        cfg = AttributeDict(cfg)
        if cfg is None:
            raise ValueError("cfg is None")

    basename = cfg["basename"]

    fm = FileManagement()
    if config_flag:
        cfg_base = cfg
        cfg_base = fm.router(cfg_base)
    else:
        cfg_base = cfg

    logging.info(f"{basename}, application ... START")

    if basename == "stocks":
        stks = Stocks()
        cfg_base = stks.router(cfg_base)
    elif basename == "portfolio":
        workflow = PortfolioWorkflow()
        cfg_base = workflow.router(cfg_base)
    elif basename == "options":
        workflow = OptionsWorkflow()
        cfg_base = workflow.router(cfg_base)
    elif basename == "property":
        workflow = PropertyWorkflow()
        cfg_base = workflow.router(cfg_base)
    elif basename == "risk_metrics":
        workflow = RiskMetricsWorkflow()
        cfg_base = workflow.router(cfg_base)
    elif basename == "dividend_forecast":
        workflow = DividendForecastWorkflow()
        cfg_base = workflow.router(cfg_base)
    elif basename == "fundamentals":
        workflow = FundamentalsWorkflow()
        cfg_base = workflow.router(cfg_base)
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

    When inputfile is explicitly provided as a function argument,
    it takes priority over sys.argv (e.g. when called from tests or
    other Python code).
    """

    if inputfile is not None:
        if not os.path.isfile(inputfile):
            raise FileNotFoundError(f"Input file {inputfile} not found ... FAIL")
        return inputfile

    if len(sys.argv) > 1:
        if not os.path.isfile(sys.argv[1]):
            raise FileNotFoundError(f"Input file {sys.argv[1]} not found ... FAIL")
        return sys.argv[1]

    raise ValueError(
        "No input file provided via function argument or command-line argument ... FAIL"
    )
