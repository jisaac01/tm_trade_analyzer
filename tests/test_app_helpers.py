"""Tests for helper functions in app.py"""
import pytest
import math
import numpy as np
from app import clean_for_json


class TestCleanForJson:
    """Test clean_for_json() function for JSON serialization."""
    
    def test_numpy_int_scalar(self):
        """Test conversion of numpy int scalar to Python int."""
        value = np.int64(42)
        result = clean_for_json(value)
        assert result == 42
        assert isinstance(result, int)
    
    def test_numpy_float_scalar(self):
        """Test conversion of numpy float scalar to Python float."""
        value = np.float64(3.14)
        result = clean_for_json(value)
        assert result == 3.14
        assert isinstance(result, float)
    
    def test_nan_converts_to_none(self):
        """Test that NaN values are converted to None for JSON compatibility."""
        result = clean_for_json(float('nan'))
        assert result is None
    
    def test_infinity_converts_to_none(self):
        """Test that Infinity values are converted to None for JSON compatibility."""
        result = clean_for_json(float('inf'))
        assert result is None
        
        result_neg = clean_for_json(float('-inf'))
        assert result_neg is None
    
    def test_normal_float_passes_through(self):
        """Test that normal floats pass through unchanged."""
        result = clean_for_json(3.14159)
        assert result == 3.14159
        assert isinstance(result, float)
    
    def test_list_with_numpy_types(self):
        """Test that lists containing numpy types are recursively cleaned."""
        value = [np.int64(1), np.float64(2.5), 3]
        result = clean_for_json(value)
        assert result == [1, 2.5, 3]
        assert all(not hasattr(v, 'item') for v in result)
    
    def test_list_with_nan_and_inf(self):
        """Test that lists containing NaN and Inf are cleaned."""
        value = [1.0, float('nan'), 2.0, float('inf'), 3.0]
        result = clean_for_json(value)
        assert result == [1.0, None, 2.0, None, 3.0]
    
    def test_dict_with_numpy_types(self):
        """Test that dicts with numpy values are recursively cleaned."""
        value = {'a': np.int64(10), 'b': np.float64(20.5), 'c': 30}
        result = clean_for_json(value)
        assert result == {'a': 10, 'b': 20.5, 'c': 30}
    
    def test_dict_with_nan_values(self):
        """Test that dicts containing NaN values are cleaned."""
        value = {'x': 1.0, 'y': float('nan'), 'z': 3.0}
        result = clean_for_json(value)
        assert result == {'x': 1.0, 'y': None, 'z': 3.0}
    
    def test_nested_structures(self):
        """Test deeply nested lists and dicts with mixed types."""
        value = {
            'data': [
                {'value': np.float64(1.5), 'flag': True},
                {'value': float('nan'), 'count': np.int64(5)}
            ],
            'stats': [np.float64(10.0), float('inf'), 20.0]
        }
        expected = {
            'data': [
                {'value': 1.5, 'flag': True},
                {'value': None, 'count': 5}
            ],
            'stats': [10.0, None, 20.0]
        }
        result = clean_for_json(value)
        assert result == expected
    
    def test_tuple_converts_to_list(self):
        """Test that tuples are converted to lists with cleaned values."""
        value = (np.int64(1), 2, np.float64(3.5))
        result = clean_for_json(value)
        assert result == [1, 2, 3.5]
        assert isinstance(result, list)
    
    def test_regular_python_types_pass_through(self):
        """Test that regular Python types are unchanged."""
        assert clean_for_json(42) == 42
        assert clean_for_json("hello") == "hello"
        assert clean_for_json(True) is True
        assert clean_for_json(None) is None
    
    def test_empty_collections(self):
        """Test that empty lists and dicts are handled correctly."""
        assert clean_for_json([]) == []
        assert clean_for_json({}) == {}
        assert clean_for_json(()) == []


