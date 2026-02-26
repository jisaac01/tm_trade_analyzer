import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import replay
import pytest


class TestReplayActualTrades:
    """Tests for historical trade replay functionality."""

    def test_replay_with_fixed_contracts_all_wins(self):
        """Replay actual trades with fixed contract sizing - all wins."""
        trade_stats = {
            'num_trades': 5,
            'win_rate': 1.0,
            'avg_win': 100,
            'avg_loss': -50,
            'max_win': 200,
            'max_loss': -100,
            'max_theoretical_loss': 100,
            'conservative_theoretical_max_loss': 80,
            'pnl_distribution': [50, 75, 100, 60, 80],  # All positive
            'per_trade_theoretical_risk': [100, 100, 100, 100, 100],
            'per_trade_theoretical_reward': [50, 50, 50, 50, 50],
            'per_trade_dates': ['2023-01-01', '2023-02-01', '2023-03-01', '2023-04-01', '2023-05-01']
        }
        
        result = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=1000,
            position_sizing='contracts',
            position_size=2,  # Fixed 2 contracts
            dynamic_risk_sizing=False,
            risk_calculation_method='conservative_theoretical'
        )
        
        # Should have 5 trades
        assert len(result['trade_history']) == 6  # Initial + 5 trades
        
        # Expected: 1000 + 2*(50+75+100+60+80) = 1000 + 2*365 = 1730
        assert result['final_balance'] == 1730
        
        # No drawdown with all wins
        assert result['max_drawdown'] == 0
        
        # No losing streak
        assert result['max_losing_streak'] == 0

    def test_replay_with_fixed_contracts_mixed_results(self):
        """Replay actual trades with fixed contract sizing - mixed wins and losses."""
        trade_stats = {
            'num_trades': 6,
            'win_rate': 0.5,
            'avg_win': 100,
            'avg_loss': -50,
            'max_win': 200,
            'max_loss': -100,
            'max_theoretical_loss': 100,
            'conservative_theoretical_max_loss': 80,
            'pnl_distribution': [50, -40, 100, -60, 75, -30],  # Mix of wins/losses
            'per_trade_theoretical_risk': [150, 150, 150, 150, 150, 150],
            'per_trade_theoretical_reward': [100, 100, 100, 100, 100, 100],
            'per_trade_dates': ['2023-01-01', '2023-02-01', '2023-03-01', '2023-04-01', '2023-05-01', '2023-06-01']
        }
        
        result = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=1000,
            position_sizing='contracts',
            position_size=2,
            dynamic_risk_sizing=False,
            risk_calculation_method='conservative_theoretical'
        )
        
        # Calculate expected balance:
        # P/L per contract: 50, -40, 100, -60, 75, -30 = total 95/contract
        # With 2 contracts: 95 * 2 = 190 profit
        # Max affordable per trade: 1000/150 = 6 contracts, so 2 contracts is fine
        assert result['final_balance'] == 1190
        
        # Verify trade history progression
        expected_balances = [1000, 1100, 1020, 1220, 1100, 1250, 1190]
        assert result['trade_history'] == expected_balances
        
        # Max losing streak should be 1 (each loss is followed by a win)
        assert result['max_losing_streak'] == 1

    def test_replay_with_dynamic_risk_sizing(self):
        """Replay actual trades with dynamic risk percentage sizing."""
        trade_stats = {
            'num_trades': 4,
            'win_rate': 0.5,
            'avg_win': 100,
            'avg_loss': -50,
            'max_win': 200,
            'max_loss': -100,
            'max_theoretical_loss': 100,
            'conservative_theoretical_max_loss': 100,
            'pnl_distribution': [100, -50, 80, -40],
            'per_trade_theoretical_risk': [100, 100, 100, 100],
            'per_trade_theoretical_reward': [75, 75, 75, 75],
            'per_trade_dates': ['2023-01-01', '2023-02-01', '2023-03-01', '2023-04-01']
        }
        
        result = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=1000,
            position_sizing='percent',
            target_risk_pct=10,  # 10% risk per trade
            dynamic_risk_sizing=True,
            risk_calculation_method='conservative_theoretical'
        )
        
        # Trade 1: 10% of 1000 = $100 risk, 1 contract max, win 100
        # Balance after: 1000 + 1*100 = 1100
        # Trade 2: 10% of 1100 = $110 risk, 1 contract max, lose 50
        # Balance after: 1100 - 1*50 = 1050
        # Trade 3: 10% of 1050 = $105 risk, 1 contract max, win 80
        # Balance after: 1050 + 1*80 = 1130
        # Trade 4: 10% of 1130 = $113 risk, 1 contract max, lose 40
        # Balance after: 1130 - 1*40 = 1090
        
        assert result['final_balance'] == 1090
        expected_balances = [1000, 1100, 1050, 1130, 1090]
        assert result['trade_history'] == expected_balances

    def test_replay_with_bankruptcy(self):
        """Replay should stop when balance reaches zero."""
        trade_stats = {
            'num_trades': 5,
            'win_rate': 0.0,
            'avg_win': 100,
            'avg_loss': -50,
            'max_win': 200,
            'max_loss': -100,
            'max_theoretical_loss': 100,
            'conservative_theoretical_max_loss': 100,
            'pnl_distribution': [-80, -60, -70, -50, -40],  # All losses
            'per_trade_theoretical_risk': [100, 100, 100, 100, 100],
            'per_trade_theoretical_reward': [60, 60, 60, 60, 60],
            'per_trade_dates': ['2023-01-01', '2023-02-01', '2023-03-01', '2023-04-01', '2023-05-01']
        }
        
        result = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=200,
            position_sizing='contracts',
            position_size=2,
            dynamic_risk_sizing=False,
            risk_calculation_method='conservative_theoretical'
        )
        
        # Trade 1: 200 - 2*80 = 40
        # Trade 2: 40 - 2*60 = -80, but balance can't go negative
        # Position size should be capped: 40/100 = 0 contracts (bankruptcy)
        
        assert result['final_balance'] == 40
        # Should have stopped after 1 trade
        assert len(result['trade_history']) == 2  # Initial + 1 trade

    def test_replay_tracks_max_drawdown(self):
        """Replay should correctly track maximum drawdown."""
        trade_stats = {
            'num_trades': 5,
            'win_rate': 0.6,
            'avg_win': 100,
            'avg_loss': -50,
            'max_win': 200,
            'max_loss': -100,
            'max_theoretical_loss': 100,
            'conservative_theoretical_max_loss': 100,
            'pnl_distribution': [100, 150, -80, -70, 200],
            'per_trade_theoretical_risk': [100, 100, 100, 100, 100],
            'per_trade_theoretical_reward': [80, 80, 80, 80, 80],
            'per_trade_dates': ['2023-01-01', '2023-02-01', '2023-03-01', '2023-04-01', '2023-05-01']
        }
        
        result = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=1000,
            position_sizing='contracts',
            position_size=1,
            dynamic_risk_sizing=False,
            risk_calculation_method='conservative_theoretical'
        )
        
        # Balance progression: 1000, 1100, 1250, 1170, 1100, 1300
        # Peak: 1250 (after trade 2)
        # Drawdown after trade 3: 1250 - 1170 = 80
        # Drawdown after trade 4: 1250 - 1100 = 150 (max)
        
        assert result['max_drawdown'] == 150

    def test_replay_with_position_size_capping(self):
        """Position size should be capped when balance decreases."""
        trade_stats = {
            'num_trades': 3,
            'win_rate': 0.33,
            'avg_win': 50,
            'avg_loss': -50,
            'max_win': 100,
            'max_loss': -100,
            'max_theoretical_loss': 100,
            'conservative_theoretical_max_loss': 100,
            'pnl_distribution': [-80, -60, 50],
            'per_trade_theoretical_risk': [100, 100, 100],
            'per_trade_theoretical_reward': [70, 70, 70],
            'per_trade_dates': ['2023-01-01', '2023-02-01', '2023-03-01']
        }
        
        result = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=250,
            position_sizing='contracts',
            position_size=5,  # Request 5 contracts
            dynamic_risk_sizing=False,
            risk_calculation_method='conservative_theoretical'
        )
        
        # Trade 1: Can afford 2 contracts (250/100=2.5), lose 80*2=160
        # Balance: 250 - 160 = 90
        # Trade 2: Can afford 0 contracts (90/100=0.9), bankruptcy!
        
        assert result['final_balance'] == 90
        assert len(result['trade_history']) == 2  # Stopped after trade 1

    def test_replay_respects_risk_calculation_method(self):
        """Replay uses per-trade theoretical risk regardless of risk_calculation_method."""
        trade_stats = {
            'num_trades': 2,
            'win_rate': 0.5,
            'avg_win': 100,
            'avg_loss': -50,
            'max_win': 200,
            'max_loss': -100,
            'max_theoretical_loss': 200,  # Higher
            'conservative_theoretical_max_loss': 100,  # Lower
            'pnl_distribution': [50, -60],
            'per_trade_theoretical_risk': [200, 200],
            'per_trade_theoretical_reward': [150, 150],
            'per_trade_dates': ['2023-01-01', '2023-02-01']
        }
        
        # With conservative method - but per_trade_theoretical_risk overrides
        result_conservative = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=1000,
            position_sizing='contracts',
            position_size=15,
            dynamic_risk_sizing=False,
            risk_calculation_method='conservative_theoretical'
        )
        
        # Position sizing now uses per_trade_theoretical_risk (200):
        # Trade 1: 1000/200 = 5 contracts max, win 50*5 = 250, balance = 1250
        # Trade 2: 1250/200 = 6 contracts max, lose 60*6 = 360, balance = 890
        assert result_conservative['final_balance'] == 890
        
        # With max_theoretical method - should get same result since using per-trade risk
        result_max = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=1000,
            position_sizing='contracts',
            position_size=15,
            dynamic_risk_sizing=False,
            risk_calculation_method='max_theoretical'
        )
        
        # Same calculation - per_trade_theoretical_risk (200) is used:
        # Trade 1: 1000/200 = 5 contracts max, win 50*5 = 250, balance = 1250
        # Trade 2: 1250/200 = 6 contracts max, lose 60*6 = 360, balance = 890
        assert result_max['final_balance'] == 890
        
        # Both should be identical since per-trade risk overrides risk_calculation_method
        assert result_conservative['final_balance'] == result_max['final_balance']

    def test_replay_empty_pnl_distribution(self):
        """Replay should raise error with empty P/L distribution."""
        trade_stats = {
            'num_trades': 0,
            'win_rate': 0.5,
            'avg_win': 100,
            'avg_loss': -50,
            'max_win': 200,
            'max_loss': -100,
            'max_theoretical_loss': 100,
            'conservative_theoretical_max_loss': 100,
            'pnl_distribution': [],
            'per_trade_theoretical_risk': [],
            'per_trade_theoretical_reward': [],
            'per_trade_dates': []
        }
        
        with pytest.raises(ValueError, match="pnl_distribution.*empty"):
            replay.replay_actual_trades(
                trade_stats=trade_stats,
                initial_balance=1000,
                position_sizing='contracts',
                position_size=2,
                dynamic_risk_sizing=False,
                risk_calculation_method='conservative_theoretical'
            )

    def test_replay_uses_per_trade_risk_when_available(self):
        """Test that per_trade_theoretical_risk is used for position sizing when available."""
        # Trade 1: theoretical max = $500, P/L = +$100
        # Trade 2: theoretical max = $200, P/L = +$50  
        # Trade 3: theoretical max = $1000, P/L = +$200
        trade_stats = {
            'pnl_distribution': [100, 50, 200],
            'per_trade_theoretical_risk': [500, 200, 1000],
            'per_trade_theoretical_reward': [300, 150, 600],
            'per_trade_dates': ['2023-01-01', '2023-02-01', '2023-03-01'],
            'num_trades': 3,
            'max_theoretical_loss': 500,
            'conservative_theoretical_max_loss': 450,
            'max_theoretical_reward': 300,
            'conservative_max_theoretical_reward': 250
        }
        
        # With $10,000 balance and 2% risk target (dynamic):
        # Trade 1: risk $500, want 2% of $10,000 = $200 risk, so max(1, floor(200/500)) = 1 contract
        #   After: $10,100
        # Trade 2: risk $200, want 2% of $10,100 = $202, so max(1, floor(202/200)) = 1 contract
        #   After: $10,150
        # Trade 3: risk $1000, want 2% of $10,150 = $203, so max(1, floor(203/1000)) = 1 contract
        #   After: $10,350
        
        result = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=10000,
            position_sizing='percent',
            target_risk_pct=2.0,
            dynamic_risk_sizing=True,
            risk_calculation_method='conservative_theoretical'
        )
        
        assert result['final_balance'] == 10350
        assert len(result['trade_history']) == 4  # Initial + 3 trades
        total_pnl = result['final_balance'] - 10000
        assert total_pnl == 350
    
    def test_replay_errors_when_per_trade_risk_missing(self):
        """Test that error is raised when per_trade_theoretical_risk is missing."""
        trade_stats = {
            'pnl_distribution': [100, -50, 200],
            # No per_trade_theoretical_risk provided
            'num_trades': 3,
            'max_theoretical_loss': 300,
            'conservative_theoretical_max_loss': 250,
            'max_theoretical_reward': 400,
            'conservative_max_theoretical_reward': 300
        }
        
        with pytest.raises(ValueError, match="per_trade_theoretical_risk is required but missing"):
            replay.replay_actual_trades(
                trade_stats=trade_stats,
                initial_balance=10000,
                position_sizing='contracts',
                position_size=2,
                risk_calculation_method='conservative_theoretical'
            )
    
    def test_replay_with_varying_per_trade_risk_affects_position_sizing(self):
        """Test that different per-trade risks lead to different position limits."""
        trade_stats = {
            'pnl_distribution': [100, -50, 200],
            'per_trade_theoretical_risk': [2000, 500, 10000],  # Varying risks
            'per_trade_theoretical_reward': [1200, 300, 6000],  # Varying rewards
            'per_trade_dates': ['2023-01-01', '2023-02-01', '2023-03-01'],
            'num_trades': 3,
            'max_theoretical_loss': 2000,
            'conservative_theoretical_max_loss': 1800
        }
        
        # With $10,000 balance and fixed contract size of 10:
        # Trade 1: max affordable = int(10000/2000) = 5, takes min(10, 5) = 5 contracts
        #   5 * $100 = +$500 -> $10,500
        # Trade 2: max affordable = int(10500/500) = 21, takes min(10, 21) = 10 contracts
        #   10 * -$50 = -$500 -> $10,000
        # Trade 3: max affordable = int(10000/10000) = 1, takes min(10, 1) = 1 contract
        #   1 * $200 = +$200 -> $10,200
        
        result = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=10000,
            position_sizing='contracts',
            position_size=10,
            risk_calculation_method='conservative_theoretical'
        )
        
        assert result['final_balance'] == 10200
        assert len(result['trade_history']) == 4  # Initial + 3 trades
    
    def test_replay_errors_on_mismatched_per_trade_risk_length(self):
        """Test that error is raised when per_trade_theoretical_risk length doesn't match pnl_distribution."""
        trade_stats = {
            'pnl_distribution': [100, 50, 200],
            'per_trade_theoretical_risk': [500, 200],  # Only 2 values for 3 trades!
            'num_trades': 3,
            'max_theoretical_loss': 300,
            'conservative_theoretical_max_loss': 250
        }
        
        # Should raise error since lengths don't match
        with pytest.raises(ValueError, match="per_trade_theoretical_risk length.*must match.*pnl_distribution length"):
            replay.replay_actual_trades(
                trade_stats=trade_stats,
                initial_balance=10000,
                position_sizing='contracts',
                position_size=2,
                risk_calculation_method='conservative_theoretical'
            )
    
    def test_replay_returns_trade_details(self):
        """Test that replay_actual_trades returns detailed per-trade information."""
        trade_stats = {
            'num_trades': 3,
            'win_rate': 0.67,
            'avg_win': 100,
            'avg_loss': -50,
            'max_win': 150,
            'max_loss': -50,
            'max_theoretical_loss': 200,
            'conservative_theoretical_max_loss': 180,
            'pnl_distribution': [100, -40, 80],
            'per_trade_theoretical_risk': [200, 180, 200],
            'per_trade_theoretical_reward': [150, 120, 150],
            'per_trade_dates': ['2023-01-01', '2023-02-01', '2023-03-01']
        }
        
        result = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=1000,
            position_sizing='contracts',
            position_size=2,
            dynamic_risk_sizing=False,
            risk_calculation_method='conservative_theoretical'
        )
        
        # Verify trade_details is returned
        assert 'trade_details' in result
        assert len(result['trade_details']) == 3
        
        # Check first trade details
        trade1 = result['trade_details'][0]
        assert trade1['date'] == '2023-01-01'
        assert trade1['contracts'] == 2
        assert trade1['pnl_per_contract'] == 100
        assert trade1['total_pnl'] == 200
        assert trade1['theoretical_risk'] == 200
        assert trade1['theoretical_reward'] == 150
        assert trade1['balance_before'] == 1000
        assert trade1['balance_after'] == 1200
        
        # Check second trade details
        trade2 = result['trade_details'][1]
        assert trade2['date'] == '2023-02-01'
        assert trade2['contracts'] == 2
        assert trade2['pnl_per_contract'] == -40
        assert trade2['total_pnl'] == -80
        assert trade2['theoretical_reward'] == 120
        assert trade2['theoretical_risk'] == 180
        assert trade2['balance_before'] == 1200
        assert trade2['balance_after'] == 1120
        
        # Check third trade details
        trade3 = result['trade_details'][2]
        assert trade3['date'] == '2023-03-01'
        assert trade3['contracts'] == 2
        assert trade3['pnl_per_contract'] == 80
        assert trade3['total_pnl'] == 160
        assert trade3['theoretical_risk'] == 200
        assert trade3['theoretical_reward'] == 150
        assert trade3['balance_before'] == 1120
        assert trade3['balance_after'] == 1280
    
    def test_replay_returns_trade_details_with_dynamic_sizing(self):
        """Test replay_actual_trades returns correct contract counts with dynamic risk sizing."""
        trade_stats = {
            'num_trades': 3,
            'win_rate': 0.67,
            'avg_win': 100,
            'avg_loss': -50,
            'max_win': 150,
            'max_loss': -50,
            'max_theoretical_loss': 100,
            'conservative_theoretical_max_loss': 100,
            'pnl_distribution': [50, -40, 50],
            'per_trade_theoretical_risk': [100, 100, 100],
            'per_trade_theoretical_reward': [80, 80, 80],
            'per_trade_dates': ['2023-01-15', '2023-02-15', '2023-03-15']
        }
        
        # 2% risk per trade with dynamic sizing
        result = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=10000,
            position_sizing='percent',
            target_risk_pct=2.0,
            dynamic_risk_sizing=True,
            risk_calculation_method='conservative_theoretical'
        )
        
        assert 'trade_details' in result
        assert len(result['trade_details']) == 3
        
        # Trade 1: Balance 10000, 2% risk = 200, 200/100 = 2 contracts
        assert result['trade_details'][0]['contracts'] == 2
        assert result['trade_details'][0]['balance_before'] == 10000
        assert result['trade_details'][0]['balance_after'] == 10100  # 10000 + 2*50
        
        # Trade 2: Balance 10100, 2% risk = 202, 202/100 = 2 contracts
        assert result['trade_details'][1]['contracts'] == 2
        assert result['trade_details'][1]['balance_before'] == 10100
        assert result['trade_details'][1]['balance_after'] == 10020  # 10100 + 2*(-40)
        
        # Trade 3: Balance 10020, 2% risk = 200.4, 200.4/100 = 2 contracts
        assert result['trade_details'][2]['contracts'] == 2
        assert result['trade_details'][2]['balance_before'] == 10020
        assert result['trade_details'][2]['balance_after'] == 10120  # 10020 + 2*50


