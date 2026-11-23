# ABOUTME: Calculates single and multiple investment value from stock price data.
# ABOUTME: Computes daily returns, annual profit, and monthly return tables.

# Standard library imports
import logging
import os

# Third party imports
import pandas as pd


class InvestmentValue:

    def __init__(self):
        pass

    def router(self, cfg, daily_data):

        daily_data = self.single_investment(cfg, daily_data)
        daily_data = self.multiple_investment(daily_data)

        return cfg

    def single_investment(self, cfg, prices_data):

        prices_data = prices_data.copy()
        single_investment_cfg = cfg['investment_settings']

        initial_investment = single_investment_cfg['single']['investment']

        prices_data['investment'] = initial_investment
        prices_data['Units Bought'] = initial_investment / prices_data['Close']
        prices_data['daily_returns'] = prices_data['Close'].pct_change()
        prices_data['Value'] = prices_data['daily_returns'] + initial_investment

        prices_data['average_annual_investment'] = 0.0
        for idx, row in prices_data.iterrows():
            if idx != 0:
                date_diff = row['Date'] - prices_data['Date'].iloc[idx - 1]
                if hasattr(date_diff, 'days'):
                    days = date_diff.days
                else:
                    days = int(date_diff)
                average_annual_investment_increment = prices_data.at[idx - 1, 'investment'] * days / 365
                average_annual_investment = prices_data.at[idx - 1, 'average_annual_investment'] + average_annual_investment_increment
                prices_data.at[idx, 'average_annual_investment'] = average_annual_investment

        prices_data['average_days'] = prices_data['investment'] * (prices_data['Date'] - prices_data['Date'].iloc[0]).dt.days

        prices_data['annual_profit'] = (prices_data['Value'] - prices_data['investment']) / prices_data['average_annual_investment'] * 100

        self.save_results(cfg, prices_data, 'single_investment.csv')

        return prices_data

    def multiple_investment(self, prices_data):

        prices_data['Date'] = pd.to_datetime(prices_data['Date'])
        prices_data.set_index('Date', inplace=True)

        if not isinstance(prices_data.index, pd.DatetimeIndex):
            raise ValueError("prices_data index must be a pandas DatetimeIndex.")

        prices_data = prices_data.sort_index()

        monthly_close = prices_data['Close'].resample('ME').last()

        monthly_returns = monthly_close.pct_change()

        monthly_returns_df = monthly_returns.reset_index()
        monthly_returns_df['Year'] = monthly_returns_df['Date'].dt.year
        monthly_returns_df['Month'] = monthly_returns_df['Date'].dt.strftime('%b')
        monthly_returns_df = monthly_returns_df.pivot(index='Year', columns='Month', values='Close')

        monthly_returns_df.columns.name = None

        month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        monthly_returns_df = monthly_returns_df[month_order]
        monthly_returns_df = monthly_returns_df.reset_index()

        self.save_results_df(monthly_returns_df, 'multiple_investment.csv')

        return monthly_returns_df

    def calculate_interest(self, cfg, prices_data, total_investment):
        """
        Simple and compound interest based on cumulative investment.
        """
        annual_rate = 0.05
        principal = total_investment
        start_date = prices_data['Date'].iloc[0]
        end_date = prices_data['Date'].iloc[-1]
        time_in_years = (end_date - start_date).days / 365

        simple_interest = principal * annual_rate * time_in_years

        compound_interest = principal * ((1 + annual_rate) ** time_in_years - 1)

        return simple_interest, compound_interest

    def save_results(self, cfg, prices_data, file_name):
        if 'Analysis' not in cfg or 'analysis_root_folder' not in cfg.get('Analysis', {}):
            logging.warning("Skipping save_results: 'Analysis.analysis_root_folder' not configured")
            return
        csv_path = os.path.join(cfg['Analysis']['analysis_root_folder'], file_name)
        prices_data.to_csv(csv_path, index=False)

    def save_results_df(self, df, file_name):
        logging.info(f"Multiple investment results computed: {file_name}")