class TestFormatMonteCarloTable:
    """Test format_monte_carlo_table() helper function."""
    
    def test_format_percent_mode_with_allow_exceed(self):
        """Test table formatting in percent mode with allow_exceed_target_risk=True."""
        from app import format_monte_carlo_table
        
        report = {
            'table_rows': [
                {'Contracts': 1, 'Target Risk %': '5.00%', 'Actual Risk %': '4.95%', 
                 'Avg Final $': '$15,000', 'Bankruptcy Prob': '0.0%'},
                {'Contracts': 2, 'Target Risk %': '10.00%', 'Actual Risk %': '9.90%', 
                 'Avg Final $': '$18,000', 'Bankruptcy Prob': '2.5%'}
            ]
        }
        
        html = format_monte_carlo_table(report, position_sizing='percent', allow_exceed=True)
        
        # Should keep Target Risk % column name (not rename to Risk Ceiling %)
        assert 'Target Risk %' in html
        assert 'Risk Ceiling %' not in html
        assert 'Actual Risk %' in html
        
        # Should have tooltips
        assert 'title=' in html
        assert 'Contracts' in html
        
    def test_format_percent_mode_strict_enforcement(self):
        """Test table formatting in percent mode with allow_exceed_target_risk=False."""
        from app import format_monte_carlo_table
        
        report = {
            'table_rows': [
                {'Contracts': 1, 'Target Risk %': '5.00%', 'Actual Risk %': '4.95%', 
                 'Avg Final $': '$15,000', 'Bankruptcy Prob': '0.0%'}
            ]
        }
        
        html = format_monte_carlo_table(report, position_sizing='percent', allow_exceed=False)
        
        # Should rename Target Risk % to Risk Ceiling %
        assert 'Risk Ceiling %' in html
        assert 'Target Risk %' not in html
        assert 'Actual Risk %' in html
        
        # Should have different tooltip text for strict enforcement
        assert 'hard ceiling' in html.lower() or 'maximum percentage' in html.lower()
        
    def test_format_contracts_mode(self):
        """Test table formatting in contracts mode."""
        from app import format_monte_carlo_table
        
        report = {
            'table_rows': [
                {'Contracts': 3, 'Target Risk %': '15.00%', 'Actual Risk %': '14.85%', 
                 'Avg Final $': '$20,000', 'Bankruptcy Prob': '5.0%'}
            ]
        }
        
        html = format_monte_carlo_table(report, position_sizing='contracts', allow_exceed=False)
        
        # Should rename Actual Risk % to Initial Risk %
        assert 'Initial Risk %' in html
        assert 'Actual Risk %' not in html
        
        # Should not have Target Risk % or Risk Ceiling % columns
        assert 'Target Risk %' not in html
        assert 'Risk Ceiling %' not in html
        
        # Should have contracts-specific tooltips
        assert 'Fixed number of contracts' in html
        
    def test_tooltip_injection(self):
        """Test that all expected tooltips are injected into headers."""
        from app import format_monte_carlo_table
        
        report = {
            'table_rows': [
                {'Contracts': 1, 'Target Risk %': '5.00%', 'Actual Risk %': '4.95%', 
                 'Avg Final $': '$15,000', 'Bankruptcy Prob': '0.0%',
                 'Avg Max Drawdown': '$500', 'Max Drawdown': '$1000',
                 'Avg Max Losing Streak': '3', 'Max Losing Streak': '5'}
            ]
        }
        
        html = format_monte_carlo_table(report, position_sizing='percent', allow_exceed=True)
        
        # Check that key tooltips exist
        assert 'Average final account balance' in html
        assert 'Probability of account balance reaching zero' in html
        assert 'maximum drawdown' in html
        assert 'losing streak' in html


