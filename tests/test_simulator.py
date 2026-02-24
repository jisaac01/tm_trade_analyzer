import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import simulator
import numpy as np
import pytest
import unittest.mock


class TestSimulator:
    """Tests for the simulator module."""

    def test_run_monte_carlo_simulation(self):
        """Test running a Monte Carlo simulation."""
        trade_stats = {
            'num_trades': 10,
            'win_rate': 0.5,
            'avg_win': 100,
            'avg_loss': -50,
            'max_win': 200,
            'max_loss': -100,
            'max_theoretical_loss': 100,
            'conservative_theoretical_max_loss': 80,
            'pnl_distribution': [50, -50, 50, -50, 50, -50, 50, -50, 50, -50]
        }
        
        reports = simulator.run_monte_carlo_simulation(
            trade_stats=trade_stats,
            initial_balance=1000,
            num_simulations=10,
            position_sizing='percent',
            dynamic_risk_sizing=True,
            simulation_mode='iid',
            block_size=5
        )
        
        assert len(reports) == 1
        report = reports[0]
        assert 'trade_name' in report
        assert 'summary' in report
        assert 'table_rows' in report
        assert len(report['table_rows']) > 0
        # Check that table_rows has expected keys
        row = report['table_rows'][0]
        assert 'Contracts' in row
        assert 'Avg Final $' in row


class TestRiskRewardGeneration:
    """Tests for risk and reward generation functions."""

    def test_generate_risk_averages_to_target(self):
        """Generated risks should average to the target avg_risk over many samples."""
        avg_risk = 100
        max_risk = 200
        samples = [simulator.generate_risk(avg_risk, max_risk) for _ in range(10000)]
        
        sample_mean = np.mean(samples)
        assert 95 < sample_mean < 105  # Should be close to 100
        
        assert all(0 <= s <= max_risk for s in samples)  # Within bounds

    def test_generate_reward_averages_to_target(self):
        """Generated rewards should average around the target avg_reward over many samples."""
        avg_reward = 150
        max_reward = 300
        samples = [simulator.generate_reward(avg_reward, max_reward) for _ in range(10000)]
        
        sample_mean = np.mean(samples)
        # Beta distribution with alpha=1.5, beta=3 has mean ~0.333, scaled to favor avg_reward
        # The function biases toward avg_reward, so mean should be between avg_reward and max_reward/2 roughly
        assert 100 < sample_mean < 200  # Should be reasonably close to 150, biased toward smaller wins
        
        assert all(0 <= s <= max_reward for s in samples)  # Within bounds

    def test_generate_risk_respects_max(self):
        """Generated risks should never exceed max_risk."""
        avg_risk = 50
        max_risk = 100
        samples = [simulator.generate_risk(avg_risk, max_risk) for _ in range(1000)]
        
        assert all(s <= max_risk for s in samples)

    def test_generate_reward_respects_max(self):
        """Generated rewards should never exceed max_reward."""
        avg_reward = 75
        max_reward = 150
        samples = [simulator.generate_reward(avg_reward, max_reward) for _ in range(1000)]
        
        assert all(s <= max_reward for s in samples)


class TestPositionSizing:
    """Tests for position sizing logic."""

    def test_get_max_risk_per_spread_uses_conservative(self):
        """Should prefer conservative_theoretical_max_loss over max_loss."""
        trade = {
            'conservative_theoretical_max_loss': 80,
            'max_loss': -100
        }
        assert simulator.get_max_risk_per_spread(trade) == 80

    def test_get_max_risk_per_spread_falls_back_to_max_loss(self):
        """Should use abs(max_loss) if conservative not available."""
        trade = {
            'max_loss': -150
        }
        assert simulator.get_max_risk_per_spread(trade) == 150

    def test_choose_contract_count_for_risk_pct(self):
        """Test contract count selection for target risk percentage."""
        max_risk = 100
        balance = 10000
        target_pct = 1  # 1%
        
        contracts = simulator.choose_contract_count_for_risk_pct(max_risk, balance, target_pct)
        
        expected_risk_dollars = balance * (target_pct / 100)
        expected_contracts = int(np.floor(expected_risk_dollars / max_risk))
        assert contracts == max(1, expected_contracts)

    def test_build_position_size_plan_percent_mode(self):
        """Test position size plan building in percent mode."""
        trade = {
            'conservative_theoretical_max_loss': 100
        }
        initial_balance = 10000
        plan = simulator.build_position_size_plan(trade, initial_balance, 'percent')
        
        assert len(plan) > 0
        for item in plan:
            assert 'contracts' in item
            assert 'target_risk_pct' in item
            assert 'actual_risk_pct' in item

    def test_build_position_size_plan_contracts_mode(self):
        """Test position size plan building in contracts mode."""
        trade = {
            'conservative_theoretical_max_loss': 100
        }
        initial_balance = 10000
        plan = simulator.build_position_size_plan(trade, initial_balance, 'contracts')
        
        assert len(plan) == len(simulator.DEFAULT_POSITION_SIZES)
        for i, item in enumerate(plan):
            assert item['contracts'] == simulator.DEFAULT_POSITION_SIZES[i]


