import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import monte_carlo_trade_sizing as mcts
import trade_parser
import numpy as np
import pytest
import pandas as pd
import tempfile


class TestAnalyzeTradeFile:
    """Tests for the analyze_trade_file function."""

    def test_analyze_call_spread_file(self):
        """Test analysis of the actual call spread trade file."""
        file_path = 'tests/test_data/CML TM Trades Long 60 Delta, Short 30 Delta Call 20260223.csv'
        stats = trade_parser.parse_trade_csv(file_path)
        
        assert stats['num_trades'] == 57
        assert 0.75 < stats['win_rate'] < 0.80  # Approximately 77%
        assert 290 < stats['avg_win'] < 300
        assert -260 < stats['avg_loss'] < -250
        assert stats['max_win'] > 1000
        assert stats['max_loss'] < -400
        assert len(stats['pnl_distribution']) == 57

    def test_analyze_put_spread_file(self):
        """Test analysis of the actual put spread trade file."""
        file_path = 'tests/test_data/CML TM Trades Short 50 Delta, Long 40 Delta Put 20260223.csv'
        stats = trade_parser.parse_trade_csv(file_path)
        
        assert stats['num_trades'] == 60
        assert 0.80 < stats['win_rate'] < 0.85  # Approximately 82%
        assert 80 < stats['avg_win'] < 90
        assert -110 < stats['avg_loss'] < -100
        assert stats['max_win'] > 300
        assert stats['max_loss'] < -180
        assert len(stats['pnl_distribution']) == 60

    def test_file_not_found(self):
        """Test handling of non-existent file."""
        with pytest.raises(FileNotFoundError):
            trade_parser.parse_trade_csv('nonexistent_file.csv')

    def test_empty_file(self):
        """Test analysis of a file with no valid trades."""
        # Create a temporary CSV with no close rows
        data = {
            'Date': ['2023-01-01'],
            'Description': ['Open Test'],
            'Size': [1],
            'Symbol': ['SPY'],
            'Expiration': ['2023-01-31'],
            'Strike': [100],
            'Type': ['Call'],
            'Trade Price': ['$5.00'],
            'Profit/Loss': [None],  # No P/L
            'Stock Price': ['$100'],
            'Adjusted Stock Price': ['$100']
        }
        df = pd.DataFrame(data)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            stats = trade_parser.parse_trade_csv(f.name)
        
        os.unlink(f.name)
        
        assert stats['num_trades'] == 0
        assert stats['win_rate'] == 0
        assert stats['avg_win'] == 0
        assert stats['avg_loss'] == 0

    def test_mixed_pnl_values(self):
        """Test analysis with a mix of wins and losses."""
        # Create test data with known outcomes
        data = []
        
        # Trade 1: Win
        data.extend([
            {'Date': '2023-01-01', 'Description': 'Open Long', 'Size': 1, 'Symbol': 'SPY', 'Expiration': '2023-01-31', 'Strike': 100, 'Type': 'Call', 'Trade Price': '$5.00', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'},
            {'Date': '2023-01-01', 'Description': 'Open Short', 'Size': -1, 'Symbol': 'SPY', 'Expiration': '2023-01-31', 'Strike': 105, 'Type': 'Call', 'Trade Price': '$2.00', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'},
            {'Date': '2023-01-31', 'Description': 'Close Long', 'Size': -1, 'Symbol': 'SPY', 'Expiration': '2023-01-31', 'Strike': 100, 'Type': 'Call', 'Trade Price': '$8.00', 'Profit/Loss': '$300', 'Stock Price': '$105', 'Adjusted Stock Price': '$105'},
            {'Date': '2023-01-31', 'Description': 'Close Short', 'Size': 1, 'Symbol': 'SPY', 'Expiration': '2023-01-31', 'Strike': 105, 'Type': 'Call', 'Trade Price': '$1.00', 'Profit/Loss': '$100', 'Stock Price': '$105', 'Adjusted Stock Price': '$105'}
        ])
        
        # Trade 2: Loss
        data.extend([
            {'Date': '2023-02-01', 'Description': 'Open Long', 'Size': 1, 'Symbol': 'SPY', 'Expiration': '2023-02-28', 'Strike': 100, 'Type': 'Call', 'Trade Price': '$5.00', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'},
            {'Date': '2023-02-01', 'Description': 'Open Short', 'Size': -1, 'Symbol': 'SPY', 'Expiration': '2023-02-28', 'Strike': 105, 'Type': 'Call', 'Trade Price': '$2.00', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'},
            {'Date': '2023-02-28', 'Description': 'Close Long', 'Size': -1, 'Symbol': 'SPY', 'Expiration': '2023-02-28', 'Strike': 100, 'Type': 'Call', 'Trade Price': '$1.00', 'Profit/Loss': '-$400', 'Stock Price': '$95', 'Adjusted Stock Price': '$95'},
            {'Date': '2023-02-28', 'Description': 'Close Short', 'Size': 1, 'Symbol': 'SPY', 'Expiration': '2023-02-28', 'Strike': 105, 'Type': 'Call', 'Trade Price': '$3.00', 'Profit/Loss': '-$100', 'Stock Price': '$95', 'Adjusted Stock Price': '$95'}
        ])
        
        df = pd.DataFrame(data)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            stats = trade_parser.parse_trade_csv(f.name)
        
        os.unlink(f.name)
        
        assert stats['num_trades'] == 2
        assert stats['win_rate'] == 0.5  # 1 win, 1 loss
        assert stats['avg_win'] == 400  # (300 + 100) / 1
        assert stats['avg_loss'] == -500  # (400 + 100) / 1 = 500, then negative
        assert stats['max_win'] == 400
        assert stats['max_loss'] == -500

    def test_pnl_distribution_contains_actual_values(self):
        """Test that pnl_distribution contains the actual trade P/L values."""
        file_path = 'tests/test_data/CML TM Trades Long 60 Delta, Short 30 Delta Call 20260223.csv'
        stats = trade_parser.parse_trade_csv(file_path)
        
        # Check that distribution contains expected range of values
        pnl_dist = stats['pnl_distribution']
        assert all(isinstance(x, (int, float)) for x in pnl_dist)
        assert min(pnl_dist) < 0  # Has losses
        assert max(pnl_dist) > 0  # Has wins
        assert len(pnl_dist) == stats['num_trades']

    def test_theoretical_max_loss_is_reported_for_conservative_risk(self):
        """Theoretical spread max loss should be tracked separately from realized max loss."""
        data = [
            {
                'Date': '2026-01-01', 'Description': 'Open TechnicalOpen:Short Puts', 'Size': -1,
                'Symbol': 'SPY', 'Expiration': '2026-01-08', 'Strike': 105, 'Type': 'Put',
                'Trade Price': '$3.00', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'
            },
            {
                'Date': '2026-01-01', 'Description': 'Open TechnicalOpen:Long Puts', 'Size': 1,
                'Symbol': 'SPY', 'Expiration': '2026-01-08', 'Strike': 100, 'Type': 'Put',
                'Trade Price': '$2.00', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'
            },
            {
                'Date': '2026-01-05', 'Description': 'Close Short Puts', 'Size': 1,
                'Symbol': 'SPY', 'Expiration': '2026-01-08', 'Strike': 105, 'Type': 'Put',
                'Trade Price': '$1.00', 'Profit/Loss': '$200', 'Stock Price': '$102', 'Adjusted Stock Price': '$102'
            },
            {
                'Date': '2026-01-05', 'Description': 'Close Long Puts', 'Size': -1,
                'Symbol': 'SPY', 'Expiration': '2026-01-08', 'Strike': 100, 'Type': 'Put',
                'Trade Price': '$1.90', 'Profit/Loss': '-$10', 'Stock Price': '$102', 'Adjusted Stock Price': '$102'
            },
            {
                'Date': '2026-01-10', 'Description': 'Open TechnicalOpen:Short Puts', 'Size': -1,
                'Symbol': 'SPY', 'Expiration': '2026-01-17', 'Strike': 110, 'Type': 'Put',
                'Trade Price': '$1.20', 'Profit/Loss': None, 'Stock Price': '$109', 'Adjusted Stock Price': '$109'
            },
            {
                'Date': '2026-01-10', 'Description': 'Open TechnicalOpen:Long Puts', 'Size': 1,
                'Symbol': 'SPY', 'Expiration': '2026-01-17', 'Strike': 108, 'Type': 'Put',
                'Trade Price': '$0.70', 'Profit/Loss': None, 'Stock Price': '$109', 'Adjusted Stock Price': '$109'
            },
            {
                'Date': '2026-01-16', 'Description': 'Close Short Puts', 'Size': 1,
                'Symbol': 'SPY', 'Expiration': '2026-01-17', 'Strike': 110, 'Type': 'Put',
                'Trade Price': '$1.40', 'Profit/Loss': '-$20', 'Stock Price': '$108', 'Adjusted Stock Price': '$108'
            },
            {
                'Date': '2026-01-16', 'Description': 'Close Long Puts', 'Size': -1,
                'Symbol': 'SPY', 'Expiration': '2026-01-17', 'Strike': 108, 'Type': 'Put',
                'Trade Price': '$1.10', 'Profit/Loss': '-$20', 'Stock Price': '$108', 'Adjusted Stock Price': '$108'
            }
        ]

        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            stats = trade_parser.parse_trade_csv(f.name)

        os.unlink(f.name)

        assert stats['max_win'] == 190
        assert stats['max_loss'] == -40
        assert stats['max_theoretical_loss'] == 400

    def test_conservative_theoretical_max_loss_uses_p95_not_raw_max(self):
        """Conservative risk should use p95 of theoretical max loss to reduce outlier dominance."""
        data = []

        expirations = [
            ('2026-01-08', 100, 101, 100),
            ('2026-01-15', 100, 101, 100),
            ('2026-01-22', 100, 101, 100),
            ('2026-01-29', 100, 101, 100),
            ('2026-02-05', 100, 105, 500),
        ]

        for expiration, long_strike, short_strike, theoretical_max_loss in expirations:
            width = (short_strike - long_strike) * 100
            credit = width - theoretical_max_loss
            short_price = max(credit / 100, 0)

            data.extend([
                {
                    'Date': '2026-01-01', 'Description': 'Open TechnicalOpen:Short Puts', 'Size': -1,
                    'Symbol': 'SPY', 'Expiration': expiration, 'Strike': short_strike, 'Type': 'Put',
                    'Trade Price': f'${short_price:.2f}', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'
                },
                {
                    'Date': '2026-01-01', 'Description': 'Open TechnicalOpen:Long Puts', 'Size': 1,
                    'Symbol': 'SPY', 'Expiration': expiration, 'Strike': long_strike, 'Type': 'Put',
                    'Trade Price': '$0.00', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'
                },
                {
                    'Date': '2026-01-02', 'Description': 'Close Short Puts', 'Size': 1,
                    'Symbol': 'SPY', 'Expiration': expiration, 'Strike': short_strike, 'Type': 'Put',
                    'Trade Price': '$0.10', 'Profit/Loss': '$10', 'Stock Price': '$101', 'Adjusted Stock Price': '$101'
                },
                {
                    'Date': '2026-01-02', 'Description': 'Close Long Puts', 'Size': -1,
                    'Symbol': 'SPY', 'Expiration': expiration, 'Strike': long_strike, 'Type': 'Put',
                    'Trade Price': '$0.05', 'Profit/Loss': '$5', 'Stock Price': '$101', 'Adjusted Stock Price': '$101'
                }
            ])

        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            stats = trade_parser.parse_trade_csv(f.name)

        os.unlink(f.name)

        assert stats['max_theoretical_loss'] == 500
        assert abs(stats['conservative_theoretical_max_loss'] - 420) < 0.0001

    def test_median_risk_per_spread_uses_median_losing_trade(self):
        """Displayed risk-per-spread metric should be median of realized losing trade outcomes."""
        data = [
            {
                'Date': '2026-01-01', 'Description': 'Open TechnicalOpen:Short Puts', 'Size': -1,
                'Symbol': 'SPY', 'Expiration': '2026-01-08', 'Strike': 101, 'Type': 'Put',
                'Trade Price': '$0.60', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'
            },
            {
                'Date': '2026-01-01', 'Description': 'Open TechnicalOpen:Long Puts', 'Size': 1,
                'Symbol': 'SPY', 'Expiration': '2026-01-08', 'Strike': 100, 'Type': 'Put',
                'Trade Price': '$0.00', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'
            },
            {
                'Date': '2026-01-02', 'Description': 'Close Short Puts', 'Size': 1,
                'Symbol': 'SPY', 'Expiration': '2026-01-08', 'Strike': 101, 'Type': 'Put',
                'Trade Price': '$0.10', 'Profit/Loss': '-$50', 'Stock Price': '$101', 'Adjusted Stock Price': '$101'
            },
            {
                'Date': '2026-01-02', 'Description': 'Close Long Puts', 'Size': -1,
                'Symbol': 'SPY', 'Expiration': '2026-01-08', 'Strike': 100, 'Type': 'Put',
                'Trade Price': '$0.05', 'Profit/Loss': '$0', 'Stock Price': '$101', 'Adjusted Stock Price': '$101'
            },
            {
                'Date': '2026-01-03', 'Description': 'Open TechnicalOpen:Short Puts', 'Size': -1,
                'Symbol': 'SPY', 'Expiration': '2026-01-15', 'Strike': 101, 'Type': 'Put',
                'Trade Price': '$0.60', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'
            },
            {
                'Date': '2026-01-03', 'Description': 'Open TechnicalOpen:Long Puts', 'Size': 1,
                'Symbol': 'SPY', 'Expiration': '2026-01-15', 'Strike': 100, 'Type': 'Put',
                'Trade Price': '$0.00', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'
            },
            {
                'Date': '2026-01-04', 'Description': 'Close Short Puts', 'Size': 1,
                'Symbol': 'SPY', 'Expiration': '2026-01-15', 'Strike': 101, 'Type': 'Put',
                'Trade Price': '$0.10', 'Profit/Loss': '-$100', 'Stock Price': '$101', 'Adjusted Stock Price': '$101'
            },
            {
                'Date': '2026-01-04', 'Description': 'Close Long Puts', 'Size': -1,
                'Symbol': 'SPY', 'Expiration': '2026-01-15', 'Strike': 100, 'Type': 'Put',
                'Trade Price': '$0.05', 'Profit/Loss': '$0', 'Stock Price': '$101', 'Adjusted Stock Price': '$101'
            },
            {
                'Date': '2026-01-05', 'Description': 'Open TechnicalOpen:Short Puts', 'Size': -1,
                'Symbol': 'SPY', 'Expiration': '2026-01-22', 'Strike': 101, 'Type': 'Put',
                'Trade Price': '$0.60', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'
            },
            {
                'Date': '2026-01-05', 'Description': 'Open TechnicalOpen:Long Puts', 'Size': 1,
                'Symbol': 'SPY', 'Expiration': '2026-01-22', 'Strike': 100, 'Type': 'Put',
                'Trade Price': '$0.00', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'
            },
            {
                'Date': '2026-01-06', 'Description': 'Close Short Puts', 'Size': 1,
                'Symbol': 'SPY', 'Expiration': '2026-01-22', 'Strike': 101, 'Type': 'Put',
                'Trade Price': '$0.10', 'Profit/Loss': '-$200', 'Stock Price': '$101', 'Adjusted Stock Price': '$101'
            },
            {
                'Date': '2026-01-06', 'Description': 'Close Long Puts', 'Size': -1,
                'Symbol': 'SPY', 'Expiration': '2026-01-22', 'Strike': 100, 'Type': 'Put',
                'Trade Price': '$0.05', 'Profit/Loss': '$0', 'Stock Price': '$101', 'Adjusted Stock Price': '$101'
            }
        ]

        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            stats = trade_parser.parse_trade_csv(f.name)

        os.unlink(f.name)

        assert stats['avg_loss'] == -116.66666666666667
        assert stats['median_loss'] == -100
        assert stats['median_risk_per_spread'] == 100

    def test_conservative_realized_max_reward_uses_p95_not_raw_max(self):
        """Conservative realized reward cap should use p95 of winning trade outcomes."""
        data = []

        expirations = [
            ('2026-01-08', 100),
            ('2026-01-15', 100),
            ('2026-01-22', 100),
            ('2026-01-29', 100),
            ('2026-02-05', 500),
        ]

        for expiration, realized_win in expirations:
            data.extend([
                {
                    'Date': '2026-01-01', 'Description': 'Open TechnicalOpen:Short Puts', 'Size': -1,
                    'Symbol': 'SPY', 'Expiration': expiration, 'Strike': 101, 'Type': 'Put',
                    'Trade Price': '$0.50', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'
                },
                {
                    'Date': '2026-01-01', 'Description': 'Open TechnicalOpen:Long Puts', 'Size': 1,
                    'Symbol': 'SPY', 'Expiration': expiration, 'Strike': 100, 'Type': 'Put',
                    'Trade Price': '$0.00', 'Profit/Loss': None, 'Stock Price': '$100', 'Adjusted Stock Price': '$100'
                },
                {
                    'Date': '2026-01-02', 'Description': 'Close Short Puts', 'Size': 1,
                    'Symbol': 'SPY', 'Expiration': expiration, 'Strike': 101, 'Type': 'Put',
                    'Trade Price': '$0.10', 'Profit/Loss': f'${realized_win:.0f}', 'Stock Price': '$101', 'Adjusted Stock Price': '$101'
                },
                {
                    'Date': '2026-01-02', 'Description': 'Close Long Puts', 'Size': -1,
                    'Symbol': 'SPY', 'Expiration': expiration, 'Strike': 100, 'Type': 'Put',
                    'Trade Price': '$0.05', 'Profit/Loss': '$0', 'Stock Price': '$101', 'Adjusted Stock Price': '$101'
                }
            ])

        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            stats = trade_parser.parse_trade_csv(f.name)

        os.unlink(f.name)

        assert stats['max_win'] == 500
        assert abs(stats['conservative_realized_max_reward'] - 420) < 0.0001

    def test_official_style_summary_metrics_present_for_call_spread_csv(self):
        """Call spread CSV should expose detailed summary metrics used in backtest cards."""
        file_path = 'tests/test_data/CML TM Trades Long 60 Delta, Short 30 Delta Call 20260223.csv'
        stats = trade_parser.parse_trade_csv(file_path)

        assert stats['wins'] == 44
        assert stats['losses'] == 13
        assert abs(stats['total_return'] - 9613.5) < 0.01
        assert abs(stats['gross_gain'] - 12905.0) < 0.01
        assert abs(stats['gross_loss'] - (-3291.5)) < 0.01
        assert 37.9 < stats['avg_pct_return'] < 38.2
        assert 69.5 < stats['avg_pct_win'] < 69.9
        assert -69.3 < stats['avg_pct_loss'] < -68.8


class TestSimulateTrades:
    """Comprehensive tests for the simulate_trades function."""

    def test_perfect_win_rate(self):
        """Test with 100% win rate - all simulations should result in maximum profit."""
        # Mock the generators to return fixed values for testing
        import unittest.mock
        
        with unittest.mock.patch('monte_carlo_trade_sizing.generate_risk', return_value=100), \
             unittest.mock.patch('monte_carlo_trade_sizing.generate_reward', return_value=50):
            
            trade = {
                "name": "Test", 
                "avg_loss": -100,  # Will be converted to positive risk
                "max_loss": -100,  # Max risk = 100
                "avg_win": 50, 
                "max_win": 50,
                "win_rate": 1.0
            }
            position_size = 1
            initial_balance = 1000
            num_trades = 10
            num_simulations = 100

            results = mcts.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

            expected_final_balance = initial_balance + (50 * position_size * num_trades)  # reward * position_size * num_trades
            expected_drawdown = 0  # No losses, so no drawdown

            for result in results:
                assert result['final_balance'] == expected_final_balance
                assert result['max_drawdown'] == expected_drawdown
                assert result['max_losing_streak'] == 0  # No losses in perfect win rate

    def test_zero_win_rate(self):
        """Test with 0% win rate - all simulations should result in bankruptcy."""
        # Mock the generators to return fixed values for testing
        import unittest.mock
        
        with unittest.mock.patch('monte_carlo_trade_sizing.generate_risk', return_value=100), \
             unittest.mock.patch('monte_carlo_trade_sizing.generate_reward', return_value=50):
            
            trade = {
                "name": "Test", 
                "avg_loss": -100,  # Will be converted to positive risk
                "max_loss": -100,  # Max risk = 100
                "avg_win": 50, 
                "max_win": 50,
                "win_rate": 0.0
            }
            position_size = 1
            initial_balance = 1000
            num_trades = 10
            num_simulations = 100

            results = mcts.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

            # Since risk per trade = 100, and initial = 1000, after 10 losses, balance = 0
            expected_final_balance = 0
            # Drawdown should be the total loss
            expected_drawdown = initial_balance

            for result in results:
                assert result['final_balance'] == expected_final_balance
                assert result['max_drawdown'] == expected_drawdown

    def test_partial_win_rate(self):
        """Test with 50% win rate - check statistical properties."""
        # Mock the generators to return fixed values for testing
        import unittest.mock
        
        with unittest.mock.patch('monte_carlo_trade_sizing.generate_risk', return_value=100), \
             unittest.mock.patch('monte_carlo_trade_sizing.generate_reward', return_value=100):
            
            trade = {
                "name": "Test", 
                "avg_loss": -100,  # Will be converted to positive risk
                "max_loss": -100,  # Max risk = 100
                "avg_win": 100, 
                "max_win": 100,
                "win_rate": 0.5
            }
            position_size = 1
            initial_balance = 1000
            num_trades = 100
            num_simulations = 1000

            results = mcts.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

            final_balances = [r['final_balance'] for r in results]
            drawdowns = [r['max_drawdown'] for r in results]

            # Expected final balance should be around initial + (0.5*100 - 0.5*100)*100 = 1000
            avg_final_balance = np.mean(final_balances)
            assert 900 < avg_final_balance < 1100  # Allow some variance

            # Should have some bankruptcies
            bankrupt_count = sum(1 for b in final_balances if b == 0)
            assert bankrupt_count > 0

            # Drawdowns should be positive
            assert all(d >= 0 for d in drawdowns)

    def test_bankruptcy_mid_simulation(self):
        """Test bankruptcy occurring mid-simulation."""
        # Mock the generators to return fixed values for testing
        import unittest.mock
        
        with unittest.mock.patch('monte_carlo_trade_sizing.generate_risk', return_value=500), \
             unittest.mock.patch('monte_carlo_trade_sizing.generate_reward', return_value=100):
            
            trade = {
                "name": "Test", 
                "avg_loss": -500,  # Will be converted to positive risk
                "max_loss": -500,  # Max risk = 500
                "avg_win": 100, 
                "max_win": 100,
                "win_rate": 0.0
            }
            position_size = 1
            initial_balance = 1000
            num_trades = 10
            num_simulations = 100

            results = mcts.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

            # Risk = 500, initial = 1000, so after 2 losses, balance = 0
            for result in results:
                assert result['final_balance'] == 0
            assert result['max_drawdown'] == initial_balance

    def test_position_size_scaling(self):
        """Test that position size properly scales risk and reward."""
        # Mock the generators to return fixed values for testing
        import unittest.mock
        
        with unittest.mock.patch('monte_carlo_trade_sizing.generate_risk', return_value=100), \
             unittest.mock.patch('monte_carlo_trade_sizing.generate_reward', return_value=50):
            
            trade = {
                "name": "Test", 
                "avg_loss": -100,  # Will be converted to positive risk
                "max_loss": -100,  # Max risk = 100
                "avg_win": 50, 
                "max_win": 50,
                "win_rate": 1.0
            }
            position_size = 2
            initial_balance = 1000
            num_trades = 5
            num_simulations = 10

            results = mcts.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

            expected_final_balance = initial_balance + (50 * num_trades)  # Mock returns 50 per win
            expected_drawdown = 0

            for result in results:
                assert result['final_balance'] == expected_final_balance
                assert result['max_drawdown'] == expected_drawdown

    def test_zero_trades(self):
        """Test with 0 trades - balance should remain initial."""
        trade = {
            "name": "Test", 
            "avg_loss": -100,  # Will be converted to positive risk
            "max_loss": -100,  # Max risk = 100
            "avg_win": 50, 
            "max_win": 50,
            "win_rate": 0.5
        }
        position_size = 1
        initial_balance = 1000
        num_trades = 0
        num_simulations = 10

        results = mcts.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

        for result in results:
            assert result['final_balance'] == initial_balance
            assert result['max_drawdown'] == 0

    def test_single_simulation_single_trade_win(self):
        """Test single simulation, single trade, win."""
        # Mock the generators to return fixed values for testing
        import unittest.mock
        
        with unittest.mock.patch('monte_carlo_trade_sizing.generate_risk', return_value=100), \
             unittest.mock.patch('monte_carlo_trade_sizing.generate_reward', return_value=50):
            
            trade = {
                "name": "Test", 
                "avg_loss": -100,  # Will be converted to positive risk
                "max_loss": -100,  # Max risk = 100
                "avg_win": 50, 
                "max_win": 50,
                "win_rate": 1.0
            }
            position_size = 1
            initial_balance = 1000
            num_trades = 1
            num_simulations = 1

            results = mcts.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

            assert len(results) == 1
            assert results[0]['final_balance'] == initial_balance + 50  # reward
            assert results[0]['max_drawdown'] == 0

    def test_single_simulation_single_trade_loss(self):
        """Test single simulation, single trade, loss."""
        # Mock the generators to return fixed values for testing
        import unittest.mock
        
        with unittest.mock.patch('monte_carlo_trade_sizing.generate_risk', return_value=100), \
             unittest.mock.patch('monte_carlo_trade_sizing.generate_reward', return_value=50):
            
            trade = {
                "name": "Test", 
                "avg_loss": -100,  # Will be converted to positive risk
                "max_loss": -100,  # Max risk = 100
                "avg_win": 50, 
                "max_win": 50,
                "win_rate": 0.0
            }
            position_size = 1
            initial_balance = 1000
            num_trades = 1
            num_simulations = 1

            results = mcts.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

            assert len(results) == 1
            assert results[0]['final_balance'] == initial_balance - 100  # risk
            assert results[0]['max_drawdown'] == 100

    def test_drawdown_calculation(self):
        """Test drawdown calculation with mixed wins/losses."""
        # Mock the generators to return fixed values for testing
        import unittest.mock
        
        with unittest.mock.patch('monte_carlo_trade_sizing.generate_risk', return_value=100), \
             unittest.mock.patch('monte_carlo_trade_sizing.generate_reward', return_value=50):
            
            trade = {
                "name": "Test", 
                "avg_loss": -100,  # Will be converted to positive risk
                "max_loss": -100,  # Max risk = 100
                "avg_win": 50, 
                "max_win": 50,
                "win_rate": 0.8
            }
            position_size = 1
            initial_balance = 1000
            num_trades = 50
            num_simulations = 100

            results = mcts.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

            for result in results:
                assert result['max_drawdown'] >= 0
                assert result['max_drawdown'] <= initial_balance + (50 * num_trades)  # Theoretical max

    def test_large_position_size_bankruptcy(self):
        """Test with large position size leading to quick bankruptcy."""
        # Mock the generators to return fixed values for testing
        import unittest.mock
        
        with unittest.mock.patch('monte_carlo_trade_sizing.generate_risk', return_value=1000), \
             unittest.mock.patch('monte_carlo_trade_sizing.generate_reward', return_value=100):
            
            trade = {
                "name": "Test", 
                "avg_loss": -1000,  # Will be converted to positive risk
                "max_loss": -1000,  # Max risk = 1000
                "avg_win": 100, 
                "max_win": 100,
                "win_rate": 0.0
            }
            position_size = 2  # Risk = 2000 per trade
            initial_balance = 1000
            num_trades = 5
            num_simulations = 10

            results = mcts.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

            # Should bankrupt on first trade
            for result in results:
                assert result['final_balance'] == 0
                assert result['max_drawdown'] == 1000  # Mock returns 1000 per loss

    def test_dynamic_risk_sizing_recomputes_contracts_from_current_equity(self):
        """When enabled, percent-risk sizing should recompute contracts each trade from current balance."""
        import unittest.mock

        trade = {
            "name": "Test",
            "avg_loss": -100,
            "max_loss": -100,
            "conservative_theoretical_max_loss": 100,
            "avg_win": 50,
            "max_win": 50,
            "win_rate": 0.0,
        }

        with unittest.mock.patch('monte_carlo_trade_sizing.generate_risk', side_effect=lambda avg, _max: avg), \
             unittest.mock.patch('monte_carlo_trade_sizing.generate_reward', return_value=0):

            dynamic_results = mcts.simulate_trades(
                trade=trade,
                position_size=2,
                initial_balance=1000,
                num_trades=3,
                num_simulations=1,
                target_risk_pct=25,
                dynamic_risk_sizing=True,
            )

            static_results = mcts.simulate_trades(
                trade=trade,
                position_size=2,
                initial_balance=1000,
                num_trades=3,
                num_simulations=1,
                target_risk_pct=25,
                dynamic_risk_sizing=False,
            )

        assert dynamic_results[0]['final_balance'] == 500
        assert static_results[0]['final_balance'] == 400


class TestPositionSizingMode:
    """Tests for CLI-driven position sizing options."""

    def test_parse_args_defaults_to_percentage_mode(self):
        """Default CLI mode should be percent sizing with no extra complexity."""
        args = mcts.parse_args([])

        assert args.position_sizing == 'percent'

    def test_parse_args_allows_contract_mode_switch(self):
        """Users should be able to opt into contract sizing with one switch."""
        args = mcts.parse_args(['--position-sizing', 'contracts'])

        assert args.position_sizing == 'contracts'

    def test_parse_args_defaults_dynamic_risk_sizing_on(self):
        """Per-trade dynamic percent-risk sizing should be enabled by default."""
        args = mcts.parse_args([])

        assert args.dynamic_risk_sizing is True

    def test_parse_args_defaults_simulation_mode_to_iid(self):
        """Default simulation mode should remain IID unless explicitly overridden."""
        args = mcts.parse_args([])

        assert args.simulation_mode == 'iid'

    def test_choose_contract_count_for_risk_pct_picks_nearest_contract_count(self):
        """Contract count should target percentage risk as closely as possible."""
        account_balance = 10_000
        max_risk_per_spread = 200
        target_risk_pct = 7

        contracts = mcts.choose_contract_count_for_risk_pct(
            max_risk_per_spread=max_risk_per_spread,
            account_balance=account_balance,
            target_risk_pct=target_risk_pct
        )

        actual_risk_pct = (contracts * max_risk_per_spread / account_balance) * 100
        target_risk_dollars = account_balance * (target_risk_pct / 100)
        one_contract_step_pct = (max_risk_per_spread / account_balance) * 100

        assert contracts == 4
        assert abs(actual_risk_pct - target_risk_pct) <= one_contract_step_pct / 2
        assert abs(contracts * max_risk_per_spread - target_risk_dollars) <= max_risk_per_spread / 2

    def test_build_position_size_plan_percent_mode_uses_fixed_risk_distribution(self):
        """Percent mode should use predefined risk buckets for simpler UX."""
        trade = {
            'max_theoretical_loss': 200,
            'max_loss': -150,
            'avg_loss': -100
        }

        plan = mcts.build_position_size_plan(
            trade=trade,
            initial_balance=10_000,
            position_sizing='percent'
        )

        assert [row['target_risk_pct'] for row in plan] == [float(x) for x in mcts.DEFAULT_RISK_PCTS]
        assert all(row['contracts'] >= 1 for row in plan)

    def test_build_position_size_plan_contract_mode_uses_default_contract_distribution(self):
        """Contract mode should use predefined position sizes."""
        trade = {
            'max_theoretical_loss': 250,
            'max_loss': -180,
            'avg_loss': -120
        }

        plan = mcts.build_position_size_plan(
            trade=trade,
            initial_balance=10_000,
            position_sizing='contracts'
        )

        assert [row['contracts'] for row in plan] == [1, 2, 5, 10, 15, 20]
        assert all('target_risk_pct' in row for row in plan)


class TestMovingBlockBootstrap:
    """Tests for moving-block bootstrap sampling and simulation mode."""

    def test_sample_moving_block_returns_concatenated_blocks(self):
        """Moving-block sampler should stitch contiguous blocks to requested trade count."""
        import unittest.mock

        pnl_distribution = [10, -5, 20, -15]
        with unittest.mock.patch('monte_carlo_trade_sizing.np.random.randint', side_effect=[1, 0, 2]):
            sampled = mcts.sample_pnl_moving_blocks(
                pnl_distribution=pnl_distribution,
                num_trades=6,
                block_size=2
            )

        assert sampled == [-5, 20, 10, -5, 20, -15]

    def test_simulate_trades_bootstrap_mode_uses_pnl_distribution_not_iid_generators(self):
        """Bootstrap mode should use sampled realized P/L sequence instead of synthetic risk/reward draws."""
        import unittest.mock

        trade = {
            "name": "Bootstrap Test",
            "avg_loss": -100,
            "max_loss": -100,
            "conservative_theoretical_max_loss": 100,
            "avg_win": 50,
            "max_win": 50,
            "win_rate": 0.5,
            "pnl_distribution": [-100, -100, 80, 80]
        }

        with unittest.mock.patch('monte_carlo_trade_sizing.generate_risk', side_effect=AssertionError("iid risk path used")), \
             unittest.mock.patch('monte_carlo_trade_sizing.generate_reward', side_effect=AssertionError("iid reward path used")), \
             unittest.mock.patch('monte_carlo_trade_sizing.sample_pnl_moving_blocks', return_value=[-100, -100, -100, -100]):

            results = mcts.simulate_trades(
                trade=trade,
                position_size=1,
                initial_balance=1000,
                num_trades=4,
                num_simulations=1,
                simulation_mode='moving-block-bootstrap',
                block_size=2,
                dynamic_risk_sizing=False
            )

        assert results[0]['final_balance'] == 600
        assert results[0]['max_losing_streak'] == 4


class TestHtmlReportOutput:
    """Tests for HTML report rendering/output defaults."""

    def test_parse_args_defaults_to_html_output_file(self):
        """Report should default to writing an HTML file."""
        args = mcts.parse_args([])

        assert args.output_html.endswith('monte_carlo_trade_sizing_report.html')

    def test_build_html_report_contains_summary_and_table(self):
        """Rendered HTML should include the trade section, summary, and simulation table."""
        trade_reports = [
            {
                'trade_name': 'Call Spread',
                'summary': {
                    'risked': 1000,
                    'total_return': 250,
                    'pct_return': 25.0,
                    'avg_pct_return': 4.2,
                    'commissions': 40,
                    'win_rate': 0.8,
                    'wins': 8,
                    'losses': 2,
                    'avg_win': 120,
                    'avg_loss': -80,
                    'avg_pct_win': 10.0,
                    'avg_pct_loss': -5.0,
                    'gross_gain': 960,
                    'gross_loss': -160,
                    'median_risk_per_spread': 90,
                    'conservative_theoretical_max_loss': 120,
                    'max_theoretical_loss': 150,
                    'conservative_realized_max_reward': 130,
                    'max_win': 200,
                    'max_loss': -100,
                    'num_trades': 10,
                    'pnl_distribution': [100, -50, 80]
                },
                'table_rows': [
                    {
                        'Contracts': 2,
                        'Target Risk %': '5.00%',
                        'Actual Risk %': '4.80%',
                        'Avg Final $': '$120000.00',
                        'Bankruptcy Prob': '0.500%',
                        'Avg Max Drawdown': '$3000.00',
                        'Max Drawdown': '$12000.00',
                        'Avg Max Losing Streak': '2.4',
                        'Max Losing Streak': '6'
                    }
                ]
            }
        ]

        html = mcts.build_html_report(
            trade_reports=trade_reports,
            initial_balance=100000,
            position_sizing='percent',
            dynamic_risk_sizing=True,
            simulation_mode='iid',
            block_size=5
        )

        assert '<html' in html.lower()
        assert 'Monte Carlo Trade Sizing Report' in html
        assert 'TradeMachine Backtest Results (from CSV file)' in html
        assert 'Monte Carlo Simulation Results (generated)' in html
        assert 'Call Spread' in html
        assert 'Bankruptcy Prob' in html
        assert '0.500%' in html


class TestFormattingHelpers:
    """Tests for user-facing numeric formatting helpers."""

    def test_format_percent_whole_displays_no_decimals(self):
        """Percent labels should be whole numbers so 0.04 is clearly 4%."""
        assert mcts.format_percent_whole(0.04) == '4%'
        assert mcts.format_percent_whole(0.0004) == '0%'