# Standard library imports
import os  # noqa

# Third party imports
import matplotlib.pyplot as plt  # noqa
import pandas as pd  # noqa
import pytz
from assetutilities.common.update_deep import update_deep_dictionary

# Reader imports
from assethold.modules.stocks.investment_value import InvestmentValue
from assethold.modules.stocks.investment_value_ffn import InvestmentValueFfn
from assethold.modules.stocks.portfolio import Portfolio


class StockAnalysis():

    def __init__(self, cfg, portfolio=None, investment_value=None, investment_value_ffn=None):
        self.cfg = cfg
        self.portfolio = portfolio or Portfolio()
        self.iv = investment_value or InvestmentValue()
        self.ivf = investment_value_ffn or InvestmentValueFfn()
        self.insider_analysis_by_relation_df = pd.DataFrame()
        self.insider_analysis_by_timeline_df = pd.DataFrame()
        self.call_effective_value_df = pd.DataFrame()
        self.call_effective_value_df_filtered = pd.DataFrame()
        self.insider_info = None
        self.insider_df_buy = pd.DataFrame()
        self.insider_df_sell = pd.DataFrame()
        self.status = {'insider': {}}

    def router(self, cfg, data):
        """
        Router function for StockAnalysis
        """
        analysis_output = {}
        status = {}
        analysis_status = {}
        analysis = {}
        if 'analysis' in cfg and cfg['analysis'].get('breakout', False):
            daily_data = data['daily']['data']
            daily_data['Date'] = pd.to_datetime(daily_data['Date'])
            if 'period' in cfg.get('data', {}):
                period = cfg['data']['period']
                daily_data = daily_data[daily_data['Date'] > pd.Timestamp.now() - pd.Timedelta(days=period)] 
            cfg, breakout_trend = self.breakout_trend_analysis(cfg, daily_data)

            analysis_output = {
                'breakout_trend': breakout_trend
            }

            analysis_status = {'breakout_trend': breakout_trend['status']}
            analysis = {'data': analysis_output, 'status': status}

        elif 'analysis' in cfg and cfg['analysis'].get('portfolio', False):
            cfg = self.portfolio.router(cfg)
        elif 'analysis' in cfg and cfg['analysis'].get('investment', False):
            ticker_data = data['daily']['data']
            cfg = self.iv.router(cfg, ticker_data)
        elif 'analysis' in cfg and cfg['analysis'].get('ffn', False):
            ticker_data = data['daily']['data']
            cfg = self.ivf.router(cfg, ticker_data)
        else:
            raise Exception("Analysis not requested by user.")

        cfg_status_dict = {cfg['basename']: {'analysis': {'status': analysis_status}}}
        cfg = update_deep_dictionary(cfg, cfg_status_dict)

        return cfg, analysis

    def breakout_trend_analysis(self,cfg, daily_data):

        self.status.update({'breakout_trend': True})
        self.breakout_summary_array = []
        columns = ['Description', 'Value']
        breakout_df = pd.DataFrame(columns=columns)
        breakout_df.loc[len(breakout_df)] = self.check_if_price_above_150_and_200_moving(daily_data)
        breakout_df.loc[len(breakout_df)] = self.check_if_150_moving_above_200_moving(daily_data)
        breakout_df.loc[len(breakout_df)] = self.check_if_200_moving_up_for_1mo(daily_data)
        breakout_df.loc[len(breakout_df)] = self.check_if_50_day_above_150_and_200_moving(daily_data)
        breakout_df.loc[len(breakout_df)] = self.check_if_price_above_50_moving(daily_data)
        breakout_df.loc[len(breakout_df)] = self.check_if_price_above_1p3_52wk_low(daily_data)
        breakout_df.loc[len(breakout_df)] = self.check_if_price_near_52wk_high_range(daily_data)

        breakout_trend = {'data': breakout_df.to_dict(orient='records'), 'status': True} 
        
        self.save_plots(cfg,breakout_df,daily_data)
        
        return cfg, breakout_trend
    
    def save_plots(self,cfg,breakout_df,daily_data):
        
        self.plot_breakout_trend(cfg,breakout_df,daily_data)
        self.save_and_close_plots(cfg)

    def plot_breakout_trend(self, cfg, breakout_df, daily_data):

        # Standard library imports
        import re  # noqa

        # Third party imports
        import matplotlib.dates as mdates  # noqa

        # Use .loc to modify the 'Date' column directly
        daily_data.loc[:, 'Date'] = pd.to_datetime(daily_data['Date'])

        def extract_analysis(value_str, description):
             
            if not isinstance(description, str):
                description = str(description)
    
            if isinstance(value_str, bool):
                return value_str, {}

            value_str = str(value_str)

            analysis = re.findall(r'\[.*?\]', value_str)
            value_cleaned = re.sub(r'\[.*?\]', '', value_str).strip()

            if value_cleaned in ['True', 'False']:
                value_cleaned = value_cleaned == 'True'

            description_cleaned = re.sub(r'\[.*?\]', '', description).strip()

            cleaned_analysis = {}
            if analysis:
                for part in analysis:
                    key = re.sub(r'.*\[(.*)\].*', r'\1', description) 
                    value = part.strip('[]').replace('mo.', '').replace('%', '').strip() 
                    if 'mo.' in key:
                        cleaned_analysis[key] = [f'{value}']
                    elif '%' in key:
                        cleaned_analysis[key] = [f'{value}']
                    else:
                        cleaned_analysis[key] = [value]

            return value_cleaned, cleaned_analysis if cleaned_analysis else {}

        breakout_analysis_df = pd.DataFrame(columns=['Description', 'Value', 'Analysis'])

        for index, row in breakout_df.iterrows():
            description = row['Description']
            value_str = row['Value']

            value_cleaned, analysis = extract_analysis(value_str, description)

            # Add to the cleaned DataFrame
            breakout_analysis_df.loc[index] = [
                re.sub(r'\[.*?\]', '', description).strip(), 
                value_cleaned,                                   
                analysis                                         
            ]
        
        breakout_daily_data_trend_df = pd.DataFrame(columns=[
        'Date', 'Close','Price Above 150 & 200 day avgs.', '150 day avg. above 200 day avg.',
        '200 day avg. uptrend for 1 mo [n mo.]', '50 day avg. Above 150 & 200 day avgs.',
        'Price Above 50 day avg. [x; y %]', 'Price 30% Above 52 wk low [% Above]', 
        'Price within 25% Of 52 wk high range [% value]', 'no_of_fails', 'plot_color'
            ])

        colors = []  # For plot color points 

        trend_data = []

        for idx, row in daily_data.iterrows():
            
            # Store the results of checks in variables
            price_above_150_and_200 = self.check_if_price_above_150_and_200_moving(row, is_single_row=True)[1]
            avg_150_above_200 = self.check_if_150_moving_above_200_moving(row, is_single_row=True)[1]
            avg_200_uptrend_1mo = self.breakout_plot_helper(daily_data, idx)[1]
            avg_50_above_150_and_200 = self.check_if_50_day_above_150_and_200_moving(row, is_single_row=True)[1]
            price_above_50 = self.check_if_price_above_50_moving(row, is_single_row=True)[1].split()[0] == 'True'
            price_above_1p3_52wk_low = self.breakout_plot_helper_2(daily_data, idx)[1]
            price_near_52wk_high_range = self.breakout_plot_helper_3(daily_data, idx)[1]

            # Use stored results to calculate failed_conditions
            failed_conditions = sum([not price_above_150_and_200, not avg_150_above_200, not avg_200_uptrend_1mo,
                                     not avg_50_above_150_and_200, not price_above_50, not price_above_1p3_52wk_low,
                                     not price_near_52wk_high_range])
            
            plot_color = 'green' if failed_conditions == 0 else 'gold' if failed_conditions == 1 else 'red'
            colors.append(plot_color)


            trend_data.append({
            'Date': row['Date'],
            'Close': row['Close'],
            'Price Above 150 & 200 day avgs.': 'True' if price_above_150_and_200 else 'False',
            '150 day avg. above 200 day avg.': 'True' if avg_150_above_200 else 'False',
            '200 day avg. uptrend for 1 mo': 'True' if avg_200_uptrend_1mo else 'False',
            '50 day avg. Above 150 & 200 day avgs.': 'True' if avg_50_above_150_and_200 else 'False',
            'Price Above 50 day avg.': 'True' if price_above_50 else 'False',
            'Price 30% Above 52 wk low': 'True' if price_above_1p3_52wk_low else 'False',
            'Price within 25% of 52 wk high range': 'True' if price_near_52wk_high_range else 'False',
            'no_of_fails': failed_conditions,
            'plot_color': plot_color
             })
                
            
        ticker = cfg['input']['ticker']
        breakout_daily_data_trend_df = pd.DataFrame(trend_data) 

        csv_file_path = f'tests/modules/stocks/analysis/breakout/results/Data/breakout_trend_{ticker}.csv'
        breakout_daily_data_trend_df.to_csv(csv_file_path, index=False) 
           
              
        # Apply colors only when there's a change in plot color
        filtered_colors = [colors[0]]  # always include the first color
        filtered_dates = [daily_data['Date'].iloc[0]]  
        filtered_close = [daily_data['Close'].iloc[0]]  

        for i in range(1, len(colors)):
            if colors[i] != colors[i - 1]:  # apply color when there is change in plot color
                filtered_colors.append(colors[i])
                filtered_dates.append(daily_data['Date'].iloc[i])
                filtered_close.append(daily_data['Close'].iloc[i])
        
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(daily_data['Date'], daily_data['Close'], color='skyblue',label='Close Price')

        ax.scatter(filtered_dates, filtered_close, color= filtered_colors, s=40)

        ax.scatter([], [], color='green', label='breakout 0 fails')
        ax.scatter([], [], color='gold', label='breakout 1 fail')
        ax.scatter([], [], color='red', label='More than 1 fail')

        ax.set_title('Breakout Trend Analysis')
        ax.set_xlabel('Date')
        ax.set_ylabel('Price')
        ax.legend()
        ax.grid(True)

        #ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%d'))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y')) # sets date in months 
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3)) # sets interval of 3 months

        plt.xticks(rotation=45) # rotates x-axis labels
        fig.autofmt_xdate() # auto formats x-axis date
    

    def check_if_price_above_150_and_200_moving(self, daily_data, close="Close", is_single_row=False):

        description = 'Price Above 150 & 200 day avgs.'
        if is_single_row:
            value = ( daily_data[close] > daily_data['150_day_rolling'] if pd.notna(daily_data['150_day_rolling']) else True 
                     ) and ( daily_data[close] > daily_data['200_day_rolling'] if pd.notna(daily_data['200_day_rolling']) else True )
        else:
            value = ( daily_data.iloc[-1][close] > daily_data.iloc[-1]['150_day_rolling'] if pd.notna(daily_data.iloc[-1]['150_day_rolling']) else True
                    )  and ( daily_data.iloc[-1][close] > daily_data.iloc[-1]['200_day_rolling'] if pd.notna(daily_data.iloc[-1]['200_day_rolling']) else True )
        
        return [description, value]

    def check_if_150_moving_above_200_moving(self, daily_data, is_single_row=False):

        description = '150 day avg. above 200 day avg.'
        if is_single_row:
            value =  daily_data['150_day_rolling'] > daily_data['200_day_rolling'] if pd.notna(daily_data['200_day_rolling']) else True 
        else:
            value = daily_data.iloc[-1]['150_day_rolling'] > daily_data.iloc[-1]['200_day_rolling'] if pd.notna(daily_data.iloc[-1]['200_day_rolling']) else True

        return [description, value]

    def check_if_200_moving_up_for_1mo(self, daily_data):

        description = '200 day avg. uptrend for 1 mo [n mo.]'
        no_of_months_trend_above = self.get_200_moving_up_for_n_mo(daily_data)
        value = no_of_months_trend_above >= 1

        return [description, str(value) + " [{} mo.]".format(no_of_months_trend_above)]

    def get_200_moving_up_for_n_mo(self, daily_data):

        # Standard library imports
        import datetime
        
        daily_data = daily_data.copy() 
        # Use .loc to safely assign the new column to avoid SettingWithCopyWarning
        daily_data.loc[:, '200_day_diff'] = daily_data['200_day_rolling'].diff(periods=1).values

        no_of_months_trend_above = 0
        half_months = 11
        for no_of_half_months in range(1, half_months):
            no_of_months_trend_above = 0.5 * (no_of_half_months - 1)
            days_period = 0.5 * no_of_half_months * 30
            start_time = daily_data.Date.iloc[-1] + datetime.timedelta(
                days=-days_period)
            if start_time > daily_data.Date.iloc[0]:
                daily_data_temp = daily_data[daily_data.Date > start_time].copy()
                if daily_data_temp['200_day_diff'].min() > 0:
                    no_of_months_trend_above = 0.5 * (no_of_half_months - 1)
                else:
                    break
            else:
                break

        return no_of_months_trend_above

    def check_if_50_day_above_150_and_200_moving(self, daily_data, is_single_row=False):

        description = '50 day avg. Above 150 & 200 day avgs.'
        if is_single_row:
            value = ( daily_data['50_day_rolling'] > daily_data['150_day_rolling'] if pd.notna(daily_data['150_day_rolling']) else True 
                     ) and ( daily_data['50_day_rolling'] > daily_data['200_day_rolling'] if pd.notna(daily_data['200_day_rolling']) else True )
        else:
            value = ( daily_data.iloc[-1]['50_day_rolling'] > daily_data.iloc[-1]['150_day_rolling'] if pd.notna(daily_data.iloc[-1]['150_day_rolling']) else True 
                    ) and ( daily_data.iloc[-1]['50_day_rolling'] > daily_data.iloc[-1]['200_day_rolling'] if pd.notna(daily_data.iloc[-1]['200_day_rolling']) else True )
        
        return [description, value]

    def check_if_price_above_50_moving(self, daily_data, close='Close', is_single_row=False):

        description = 'Price Above 50 day avg. [x; y %]'
        if is_single_row:
            price_above_50_moving = (daily_data[close] - daily_data['50_day_rolling']).__round__(1) if pd.notna(daily_data['50_day_rolling']) else 0
            percent_price_above_50_moving = (
            ((daily_data[close] - daily_data['50_day_rolling']) / daily_data['50_day_rolling'] * 100).__round__(0)
            if pd.notna(daily_data['50_day_rolling']) else 0
            )
        else:
             price_above_50_moving = (daily_data.iloc[-1][close] - daily_data.iloc[-1]['50_day_rolling']).__round__(1) if pd.notna(daily_data.iloc[-1]['50_day_rolling']) else 0
             percent_price_above_50_moving = (
            ((daily_data.iloc[-1][close] - daily_data.iloc[-1]['50_day_rolling']) / daily_data.iloc[-1]['50_day_rolling'] * 100).__round__(0)
            if pd.notna(daily_data.iloc[-1]['50_day_rolling']) else 0
        )
            
        value = price_above_50_moving > 0
        return [description, str(value) + " [{}; {}%]".format(price_above_50_moving,
                                             percent_price_above_50_moving)]

    def check_if_price_above_1p3_52wk_low(self, daily_data, close='Close'):

        # Standard library imports
        import datetime
        description = 'Price 30% Above 52 wk low [% Above]'
       
        fiftyTwoWeekLow = daily_data[daily_data['Date'] > datetime.datetime.now(
            pytz.timezone('America/New_York')) +
                            datetime.timedelta(days=-365)].Close.min()
        percent_above_52wklow = ((daily_data.iloc[-1][close] / fiftyTwoWeekLow - 1) *
                                100).__round__(0)
        
        value = percent_above_52wklow > 30

        return [description, str(value) + " [{} %]".format(percent_above_52wklow)]

    def check_if_price_near_52wk_high_range(self, daily_data, close='Close'):
        
        # Standard library imports
        import datetime
        description = 'Price within 25% of 52 wk high range [% value]'
        
        fiftyTwoWeekHigh = daily_data[daily_data['Date'] > datetime.datetime.now(
            pytz.timezone('America/New_York')) +
                            datetime.timedelta(days=-365)].Close.max()
        percent_above_52wkhigh = ((daily_data.iloc[-1][close] / fiftyTwoWeekHigh - 1) *
                                100).__round__(0)
        
        value = percent_above_52wkhigh > -25

        return [description, str(value) + " [{} %]".format(percent_above_52wkhigh)]
    
    def breakout_plot_helper(self,daily_data,idx):
        """
        check if 200 day moving average uptrend for 1 month
        """
        
        # Standard library imports
        import datetime

        description = '200 day avg. uptrend for 1 mo [n mo.]'

        # Make a copy to avoid modifying the original DataFrame
        daily_data = daily_data.copy()

        # Use .loc to safely assign the new column to avoid SettingWithCopyWarning
        daily_data.loc[:, '200_day_diff'] = daily_data['200_day_rolling'].diff(periods=1)

        no_of_months_trend_above = 0
        half_months = 11
        if idx < len(daily_data):
            for no_of_half_months in range(1, half_months):
                no_of_months_trend_above = 0.5 * (no_of_half_months - 1)
                days_period = 0.5 * no_of_half_months * 30
                start_time = daily_data.Date.iloc[idx] + datetime.timedelta(days=-days_period)
                if start_time > daily_data.Date.iloc[0]:
                    daily_data_temp = daily_data[daily_data.Date > start_time].copy()
                    if daily_data_temp['200_day_diff'].min() > 0:
                        no_of_months_trend_above = 0.5 * (no_of_half_months - 1)
                    else:
                        break
                else:
                    break

        value = no_of_months_trend_above >= 1

        return [description, value]
    
    def breakout_plot_helper_2(self,daily_data,idx):
        """
        check if price is 30% above 52 week low
        """

        # Standard library imports
        import datetime

        description = 'Price 30% Above 52 wk low [% above]'
        fiftyTwoWeekLow = daily_data[daily_data['Date'] > datetime.datetime.now(
            pytz.timezone('America/New_York')) + datetime.timedelta(days=-365)].Close.min()
    
        # iterate through each index
        if idx < len(daily_data):
            current_price = daily_data.iloc[idx]['Close']
            percent_above_52wklow = ((current_price / fiftyTwoWeekLow - 1) * 100).__round__(0)
            value = percent_above_52wklow > 30

        return [description, value]
        
    def breakout_plot_helper_3(self,daily_data,idx):
        """
        check if price is within 25% of 52 week high range
        """
        
        # Standard library imports
        import datetime

        description = 'Price within 25% of 52 wk high range [% value]'
        fiftyTwoWeekHigh = daily_data[daily_data['Date'] > datetime.datetime.now(
            pytz.timezone('America/New_York')) + datetime.timedelta(days=-365)].Close.max()
    
        # iterate through each index
        if idx < len(daily_data):
            current_price = daily_data.iloc[idx]['Close']
            percent_above_52wkhigh = ((current_price / fiftyTwoWeekHigh - 1) * 100).__round__(0)
            value = percent_above_52wkhigh > -25

        return [description, value]
    

    def get_plot_name_path(self, cfg):
        
        file_name = cfg['Analysis']['file_name']
        plot_folder = os.path.join(cfg["Analysis"]["result_folder"], "Plot")

        plot_name_paths = [
            os.path.join(plot_folder, file_name)
        ]

        return plot_name_paths
    
    def save_and_close_plots(self, cfg):

        plot_name_paths = self.get_plot_name_path(cfg)
        # plt = plt_properties["plt"]
        for file_name in plot_name_paths:
            plt.savefig(file_name, dpi=800)

        plt.close()