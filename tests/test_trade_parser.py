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