class TestReplayPnlPercentageCalculation:
    """Tests for P/L percentage calculation in trade details."""

    def test_pnl_percentage_constant_across_contract_counts(self):
        """Verify P/L % remains constant regardless of number of contracts."""
        trade_stats = {
            'num_trades': 3,
            'win_rate': 0.67,
            'avg_win': 50,
            'avg_loss': -60,
            'max_win': 80,
            'max_loss': -80,
            'max_theoretical_loss': 100,
            'conservative_theoretical_max_loss': 100,
            'pnl_distribution': [50, -60, 80],  # Win, Loss, Win
            'per_trade_theoretical_risk': [100, 100, 100],
            'per_trade_theoretical_reward': [100, 100, 100],
            'per_trade_dates': ['2023-01-01', '2023-02-01', '2023-03-01']
        }
        
        # Test with 1 contract
        result_1 = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=10000,
            position_sizing='contracts',
            position_size=1,
            dynamic_risk_sizing=False,
            risk_calculation_method='conservative_theoretical'
        )
        
        # Test with 2 contracts
        result_2 = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=10000,
            position_sizing='contracts',
            position_size=2,
            dynamic_risk_sizing=False,
            risk_calculation_method='conservative_theoretical'
        )
        
        # Test with 5 contracts
        result_5 = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=10000,
            position_sizing='contracts',
            position_size=5,
            dynamic_risk_sizing=False,
            risk_calculation_method='conservative_theoretical'
        )
        
        # Verify all results have trade_details with pnl_pct field
        assert 'trade_details' in result_1
        assert 'trade_details' in result_2
        assert 'trade_details' in result_5
        
        assert len(result_1['trade_details']) == 3
        assert len(result_2['trade_details']) == 3
        assert len(result_5['trade_details']) == 3
        
        # Verify each trade has pnl_pct field
        for trade in result_1['trade_details']:
            assert 'pnl_pct' in trade
        
        # Trade 1: 50 / 100 = 50%
        assert result_1['trade_details'][0]['pnl_pct'] == 50.0
        assert result_2['trade_details'][0]['pnl_pct'] == 50.0
        assert result_5['trade_details'][0]['pnl_pct'] == 50.0
        
        # Trade 2: -60 / 100 = -60%
        assert result_1['trade_details'][1]['pnl_pct'] == -60.0
        assert result_2['trade_details'][1]['pnl_pct'] == -60.0
        assert result_5['trade_details'][1]['pnl_pct'] == -60.0
        
        # Trade 3: 80 / 100 = 80%
        assert result_1['trade_details'][2]['pnl_pct'] == 80.0
        assert result_2['trade_details'][2]['pnl_pct'] == 80.0
        assert result_5['trade_details'][2]['pnl_pct'] == 80.0

    def test_pnl_percentage_with_zero_risk(self):
        """Verify replay raises error when theoretical risk is zero (invalid data)."""
        trade_stats = {
            'num_trades': 2,
            'win_rate': 1.0,
            'avg_win': 50,
            'avg_loss': 0,
            'max_win': 50,
            'max_loss': 0,
            'max_theoretical_loss': 100,
            'conservative_theoretical_max_loss': 100,
            'pnl_distribution': [50, 25],
            'per_trade_theoretical_risk': [100, 0],  # Second trade has zero risk - INVALID DATA
            'per_trade_theoretical_reward': [100, 100],
            'per_trade_dates': ['2023-01-01', '2023-02-01']
        }
        
        # Zero theoretical risk should raise an error immediately
        with pytest.raises(ValueError) as exc_info:
            replay.replay_actual_trades(
                trade_stats=trade_stats,
                initial_balance=10000,
                position_sizing='contracts',
                position_size=2,
                dynamic_risk_sizing=False,
                risk_calculation_method='conservative_theoretical'
            )
        
        assert "Invalid theoretical risk" in str(exc_info.value)
        assert "2023-02-01" in str(exc_info.value)
        assert "missing or invalid data in the CSV" in str(exc_info.value)


