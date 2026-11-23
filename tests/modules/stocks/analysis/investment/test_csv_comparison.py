import pandas as pd

def compare_daily_returns_simple(manual_csv_path: str, ffn_csv_path: str, output_csv_path: str):
    """
    Compare manually calculated daily returns with ffn-calculated daily returns
    and save the discrepancies as a CSV file.
    """
    manual_data = pd.read_csv(manual_csv_path, index_col='Date', parse_dates=True)
    ffn_data = pd.read_csv(ffn_csv_path, index_col='Date', parse_dates=True)

    manual_returns = manual_data[['daily_returns']]
    ffn_returns = ffn_data[['daily_returns']]
    
    # Merge the two DataFrames on the 'Date' index
    comparison = manual_returns.merge(ffn_returns, left_index=True, right_index=True, suffixes=('_manual', '_ffn'))
    
    # Calculate the absolute difference between the two returns
    comparison['difference'] = abs(comparison['daily_returns_manual'] - comparison['daily_returns_ffn'])
    
    # Filter discrepancies where the difference exceeds a small tolerance
    discrepancies = comparison[comparison['difference'] > 1e-6]

    discrepancies.to_csv(output_csv_path)
    
    print(f"Comparison complete. Discrepancies saved to {output_csv_path}")

manual_csv_path = r"tests\modules\stocks\analysis\investment\results\Data\ffn_daily_returns.csv"
ffn_csv_path = r"tests\modules\stocks\analysis\investment\results\Data\single_investment.csv"
output_csv_path = r"tests\modules\stocks\analysis\investment\results\comparison_results.csv"

compare_daily_returns_simple(manual_csv_path, ffn_csv_path, output_csv_path)