import pandas as pd
from deepdiff import DeepDiff
import yaml

def compare_daily_returns(manual_csv_path: str, ffn_csv_path: str, output_yaml_path: str):
    
    manual_data = pd.read_csv(manual_csv_path, index_col='Date', parse_dates=True)
    ffn_data = pd.read_csv(ffn_csv_path, index_col='Date', parse_dates=True)
    
    manual_returns = manual_data[['daily_returns']]
    ffn_returns = ffn_data[['daily_returns']]

    manual_returns.sort_index(inplace=True)
    ffn_returns.sort_index(inplace=True)

    differences = DeepDiff(
        manual_returns,
        ffn_returns,
        significant_digits=6,  
        ignore_order=True      
    )
    

    with open(output_yaml_path, 'w') as yaml_file:
        yaml.dump(differences, yaml_file)
    
    print(f"Comparison complete. Results saved to {output_yaml_path}")

manual_csv = r"tests\modules\stocks\analysis\investment\results\Data\ffn_daily_returns.csv"
ffn_csv = r"tests\modules\stocks\analysis\investment\results\Data\single_investment.csv"
output_yaml = r"tests\modules\stocks\analysis\investment\results\comparison_results.yaml"

compare_daily_returns(manual_csv, ffn_csv, output_yaml)