class TestFormatReplayTable:
    """Test format_replay_table() helper function."""
    
    def test_format_replay_percent_mode_with_allow_exceed(self):
        """Test replay table formatting in percent mode with allow_exceed=True."""
        from app import format_replay_table
        
        replay_data = [
            {'Contracts': 1, 'Target Risk %': '5.00%', 'Starting Risk %': '4.80%',
             'Max Risk %': '5.20%', 'Final Balance': '$15,000', 'Max Drawdown': '$500',
             'Max Losing Streak': '3', 'Num Trades': 50}
        ]
        
        html = format_replay_table(replay_data, position_sizing='percent', allow_exceed=True)
        
        # Should keep Target Risk % (not rename to Risk Ceiling %)
        assert 'Target Risk %' in html
        assert 'Risk Ceiling %' not in html
        assert 'Starting Risk %' in html
        assert 'Max Risk %' in html
        
    def test_format_replay_percent_mode_strict_enforcement(self):
        """Test replay table formatting in percent mode with allow_exceed=False."""
        from app import format_replay_table
        
        replay_data = [
            {'Contracts': 1, 'Target Risk %': '5.00%', 'Starting Risk %': '4.80%',
             'Max Risk %': '5.20%', 'Final Balance': '$15,000', 'Max Drawdown': '$500',
             'Max Losing Streak': '3', 'Num Trades': 50}
        ]
        
        html = format_replay_table(replay_data, position_sizing='percent', allow_exceed=False)
        
        # Should rename Target Risk % to Risk Ceiling %
        assert 'Risk Ceiling %' in html
        assert 'Target Risk %' not in html
        
    def test_format_replay_contracts_mode(self):
        """Test replay table formatting in contracts mode."""
        from app import format_replay_table
        
        replay_data = [
            {'Contracts': 3, 'Target Risk %': '15.00%', 'Starting Risk %': '14.85%',
             'Max Risk %': '15.20%', 'Final Balance': '$20,000', 'Max Drawdown': '$1000',
             'Max Losing Streak': '5', 'Num Trades': 45}
        ]
        
        html = format_replay_table(replay_data, position_sizing='contracts', allow_exceed=False)
        
        # Should rename Starting Risk % to Initial Risk %
        assert 'Initial Risk %' in html
        assert 'Starting Risk %' not in html
        
        # Should not have Target Risk % or Risk Ceiling %
        assert 'Target Risk %' not in html
        assert 'Risk Ceiling %' not in html
        
    def test_replay_tooltip_injection(self):
        """Test that replay-specific tooltips are injected."""
        from app import format_replay_table
        
        replay_data = [
            {'Contracts': 1, 'Target Risk %': '5.00%', 'Starting Risk %': '4.80%',
             'Max Risk %': '5.20%', 'Final Balance': '$15,000', 'Max Drawdown': '$500',
             'Max Losing Streak': '3', 'Num Trades': 50}
        ]
        
        html = format_replay_table(replay_data, position_sizing='percent', allow_exceed=True)
        
        # Check replay-specific tooltips
        assert 'historical replay' in html.lower()
        assert 'Final Balance' in html
        assert 'Max Risk %' in html


class TestPrepareChartData:
    """Test prepare_chart_data() helper function."""
    
    def test_prepare_chart_data_basic(self):
        """Test basic chart data preparation with Monte Carlo and replay data."""
        import json
        from app import prepare_chart_data
        
        trade_reports = [{
            'trajectory_data': {
                'scenario_1': {
                    'p50': [10000, 10500, 11000],
                    'p95': [10000, 11000, 12000]
                }
            }
        }]
        
        replay_details_data = [
            {
                'scenario_id': 'scenario_0',
                'trade_history': [10000, 10200, 10400]
            }
        ]
        
        result_json = prepare_chart_data(trade_reports, replay_details_data)
        result = json.loads(result_json)
        
        # Check structure
        assert 'monte_carlo' in result
        assert 'replay' in result
        assert 'trade_numbers' in result
        
        # Check Monte Carlo data
        assert 'scenario_1' in result['monte_carlo']
        assert result['monte_carlo']['scenario_1']['p50'] == [10000, 10500, 11000]
        
        # Check replay data
        assert 'scenario_0' in result['replay']
        assert result['replay']['scenario_0'] == [10000, 10200, 10400]
        
        # Check trade numbers
        assert result['trade_numbers'] == [0, 1, 2]
    
    def test_prepare_chart_data_empty_reports(self):
        """Test chart data preparation with empty reports."""
        import json
        from app import prepare_chart_data
        
        result_json = prepare_chart_data([], [])
        result = json.loads(result_json)
        
        assert result['monte_carlo'] == {}
        assert result['replay'] == {}
        assert result['trade_numbers'] == []
    
    def test_prepare_chart_data_cleans_numpy(self):
        """Test that numpy types are cleaned from chart data."""
        import json
        import numpy as np
        from app import prepare_chart_data
        
        trade_reports = [{
            'trajectory_data': {
                'scenario_1': {
                    'p50': [np.float64(10000), np.float64(10500)],
                }
            }
        }]
        
        replay_details_data = [
            {
                'scenario_id': 'scenario_0',
                'trade_history': [np.float64(10000), np.float64(10200)]
            }
        ]
        
        result_json = prepare_chart_data(trade_reports, replay_details_data)
        result = json.loads(result_json)
        
        # Should be clean Python floats, not numpy
        assert isinstance(result['monte_carlo']['scenario_1']['p50'][0], (int, float))
        assert isinstance(result['replay']['scenario_0'][0], (int, float))
    
    def test_prepare_chart_data_multiple_scenarios(self):
        """Test chart data with multiple replay scenarios."""
        import json
        from app import prepare_chart_data
        
        trade_reports = [{
            'trajectory_data': {
                'scenario_1': {'p50': [10000, 10500]}
            }
        }]
        
        replay_details_data = [
            {'scenario_id': 'scenario_0', 'trade_history': [10000, 10200]},
            {'scenario_id': 'scenario_1', 'trade_history': [10000, 10300]},
            {'scenario_id': 'scenario_2', 'trade_history': [10000, 10100]}
        ]
        
        result_json = prepare_chart_data(trade_reports, replay_details_data)
        result = json.loads(result_json)
        
        # Should have all replay scenarios
        assert len(result['replay']) == 3
        assert 'scenario_0' in result['replay']
        assert 'scenario_1' in result['replay']
        assert 'scenario_2' in result['replay']


