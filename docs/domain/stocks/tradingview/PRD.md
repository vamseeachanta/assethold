

# MVP Phase 

This is a sample project to develop pinescripts 

I am interested in creating 2 kinds of pine script. 

1. to develop a script that can develop a view / chart that tracks a hypothesis 
2. to develop a strategy script that can back test the hypothesis 

my current hypothesis is 
- for specific stocks (i will hand pick the tickers) that have strong fundamentals 
- some adverse event (like a 1 time crisis) can cause the price to drop 
- however since its temporary, i expect the price to catch back up 

this pattern can be detected using a chart 

- that tracks RSI and moving-average-of-RSI
- basic setup 
    - track stock and RSI over a 6 month window
    - RSI below 30 is oversold
    - RSI over 70 is overbought
    - RSI is calculated on ohlc4 
- key events to track and label
  - RSI drops below 30 - pay attention
  - if RSI >= 30 
    - exit tracking
  - if RSI < 30 & RSI-ma crosses RSI 
    - event = pay attention
  - if RSI drops back below 30 again and rises again after a few days & RSI-ma crosses RSI  
    - event = buy
 