class TestReplayDataValidation:
    """Tests for data validation in replay."""

    def test_negative_theoretical_risk_raises_error(self):
        """Verify replay raises clear error for negative theoretical risk."""
        trade_stats = {
            'num_trades': 1,
            'win_rate': 1.0,
            'avg_win': 50,
            'avg_loss': 0,
            'max_win': 50,
            'max_loss': 0,
            'max_theoretical_loss': 100,
            'conservative_theoretical_max_loss': 100,
            'pnl_distribution': [50],
            'per_trade_theoretical_risk': [-100],  # NEGATIVE - invalid data
            'per_trade_theoretical_reward': [100],
            'per_trade_dates': ['2023-01-01']
        }
        
        with pytest.raises(ValueError) as exc_info:
            replay.replay_actual_trades(
                trade_stats=trade_stats,
                initial_balance=10000,
                position_sizing='contracts',
                position_size=1,
                dynamic_risk_sizing=False,
                risk_calculation_method='conservative_theoretical'
            )
        
        assert "Invalid theoretical risk" in str(exc_info.value)
        assert "2023-01-01" in str(exc_info.value)
        assert "missing or invalid data in the CSV" in str(exc_info.value)


class TestReplayRiskPercentageCalculation:
    """Tests for risk percentage calculation in trade details."""

    def test_risk_percentage_scales_with_theoretical_risk(self):
        """Verify Risk % = (theoretical_risk / balance_before) * 100."""
        trade_stats = {
            'num_trades': 3,
            'win_rate': 1.0,
            'avg_win': 50,
            'avg_loss': 0,
            'max_win': 50,
            'max_loss': 0,
            'max_theoretical_loss': 150,
            'conservative_theoretical_max_loss': 150,
            'pnl_distribution': [50, 40, 30],  # Different P/Ls
            'per_trade_theoretical_risk': [100, 150, 50],  # Varying risk amounts
            'per_trade_theoretical_reward': [100, 100, 100],
            'per_trade_dates': ['2023-01-01', '2023-02-01', '2023-03-01']
        }
        
        result = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=10000,
            position_sizing='contracts',
            position_size=1,
            dynamic_risk_sizing=False,
            risk_calculation_method='conservative_theoretical'
        )
        
        assert len(result['trade_details']) == 3
        
        # Verify each trade has risk_pct field
        for trade in result['trade_details']:
            assert 'risk_pct' in trade
        
        # Trade 1: 100 / 10000 * 100 = 1.0%
        assert result['trade_details'][0]['risk_pct'] == 1.0
        assert result['trade_details'][0]['balance_before'] == 10000
        
        # Trade 2: 150 / 10050 * 100 = 1.49%
        assert result['trade_details'][1]['balance_before'] == 10050
        expected_risk_pct_2 = (150 / 10050) * 100
        assert abs(result['trade_details'][1]['risk_pct'] - expected_risk_pct_2) < 0.01
        
        # Trade 3: 50 / 10090 * 100 = 0.50%
        assert result['trade_details'][2]['balance_before'] == 10090
        expected_risk_pct_3 = (50 / 10090) * 100
        assert abs(result['trade_details'][2]['risk_pct'] - expected_risk_pct_3) < 0.01

    def test_risk_percentage_with_multiple_contracts(self):
        """Verify Risk % reflects actual position size (contracts * theoretical_risk per spread)."""
        trade_stats = {
            'num_trades': 2,
            'win_rate': 1.0,
            'avg_win': 50,
            'avg_loss': 0,
            'max_win': 50,
            'max_loss': 0,
            'max_theoretical_loss': 100,
            'conservative_theoretical_max_loss': 100,
            'pnl_distribution': [50, 30],
            'per_trade_theoretical_risk': [100, 100],
            'per_trade_theoretical_reward': [100, 100],
            'per_trade_dates': ['2023-01-01', '2023-02-01']
        }
        
        result = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=10000,
            position_sizing='contracts',
            position_size=3,  # 3 contracts
            dynamic_risk_sizing=False,
            risk_calculation_method='conservative_theoretical'
        )
        
        # Trade 1: theoretical_risk is per spread (100), not total
        # Risk % = 100 / 10000 * 100 = 1.0% (per spread, not 3%)
        assert result['trade_details'][0]['risk_pct'] == 1.0
        
        # Trade 2: 100 / 10150 * 100 = 0.985%
        expected_risk_pct = (100 / 10150) * 100
        assert abs(result['trade_details'][1]['risk_pct'] - expected_risk_pct) < 0.01

    def test_risk_percentage_with_zero_balance(self):
        """Verify Risk % handles zero balance gracefully."""
        trade_stats = {
            'num_trades': 2,
            'win_rate': 0.5,
            'avg_win': 50,
            'avg_loss': -1000,
            'max_win': 50,
            'max_loss': -1000,
            'max_theoretical_loss': 100,
            'conservative_theoretical_max_loss': 100,
            'pnl_distribution': [-1000, 50],  # First trade bankrupts us
            'per_trade_theoretical_risk': [100, 100],
            'per_trade_theoretical_reward': [100, 100],
            'per_trade_dates': ['2023-01-01', '2023-02-01']
        }
        
        result = replay.replay_actual_trades(
            trade_stats=trade_stats,
            initial_balance=1000,
            position_sizing='contracts',
            position_size=1,
            dynamic_risk_sizing=False,
            risk_calculation_method='conservative_theoretical'
        )
        
        # First trade executes
        assert result['trade_details'][0]['risk_pct'] == 10.0  # 100 / 1000 * 100
        
        # After first trade, balance = 0 (bankruptcy)
        assert result['trade_details'][0]['balance_after'] == 0
        
        # No second trade (balance <= 0)
        assert len(result['trade_details']) == 1
