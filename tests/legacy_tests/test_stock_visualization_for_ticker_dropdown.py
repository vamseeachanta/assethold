from dash import Dash
from dash.dependencies import Input, Output

from dashhtmlgrid.plt_children import get_figure
from dashhtmlgrid.html_layout import get_html_layout
from dashhtmlgrid.data_table import get_dash_table_from_df

from dashhtmlgrid.tests.example_stock_data import get_input_data, get_stock_data_df, get_drop_down_options
from dashhtmlgrid.tests.example_data_table import get_example_data_table_df

from assethold.common.data import AttributeDict
from assethold.finance_components import FinanceComponents
from assethold.stock_charts import StockCharts

from assethold.test.test_service_stock_analysis_run_all_tickers import \
    stock_analysis_by_ticker

fc = FinanceComponents()
sc = StockCharts()

dropdown_array = fc.fdata.get_tickers_nasdaq()
dropdown_options = get_drop_down_options(dropdown_array)

# Dashboard custom settings
grid_array = [
    'dropdown', 'table', 'figure', 'figure', 'figure', 'figure', 'figure',
    'figure', 'figure', 'figure', 'figure', 'figure', 'figure', 'figure',
    'figure', 'figure', 'figure'
]

no_of_figures = grid_array.count('figure')
figure_settings = [{
    'id': 'figure_' + str(idx),
} for idx in range(0, no_of_figures)]

dropdown_settings = [{
    'id': 'dropdownselector',
    'className': 'dropdownselector',
    "H2": 'Stock Analysis | Hold Strategies',
    "p1": ' ',
    "p2": 'Pick one or more options from the dropdown below.',
    'multiple_flag': True,
    'options': dropdown_options,
    'start_value':
        None    # Optional. None will default to 1st value from dropdown_options
}]

table_settings = [{
    "html_id": 'table_0_html',
    "H2": 'Breakout Criteria',
    'id': 'table_0_data',
    "p1": 'All Rows should pass',
}]

layout_settings_custom = {
    'grid_array': grid_array,
    'dropdown': dropdown_settings,
    'table': table_settings,
    'figure': figure_settings,
}


def run_analysis_if_required(selected_dropdown_value):
    global fc
    if 'stock_ticker' not in fc.fdata.company_info.keys(
    ) or fc.fdata.company_info['stock_ticker'] != selected_dropdown_value[0]:
        fc = stock_analysis_by_ticker(ticker=selected_dropdown_value[0])
        data_dict = fc.get_data_dict()
        fc.UI_cfg = fc.get_stock_analysis_UI_cfg(data_dict)


def get_table_0_df(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)
    df = fc.fdata.company_info['breakout_trend_indicators'].copy()
    return df


def get_figure_0(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)

    ta = fc.fanalysis.ta.copy()
    plot_cfg = {'ta': ta, 'ticker': selected_dropdown_value[0]}
    plotly_data = sc.create_price_chart(plot_cfg)

    return plotly_data


def get_figure_1(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)

    ta = fc.fanalysis.ta.copy()
    plot_cfg = {'ta': ta, 'ticker': selected_dropdown_value[0]}
    plotly_data = sc.create_volume_on_balance(plot_cfg)

    return plotly_data


def get_figure_2(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)

    ta = fc.fanalysis.ta.copy()
    plot_cfg = {'ta': ta, 'ticker': selected_dropdown_value[0]}
    plotly_data = sc.create_eom_chart(plot_cfg)

    return plotly_data


def get_figure_3(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)

    ta = fc.fanalysis.ta.copy()
    plot_cfg = {'ta': ta, 'ticker': selected_dropdown_value[0]}
    plotly_data = sc.create_cfm_chart(plot_cfg)

    return plotly_data


def get_figure_4(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)

    ta = fc.fanalysis.ta.copy()
    plot_cfg = {'ta': ta, 'ticker': selected_dropdown_value[0]}
    plotly_data = sc.create_wt_price_chart(plot_cfg)

    return plotly_data


def get_figure_5(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)

    df_insider_by_timeline = fc.fanalysis.insider_analysis_by_timeline_df.copy()
    plot_cfg = {
        'df_insider_by_timeline': df_insider_by_timeline,
        'ticker': selected_dropdown_value[0]
    }
    plotly_data = sc.create_insider_by_timeline_chart(plot_cfg)

    return plotly_data


def get_figure_6(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)

    df_insider_by_relation = fc.fanalysis.insider_analysis_by_relation_df.copy()
    plot_cfg = {
        'df_insider_by_relation': df_insider_by_relation,
        'ticker': selected_dropdown_value[0]
    }
    plotly_data = sc.create_insider_by_relation_chart(plot_cfg)

    return plotly_data


def get_figure_7(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)

    ta = fc.fanalysis.ta.copy()
    df_insider_sell = fc.fanalysis.insider_df_sell.copy()
    df_insider_buy = fc.fanalysis.insider_df_buy.copy()
    plot_cfg = {
        'ta': ta,
        'df_insider_sell': df_insider_sell,
        'df_insider_buy': df_insider_buy,
        'ticker': selected_dropdown_value[0]
    }
    plotly_data = sc.create_insider_relative_sale_chart(plot_cfg)

    return plotly_data


def get_figure_8(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)

    ta = fc.fanalysis.ta.copy()
    df_insider_sell = fc.fanalysis.insider_df_sell.copy()
    df_insider_buy = fc.fanalysis.insider_df_buy.copy()
    plot_cfg = {
        'ta': ta,
        'df_insider_sell': df_insider_sell,
        'df_insider_buy': df_insider_buy,
        'ticker': selected_dropdown_value[0]
    }
    plotly_data = sc.create_insider_relative_buy_chart(plot_cfg)

    return plotly_data


