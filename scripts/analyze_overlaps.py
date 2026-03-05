#!/usr/bin/env python3
"""Analyze master_trades.csv for overlapping trade patterns."""
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

df = pd.read_csv('scripts/master_trades.csv')
open_df = df[df['Description'].str.contains('Open', na=False)].copy()
close_df = df[df['Profit/Loss'].notna()].copy()

open_df['Date'] = pd.to_datetime(open_df['Date'], format='mixed')
close_df['Date'] = pd.to_datetime(close_df['Date'], format='mixed')

open_dates = open_df.groupby('Expiration')['Date'].min().sort_values()
close_dates = close_df.groupby('Expiration')['Date'].max()

trades = pd.DataFrame({'open': open_dates, 'close': close_dates}).dropna()
trades = trades.sort_values('open')
print('Total trades:', len(trades))
print(trades.head(20).to_string())
print()

# Check consecutive opens (sequential signals)
trade_list = list(trades.iterrows())
print('Consecutive open date pairs:')
for i in range(len(trade_list)-1):
    exp_a, a = trade_list[i]
    exp_b, b = trade_list[i+1]
    delta = (b['open'] - a['open']).days
    if delta <= 4:  # within a week - could be consecutive trading days
        print(f"  {exp_a}: open={a['open'].date()}, close={a['close'].date()}")
        print(f"  {exp_b}: open={b['open'].date()}, close={b['close'].date()}")
        print(f"  Gap: {delta} calendar days")
        print()

# Check for overlaps
print('\nOverlapping trades (trade B opens before trade A closes):')
overlaps = []
for i in range(len(trade_list)):
    exp_a, a = trade_list[i]
    for j in range(i+1, len(trade_list)):
        exp_b, b = trade_list[j]
        if b['open'] > a['close']:
            break
        if b['open'] > a['open']:
            overlaps.append((exp_a, exp_b, a['open'].date(), a['close'].date(), b['open'].date()))

print(f'Total overlapping pairs: {len(overlaps)}')
for o in overlaps[:15]:
    print(f'  ExpA={o[0]}, open={o[2]}, close={o[3]} | ExpB={o[1]}, open={o[4]}')
