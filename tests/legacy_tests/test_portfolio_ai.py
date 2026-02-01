# Third party imports
import pandas as pd

# Read CSV data into a pandas DataFrame
#TODO dividends need to be formatted and read
data_format = 'fidelity'
file_path = 'src/assethold/data/stocks/client1/2020.csv'
# df = pd.read_csv(file_path, on_bad_lines='skip')

# Define the expected columns
expected_columns = ['Run Date', 'Account', 'Action', 'Symbol', 'Description', 'Type', 'Quantity', 'Price ($)', 'Commission ($)', 'Fees ($)', 'Accrued Interest ($)', 'Amount ($)', 'Settlement Date']

# Read the CSV file, ignoring rows with more than 13 columns
df = pd.read_csv(file_path, usecols=range(13), names=expected_columns, header=0, on_bad_lines='skip')

# Convert 'Run Date' to datetime
df['Run Date'] = pd.to_datetime(df['Run Date'])


# Calculate cumulative value by account and symbol
df['Amount ($)'] = pd.to_numeric(df['Amount ($)'], errors='coerce').fillna(0)

# Separate transactions by 'Account' column into individual DataFrames
accounts = df['Account'].unique()
account_dfs = {account: df[df['Account'] == account] for account in accounts}

print(account_dfs)

# Calculate cumulative value by account and symbol
cumulative_values = {}
for account, account_df in account_dfs.items():
    cumulative_values[account] = account_df['Amount ($)'].sum()

print(cumulative_values)

# Calculate cumulative value by symbol
cumulative_values = {}
for account, account_df in account_dfs.items():
    symbols = account_df['Symbol'].unique()
    symbol_dfs = {symbol: account_df[account_df['Symbol'] == symbol] for symbol in symbols}
    cumulative_values[account] = {symbol: symbol_df['Amount ($)'].sum() for symbol, symbol_df in symbol_dfs.items()}

print(cumulative_values)