class TestRunAllReplayScenarios:
    """Test run_all_replay_scenarios() helper function with real data."""
    
    def test_run_replay_scenarios_percent_mode(self):
        """Test running replay scenarios in percent mode with real data."""
        from app import run_all_replay_scenarios
        import trade_parser
        
        # Use real test data
        csv_path = 'tests/test_data/CML TM Trades Long 60 Delta, Short 30 Delta Call 20260223.csv'
        trade_stats = trade_parser.parse_trade_csv(csv_path)
        
        params = {
            'initial_balance': 10000,
            'position_sizing': 'percent',
            'dynamic_risk_sizing': True,
            'risk_calculation_method': 'conservative_theoretical',
            'allow_exceed_target_risk': False
        }
        
        # Build position size plan (this is done in results() before calling run_all_replay_scenarios)
        import simulator
        position_size_plan = simulator.build_position_size_plan(
            trade=trade_stats,
            initial_balance=params['initial_balance'],
            position_sizing=params['position_sizing'],
            risk_calculation_method=params['risk_calculation_method'],
            allow_exceed_target_risk=params['allow_exceed_target_risk'],
            mode='replay'
        )
        
        replay_data, replay_details_data = run_all_replay_scenarios(
            trade_stats=trade_stats,
            position_size_plan=position_size_plan,
            params=params
        )
        
        # Check structure
        assert len(replay_data) > 0
        assert len(replay_details_data) == len(replay_data)
        
        # Check replay_data has expected keys
        first_row = replay_data[0]
        assert 'Contracts' in first_row
        assert 'Final Balance' in first_row
        assert 'Max Drawdown' in first_row
        assert 'Num Trades' in first_row
        
        # Check replay_details_data has expected keys
        first_details = replay_details_data[0]
        assert 'scenario_id' in first_details
        assert 'contracts' in first_details
        assert 'trade_history' in first_details
        assert 'trade_details' in first_details
    
    def test_run_replay_scenarios_contracts_mode(self):
        """Test running replay scenarios in contracts mode."""
        from app import run_all_replay_scenarios
        import trade_parser
        import simulator
        
        csv_path = 'tests/test_data/CML TM Trades Long 60 Delta, Short 30 Delta Call 20260223.csv'
        trade_stats = trade_parser.parse_trade_csv(csv_path)
        
        params = {
            'initial_balance': 10000,
            'position_sizing': 'contracts',
            'dynamic_risk_sizing': False,
            'risk_calculation_method': 'conservative_theoretical',
            'allow_exceed_target_risk': False
        }
        
        position_size_plan = simulator.build_position_size_plan(
            trade=trade_stats,
            initial_balance=params['initial_balance'],
            position_sizing=params['position_sizing'],
            risk_calculation_method=params['risk_calculation_method'],
            allow_exceed_target_risk=params['allow_exceed_target_risk'],
            mode='replay'
        )
        
        replay_data, replay_details_data = run_all_replay_scenarios(
            trade_stats=trade_stats,
            position_size_plan=position_size_plan,
            params=params
        )
        
        assert len(replay_data) > 0
        assert len(replay_details_data) == len(replay_data)
        
        # In contracts mode, scenario IDs should be numbered
        assert replay_details_data[0]['scenario_id'] == 'scenario_0'
