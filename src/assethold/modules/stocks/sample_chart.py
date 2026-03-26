import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd

ticker = "AAPL"  
stock_data = yf.download(ticker, start="2023-05-01", end="2024-08-27")

stock_data['20D_High'] = stock_data['Close'].rolling(window=20).max()

stock_data['Breakout_Up'] = stock_data['Close'] > stock_data['20D_High'].shift(1)

plt.figure(figsize=(14, 7))

plt.plot(stock_data.index, stock_data['Close'], label='Close Price', color='blue')

plt.plot(stock_data.index, stock_data['20D_High'], label='20-Day High', color='green')

breakout_points = stock_data[stock_data['Breakout_Up']]
plt.scatter(breakout_points.index, breakout_points['Close'], color='red', label='Breakout', marker='o')

plt.title(f'{ticker} Breakout Analysis')
plt.xlabel('Date')
plt.ylabel('Price')
plt.legend()
plt.grid(True)

plt.savefig('docs/sample_chart.png')
