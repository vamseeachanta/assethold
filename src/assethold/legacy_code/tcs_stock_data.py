import yfinance as yf
import os

ticker_symbol = 'TCS.NS'

stock_data = yf.download(ticker_symbol, start="2014-08-15", end="2024-08-15")

stock_data.to_csv('tcs_stock_data.csv')
