# ABOUTME: Top-level stocks module that coordinates data retrieval and analysis.
# ABOUTME: Routes configuration through GetStockData and StockAnalysis pipelines.

# Reader imports
from assethold.modules.stocks.stock_analysis import StockAnalysis
from assethold.modules.stocks.get_stock_data import GetStockData


class Stocks:

    def __init__(self, data_provider=None, analyzer=None):
        self.data_provider = data_provider or GetStockData(cfg=None)
        self.analyzer = analyzer or StockAnalysis(cfg=None)

    def router(self, cfg):
        cfg, data = self.data_provider.router(cfg)
        cfg, analysis = self.analyzer.router(cfg, data)

        return cfg
