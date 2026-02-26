import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import trade_parser
import numpy as np
import pytest
import pandas as pd
import tempfile
from io import StringIO


class TestTradeParser:
    """Tests for the trade_parser module."""

    def test_parse_trade_csv_basic(self):
        """Test basic CSV parsing functionality."""
        file_path = 'tests/test_data/test_call_spread.csv'
        stats = trade_parser.parse_trade_csv(file_path)
        
        assert stats['num_trades'] == 1
        assert stats['total_return'] == 400.0  # 300 + 100
        assert len(stats['pnl_distribution']) == 1

    def test_parse_trade_csv_stream(self):
        """Test CSV parsing with a file stream."""
        csv_data = """Date,Description,Size,Symbol,Expiration,Strike,Type,Trade Price,Profit/Loss,Stock Price,Adjusted Stock Price
2023-01-01,Open Long,1,SPY,2023-01-31,100,Call,$5.00,, $100,$100
2023-01-01,Open Short,-1,SPY,2023-01-31,105,Call,$2.00,, $100,$100
2023-01-31,Close Long,-1,SPY,2023-01-31,100,Call,$8.00,$300,$105,$105
2023-01-31,Close Short,1,SPY,2023-01-31,105,Call,$1.00,$100,$105,$105"""
        
        stream = StringIO(csv_data)
        stats = trade_parser.parse_trade_csv(stream)
        
        assert stats['num_trades'] == 1
        assert stats['total_return'] == 400.0
        assert len(stats['pnl_distribution']) == 1

    def test_parse_trade_csv_empty(self):
        """Test parsing an empty CSV."""
        csv_data = """Date,Description,Size,Symbol,Expiration,Strike,Type,Trade Price,Profit/Loss,Stock Price,Adjusted Stock Price"""
        
        stream = StringIO(csv_data)
        stats = trade_parser.parse_trade_csv(stream)
        
        assert stats['num_trades'] == 0
        assert stats['win_rate'] == 0

    def test_parse_trade_csv_returns_per_trade_dates(self):
        """Test that parse_trade_csv returns opening dates for each trade."""
        csv_data = """Date,Description,Size,Symbol,Expiration,Strike,Type,Trade Price,Profit/Loss,Stock Price,Adjusted Stock Price
2023-01-01,Open Long,1,SPY,2023-01-31,100,Call,$5.00,, $100,$100
2023-01-01,Open Short,-1,SPY,2023-01-31,105,Call,$2.00,, $100,$100
2023-01-31,Close Long,-1,SPY,2023-01-31,100,Call,$8.00,$300,$105,$105
2023-01-31,Close Short,1,SPY,2023-01-31,105,Call,$1.00,$100,$105,$105
2023-02-01,Open Long,1,SPY,2023-02-28,100,Call,$5.00,, $100,$100
2023-02-01,Open Short,-1,SPY,2023-02-28,105,Call,$2.00,, $100,$100
2023-02-28,Close Long,-1,SPY,2023-02-28,100,Call,$6.00,$100,$103,$103
2023-02-28,Close Short,1,SPY,2023-02-28,105,Call,$3.00,-$100,$103,$103"""
        
        stream = StringIO(csv_data)
        stats = trade_parser.parse_trade_csv(stream)
        
        # Should have 2 trades (grouped by expiration)
        assert stats['num_trades'] == 2
        assert 'per_trade_dates' in stats
        assert len(stats['per_trade_dates']) == 2
        
        # Dates should be in ISO format and match opening dates for each expiration
        assert stats['per_trade_dates'][0] == '2023-01-01'
        assert stats['per_trade_dates'][1] == '2023-02-01'
        
    def test_parse_trade_csv_per_trade_dates_matches_pnl_order(self):
        """Test that per_trade_dates order matches pnl_distribution order."""
        csv_data = """Date,Description,Size,Symbol,Expiration,Strike,Type,Trade Price,Profit/Loss,Stock Price,Adjusted Stock Price
2023-03-15,Open Long,1,SPY,2023-04-15,100,Call,$5.00,, $100,$100
2023-03-15,Open Short,-1,SPY,2023-04-15,105,Call,$2.00,, $100,$100
2023-04-15,Close Long,-1,SPY,2023-04-15,100,Call,$7.00,$200,$105,$105
2023-04-15,Close Short,1,SPY,2023-04-15,105,Call,$1.50,$50,$105,$105
2023-05-01,Open Long,1,SPY,2023-05-31,110,Call,$3.00,, $102,$102
2023-05-01,Open Short,-1,SPY,2023-05-31,115,Call,$1.00,, $102,$102
2023-05-31,Close Long,-1,SPY,2023-05-31,110,Call,$2.00,-$100,$101,$101
2023-05-31,Close Short,1,SPY,2023-05-31,115,Call,$1.50,-$50,$101,$101
2023-06-10,Open Long,1,SPY,2023-06-30,120,Call,$4.00,, $105,$105
2023-06-10,Open Short,-1,SPY,2023-06-30,125,Call,$2.50,, $105,$105
2023-06-30,Close Long,-1,SPY,2023-06-30,120,Call,$5.00,$100,$110,$110
2023-06-30,Close Short,1,SPY,2023-06-30,125,Call,$1.00,$150,$110,$110"""
        
        stream = StringIO(csv_data)
        stats = trade_parser.parse_trade_csv(stream)
        
        assert stats['num_trades'] == 3
        assert len(stats['per_trade_dates']) == 3
        assert len(stats['pnl_distribution']) == 3
        
        # Verify dates correspond to the correct trades
        # Trade 1: Exp 2023-04-15, opened 2023-03-15, P/L: 200+50=250
        # Trade 2: Exp 2023-05-31, opened 2023-05-01, P/L: -100-50=-150
        # Trade 3: Exp 2023-06-30, opened 2023-06-10, P/L: 100+150=250
        assert stats['per_trade_dates'][0] == '2023-03-15'
        assert stats['per_trade_dates'][1] == '2023-05-01'
        assert stats['per_trade_dates'][2] == '2023-06-10'
        assert stats['pnl_distribution'][0] == 250.0
        assert stats['pnl_distribution'][1] == -150.0
        assert stats['pnl_distribution'][2] == 250.0