def get_figure_9(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)

    df_institutional_holders = fc.fanalysis.df_institutional_holders.copy()
    plot_cfg = {
        'df_institutional_holders': df_institutional_holders,
        'ticker': selected_dropdown_value[0]
    }
    plotly_data = sc.create_institution_chart(plot_cfg)

    return plotly_data


def get_figure_10(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)

    ta = fc.fanalysis.ta.copy()
    plot_cfg = {'ta': ta, 'ticker': selected_dropdown_value[0]}
    plotly_data = sc.create_volatility_chart(plot_cfg)

    return plotly_data


def get_figure_11(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)

    ta = fc.fanalysis.ta.copy()
    plot_cfg = {'ta': ta, 'ticker': selected_dropdown_value[0]}
    plotly_data = sc.create_volatility_width_chart(plot_cfg)

    return plotly_data


def get_figure_12(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)

    ta = fc.fanalysis.ta.copy()
    plot_cfg = {'ta': ta, 'ticker': selected_dropdown_value[0]}
    plotly_data = sc.create_volatility_high_low_band_chart(plot_cfg)

    return plotly_data


def get_figure_13(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)

    ta = fc.fanalysis.ta.copy()
    plot_cfg = {'ta': ta, 'ticker': selected_dropdown_value[0]}
    plotly_data = sc.create_ulcer_chart(plot_cfg)

    return plotly_data


def get_figure_14(selected_dropdown_value):
    run_analysis_if_required(selected_dropdown_value)

    ta = fc.fanalysis.ta.copy()
    plot_cfg = {'ta': ta, 'ticker': selected_dropdown_value[0]}
    plotly_data = sc.create_strength_all_chart(plot_cfg)

    return plotly_data


# Test scripts for Example Operations
# df = get_table_0_df(['A'])
plotly_data = get_figure_5(['A'])
plotly_data = get_figure_6(['A'])
plotly_data = get_figure_7(['A'])

# Initialize the app
app = Dash(__name__)
app.config.suppress_callback_exceptions = False

app.layout = get_html_layout(layout_settings_custom)


@app.callback(Output(figure_settings[0]['id'], 'figure'),
              [Input('dropdownselector', 'value')])
def update_figure_0(selected_dropdown_value):

    plotly_data = get_figure_0(selected_dropdown_value)

    return plotly_data


@app.callback(Output(figure_settings[1]['id'], 'figure'),
              [Input('dropdownselector', 'value')])
def update_figure_1(selected_dropdown_value):

    plotly_data = get_figure_1(selected_dropdown_value)

    return plotly_data


@app.callback(Output(figure_settings[2]['id'], 'figure'),
              [Input('dropdownselector', 'value')])
def update_figure_2(selected_dropdown_value):

    plotly_data = get_figure_2(selected_dropdown_value)

    return plotly_data


@app.callback(Output(figure_settings[3]['id'], 'figure'),
              [Input('dropdownselector', 'value')])
def update_figure_3(selected_dropdown_value):

    plotly_data = get_figure_3(selected_dropdown_value)

    return plotly_data


@app.callback(Output(figure_settings[4]['id'], 'figure'),
              [Input('dropdownselector', 'value')])
def update_figure_4(selected_dropdown_value):

    plotly_data = get_figure_4(selected_dropdown_value)

    return plotly_data


@app.callback(Output(figure_settings[5]['id'], 'figure'),
              [Input('dropdownselector', 'value')])
def update_figure_5(selected_dropdown_value):

    plotly_data = get_figure_5(selected_dropdown_value)

    return plotly_data


@app.callback(Output(figure_settings[6]['id'], 'figure'),
              [Input('dropdownselector', 'value')])
def update_figure_6(selected_dropdown_value):

    plotly_data = get_figure_6(selected_dropdown_value)

    return plotly_data


@app.callback(Output(figure_settings[7]['id'], 'figure'),
              [Input('dropdownselector', 'value')])
def update_figure_7(selected_dropdown_value):

    plotly_data = get_figure_7(selected_dropdown_value)

    return plotly_data


@app.callback(Output(figure_settings[8]['id'], 'figure'),
              [Input('dropdownselector', 'value')])
def update_figure_8(selected_dropdown_value):

    plotly_data = get_figure_8(selected_dropdown_value)

    return plotly_data


@app.callback(Output(figure_settings[9]['id'], 'figure'),
              [Input('dropdownselector', 'value')])
def update_figure_9(selected_dropdown_value):

    plotly_data = get_figure_9(selected_dropdown_value)

    return plotly_data


@app.callback(Output(figure_settings[10]['id'], 'figure'),
              [Input('dropdownselector', 'value')])
def update_figure_10(selected_dropdown_value):

    plotly_data = get_figure_10(selected_dropdown_value)

    return plotly_data


@app.callback(Output(figure_settings[11]['id'], 'figure'),
              [Input('dropdownselector', 'value')])
def update_figure_11(selected_dropdown_value):

    plotly_data = get_figure_11(selected_dropdown_value)

    return plotly_data


@app.callback(Output(figure_settings[12]['id'], 'figure'),
              [Input('dropdownselector', 'value')])
def update_figure_12(selected_dropdown_value):

    plotly_data = get_figure_12(selected_dropdown_value)

    return plotly_data


# Callback for Table #1 (i.e. Example table)
@app.callback(Output(table_settings[0]['html_id'], 'children'),
              [Input('dropdownselector', 'value')])
def update_table_0(selected_dropdown_value):

    table_0_df = get_table_0_df(selected_dropdown_value)
    table = get_dash_table_from_df(table_0_df, table_settings, table_idx=0)

    return table


if __name__ == '__main__':
    app.run_server(debug=True)
