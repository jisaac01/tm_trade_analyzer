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
    
    def test_parse_trade_csv_returns_per_trade_theoretical_reward(self):
        """Test that parse_trade_csv returns theoretical reward for each trade."""
        # Credit spread: Collected $300 net credit on $500 width
        # Theoretical max gain = $300, theoretical max loss = $200
        csv_data = """Date,Description,Size,Symbol,Expiration,Strike,Type,Trade Price,Profit/Loss,Stock Price,Adjusted Stock Price
2023-01-01,Open Short,-1,SPY,2023-01-31,100,Call,$5.00,, $100,$100
2023-01-01,Open Long,1,SPY,2023-01-31,105,Call,$2.00,, $100,$100
2023-01-31,Close Short,1,SPY,2023-01-31,100,Call,$3.00,$200,$105,$105
2023-01-31,Close Long,-1,SPY,2023-01-31,105,Call,$1.50,$50,$105,$105"""
        
        stream = StringIO(csv_data)
        stats = trade_parser.parse_trade_csv(stream)
        
        # Should have per_trade_theoretical_reward
        assert 'per_trade_theoretical_reward' in stats
        assert len(stats['per_trade_theoretical_reward']) == 1
        
        # Net credit = -1 * 5.00 * 100 + 1 * 2.00 * 100 = -500 + 200 = -300 (we collected $300)
        # Width = (105 - 100) * 100 = 500
        # For credit spread: theoretical_max_gain = net_credit = 300
        assert stats['per_trade_theoretical_reward'][0] == 300.0
    
    def test_pnl_date_alignment_with_real_data(self):
        """
        Test that P/L values are correctly aligned with dates using real CSV data.
        
        This test exposes a critical bug where pandas groupby sorts expiration strings
        alphabetically (e.g., "11-Apr-25" before "5-Aug-20") while dates remain in
        chronological order, causing P/L values to be misaligned with their corresponding
        trade dates.
        
        CRITICAL: This test verifies specific known trades have correct P/L values.
        If this test fails, it means trades are getting wrong P/L values, which would
        completely corrupt both Monte Carlo simulations and historical replay results.
        """
        file_path = 'tests/test_data/CML TM Trades Long 60 Delta, Short 30 Delta Call 20260226.csv'
        stats = trade_parser.parse_trade_csv(file_path)
        
        # Extract dates and P/L in parallel lists
        dates = stats['per_trade_dates']
        pnl_dist = stats['pnl_distribution']
        
        assert len(dates) == len(pnl_dist), "Dates and P/L must have same length"
        
        # Create a mapping of date to P/L for easy lookup
        date_to_pnl = dict(zip(dates, pnl_dist))
        
        # Verify specific known trades from the CSV file
        # These values were manually verified from the actual CSV data
        # by looking at the Profit/Loss column for each Expiration group
        
        # CRITICAL TEST CASE: The 2020-07-28 trade (5-Aug-20 expiration)
        # With alphabetical sorting bug, this would incorrectly get P/L from
        # index 7 alphabetically ("11-Apr-25" = $1085) instead of chronologically correct $266
        assert '2020-07-28' in date_to_pnl, "2020-07-28 trade should exist"
        assert abs(date_to_pnl['2020-07-28'] - 266.0) < 1.0, \
            f"2020-07-28 trade should have P/L=$266, got ${date_to_pnl['2020-07-28']}"
        
        # Verify additional trades to ensure alignment across the distribution
        # First trade (31-Mar-20 expiration, opens 2020-03-24)
        assert '2020-03-24' in date_to_pnl, "2020-03-24 trade should exist"
        assert abs(date_to_pnl['2020-03-24'] - 567.0) < 1.0, \
            f"2020-03-24 trade should have P/L=$567, got ${date_to_pnl['2020-03-24']}"
        
        # Second trade (15-Apr-20 expiration, opens 2020-04-07)
        assert '2020-04-07' in date_to_pnl, "2020-04-07 trade should exist"
        assert abs(date_to_pnl['2020-04-07'] - 352.0) < 1.0, \
            f"2020-04-07 trade should have P/L=$352, got ${date_to_pnl['2020-04-07']}"
        
        # A losing trade (6-May-20 expiration, opens 2020-04-28)
        assert '2020-04-28' in date_to_pnl, "2020-04-28 trade should exist"
        assert abs(date_to_pnl['2020-04-28'] - (-319.0)) < 1.0, \
            f"2020-04-28 trade should have P/L=$-319, got ${date_to_pnl['2020-04-28']}"
        
        # Verify dates are in chronological order (not alphabetical by expiration)
        # This catches the bug at its source
        for i in range(len(dates) - 1):
            date_i = pd.to_datetime(dates[i])
            date_next = pd.to_datetime(dates[i + 1])
            assert date_i <= date_next, \
                f"Dates should be chronological, but {dates[i]} > {dates[i+1]}"
    
    def test_parse_raises_error_when_closing_data_without_opening_data(self):
        """
        Test that parser raises clear error when CSV has closing P/L but no opening data.
        
        This prevents silently falling back to buggy behavior when data integrity is compromised.
        The simulator cannot work without opening data for theoretical risk/reward and dates.
        """
        # CSV with only closing data, no opening legs
        csv_data = """Date,Description,Size,Symbol,Expiration,Strike,Type,Trade Price,Profit/Loss,Stock Price,Adjusted Stock Price
2023-01-31,Close Long,-1,SPY,2023-01-31,100,Call,$8.00,$300,$105,$105
2023-01-31,Close Short,1,SPY,2023-01-31,105,Call,$1.00,$100,$105,$105"""
        
        stream = StringIO(csv_data)
        with pytest.raises(ValueError) as exc_info:
            trade_parser.parse_trade_csv(stream)
        
        # Verify the error message is helpful
        error_msg = str(exc_info.value)
        assert "closing P/L data but no matching opening trade data" in error_msg
        assert "opening legs found" in error_msg or "Expiration values don't match" in error_msg
    
    def test_parse_raises_error_when_expirations_dont_match(self):
        """
        Test that parser raises error when opening and closing trades have different expirations.
        
        This catches data integrity issues where trades are incomplete or mismatched.
        """
        # Opening trade has one expiration, closing trade has different expiration
        csv_data = """Date,Description,Size,Symbol,Expiration,Strike,Type,Trade Price,Profit/Loss,Stock Price,Adjusted Stock Price
2023-01-01,Open Long,1,SPY,2023-01-31,100,Call,$5.00,, $100,$100
2023-01-01,Open Short,-1,SPY,2023-01-31,105,Call,$2.00,, $100,$100
2023-02-28,Close Long,-1,SPY,2023-02-28,100,Call,$8.00,$300,$105,$105
2023-02-28,Close Short,1,SPY,2023-02-28,105,Call,$1.00,$100,$105,$105"""
        
        stream = StringIO(csv_data)
        with pytest.raises(ValueError) as exc_info:
            trade_parser.parse_trade_csv(stream)
        
        error_msg = str(exc_info.value)
        assert "closing P/L data but no matching opening trade data" in error_msg