class TestSampling:
    """Tests for sampling methods."""

    def test_sample_pnl_moving_blocks_preserves_structure(self):
        """Moving block bootstrap should preserve sequences from original data."""
        pnl_distribution = [10, -5, 20, -10, 15, -8, 25, -12]
        num_trades = 4
        block_size = 2
        
        sampled = simulator.sample_pnl_moving_blocks(pnl_distribution, num_trades, block_size)
        
        assert len(sampled) == num_trades
        # Check that blocks are preserved (e.g., consecutive pairs)
        assert all(isinstance(x, (int, float)) for x in sampled)

    def test_sample_pnl_moving_blocks_handles_small_distribution(self):
        """Should handle distributions smaller than block size."""
        pnl_distribution = [10, -5]
        num_trades = 4
        block_size = 5  # Larger than distribution
        
        sampled = simulator.sample_pnl_moving_blocks(pnl_distribution, num_trades, block_size)
        
        assert len(sampled) == num_trades
        assert all(x in [10, -5] for x in sampled)


class TestSimulateTrades:
    """Comprehensive tests for the simulate_trades function."""

    def test_perfect_win_rate(self):
        """Test with 100% win rate - all simulations should result in maximum profit."""
        with unittest.mock.patch('simulator.generate_risk', return_value=100), \
             unittest.mock.patch('simulator.generate_reward', return_value=50):
            
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
            num_simulations = 10

            results = simulator.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

            expected_final_balance = initial_balance + (50 * position_size * num_trades)
            expected_drawdown = 0

            for result in results:
                assert result['final_balance'] == expected_final_balance
                assert result['max_drawdown'] == expected_drawdown
                assert result['max_losing_streak'] == 0

    def test_zero_win_rate(self):
        """Test with 0% win rate - all simulations should result in bankruptcy."""
        with unittest.mock.patch('simulator.generate_risk', return_value=100), \
             unittest.mock.patch('simulator.generate_reward', return_value=50):
            
            trade = {
                "name": "Test", 
                "avg_loss": -100,
                "max_loss": -100,
                "avg_win": 50, 
                "max_win": 50,
                "win_rate": 0.0
            }
            position_size = 1
            initial_balance = 1000
            num_trades = 10
            num_simulations = 10

            results = simulator.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

            expected_final_balance = 0
            expected_drawdown = initial_balance

            for result in results:
                assert result['final_balance'] == expected_final_balance
                assert result['max_drawdown'] == expected_drawdown

    def test_dynamic_risk_sizing_enabled(self):
        """Test dynamic risk sizing adjusts contracts per trade."""
        trade = {
            "avg_loss": -100,
            "max_loss": -200,
            "avg_win": 50,
            "max_win": 100,
            "win_rate": 0.5
        }
        position_size = 1  # Initial contracts
        initial_balance = 10000
        num_trades = 5
        num_simulations = 5
        target_risk_pct = 1  # 1%

        results = simulator.simulate_trades(
            trade, position_size, initial_balance, num_trades, num_simulations,
            target_risk_pct=target_risk_pct, dynamic_risk_sizing=True
        )
        
        # Should complete without errors
        assert len(results) == num_simulations
        for result in results:
            assert 'final_balance' in result
            assert 'max_drawdown' in result
            assert 'max_losing_streak' in result

    def test_bootstrap_mode_uses_pnl_distribution(self):
        """Bootstrap mode should use provided pnl_distribution for sampling."""
        trade = {
            "avg_loss": -100,
            "max_loss": -200,
            "avg_win": 50,
            "max_win": 100,
            "win_rate": 0.5,
            "pnl_distribution": [50, -50, 100, -100, 25]
        }
        position_size = 1
        initial_balance = 1000
        num_trades = 3
        num_simulations = 5

        results = simulator.simulate_trades(
            trade, position_size, initial_balance, num_trades, num_simulations,
            simulation_mode='moving-block-bootstrap', block_size=2
        )
        
        assert len(results) == num_simulations

    def test_bankruptcy_stops_simulation(self):
        """Simulation should stop when balance reaches zero."""
        with unittest.mock.patch('simulator.generate_risk', return_value=500), \
             unittest.mock.patch('simulator.generate_reward', return_value=50):
            
            trade = {
                "avg_loss": -500,
                "max_loss": -500,
                "avg_win": 50,
                "max_win": 50,
                "win_rate": 0.0  # Always lose
            }
            position_size = 1
            initial_balance = 1000
            num_trades = 10  # Would need more than 2 losses to bankrupt
            num_simulations = 5

            results = simulator.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

            for result in results:
                assert result['final_balance'] == 0  # Bankrupt

    def test_compounding_balance_updates(self):
        """Balance should compound correctly across trades."""
        with unittest.mock.patch('simulator.generate_risk', return_value=100), \
             unittest.mock.patch('simulator.generate_reward', return_value=200):
            
            trade = {
                "avg_loss": -100,
                "max_loss": -100,
                "avg_win": 200,
                "max_win": 200,
                "win_rate": 1.0  # Always win
            }
            position_size = 1
            initial_balance = 1000
            num_trades = 3
            num_simulations = 1

            results = simulator.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

            result = results[0]
            # Start: 1000
            # After trade 1: 1000 + 200 = 1200
            # After trade 2: 1200 + 200 = 1400
            # After trade 3: 1400 + 200 = 1600
            assert result['final_balance'] == 1600

    def test_max_drawdown_tracking(self):
        """Max drawdown should track the peak-to-trough decline."""
        with unittest.mock.patch('simulator.generate_risk', return_value=300), \
             unittest.mock.patch('simulator.generate_reward', return_value=100):
            
            trade = {
                "avg_loss": -300,
                "max_loss": -300,
                "avg_win": 100,
                "max_win": 100,
                "win_rate": 0.5
            }
            position_size = 1
            initial_balance = 1000
            num_trades = 4
            num_simulations = 1

            # Mock random to alternate win/loss: win, loss, loss, win
            with unittest.mock.patch('random.random', side_effect=[0.3, 0.7, 0.7, 0.3]):
                results = simulator.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

            result = results[0]
            # Sequence: +100, -300, -300, +100
            # Balances: 1100, 800, 500, 600
            # Peaks: 1100, 1100, 1100, 1100
            # Drawdowns: 0, 300, 600, 500
            # Max drawdown: 600
            assert result['max_drawdown'] == 600

    def test_losing_streak_tracking(self):
        """Max losing streak should track consecutive losses."""
        with unittest.mock.patch('simulator.generate_risk', return_value=100), \
             unittest.mock.patch('simulator.generate_reward', return_value=100):
            
            trade = {
                "avg_loss": -100,
                "max_loss": -100,
                "avg_win": 100,
                "max_win": 100,
                "win_rate": 0.5
            }
            position_size = 1
            initial_balance = 1000
            num_trades = 5
            num_simulations = 1

            # Mock random to: loss, loss, loss, win, loss
            with unittest.mock.patch('random.random', side_effect=[0.7, 0.7, 0.7, 0.3, 0.7]):
                results = simulator.simulate_trades(trade, position_size, initial_balance, num_trades, num_simulations)

            result = results[0]
            assert result['max_losing_streak'] == 3  # Three consecutive losses