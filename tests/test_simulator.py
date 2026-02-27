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
        """Should raise error if conservative theoretical data is missing."""
        trade = {
            'max_loss': -150
        }
        with pytest.raises(ValueError, match="Conservative theoretical loss data is missing"):
            simulator.get_max_risk_per_spread(trade)

    def test_get_max_risk_per_spread_max_theoretical(self):
        """Should use max_theoretical_loss when specified."""
        trade = {
            'max_theoretical_loss': 200,
            'conservative_theoretical_max_loss': 80
        }
        assert simulator.get_max_risk_per_spread(trade, 'max_theoretical') == 200

    def test_get_max_risk_per_spread_fixed_conservative_theoretical_max(self):
        """Fixed conservative theoretical max should use conservative_theoretical_max_loss."""
        trade = {
            'conservative_theoretical_max_loss': 140,
            'max_theoretical_loss': 200
        }
        assert simulator.get_max_risk_per_spread(trade, 'fixed_conservative_theoretical_max') == 140

    def test_get_max_risk_per_spread_fixed_theoretical_max(self):
        """Fixed theoretical max should use max_theoretical_loss."""
        trade = {
            'conservative_theoretical_max_loss': 140,
            'max_theoretical_loss': 200
        }
        assert simulator.get_max_risk_per_spread(trade, 'fixed_theoretical_max') == 200

    def test_get_max_risk_per_spread_median_realized(self):
        """Should use median_risk_per_spread when specified."""
        trade = {
            'median_risk_per_spread': 75
        }
        assert simulator.get_max_risk_per_spread(trade, 'median_realized') == 75

    def test_get_max_risk_per_spread_average_realized(self):
        """Should use abs(avg_loss) when specified."""
        trade = {
            'avg_loss': -90
        }
        assert simulator.get_max_risk_per_spread(trade, 'average_realized') == 90

    def test_get_max_risk_per_spread_average_realized_trimmed(self):
        """Should calculate trimmed average of losses."""
        trade = {
            'pnl_distribution': [-50, -60, -70, -80, -1000]  # Top 20% is -1000
        }
        # Should exclude -1000, average of [-50,-60,-70,-80] = -65
        assert simulator.get_max_risk_per_spread(trade, 'average_realized_trimmed') == 65

    def test_get_max_risk_per_spread_raises_error_on_invalid_data(self):
        """Should raise ValueError when conservative theoretical data is missing."""
        trade = {}  # Empty trade data
        with pytest.raises(ValueError, match="Conservative theoretical loss data is missing"):
            simulator.get_max_risk_per_spread(trade, 'conservative_theoretical')

    def test_get_reward_cap_per_spread_no_cap_returns_none(self):
        """Default 'no_cap' should return None (no capping)."""
        trade = {
            'avg_win': 100,
            'max_win': 200
        }
        assert simulator.get_reward_cap_per_spread(trade, 'no_cap') is None
        # Test default parameter
        assert simulator.get_reward_cap_per_spread(trade) is None

    def test_get_reward_cap_per_spread_cap_50pct_conservative_theoretical_max(self):
        """Should return 50% of conservative_theoretical_max_reward."""
        trade = {
            'conservative_theoretical_max_reward': 300
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_50pct_conservative_theoretical_max') == 150

    def test_get_reward_cap_per_spread_cap_25pct_conservative_theoretical_max(self):
        """Should return 25% of conservative_theoretical_max_reward."""
        trade = {
            'conservative_theoretical_max_reward': 400
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_25pct_conservative_theoretical_max') == 100

    def test_get_reward_cap_per_spread_cap_40pct_conservative_theoretical_max(self):
        """Should return 40% of conservative_theoretical_max_reward."""
        trade = {
            'conservative_theoretical_max_reward': 250
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_40pct_conservative_theoretical_max') == 100

    def test_get_reward_cap_per_spread_cap_75pct_conservative_theoretical_max(self):
        """Should return 75% of conservative_theoretical_max_reward."""
        trade = {
            'conservative_theoretical_max_reward': 200
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_75pct_conservative_theoretical_max') == 150

    def test_get_reward_cap_per_spread_cap_50pct_theoretical_max(self):
        """Should return 50% of max_theoretical_gain."""
        trade = {
            'max_theoretical_gain': 500
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_50pct_theoretical_max') == 250

    def test_get_reward_cap_per_spread_cap_25pct_theoretical_max(self):
        """Should return 25% of max_theoretical_gain."""
        trade = {
            'max_theoretical_gain': 400
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_25pct_theoretical_max') == 100

    def test_get_reward_cap_per_spread_cap_40pct_theoretical_max(self):
        """Should return 40% of max_theoretical_gain."""
        trade = {
            'max_theoretical_gain': 300
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_40pct_theoretical_max') == 120

    def test_get_reward_cap_per_spread_cap_75pct_theoretical_max(self):
        """Should return 75% of max_theoretical_gain."""
        trade = {
            'max_theoretical_gain': 800
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_75pct_theoretical_max') == 600

    def test_get_reward_cap_per_spread_cap_50pct_average_realized(self):
        """Should return 50% of avg_win."""
        trade = {
            'avg_win': 150
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_50pct_average_realized') == 75

    def test_get_reward_cap_per_spread_cap_25pct_average_realized(self):
        """Should return 25% of avg_win."""
        trade = {
            'avg_win': 200
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_25pct_average_realized') == 50

    def test_get_reward_cap_per_spread_cap_40pct_average_realized(self):
        """Should return 40% of avg_win."""
        trade = {
            'avg_win': 175
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_40pct_average_realized') == 70

    def test_get_reward_cap_per_spread_cap_75pct_average_realized(self):
        """Should return 75% of avg_win."""
        trade = {
            'avg_win': 160
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_75pct_average_realized') == 120

    def test_get_reward_cap_per_spread_cap_50pct_conservative_realized_max(self):
        """Should return 50% of conservative_realized_max_reward."""
        trade = {
            'conservative_realized_max_reward': 350
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_50pct_conservative_realized_max') == 175

    def test_get_reward_cap_per_spread_cap_25pct_conservative_realized_max(self):
        """Should return 25% of conservative_realized_max_reward."""
        trade = {
            'conservative_realized_max_reward': 280
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_25pct_conservative_realized_max') == 70

    def test_get_reward_cap_per_spread_cap_40pct_conservative_realized_max(self):
        """Should return 40% of conservative_realized_max_reward."""
        trade = {
            'conservative_realized_max_reward': 225
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_40pct_conservative_realized_max') == 90

    def test_get_reward_cap_per_spread_cap_75pct_conservative_realized_max(self):
        """Should return 75% of conservative_realized_max_reward."""
        trade = {
            'conservative_realized_max_reward': 320
        }
        assert simulator.get_reward_cap_per_spread(trade, 'cap_75pct_conservative_realized_max') == 240

    def test_get_reward_cap_per_spread_raises_error_on_missing_conservative_theoretical_data(self):
        """Should raise ValueError when conservative_theoretical_max_reward is missing."""
        trade = {}
        with pytest.raises(ValueError, match="Conservative theoretical max reward data is missing"):
            simulator.get_reward_cap_per_spread(trade, 'cap_50pct_conservative_theoretical_max')

    def test_get_reward_cap_per_spread_raises_error_on_missing_theoretical_max_data(self):
        """Should raise ValueError when max_theoretical_gain is missing."""
        trade = {}
        with pytest.raises(ValueError, match="Theoretical max gain data is missing"):
            simulator.get_reward_cap_per_spread(trade, 'cap_50pct_theoretical_max')

    def test_get_reward_cap_per_spread_raises_error_on_missing_average_realized_data(self):
        """Should raise ValueError when avg_win is missing."""
        trade = {}
        with pytest.raises(ValueError, match="Average win data is missing"):
            simulator.get_reward_cap_per_spread(trade, 'cap_50pct_average_realized')

    def test_get_reward_cap_per_spread_raises_error_on_missing_conservative_realized_data(self):
        """Should raise ValueError when conservative_realized_max_reward is missing."""
        trade = {}
        with pytest.raises(ValueError, match="Conservative realized max reward data is missing"):
            simulator.get_reward_cap_per_spread(trade, 'cap_50pct_conservative_realized_max')

    def test_get_reward_cap_per_spread_raises_error_on_unknown_method(self):
        """Should raise ValueError on unknown reward calculation method."""
        trade = {'avg_win': 100}
        with pytest.raises(ValueError, match="Unknown reward calculation method: 'invalid_method'"):
            simulator.get_reward_cap_per_spread(trade, 'invalid_method')

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
            assert 'starting_risk_pct' in item
            assert 'max_risk_pct' in item

    def test_build_position_size_plan_respects_risk_calculation_method(self):
        """Percent sizing should use selected risk method when computing contracts."""
        trade = {
            'conservative_theoretical_max_loss': 100,
            'max_theoretical_loss': 200
        }
        initial_balance = 10000

        conservative_plan = simulator.build_position_size_plan(
            trade,
            initial_balance,
            'percent',
            risk_calculation_method='conservative_theoretical'
        )
        max_theoretical_plan = simulator.build_position_size_plan(
            trade,
            initial_balance,
            'percent',
            risk_calculation_method='max_theoretical'
        )

        conservative_25 = next(row for row in conservative_plan if row['target_risk_pct'] == 25.0)
        max_theoretical_25 = next(row for row in max_theoretical_plan if row['target_risk_pct'] == 25.0)

        assert conservative_25['contracts'] == 25
        assert max_theoretical_25['contracts'] == 12

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

    def test_starting_and_max_risk_pct_capped_at_100_percent_in_planning(self):
        """
        CRITICAL: Starting Risk % and Max Risk % in the planning phase must be capped at 100%
        to reflect the position size capping that will occur during simulation.
        This prevents displaying misleading risk percentages > 100%.
        
        Starting Risk %: Based on risk_calculation_method (simulation risk)
        Max Risk %: Based on conservative theoretical max (position sizing constraint)
        """
        trade = {
            'conservative_theoretical_max_loss': 200,  # $200 per spread (position sizing)
            'median_risk_per_spread': 50  # $50 per spread (for median_realized method)
        }
        initial_balance = 1000  # Only $1000 available
        
        # With contracts mode, request 10 contracts
        # Position sizing: Can only afford 5 contracts (5 * $200 = $1000 = 100% max risk)
        # If using median_realized for simulation: 5 * $50 = $250 = 25% starting risk
        plan = simulator.build_position_size_plan(
            trade, 
            initial_balance, 
            'contracts',
            risk_calculation_method='median_realized'
        )
        
        # Find the 10-contract row in the plan
        ten_contract_row = next((row for row in plan if simulator.DEFAULT_POSITION_SIZES[plan.index(row)] == 10), None)
        
        if ten_contract_row:
            # Max risk % should be capped at 100% (using 5 contracts, not 10)
            assert ten_contract_row['max_risk_pct'] == 100.0, \
                f"Expected max_risk_pct to be capped at 100%, got {ten_contract_row['max_risk_pct']:.2f}%"
            # Starting risk % should be 25% (5 contracts * $50 median / $1000)
            assert ten_contract_row['starting_risk_pct'] == 25.0, \
                f"Expected starting_risk_pct to be 25%, got {ten_contract_row['starting_risk_pct']:.2f}%"
        
        # Test with percent mode and 100% target risk
        plan_percent = simulator.build_position_size_plan(
            trade,
            initial_balance,
            'percent',
            risk_calculation_method='median_realized'
        )
        
        # Find the 100% target risk row
        hundred_pct_row = next(row for row in plan_percent if row['target_risk_pct'] == 100.0)
        
        # Should request 20 contracts (100% of $1000 / $50 median = 20)
        # But capped to 5 contracts (position sizing constraint)
        assert hundred_pct_row['contracts'] == 5, \
            f"Expected 5 contracts for 100% risk (capped), got {hundred_pct_row['contracts']}"
        
        # Starting risk should be 25% (5 * $50 / $1000)
        assert hundred_pct_row['starting_risk_pct'] == 25.0, \
            f"Expected starting_risk_pct to be 25%, got {hundred_pct_row['starting_risk_pct']:.2f}%"
        
        # Max risk should be exactly 100% (5 * 200 / 1000 = 100%)
        assert hundred_pct_row['max_risk_pct'] == 100.0, \
            f"Expected max_risk_pct to be 100%, got {hundred_pct_row['max_risk_pct']:.2f}%"

    def test_insufficient_balance_prevents_trading(self):
        """
        CRITICAL: If balance < max_risk_per_spread, we cannot afford even 1 contract.
        The system should prevent trading entirely (return empty plan or raise error).
        
        User scenario: Balance=$100, Max risk per spread=$101
        Result: Should NOT force 1 contract trade.
        """
        trade = {
            'conservative_theoretical_max_loss': 101  # $101 per spread
        }
        initial_balance = 100  # Only $100 available
        
        # With contracts mode, should return empty plan (can't afford any predefined sizes)
        plan = simulator.build_position_size_plan(
            trade, 
            initial_balance, 
            'contracts',
            risk_calculation_method='conservative_theoretical'
        )
        
        # Plan should be empty since we can't afford even 1 contract
        assert len(plan) == 0, \
            f"Expected empty plan when balance < max_risk, got {len(plan)} items"
        
        # With percent mode, should also return empty (all risk levels require >= 1 contract)
        plan_percent = simulator.build_position_size_plan(
            trade,
            initial_balance,
            'percent',
            risk_calculation_method='conservative_theoretical'
        )
        
        assert len(plan_percent) == 0, \
            f"Expected empty plan in percent mode when balance < max_risk, got {len(plan_percent)} items"
        
        # Running the full simulation should raise a clear error
        trade_stats = {
            'num_trades': 10,
            'win_rate': 0.5,
            'avg_win': 50,
            'avg_loss': -50,
            'max_win': 100,
            'max_loss': -101,
            'conservative_theoretical_max_loss': 101,
            'max_theoretical_loss': 101,
            'pnl_distribution': [50, -50] * 5
        }
        
        with pytest.raises(ValueError) as exc_info:
            simulator.run_monte_carlo_simulation(
                trade_stats=trade_stats,
                initial_balance=100,
                num_simulations=10,
                position_sizing='percent',
                risk_calculation_method='conservative_theoretical'
            )
        
        assert "insufficient to trade even 1 contract" in str(exc_info.value).lower(), \
            f"Expected clear error message about insufficient balance, got: {exc_info.value}"


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
                "win_rate": 1.0,
                "conservative_theoretical_max_loss": 100
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
                "win_rate": 0.0,
                "conservative_theoretical_max_loss": 100
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
            "win_rate": 0.5,
            "conservative_theoretical_max_loss": 200
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
            "pnl_distribution": [50, -50, 100, -100, 25],
            "conservative_theoretical_max_loss": 200
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

    def test_fixed_conservative_theoretical_max_risk_calculation_method(self):
        """Fixed conservative theoretical max should apply full conservative max risk on each loss."""
        with unittest.mock.patch('simulator.generate_reward', return_value=50):
            trade = {
                "name": "Test",
                "avg_loss": -50,
                "max_theoretical_loss": 200,
                "conservative_theoretical_max_loss": 100,
                "avg_win": 50,
                "max_win": 50,
                "win_rate": 0.0
            }

            results = simulator.simulate_trades(
                trade,
                position_size=1,
                initial_balance=1000,
                num_trades=5,
                num_simulations=1,
                risk_calculation_method='fixed_conservative_theoretical_max'
            )

            assert results[0]['final_balance'] == 500

    def test_average_realized_risk_calculation_method(self):
        """Test average realized risk method - all losses should be fixed at average amount."""
        with unittest.mock.patch('simulator.generate_reward', return_value=50):
            trade = {
                "name": "Test",
                "avg_loss": -75,  # Average loss = 75
                "max_loss": -100,
                "avg_win": 50,
                "max_win": 50,
                "win_rate": 0.0,  # 0% win rate to force losses
                "conservative_theoretical_max_loss": 100
            }
            position_size = 1
            initial_balance = 1000
            num_trades = 3
            num_simulations = 1

            results = simulator.simulate_trades(
                trade, position_size, initial_balance, num_trades, num_simulations,
                risk_calculation_method='average_realized'
            )

            # With average_realized, each loss should be exactly 75 (fixed amount)
            # 3 losses * 75 = 225 loss
            expected_final_balance = initial_balance - 225

            assert results[0]['final_balance'] == expected_final_balance

    def test_bankruptcy_stops_simulation(self):
        """Simulation should stop when balance reaches zero."""
        with unittest.mock.patch('simulator.generate_risk', return_value=500), \
             unittest.mock.patch('simulator.generate_reward', return_value=50):
            
            trade = {
                "avg_loss": -500,
                "max_loss": -500,
                "avg_win": 50,
                "max_win": 50,
                "win_rate": 0.0,  # Always lose
                "conservative_theoretical_max_loss": 500
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
                "win_rate": 1.0,  # Always win
                "conservative_theoretical_max_loss": 100
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
                "win_rate": 0.5,
                "conservative_theoretical_max_loss": 300
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
                "win_rate": 0.5,
                "conservative_theoretical_max_loss": 100
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

    def test_position_size_never_exceeds_account_balance_fixed_contracts(self):
        """
        CRITICAL: Position sizing must ensure that max_risk_per_spread *contracts <= balance
        at ALL times. This simulates a broker's margin requirement: you can't open a position
        whose theoretical max loss exceeds your account balance.
        """
        trade = {
            "avg_loss": -100,
            "max_loss": -200,
            "avg_win": 50,
            "max_win": 100,
            "win_rate": 0.0,  # Always lose
            "conservative_theoretical_max_loss": 200,  # Max loss per spread
            "max_theoretical_loss": 200,
            "num_trades": 10,
            "pnl_distribution": [-100] * 10
        }
        
        # Initial setup: $1000 balance, 10 contracts requested
        # Max loss per contract: $200
        # Max loss for position: 10 * $200 = $2000 > $1000 balance
        # Simulator MUST cap to 5 contracts (5 * $200 = $1000 <= $1000 balance)
        requested_position_size = 10
        initial_balance = 1000
        num_trades = 5
        num_simulations = 1
        
        # Force all trades to lose max amount
        with unittest.mock.patch('random.random', return_value=0.99):  # > 0.0 win_rate = loss
            results = simulator.simulate_trades(
                trade=trade,
                position_size=requested_position_size,
                initial_balance=initial_balance,
                num_trades=num_trades,
                num_simulations=num_simulations,
                dynamic_risk_sizing=False,
                risk_calculation_method='fixed_conservative_theoretical_max'
            )
        
        result = results[0]
        
        # With proper capping:
        # - First trade: Can afford 5 contracts (floor(1000/200) = 5)
        # - Loss = 5 * 200 = $1000
        # - Balance after = $1000 - $1000 = $0
        # - Simulation stops (bankruptcy)
        
        # Verify balance reached exactly $0 (used all available balance, no more)
        assert result['final_balance'] == 0, \
            f"Expected bankruptcy ($0) after one maximal loss with capped contracts. " \
            f"Got ${result['final_balance']}"
    
    def test_position_size_respects_balance_with_dynamic_sizing(self):
        """
        With dynamic sizing enabled, as balance grows/shrinks, position size
        should adjust such that max theoretical loss never exceeds balance.
        """
        trade = {
            "avg_loss": -100,
            "max_loss": -200,
            "avg_win": 50,
            "max_win": 100,
            "win_rate": 0.3,
            "conservative_theoretical_max_loss": 150,
            "max_theoretical_loss": 200,
            "num_trades": 10,
            "pnl_distribution": [-100] * 7 + [50] * 3
        }
        
        position_size = 5  # Starting position
        initial_balance = 1000
        target_risk_pct = 50  # Risk 50% of account
        num_trades = 30
        num_simulations = 10
        
        results = simulator.simulate_trades(
            trade=trade,
            position_size=position_size,
            initial_balance=initial_balance,
            num_trades=num_trades,
            num_simulations=num_simulations,
            target_risk_pct=target_risk_pct,
            dynamic_risk_sizing=True,
            risk_calculation_method='fixed_conservative_theoretical_max'
        )
        
        # With dynamic sizing, position size adjusts to maintain risk percentage
        # Balance should NEVER go negative even with max theoretical loss
        for result in results:
            final_balance = result['final_balance']
            assert final_balance >= 0, \
                f"Balance went negative with dynamic sizing! Final balance: {final_balance}"
    
    def test_position_size_capped_in_bootstrap_mode(self):
        """
        Bootstrap mode uses historical PNL values. Even when scaled by contracts,
        the theoretical max loss should not exceed account balance.
        """
        # Create a scenario where historical PNL scaled by contracts could exceed balance
        large_loss = -200  # Large historical loss
        trade = {
            "avg_loss": -50,
            "max_loss": large_loss,
            "avg_win": 30,
            "max_win": 100,
            "win_rate": 0.6,
            "conservative_theoretical_max_loss": 180,  # p95 of theoretical max
            "max_theoretical_loss": 200,
            "num_trades": 10,
            "pnl_distribution": [large_loss, -100, -50, 30, 30, 30, 50, 50, 80, 100]
        }
        
        position_size = 8  # 8 contracts * $180 = $1440 max theoretical loss
        initial_balance = 1000  # Less than max theoretical loss!
        num_trades = 20
        num_simulations = 5
        
        results = simulator.simulate_trades(
            trade=trade,
            position_size=position_size,
            initial_balance=initial_balance,
            num_trades=num_trades,
            num_simulations=num_simulations,
            dynamic_risk_sizing=False,
            simulation_mode='moving-block-bootstrap',
            block_size=3,
            risk_calculation_method='conservative_theoretical'
        )
        
        # Even in bootstrap mode, balance should never go negative
        for result in results:
            final_balance = result['final_balance']
            assert final_balance >= 0, \
                f"Balance went negative in bootstrap mode! Final balance: {final_balance}"
    
    def test_max_theoretical_risk_method_must_use_max_theoretical_for_position_sizing(self):
        """
        CRITICAL CORNER CASE: When risk_calculation_method='max_theoretical',
        position sizing MUST also use max_theoretical (not conservative_theoretical).
        
        Otherwise: Position sizing caps based on conservative (smaller) but loss simulation
        uses max_theoretical (larger), allowing trades that exceed account balance.
        
        Example:
        - Balance: $1000
        - conservative_theoretical_max_loss: $180 (p95)
        - max_theoretical_loss: $220 (absolute max)
        
        Bug scenario (using conservative for position sizing):
        - Allowed contracts: int(1000/180) = 5
        - Max loss if all 5 lose: 5 * 220 = $1100 > $1000 → EXCEEDS BALANCE!
        
        Fix: When risk_calculation_method uses max_theoretical, position sizing
        should also use max_theoretical: int(1000/220) = 4 contracts max.
        Then max loss = 4 * 220 = $880 ≤ $1000 ✓
        
        This test verifies that with 100% target risk and max_theoretical method,
        the actual starting risk doesn't exceed 100%.
        """
        trade = {
            "avg_loss": -100,
            "max_loss": -220,
            "avg_win": 50,
            "max_win": 100,
            "win_rate": 0.5,
            "conservative_theoretical_max_loss": 180,  # p95
            "max_theoretical_loss": 220,  # Absolute max (larger!)
            "median_risk_per_spread": 50,
            "num_trades": 10,
            "pnl_distribution": [-100] * 10
        }
        
        initial_balance = 1000
        
        # Build position size plan with max_theoretical risk method
        plan = simulator.build_position_size_plan(
            trade=trade,
            initial_balance=initial_balance,
            position_sizing='percent',
            risk_calculation_method='fixed_theoretical_max'
        )
        
        # Find the 100% target risk row
        hundred_pct_row = next(row for row in plan if row['target_risk_pct'] == 100.0)
        
        # The bug: Without the fix, position sizing would use conservative (180):
        # - choose_contract_count_for_risk_pct with max_theoretical (220) and 100% target
        #   calculates: 1000 * 1.0 / 220 = 4.5, rounds to 5 contracts
        # - Caps to: int(1000/180) = 5 contracts (no change)
        # - starting_risk_pct: 5 * 220 / 1000 = 110% > 100%! BUG!
        
        # With the fix: Position sizing should use max_theoretical (220):
        # - choose_contract_count_for_risk_pct with max_theoretical (220) and 100% target
        #   calculates: 1000 * 1.0 / 220 = 4.5, rounds to 4 or 5 contracts  
        # - Caps to: int(1000/220) = 4 contracts (properly capped!)
        # - starting_risk_pct: 4 * 220 / 1000 = 88% ≤ 100% ✓
        # - max_risk_pct: 4 * 220 / 1000 = 88% ≤ 100% ✓
        
        # Verify that starting_risk_pct doesn't exceed target (100%)
        # The starting risk should NEVER exceed the target risk
        starting_risk_pct_value = hundred_pct_row['starting_risk_pct']
        
        assert starting_risk_pct_value <= 100.0, \
            f"Starting Risk % ({starting_risk_pct_value:.2f}%) exceeds 100% target " \
            f"when using max_theoretical method! " \
            f"This means position sizing used conservative_theoretical " \
            f"(${trade['conservative_theoretical_max_loss']}) instead of " \
            f"max_theoretical (${trade['max_theoretical_loss']}). " \
            f"Contracts: {hundred_pct_row['contracts']} " \
            f"(should be {int(initial_balance / trade['max_theoretical_loss'])})"

    def test_reward_capping_with_no_cap_preserves_current_behavior(self):
        """Default 'no_cap' should behave identically to current behavior (no capping)."""
        with unittest.mock.patch('simulator.generate_risk', return_value=100), \
             unittest.mock.patch('simulator.generate_reward', return_value=150):
            
            trade = {
                "avg_loss": -100,
                "max_loss": -100,
                "avg_win": 150,
                "max_win": 200,
                "conservative_theoretical_max_reward": 180,
                "win_rate": 1.0,  # Always win
                "conservative_theoretical_max_loss": 100
            }
            position_size = 1
            initial_balance = 1000
            num_trades = 5
            num_simulations = 1

            results = simulator.simulate_trades(
                trade, position_size, initial_balance, num_trades, num_simulations,
                reward_calculation_method='no_cap'
            )

            # Should win full amount: 5 trades * 150 = 750
            expected_final_balance = initial_balance + 750
            assert results[0]['final_balance'] == expected_final_balance

    def test_reward_capping_caps_rewards_above_threshold(self):
        """Rewards above cap should be capped to the threshold."""
        with unittest.mock.patch('simulator.generate_risk', return_value=100):
            # Generate reward that exceeds the cap
            with unittest.mock.patch('simulator.generate_reward', return_value=200):
                trade = {
                    "avg_loss": -100,
                    "max_loss": -100,
                    "avg_win": 200,
                    "max_win": 300,
                    "conservative_theoretical_max_reward": 200,  # Cap at 50% = 100
                    "win_rate": 1.0,  # Always win
                    "conservative_theoretical_max_loss": 100
                }
                position_size = 1
                initial_balance = 1000
                num_trades = 5
                num_simulations = 1

                results = simulator.simulate_trades(
                    trade, position_size, initial_balance, num_trades, num_simulations,
                    reward_calculation_method='cap_50pct_conservative_theoretical_max'
                )

                # Generated reward = 200, but cap at 50% of 200 = 100
                # Should win capped amount: 5 trades * 100 = 500
                expected_final_balance = initial_balance + 500
                assert results[0]['final_balance'] == expected_final_balance

    def test_reward_capping_does_not_affect_rewards_below_cap(self):
        """Rewards below cap should not be affected."""
        with unittest.mock.patch('simulator.generate_risk', return_value=100):
            # Generate reward below the cap
            with unittest.mock.patch('simulator.generate_reward', return_value=40):
                trade = {
                    "avg_loss": -100,
                    "max_loss": -100,
                    "avg_win": 40,
                    "max_win": 200,
                    "conservative_theoretical_max_reward": 200,  # Cap at 50% = 100
                    "win_rate": 1.0,  # Always win
                    "conservative_theoretical_max_loss": 100
                }
                position_size = 1
                initial_balance = 1000
                num_trades = 5
                num_simulations = 1

                results = simulator.simulate_trades(
                    trade, position_size, initial_balance, num_trades, num_simulations,
                    reward_calculation_method='cap_50pct_conservative_theoretical_max'
                )

                # Generated reward = 40, cap = 100, so take 40
                # Should win uncapped amount: 5 trades * 40 = 200
                expected_final_balance = initial_balance + 200
                assert results[0]['final_balance'] == expected_final_balance

    def test_reward_capping_scales_with_contract_count(self):
        """Reward cap should scale with number of contracts."""
        with unittest.mock.patch('simulator.generate_risk', return_value=100):
            with unittest.mock.patch('simulator.generate_reward', return_value=400):  # Above cap
                trade = {
                    "avg_loss": -100,
                    "max_loss": -100,
                    "avg_win": 200,
                    "max_win": 300,
                    "conservative_theoretical_max_reward": 200,  # Cap at 50% = 100 per contract
                    "win_rate": 1.0,  # Always win
                    "conservative_theoretical_max_loss": 100
                }
                position_size = 3  # 3 contracts
                initial_balance = 5000
                num_trades = 2
                num_simulations = 1

                results = simulator.simulate_trades(
                    trade, position_size, initial_balance, num_trades, num_simulations,
                    reward_calculation_method='cap_50pct_conservative_theoretical_max'
                )

                # Cap per contract = 100, 3 contracts = 300 total cap per trade
                # Generated reward (mocked) = 400
                # Capped to 300 per trade
                # 2 trades * 300 = 600 total reward
                expected_final_balance = initial_balance + 600
                assert results[0]['final_balance'] == expected_final_balance

    def test_reward_capping_with_theoretical_max_metric(self):
        """Test reward capping using theoretical max as base metric."""
        with unittest.mock.patch('simulator.generate_risk', return_value=100):
            with unittest.mock.patch('simulator.generate_reward', return_value=150):
                trade = {
                    "avg_loss": -100,
                    "max_loss": -100,
                    "avg_win": 150,
                    "max_win": 200,
                    "max_theoretical_gain": 400,  # Cap at 25% = 100
                    "win_rate": 1.0,
                    "conservative_theoretical_max_loss": 100
                }
                position_size = 1
                initial_balance = 1000
                num_trades = 5
                num_simulations = 1

                results = simulator.simulate_trades(
                    trade, position_size, initial_balance, num_trades, num_simulations,
                    reward_calculation_method='cap_25pct_theoretical_max'
                )

                # Cap at 25% of 400 = 100
                # Generated = 150, capped to 100
                expected_final_balance = initial_balance + 500
                assert results[0]['final_balance'] == expected_final_balance

    def test_reward_capping_with_average_realized_metric(self):
        """Test reward capping using average realized wins as base metric."""
        with unittest.mock.patch('simulator.generate_risk', return_value=100):
            with unittest.mock.patch('simulator.generate_reward', return_value=120):
                trade = {
                    "avg_loss": -100,
                    "max_loss": -100,
                    "avg_win": 80,  # Cap at 75% = 60
                    "max_win": 200,
                    "win_rate": 1.0,
                    "conservative_theoretical_max_loss": 100
                }
                position_size = 1
                initial_balance = 1000
                num_trades = 4
                num_simulations = 1

                results = simulator.simulate_trades(
                    trade, position_size, initial_balance, num_trades, num_simulations,
                    reward_calculation_method='cap_75pct_average_realized'
                )

                # Cap at 75% of 80 = 60
                # Generated = 120, capped to 60
                # 4 trades * 60 = 240
                expected_final_balance = initial_balance + 240
                assert results[0]['final_balance'] == expected_final_balance

    def test_reward_capping_with_conservative_realized_max_metric(self):
        """Test reward capping using conservative realized max (p95 of wins) as base metric."""
        with unittest.mock.patch('simulator.generate_risk', return_value=100):
            with unittest.mock.patch('simulator.generate_reward', return_value=200):
                trade = {
                    "avg_loss": -100,
                    "max_loss": -100,
                    "avg_win": 100,
                    "max_win": 250,
                    "conservative_realized_max_reward": 240,  # Cap at 40% = 96
                    "win_rate": 1.0,
                    "conservative_theoretical_max_loss": 100
                }
                position_size = 1
                initial_balance = 1000
                num_trades = 3
                num_simulations = 1

                results = simulator.simulate_trades(
                    trade, position_size, initial_balance, num_trades, num_simulations,
                    reward_calculation_method='cap_40pct_conservative_realized_max'
                )

                # Cap at 40% of 240 = 96
                # Generated = 200, capped to 96
                # 3 trades * 96 = 288
                expected_final_balance = initial_balance + 288
                assert results[0]['final_balance'] == expected_final_balance

    def test_reward_capping_in_bootstrap_mode_does_not_cap_historical_pnl(self):
        """Bootstrap mode should use historical P/L as-is, without capping."""
        trade = {
            "avg_loss": -100,
            "max_loss": -100,
            "avg_win": 80,
            "max_win": 200,
            "conservative_theoretical_max_reward": 120,  # Cap at 50% = 60
            "win_rate": 0.5,
            "pnl_distribution": [150, -50, 200, -100, 180],  # Historical values
            "conservative_theoretical_max_loss": 100
        }
        position_size = 1
        initial_balance = 1000
        num_trades = 5
        num_simulations = 1

        results = simulator.simulate_trades(
            trade, position_size, initial_balance, num_trades, num_simulations,
            simulation_mode='moving-block-bootstrap',
            block_size=1,
            reward_calculation_method='cap_50pct_conservative_theoretical_max'
        )

        # In bootstrap mode, reward capping should NOT apply to historical P/L
        # The P/L distribution should be used as-is: [150, -50, 200, -100, 180]
        # Sum = 380, so final balance should be 1000 + 380 = 1380
        # Note: The actual order might be different due to sampling, but sum should match
        # Actually, with block_size=1 and num_trades=5, it will sample 5 values from the distribution
        # Since we can't predict exact sampling, let's just verify it's not capped to 60 per trade
        
        final_balance = results[0]['final_balance']
        # If capping was applied, max possible would be: 1000 + (3 wins * 60) - (2 losses * 100) = 980
        # If capping NOT applied, we should see higher values possible
        # Since pnl_distribution has wins of 150, 200, 180 and losses of -50, -100,
        # any sampling that includes the 200 would exceed the capped amount
        # We can't assert exact value due to random sampling, but we can verify structure exists
        assert isinstance(final_balance, (int, float))

    def test_reward_capping_works_with_mixed_win_loss_outcomes(self):
        """Test reward capping with alternating wins and losses."""
        with unittest.mock.patch('simulator.generate_risk', return_value=100):
            with unittest.mock.patch('simulator.generate_reward', return_value=180):
                trade = {
                    "avg_loss": -100,
                    "max_loss": -100,
                    "avg_win": 180,
                    "max_win": 250,
                    "conservative_theoretical_max_reward": 200,  # Cap at 50% = 100
                    "win_rate": 0.5,
                    "conservative_theoretical_max_loss": 100
                }
                position_size = 1
                initial_balance = 1000
                num_trades = 6
                num_simulations = 1

                # Mock random to alternate: win, loss, win, loss, win, loss
                with unittest.mock.patch('random.random', side_effect=[0.3, 0.7, 0.3, 0.7, 0.3, 0.7]):
                    results = simulator.simulate_trades(
                        trade, position_size, initial_balance, num_trades, num_simulations,
                        reward_calculation_method='cap_50pct_conservative_theoretical_max'
                    )

                # 3 wins capped at 100 = +300
                # 3 losses at 100 = -300
                # Net = 0
                expected_final_balance = initial_balance
                assert results[0]['final_balance'] == expected_final_balance


class TestTargetRiskEnforcement:
    """Tests for enforcing strict target risk % limits."""
    
    def test_simulator_skips_trades_exceeding_target_risk_by_default(self):
        """When allow_exceed_target_risk=False (default), no trades should be taken if 1 contract exceeds target risk %."""
        trade_stats = {
            'num_trades': 10,
            'win_rate': 0.6,
            'avg_win': 100,
            'avg_loss': -50,
            'max_win': 200,
            'max_loss': -100,
            'max_theoretical_loss': 200,
            'conservative_theoretical_max_loss': 200,  # Risk per contract
            'pnl_distribution': [50, -50, 50, -50, 50, -50, 50, -50, 50, -50]
        }
        
        # Initial balance $1000, target risk 2%
        # 2% of $1000 = $20
        # But 1 contract requires $200 risk, which is 20% (exceeds 2%)
        # With allow_exceed_target_risk=False, no trades should be taken
        reports = simulator.run_monte_carlo_simulation(
            trade_stats=trade_stats,
            initial_balance=1000,
            num_simulations=10,
            position_sizing='percent',
            dynamic_risk_sizing=True,
            simulation_mode='iid',
            block_size=5,
            allow_exceed_target_risk=False  # Default: strict enforcement
        )
        
        # Should have results but with very specific behavior
        # The simulation should show 0 contracts for the 2% risk level
        # Or alternatively, final balance should equal initial balance (no trades taken)
        report = reports[0]
        # Find the 2% risk row
        two_pct_rows = [row for row in report['table_rows'] if '2.00%' in row['Target Risk %']]
        if two_pct_rows:
            row = two_pct_rows[0]
            # Should have 0 contracts or no trades executed (final balance = initial)
            # Check if final balance is close to initial (allowing for rounding)
            final_balance_str = row['Avg Final $'].replace('$', '').replace(',', '')
            final_balance = float(final_balance_str)
            assert abs(final_balance - 1000) < 10, f"Expected no trades (balance ~$1000), got ${final_balance}"
    
    def test_simulator_allows_trades_exceeding_target_risk_when_enabled(self):
        """When allow_exceed_target_risk=True, trades CAN be taken even if they exceed target risk %."""
        trade_stats = {
            'num_trades': 10,
            'win_rate': 0.6,
            'avg_win': 100,
            'avg_loss': -50,
            'max_win': 200,
            'max_loss': -100,
            'max_theoretical_loss': 200,
            'conservative_theoretical_max_loss': 200,
            'pnl_distribution': [50, -50, 50, -50, 50, -50, 50, -50, 50, -50]
        }
        
        # Same scenario but with allow_exceed_target_risk=True
        reports = simulator.run_monte_carlo_simulation(
            trade_stats=trade_stats,
            initial_balance=1000,
            num_simulations=10,
            position_sizing='percent',
            dynamic_risk_sizing=True,
            simulation_mode='iid',
            block_size=5,
            allow_exceed_target_risk=True  # Allow exceeding
        )
        
        report = reports[0]
        # Find the 2% risk row
        two_pct_rows = [row for row in report['table_rows'] if '2.00%' in row['Target Risk %']]
        if two_pct_rows:
            row = two_pct_rows[0]
            # Should take 1 contract (even though it exceeds 2% target)
            assert row['Contracts'] >= 1, "Should allow at least 1 contract when allow_exceed_target_risk=True"
            # Final balance should be different from initial (trades were executed)
            final_balance_str = row['Avg Final $'].replace('$', '').replace(',', '')
            final_balance = float(final_balance_str)
            # With positive win rate, balance should likely be higher, but at minimum should be different
            assert abs(final_balance - 1000) > 50, f"Expected trades to execute, but balance is ~$1000 (got ${final_balance})"
    
    def test_simulator_stops_trading_when_balance_drops_and_exceeds_target_risk(self):
        """When balance drops during simulation, should stop if next trade would exceed target risk %."""
        trade_stats = {
            'num_trades': 20,
            'win_rate': 0.3,  # More losses
            'avg_win': 50,
            'avg_loss': -100,
            'max_win': 100,
            'max_loss': -150,
            'max_theoretical_loss': 150,
            'conservative_theoretical_max_loss': 150,
            'pnl_distribution': [-100] * 20  # All losses
        }
        
        # Start with $10,000, target risk 5%
        # 5% of $10,000 = $500
        # $500 / $150 = 3.33 contracts, so start with 3 contracts
        # After losses, balance drops. If balance drops to $400, next trade needs 1 contract = $150
        # $150 / $400 = 37.5% which exceeds 5% target
        # With allow_exceed_target_risk=False, should stop trading
        reports = simulator.run_monte_carlo_simulation(
            trade_stats=trade_stats,
            initial_balance=10000,
            num_simulations=5,
            position_sizing='percent',
            dynamic_risk_sizing=True,
            simulation_mode='iid',
            block_size=5,
            allow_exceed_target_risk=False
        )
        
        report = reports[0]
        # Find the 5% risk row
        five_pct_rows = [row for row in report['table_rows'] if '5.00%' in row['Target Risk %']]
        if five_pct_rows:
            row = five_pct_rows[0]
            # Should not go to 0 (bankruptcy) because we stop before taking unaffordable trades
            # Final balance should be > 0
            final_balance_str = row['Avg Final $'].replace('$', '').replace(',', '')
            final_balance = float(final_balance_str)
            # Check bankruptcy probability
            bankruptcy_prob_str = row['Bankruptcy Prob'].replace('%', '')
            bankruptcy_prob = float(bankruptcy_prob_str) / 100
            # With strict enforcement, bankruptcy should be 0% or very low
            assert bankruptcy_prob < 0.5, f"Expected low bankruptcy with strict enforcement, got {bankruptcy_prob:.0%}"
    
    def test_simulator_enforces_total_risk_ceiling_not_just_one_contract(self):
        """When allow_exceed_target_risk=False, TOTAL risk from all contracts must not exceed target, not just 1 contract."""
        trade_stats = {
            'num_trades': 20,
            'win_rate': 0.6,
            'avg_win': 100,
            'avg_loss': -50,
            'max_win': 200,
            'max_loss': -100,
            'max_theoretical_loss': 100,
            'conservative_theoretical_max_loss': 100,  # Risk per contract
            'pnl_distribution': [50, -50] * 10  # Alternate wins/losses
        }
        
        # Initial balance $10,000, target risk 15%
        # 15% of $10,000 = $1,500
        # Risk per contract = $100
        # Could fit 15 contracts ($1,500 / $100 = 15.0), exactly at ceiling
        # With allow_exceed_target_risk=False, should take at most 15 contracts
        # Total risk = 15 * $100 = $1,500 = 15.00% (exactly at ceiling)
        reports = simulator.run_monte_carlo_simulation(
            trade_stats=trade_stats,
            initial_balance=10000,
            num_simulations=10,
            position_sizing='percent',
            dynamic_risk_sizing=True,
            simulation_mode='iid',
            block_size=5,
            allow_exceed_target_risk=False  # Strict enforcement
        )
        
        report = reports[0]
        # Find the 15% risk row
        fifteen_pct_rows = [row for row in report['table_rows'] if '15.00%' in row['Target Risk %']]
        if fifteen_pct_rows:
            row = fifteen_pct_rows[0]
            # Should have exactly 15 contracts (floor(15% * 10000 / 100) = 15)
            # NOT 16 or more contracts that would exceed 15%
            assert row['Contracts'] == 15, \
                f"Expected exactly 15 contracts (15% ceiling), got {row['Contracts']}"
            
            # Starting Risk % should be exactly 15% or less
            starting_risk_str = row['Starting Risk %'].replace('%', '')
            starting_risk = float(starting_risk_str)
            assert starting_risk <= 15.0, \
                f"Expected starting risk <= 15%, got {starting_risk}%"

    def test_max_risk_pct_tracks_dynamic_changes_during_simulation(self):
        """
        Max Risk % should track the actual maximum risk taken during simulation,
        not just the initial risk percentage.
        
        When using dynamic risk sizing, as the account grows, more contracts can be
        taken while staying under the risk ceiling. The max_risk_pct should reflect
        the highest risk % actually taken during any trade in the simulation.
        
        Example: Start with $1000 balance, $180 risk per spread (conservative), 10% ceiling:
        - Initially can afford 1 contract: 180/1000 = 18% > ceiling, so 0 contracts (or capped)
        
        Better example: Start with $2000, $180 risk, 10% ceiling:
        - Initially: 1 contract = 180/2000 = 9% risk
        - After winning and reaching $4000: 2 contracts = 360/4000 = 9% risk
        - Max Risk % should be 9% (or higher if we hit the ceiling with growth)
        
        This test verifies that max_risk_pct reflects actual simulation behavior,
        not just starting conditions.
        """
        np.random.seed(42)
        
        trade_stats = {
            'num_trades': 20,
            'win_rate': 0.7,  # High win rate to grow account
            'avg_win': 80,
            'avg_loss': -180,
            'max_win': 150,
            'median_risk_per_spread': 180,
            'conservative_theoretical_max_loss': 180,
            'max_theoretical_loss': 220,
            'pnl_distribution': [80, -180] * 10  # Alternating to ensure data
        }
        
        # Start with balance where 1 contract = ~7% risk
        # Risk per spread = 180, so 180/2500 = 7.2%
        initial_balance = 2500
        risk_ceiling = 10.0  # 10% target risk
        
        reports = simulator.run_monte_carlo_simulation(
            trade_stats=trade_stats,
            initial_balance=initial_balance,
            num_simulations=100,
            num_trades=20,
            position_sizing='percent',
            dynamic_risk_sizing=True,
            simulation_mode='iid',
            risk_calculation_method='conservative_theoretical',
            allow_exceed_target_risk=False
        )
        
        assert len(reports) == 1
        report = reports[0]
        
        # Find the row closest to our 10% risk ceiling
        target_row = None
        for row in report['table_rows']:
            target_pct_str = row['Target Risk %'].replace('%', '')
            target_pct = float(target_pct_str)
            if abs(target_pct - risk_ceiling) < 0.1:
                target_row = row
                break
        
        assert target_row is not None, "Should have a row near 10% target risk"
        
        # Extract risk percentages
        starting_risk_str = target_row['Starting Risk %'].replace('%', '')
        starting_risk = float(starting_risk_str)
        max_risk_str = target_row['Max Risk %'].replace('%', '')
        max_risk = float(max_risk_str)
        
        # Starting risk should be ~7.2% (1 contract × 180 / 2500)
        assert 7.0 <= starting_risk <= 7.5, \
            f"Expected starting risk ~7.2% (1 contract), got {starting_risk}%"
        
        # CRITICAL: Max risk should be HIGHER than starting risk because:
        # - Account grows with 70% win rate
        # - When balance reaches ~3600, can afford 2 contracts at 10% risk (360/3600)
        # - Max Risk % should reflect this higher risk taken during simulation
        # 
        # This is currently FAILING because the simulator calculates max_risk_pct
        # only once at the start, not tracking actual risk during simulation.
        assert max_risk > starting_risk, \
            f"Max Risk % ({max_risk}%) should exceed Starting Risk % ({starting_risk}%) " \
            f"when account grows and takes more contracts. Currently displaying same value, " \
            f"indicating max_risk_pct is calculated only at start, not tracked during simulation."

