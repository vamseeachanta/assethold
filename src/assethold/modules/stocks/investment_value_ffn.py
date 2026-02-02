import logging
import os

import ffn
import matplotlib.pyplot as plt
import pandas as pd


class InvestmentValueFfn:

    def __init__(self):
        pass

    def router(self, cfg, prices_data):

        prices_data = self.prepare_data(prices_data)
        data = self.get_daily_returns(cfg, prices_data)
        data = self.get_monthly_returns(cfg, prices_data)

        return cfg

    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        fix up the data for analysis by ensuring the index is a DatetimeIndex.
        """
        if not isinstance(data.index, pd.DatetimeIndex):
            if 'Date' in data.columns:
                data['Date'] = pd.to_datetime(data['Date'])
                data.set_index('Date', inplace=True)
            else:
                raise ValueError("Data must include a 'Date' column to set as a DatetimeIndex.")

        self.get_statistics(data)
        return data

    def get_statistics(self, data):

        perf_stats = data.calc_stats()
        stats_summary = perf_stats.stats
        lookback_returns = perf_stats.lookback_returns

        return perf_stats, stats_summary, lookback_returns

    def get_daily_returns(self, cfg, prices_data):

        prices_data = prices_data.copy()
        returns = ffn.to_log_returns(prices_data['Close'])
        prices_data['daily_returns'] = returns

        self.plot_returns(cfg, returns, prices_data)
        self.save_results(cfg, prices_data, 'ffn_daily_returns.csv')

        return prices_data

    def get_monthly_returns(self, cfg, prices_data):

        prices_data = prices_data.copy()
        prices_data.sort_index(inplace=True)
        prices_data = prices_data[~prices_data.index.duplicated()]

        stats = prices_data['Close'].calc_stats()

        monthly_returns = stats.return_table

        self.save_results(cfg, monthly_returns, 'ffn_monthly_returns.csv')

        return monthly_returns

    def plot_returns(self, cfg, daily_returns, prices_data):
        import matplotlib.dates as mdates

        ticker = cfg['input']['ticker']

        daily_returns = daily_returns.dropna()
        daily_returns = daily_returns[:100]
        fig, ax = plt.subplots(figsize=(12, 6))

        plt.plot(daily_returns.index, daily_returns, label='Returns', color='green')
        plt.title('Daily Returns', fontsize=16)
        plt.xlabel('Date', fontsize=12)
        plt.ylabel('Returns', fontsize=12)
        plt.legend()
        ax.grid(True)

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))

        if 'Analysis' in cfg and 'analysis_root_folder' in cfg['Analysis']:
            plot_path = os.path.join(cfg['Analysis']['analysis_root_folder'], f'{ticker}_daily_returns.png')
            plt.savefig(plot_path)
        plt.close()

    def save_results(self, cfg, prices_data, file_name):
        if 'Analysis' not in cfg or 'analysis_root_folder' not in cfg.get('Analysis', {}):
            logging.warning("Skipping save_results: 'Analysis.analysis_root_folder' not configured")
            return
        ticker = cfg['input']['ticker']
        csv_path = os.path.join(cfg['Analysis']['analysis_root_folder'], f'{ticker}_{file_name}')
        prices_data.to_csv(csv_path, index=True)
