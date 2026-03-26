<<<<<<< Updated upstream
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
=======
# Reader imports
from assethold.modules.stocks.stock_analysis import StockAnalysis
from assethold.modules.stocks.get_stock_data import GetStockData

stk_data = GetStockData(cfg=None)
stk_analysis = StockAnalysis(cfg=None)

class Stocks:
    
    def __init__(self):
        pass
    
    def router(self, cfg):

        cfg, data =  stk_data.router(cfg)
        cfg, analysis = stk_analysis.router(cfg, data)

        return cfg
>>>>>>> Stashed changes
