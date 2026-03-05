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
    
    def test_aggregate_stats_are_order_independent(self):
        """
        Test that aggregate statistics (wins, losses, totals, averages) are correctly 
        calculated regardless of whether groupby sorts alphabetically or chronologically.
        
        This verifies that the pnl_values array (used for aggregate stats) produces
        the same results whether it comes from sorted or unsorted groupby, since
        operations like sum(), mean(), len() are order-independent.
        
        This test should pass both before and after adding sort=False to line 70,
        proving the change is safe for aggregate statistics.
        """
        file_path = 'tests/test_data/CML TM Trades Long 60 Delta, Short 30 Delta Call 20260226.csv'
        stats = trade_parser.parse_trade_csv(file_path)
        
        # Verify key aggregate statistics that should be order-independent
        # These values are calculated from the real CSV file
        assert stats['num_trades'] > 100, "Should have many trades in test file"
        
        # Total return should be sum of all P/L regardless of order
        assert isinstance(stats['total_return'], (int, float))
        
        # Win rate should be proportion of wins
        assert 0 <= stats['win_rate'] <= 1
        assert stats['wins'] + stats['losses'] == stats['num_trades']
        
        # Verify wins and losses counts
        assert stats['wins'] > 0, "Test file should have winning trades"
        assert stats['losses'] > 0, "Test file should have losing trades"
        
        # Verify aggregate stats are consistent
        assert abs(stats['gross_gain'] + stats['gross_loss'] - stats['total_return']) < 0.01, \
            "Gross gain + gross loss should equal total return"
        
        # Verify means are reasonable
        if stats['wins'] > 0:
            assert stats['avg_win'] > 0, "Average win should be positive"
        if stats['losses'] > 0:
            assert stats['avg_loss'] < 0, "Average loss should be negative"
        
        # These aggregate values should be identical whether pnl_values is from
        # alphabetically-sorted or chronologically-sorted groupby
        # because numpy operations (sum, mean, max, min) are order-independent

    def test_parse_trade_csv_returns_raw_trade_data(self):
        """Test that parse_trade_csv returns raw CSV data grouped by trade."""
        csv_data = """Date,Description,Size,Symbol,Expiration,Strike,Type,Trade Price,Profit/Loss,Stock Price,Adjusted Stock Price
2023-01-01,Open Long,1,SPY,2023-01-31,100,Call,$5.00,, $100,$100
2023-01-01,Open Short,-1,SPY,2023-01-31,105,Call,$2.00,, $100,$100
2023-01-31,Close Long,-1,SPY,2023-01-31,100,Call,$8.00,$300,$105,$105
2023-01-31,Close Short,1,SPY,2023-01-31,105,Call,$1.00,$100,$105,$105
2023-02-01,Open Long,1,SPY,2023-02-28,110,Call,$3.00,, $102,$102
2023-02-01,Open Short,-1,SPY,2023-02-28,115,Call,$1.50,, $102,$102
2023-02-28,Close Long,-1,SPY,2023-02-28,110,Call,$2.00,-$100,$101,$101
2023-02-28,Close Short,1,SPY,2023-02-28,115,Call,$2.00,-$50,$101,$101"""
        
        stream = StringIO(csv_data)
        stats = trade_parser.parse_trade_csv(stream)
        
        # Should have raw_trade_data key
        assert 'raw_trade_data' in stats
        raw_data = stats['raw_trade_data']
        
        # Should have 2 trades
        assert len(raw_data) == 2
        
        # First trade
        trade1 = raw_data[0]
        assert trade1['expiration'] == '2023-01-31'
        assert len(trade1['opening_legs']) == 2
        assert len(trade1['closing_legs']) == 2
        
        # Check opening leg data structure
        open_leg1 = trade1['opening_legs'][0]
        assert open_leg1['date'] == '2023-01-01'
        assert open_leg1['description'] == 'Open Long'
        assert open_leg1['size'] == 1
        assert open_leg1['symbol'] == 'SPY'
        assert open_leg1['strike'] == 100.0
        assert open_leg1['type'] == 'Call'
        assert open_leg1['trade_price'] == '$5.00'
        
        # Check closing leg data structure
        close_leg1 = trade1['closing_legs'][0]
        assert close_leg1['date'] == '2023-01-31'
        assert close_leg1['description'] == 'Close Long'
        assert close_leg1['profit_loss'] == '$300'
        
        # Second trade
        trade2 = raw_data[1]
        assert trade2['expiration'] == '2023-02-28'
        assert len(trade2['opening_legs']) == 2
        assert len(trade2['closing_legs']) == 2


