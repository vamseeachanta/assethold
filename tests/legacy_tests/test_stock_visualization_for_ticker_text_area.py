from threading import Thread
from dash import Dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from dashhtmlgrid.html_layout import get_html_layout
from dashhtmlgrid.data_table import get_dash_table_from_df

from assethold.finance_components import FinanceComponents
from assethold.stock_charts import StockCharts

global fc, sc, rerun_thread
fc = FinanceComponents()
sc = StockCharts()
rerun_thread = Thread()

dropdown_array = fc.fdata.get_tickers_nasdaq()

# Dashboard custom settings
grid_array = [
    'text_area', 'table', 'figure', 'figure', 'figure', 'figure', 'figure',
    'figure', 'figure', 'figure', 'figure', 'figure', 'figure', 'figure',
    'figure'
]

no_of_figures = grid_array.count('figure')
figure_settings = [{
    'id': 'figure_' + str(idx),
} for idx in range(0, no_of_figures)]

dropdown_settings = []

text_area_settings = [{
    'id': 'textarea-state',
    'value': 'RIG',
    'submit_text': 'Submit',
    'button_id': 'textarea-state-button'
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
    'text_area': text_area_settings,
    'table': table_settings,
    'figure': figure_settings,
}


def run_analysis_if_required(selected_dropdown_value):
    global fc
    if 'stock_ticker' not in fc.fdata.company_info.keys(
    ) or fc.fdata.company_info['stock_ticker'] != selected_dropdown_value:
        fc.stock_analysis_by_ticker(ticker=selected_dropdown_value)


def get_table_0_df(fc, selected_dropdown_value):
    df = fc.fdata.company_info['breakout_trend_indicators'].copy()
    return df


# Test scripts for a sample ticker
# run_analysis_if_required('RIG')
# df = get_table_0_df('RIG')
# plotly_data = sc.get_figure_5(fc, 'RIG')
# plotly_data = sc.get_figure_6(fc, 'RIG')
# plotly_data = sc.get_figure_7(fc, 'RIG')

# Initialize the app
app = Dash(__name__)
app.config.suppress_callback_exceptions = True

app.layout = get_html_layout(layout_settings_custom)

# @app.callback(Input(text_area_settings[0]['button_id'], 'n_clicks'),
#               State(text_area_settings[0]['id'], 'value'))
# def rerun_analysis(n_clicks, selected_dropdown_value):
#     if n_clicks > 0:
#         rerun_thread = Thread(run_analysis_if_required(selected_dropdown_value))
#         update_table_0()
#     else:
#         raise PreventUpdate


# Callback for Table #1 (i.e. Example table)
@app.callback(Output(table_settings[0]['html_id'], 'children'),
              Input(text_area_settings[0]['button_id'], 'n_clicks'),
              State(text_area_settings[0]['id'], 'value'))
def update_table_0(n_clicks, selected_dropdown_value):
    if n_clicks > 0:
        run_analysis_if_required(selected_dropdown_value)
        table_0_df = get_table_0_df(fc, fc.fdata.company_info['stock_ticker'])
        table = get_dash_table_from_df(table_0_df, table_settings, table_idx=0)
        return table
    else:
        raise PreventUpdate


@app.callback(Output(figure_settings[0]['id'], 'figure'),
              Input(text_area_settings[0]['button_id'], 'n_clicks'),
              State(text_area_settings[0]['id'], 'value'))
def update_figure_0(n_clicks, selected_dropdown_value):
    if n_clicks > 0:
        run_analysis_if_required(selected_dropdown_value)
        plotly_data = sc.get_figure_0(fc, selected_dropdown_value)
        return plotly_data
    else:
        raise PreventUpdate


@app.callback(Output(figure_settings[1]['id'], 'figure'),
              Input(text_area_settings[0]['button_id'], 'n_clicks'),
              State(text_area_settings[0]['id'], 'value'))
def update_figure_1(n_clicks, selected_dropdown_value):
    if n_clicks > 0:
        run_analysis_if_required(selected_dropdown_value)
        plotly_data = sc.get_figure_1(fc, selected_dropdown_value)
        return plotly_data
    else:
        raise PreventUpdate


@app.callback(Output(figure_settings[2]['id'], 'figure'),
              Input(text_area_settings[0]['button_id'], 'n_clicks'),
              State(text_area_settings[0]['id'], 'value'))
def update_figure_2(n_clicks, selected_dropdown_value):
    if n_clicks > 0:
        run_analysis_if_required(selected_dropdown_value)
        plotly_data = sc.get_figure_2(fc, selected_dropdown_value)
        return plotly_data
    else:
        raise PreventUpdate


@app.callback(Output(figure_settings[3]['id'], 'figure'),
              Input(text_area_settings[0]['button_id'], 'n_clicks'),
              State(text_area_settings[0]['id'], 'value'))
def update_figure_3(n_clicks, selected_dropdown_value):
    if n_clicks > 0:
        run_analysis_if_required(selected_dropdown_value)
        plotly_data = sc.get_figure_3(fc, selected_dropdown_value)
        return plotly_data
    else:
        raise PreventUpdate


@app.callback(Output(figure_settings[4]['id'], 'figure'),
              Input(text_area_settings[0]['button_id'], 'n_clicks'),
              State(text_area_settings[0]['id'], 'value'))
def update_figure_4(n_clicks, selected_dropdown_value):
    if n_clicks > 0:
        run_analysis_if_required(selected_dropdown_value)
        plotly_data = sc.get_figure_4(fc, selected_dropdown_value)
        return plotly_data
    else:
        raise PreventUpdate


@app.callback(Output(figure_settings[5]['id'], 'figure'),
              Input(text_area_settings[0]['button_id'], 'n_clicks'),
              State(text_area_settings[0]['id'], 'value'))
def update_figure_5(n_clicks, selected_dropdown_value):
    if n_clicks > 0:
        run_analysis_if_required(selected_dropdown_value)
        plotly_data = sc.get_figure_5(fc, selected_dropdown_value)
        return plotly_data
    else:
        raise PreventUpdate


@app.callback(Output(figure_settings[6]['id'], 'figure'),
              Input(text_area_settings[0]['button_id'], 'n_clicks'),
              State(text_area_settings[0]['id'], 'value'))
def update_figure_6(n_clicks, selected_dropdown_value):
    if n_clicks > 0:
        run_analysis_if_required(selected_dropdown_value)
        plotly_data = sc.get_figure_6(fc, selected_dropdown_value)
        return plotly_data
    else:
        raise PreventUpdate


@app.callback(Output(figure_settings[7]['id'], 'figure'),
              Input(text_area_settings[0]['button_id'], 'n_clicks'),
              State(text_area_settings[0]['id'], 'value'))
def update_figure_7(n_clicks, selected_dropdown_value):
    if n_clicks > 0:
        run_analysis_if_required(selected_dropdown_value)
        plotly_data = sc.get_figure_7(fc, selected_dropdown_value)
        return plotly_data
    else:
        raise PreventUpdate


@app.callback(Output(figure_settings[8]['id'], 'figure'),
              Input(text_area_settings[0]['button_id'], 'n_clicks'),
              State(text_area_settings[0]['id'], 'value'))
def update_figure_8(n_clicks, selected_dropdown_value):
    if n_clicks > 0:
        run_analysis_if_required(selected_dropdown_value)
        plotly_data = sc.get_figure_8(fc, selected_dropdown_value)
        return plotly_data
    else:
        raise PreventUpdate


@app.callback(Output(figure_settings[9]['id'], 'figure'),
              Input(text_area_settings[0]['button_id'], 'n_clicks'),
              State(text_area_settings[0]['id'], 'value'))
def update_figure_9(n_clicks, selected_dropdown_value):
    if n_clicks > 0:
        run_analysis_if_required(selected_dropdown_value)
        plotly_data = sc.get_figure_9(fc, selected_dropdown_value)
        return plotly_data
    else:
        raise PreventUpdate


@app.callback(Output(figure_settings[10]['id'], 'figure'),
              Input(text_area_settings[0]['button_id'], 'n_clicks'),
              State(text_area_settings[0]['id'], 'value'))
def update_figure_10(n_clicks, selected_dropdown_value):
    if n_clicks > 0:
        run_analysis_if_required(selected_dropdown_value)
        plotly_data = sc.get_figure_10(fc, selected_dropdown_value)
        return plotly_data
    else:
        raise PreventUpdate


@app.callback(Output(figure_settings[11]['id'], 'figure'),
              Input(text_area_settings[0]['button_id'], 'n_clicks'),
              State(text_area_settings[0]['id'], 'value'))
def update_figure_11(n_clicks, selected_dropdown_value):
    if n_clicks > 0:
        run_analysis_if_required(selected_dropdown_value)
        plotly_data = sc.get_figure_11(fc, selected_dropdown_value)
        return plotly_data
    else:
        raise PreventUpdate


@app.callback(Output(figure_settings[12]['id'], 'figure'),
              Input(text_area_settings[0]['button_id'], 'n_clicks'),
              State(text_area_settings[0]['id'], 'value'))
def update_figure_12(n_clicks, selected_dropdown_value):
    if n_clicks > 0:
        run_analysis_if_required(selected_dropdown_value)
        plotly_data = sc.get_figure_12(fc, selected_dropdown_value)
        return plotly_data
    else:
        raise PreventUpdate


if __name__ == '__main__':
    app.run_server(debug=True)
