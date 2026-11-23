## Introduction

Percentage returns for stocks is to be calulcated. The following two methods are evaluated :

- ffn (Financial Functions for Python) standard library
- assethold hand calculation

## Summary and Conclusions

ffn is chosen for return analysis.

### Detailed Analysis

| Ticker | Analysis Duration | Dividends | % Return | Method | Conclusion |
| --- | --- | --- | --- | --- | --- |
| XOM | 1 yr | Yes | 17.66 | ffn | Matches |
| SPY | 1 yr | Yes | 34.88 | ffn | Matches | 
| DJIA | 1 yr | Yes | 16.93 | ffn  | Matches  |
| AAPL | 1 yr | Yes | 26.25 | ffn | Matches |

### References

- [ffn] (https://pmorissette.github.io/ffn/)
- [assethold repo tests] <https://github.com/samdansk2/assethold/tree/first_pass_run/tests/modules/stocks/analysis/investment>
