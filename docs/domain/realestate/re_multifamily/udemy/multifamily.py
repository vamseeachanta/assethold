import os
import json
import pprint
import pandas as pd
import pathlib
from multifamily_analysis import MultiFamily
from multifamily_analysis import MultiFamilyCharts

mf = MultiFamily()

config_filenames = ['multifamily_2.yaml', 'multifamily_4.yaml']
config_outputs = []

for config_filename in config_filenames:
    config = mf.get_config_data(config_filename=config_filename)
    config = mf.add_missing_inputs(config=config)
    config = mf.get_metrics(config)

    config_outputs.append(config)
    print("=======================================")
    print("For Project A:")
    pprint.pprint(config['projects'][0])

    output_filename = os.path.join(
        pathlib.Path(__file__).resolve().parent,
        config_filename.split('.')[0] + '_out.yaml')
    with open(output_filename, 'w') as output_file:
        output_file.write(json.dumps(config, indent=4))

mfc = MultiFamilyCharts()
mfc.get_common_chart_data(config_outputs)
mfc.get_all_charts(config_outputs)
'''
TODO 
a/ Increase incentive brackets further
b/ Add more breakdown to expenses, renovations, etc.
c/ Automate market research numbers using python tools
'''