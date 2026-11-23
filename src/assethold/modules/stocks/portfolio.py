import pandas as pd #noqa
import yaml #noqa
import numpy as np #noqa
import os #noqa

class Portfolio:
    
    def __init__(self):
        pass

    def router(self, cfg):
        self.cfg = cfg

        results_path = r"src\assethold\tests\test_data\analysis\Portfolio\results\Data" 
        os.makedirs(results_path, exist_ok=True)  

        cumulative_by_account = {}
        cumulative_by_symbol = {}
        years_data = cfg['portfolio']

        for key, file_path in years_data.items():
            year = file_path.split('/')[-1].split('.')[0]
            year_data = self.portfolio_value(file_path)

            for account, value in year_data['by_account'].items():
                if account not in cumulative_by_account:
                    cumulative_by_account[account]={}
                cumulative_by_account[account][year]=value

            for symbol, value in year_data['by_symbol'].items():
                if symbol not in cumulative_by_symbol:
                    cumulative_by_symbol[symbol]={}
                cumulative_by_symbol[symbol][year]=value

            df_account = pd.DataFrame(cumulative_by_account)
            df_symbol = pd.DataFrame(cumulative_by_symbol)

            df_account.to_csv(os.path.join(results_path,"by_account.csv"))
            df_symbol.to_csv(os.path.join(results_path,"by_symbol.csv"))

        print(f"****Cumulative values for each year have been saved successfully.****")
        print()

        return cfg

    def portfolio_value(self, file_path):

        expected_columns = [
            'Run Date', 'Account', 'Action', 'Symbol', 'Description', 'Type',
            'Quantity', 'Price ($)', 'Commission ($)', 'Fees ($)', 
            'Accrued Interest ($)', 'Amount ($)', 'Settlement Date'
        ]

        df = pd.read_csv(file_path, usecols=range(13), names=expected_columns, header=0, on_bad_lines='skip')

        df['Run Date'] = pd.to_datetime(df['Run Date'])
        df['Amount ($)'] = pd.to_numeric(df['Amount ($)'], errors='coerce').fillna(0)
        df['Symbol'] = df['Symbol'].str.strip()
        df['Symbol'] = df['Symbol'].replace('', np.nan) # replace empty strings with NaN
        df['Account'] = df['Account'].str.strip()

        #  replace missing 'Symbol' with 'cash' in brokerage and IRA accounts.
        #  Accounts are matched by type prefix, never by account number.
        no_symbol = df['Symbol'].isna()
        cash_action = df['Action'].str.contains('cash', case=False, na=False)
        brokerage_acc = df['Account'].str.startswith(('Individual', 'Traditional IRA'), na=False)
        df.loc[brokerage_acc & no_symbol & cash_action, 'Symbol'] = 'cash'

        #  Employer-plan rows carry the fund name in Description, not Symbol.
        #  The plan account name is personal, so it comes from the environment.
        employer_plan = os.environ.get('ASSETHOLD_EMPLOYER_PLAN_ACCOUNT', 'EMPLOYEE')
        employer_acc = df['Account'].str.contains(employer_plan, case=False, regex=False, na=False) & no_symbol
        df.loc[employer_acc, 'Symbol'] = df.loc[employer_acc, 'Description']

        accounts = df['Account'].unique()
        account_dfs = {account: df[df['Account'] == account] for account in accounts}

        # Cumulative metrics by account
        cumulative_by_account = {}
        for account, account_df in account_dfs.items():
            cumulative_by_account[account] = account_df['Amount ($)'].sum()

        cumulative_by_symbol = {}
        for account, account_df in account_dfs.items():
            symbols = account_df['Symbol'].unique()
            symbol_dfs = {symbol: account_df[account_df['Symbol'] == symbol] for symbol in symbols}
            cumulative_by_symbol[account] = {symbol: symbol_df['Amount ($)'].sum() for symbol, symbol_df in symbol_dfs.items()}

        return {'by_account': cumulative_by_account, 'by_symbol': cumulative_by_symbol}