class TestSameExpirationOverlappingTrades:
    """
    Tests that two overlapping trades sharing the same Expiration date are
    parsed as SEPARATE trades rather than merged into one.

    test_same_expiration_overlapping.csv contains:
      Trade A: open 01-Nov-2023, exp 17-Nov-2023, Long Strike=440, Short Strike=445
               P/L = $250 + (-$100) = $150  [Win]
               risk = 300, reward = 200

      Trade B: open 02-Nov-2023, exp 17-Nov-2023, Long Strike=441, Short Strike=446
               P/L = $150 + (-$75) = $75    [Win]
               risk = 300, reward = 200

    Theoretical risk/reward derivation (debit spread, net_open_cashflow=-300):
      width = 500, theoretical_max_loss = 300, theoretical_max_gain = 200
    """

    SAME_EXP_CSV = 'tests/test_data/test_same_expiration_overlapping.csv'

    def _stats(self):
        return trade_parser.parse_trade_csv(self.SAME_EXP_CSV)

    # ── num_trades ───────────────────────────────────────────────────────

    def test_num_trades_is_two_not_one(self):
        """
        Critical regression test: same-expiration overlapping trades must
        produce 2 entries in pnl_distribution, not 1.
        Before the fix, groupby('Expiration') merged them into a single row.
        """
        stats = self._stats()
        assert stats['num_trades'] == 2, (
            "Two overlapping trades with the same expiration should be parsed "
            "as 2 separate trades, not merged into 1."
        )

    def test_pnl_distribution_has_two_entries(self):
        """pnl_distribution length must equal the number of separate trades (2)."""
        stats = self._stats()
        assert len(stats['pnl_distribution']) == 2

    def test_pnl_values_are_correct(self):
        """
        Trade A P/L = $250 + (-$100) = $150.
        Trade B P/L = $150 + (-$75) = $75.
        In chronological order: [150, 75].
        """
        stats = self._stats()
        pnl = stats['pnl_distribution']
        assert abs(pnl[0] - 150.0) < 0.01, f"Trade A P/L should be 150, got {pnl[0]}"
        assert abs(pnl[1] - 75.0) < 0.01, f"Trade B P/L should be 75, got {pnl[1]}"

    # ── per-trade dates ──────────────────────────────────────────────────

    def test_per_trade_dates_has_two_entries(self):
        stats = self._stats()
        assert len(stats['per_trade_dates']) == 2

    def test_per_trade_open_dates_correct(self):
        """Trade A opens 2023-11-01, Trade B opens 2023-11-02."""
        stats = self._stats()
        assert stats['per_trade_dates'][0] == '2023-11-01'
        assert stats['per_trade_dates'][1] == '2023-11-02'

    def test_per_trade_close_dates_correct(self):
        """Both trades close on 2023-11-17 (the shared expiration date)."""
        stats = self._stats()
        assert stats['per_trade_close_dates'][0] == '2023-11-17'
        assert stats['per_trade_close_dates'][1] == '2023-11-17'

    # ── theoretical risk/reward ──────────────────────────────────────────

    def test_per_trade_theoretical_risk_correct(self):
        """
        Each trade is a debit spread with net_open_cashflow=-300, width=500.
        theoretical_max_loss = 300 for both.
        """
        stats = self._stats()
        risk = stats['per_trade_theoretical_risk']
        assert len(risk) == 2
        assert abs(risk[0] - 300.0) < 0.01, f"Trade A risk should be 300, got {risk[0]}"
        assert abs(risk[1] - 300.0) < 0.01, f"Trade B risk should be 300, got {risk[1]}"

    def test_per_trade_theoretical_reward_correct(self):
        """
        width=500, debit=300 → theoretical_max_gain = 500 - 300 = 200 for both.
        """
        stats = self._stats()
        reward = stats['per_trade_theoretical_reward']
        assert len(reward) == 2
        assert abs(reward[0] - 200.0) < 0.01
        assert abs(reward[1] - 200.0) < 0.01

    # ── raw_trade_data ───────────────────────────────────────────────────

    def test_raw_trade_data_has_two_entries(self):
        """raw_trade_data must have 2 entries (one per trade), not 1."""
        stats = self._stats()
        assert len(stats['raw_trade_data']) == 2

    def test_raw_trade_data_trade_a_opening_legs(self):
        """Trade A raw data must have 2 opening legs opened on 2023-11-01."""
        stats = self._stats()
        trade_a = stats['raw_trade_data'][0]
        assert len(trade_a['opening_legs']) == 2
        for leg in trade_a['opening_legs']:
            assert leg['date'] == '2023-11-01', (
                f"Trade A opening legs must be dated 2023-11-01, got {leg['date']}"
            )

    def test_raw_trade_data_trade_b_opening_legs(self):
        """Trade B raw data must have 2 opening legs opened on 2023-11-02."""
        stats = self._stats()
        trade_b = stats['raw_trade_data'][1]
        assert len(trade_b['opening_legs']) == 2
        for leg in trade_b['opening_legs']:
            assert leg['date'] == '2023-11-02', (
                f"Trade B opening legs must be dated 2023-11-02, got {leg['date']}"
            )

    def test_raw_trade_data_expiration_is_shared(self):
        """Both entries share expiration 2023-11-17."""
        stats = self._stats()
        assert stats['raw_trade_data'][0]['expiration'] == '2023-11-17'
        assert stats['raw_trade_data'][1]['expiration'] == '2023-11-17'

    def test_raw_trade_data_closing_legs_correctly_split(self):
        """
        Trade A closing legs: Strike=440 (Long) and Strike=445 (Short).
        Trade B closing legs: Strike=441 (Long) and Strike=446 (Short).
        The legs must NOT be mixed across trades.
        """
        stats = self._stats()
        trade_a = stats['raw_trade_data'][0]
        trade_b = stats['raw_trade_data'][1]

        a_close_strikes = {leg['strike'] for leg in trade_a['closing_legs']}
        b_close_strikes = {leg['strike'] for leg in trade_b['closing_legs']}

        # Trade A only has strikes 440 and 445
        assert a_close_strikes == {440.0, 445.0}, (
            f"Trade A closing strikes should be {{440, 445}}, got {a_close_strikes}"
        )
        # Trade B only has strikes 441 and 446
        assert b_close_strikes == {441.0, 446.0}, (
            f"Trade B closing strikes should be {{441, 446}}, got {b_close_strikes}"
        )

    # ── win/loss counts ──────────────────────────────────────────────────

    def test_all_wins(self):
        """Both trades are wins (P/L > 0)."""
        stats = self._stats()
        assert stats['wins'] == 2
        assert stats['losses'] == 0

    def test_total_return(self):
        """Total return = 150 + 75 = 225."""
        stats = self._stats()
        assert abs(stats['total_return'] - 225.0) < 0.01
