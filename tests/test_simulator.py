import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import simulator
import numpy as np
import pytest
import pandas as pd
import tempfile


class TestSimulator:
    """Tests for the simulator module."""

    def test_parse_trade_csv_basic(self):
        """Test basic CSV parsing functionality."""
        file_path = 'tests/test_data/test_call_spread.csv'
        stats = simulator.parse_trade_csv(file_path)
        
        assert stats['num_trades'] == 1
        assert stats['total_return'] == 400.0  # 300 + 100
        assert len(stats['pnl_distribution']) == 1

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