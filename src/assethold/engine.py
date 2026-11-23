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
from assethold.modules.market_alerts.market_alerts import MarketAlertsWorkflow
from assethold.modules.options.options import OptionsWorkflow
from assethold.modules.portfolio.portfolio import PortfolioWorkflow
from assethold.modules.property.property import PropertyWorkflow
from assethold.modules.risk_metrics.risk_metrics import RiskMetricsWorkflow
from assethold.modules.stocks.stocks import Stocks

from assethold.common.configure_embed import configure_embed
from assethold.modules.workflow_io import output_root


def engine(
    inputfile: str = None,
    cfg: dict = None,
    config_flag: bool = True,
    root_folder: str = None,
    log_to_file: bool = True,
    embed: bool = False,
) -> dict:
    """Run an assethold workflow.

    Additive params (workspace-hub#3308, mirroring assetutilities #3297);
    defaults are byte-identical to today's assethold CLI behavior:

    - ``root_folder`` (default None): the injected sandbox root for the
      ``embed`` path. All result + cfg-dump writes land under it.
    - ``log_to_file`` (default True): carried onto ``Analysis`` by the embed
      path for #3297 parity; the default path is unaffected.
    - ``embed`` (default False): when True, configure the caller's in-memory
      ``cfg`` under ``root_folder`` (re-entrant, sandboxed) and dispatch there
      -- the embeddable run path #3287 consumes. Requires ``root_folder``.
    """

    if cfg is None:
        inputfile = validate_arguments_run_methods(inputfile)
        cfg = ymlInput(inputfile, updateYml=None)
        cfg = AttributeDict(cfg)
        if cfg is None:
            raise ValueError("cfg is None")

    basename = cfg["basename"]

    fm = FileManagement()

    if embed:
        # ---- EMBED PATH (workspace-hub#3308; the crux #3287 consumes) ----
        if root_folder is None:
            raise ValueError("engine(embed=True) requires root_folder")
        cfg_base = configure_embed(
            cfg, basename, root_folder, log_to_file=log_to_file
        )
        cfg_base = fm.router(cfg_base)
        logging.info(f"{basename}, application ... START")
        with output_root(root_folder):
            cfg_base = _dispatch(basename, cfg_base)
        save_application_cfg(cfg_base=cfg_base)
        logging.info(f"{basename}, application ... END")
        return cfg_base

    # ---- DEFAULT PATH (unchanged byte-identical) ----
    if config_flag:
        cfg_base = cfg
        cfg_base = fm.router(cfg_base)
    else:
        cfg_base = cfg

    logging.info(f"{basename}, application ... START")

    cfg_base = _dispatch(basename, cfg_base)

    save_application_cfg(cfg_base=cfg_base)
    logging.info(f"{basename}, application ... END")

    return cfg_base


def _dispatch(basename: str, cfg_base: dict) -> dict:
    """Route ``cfg_base`` to the workflow router for ``basename``.

    Pure refactor (workspace-hub#3308): the if/elif chain extracted verbatim so
    the default and embed paths share one dispatch site. Same branches, same
    ``raise Exception`` for an unknown basename.
    """
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
    elif basename == "market_alerts":
        workflow = MarketAlertsWorkflow()
        cfg_base = workflow.router(cfg_base)
    else:
        raise Exception(f"Analysis for basename: {basename} not found. ... FAIL")

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
