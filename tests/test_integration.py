import pytest
from app import app
import os
import numpy as np
import json
import re

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_end_to_end_simulation(client):
    """End-to-end test: upload CSV, run simulation with small parameters, check results."""
    # Use a real test CSV with multiple trades including losses
    csv_path = os.path.join(os.path.dirname(__file__), 'test_data', 'CML TM Trades Long 60 Delta, Short 30 Delta Call 20260223.csv')

    with open(csv_path, 'rb') as f:
        data = {
            'csv_file': f,
            'initial_balance': '10000',  # Small balance
            'num_simulations': '10',     # Very small number for speed
            'option_commission': '1.0',
            'position_sizing_mode': 'percent',
            'dynamic_risk_sizing': 'on',
            'simulation_mode': 'iid',
            'block_size': '1'
        }
        response = client.post('/', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        # Check that results page is returned with simulation data
        assert b'Monte Carlo Trade Sizing Report' in response.data
        assert b'CML TM Trades' in response.data  # Trade name from CSV
        assert b'Adjust Parameters' in response.data

    # Now test re-running with different params
    data_update = {
        'initial_balance': '20000',
        'num_simulations': '5',  # Even smaller
        'option_commission': '0.5',
        'position_sizing_mode': 'contracts',
        # dynamic_risk_sizing omitted to disable
        'simulation_mode': 'iid',
        'block_size': '1'
    }
    response = client.post('/results', data=data_update, follow_redirects=True)
    assert response.status_code == 200
    assert b'Monte Carlo Trade Sizing Report' in response.data


def test_end_to_end_insufficient_balance_error(client):
    """Test that insufficient balance errors are properly surfaced with preserved form state."""
    # Use a real test CSV
    csv_path = os.path.join(os.path.dirname(__file__), 'test_data', 'test_call_spread.csv')

    with open(csv_path, 'rb') as f:
        data = {
            'csv_file': f,
            'initial_balance': '1',  # Way too small - will trigger error
            'num_simulations': '10',
            'num_trades': '10',
            'option_commission': '0.50',
            'position_sizing_mode': 'dynamic-percent',
            'simulation_mode': 'iid',
            'block_size': '5',
            'risk_calculation_method': 'conservative_theoretical'
        }
        response = client.post('/', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        
        html = response.data.decode('utf-8')
        
        # Check that error message is displayed
        assert 'Error running simulation' in html
        assert 'insufficient' in html.lower() or 'balance' in html.lower()
        
        # Check that form is displayed with preserved values
        assert 'value="1"' in html  # initial_balance preserved
        assert 'value="10"' in html  # num_simulations preserved
        assert 'test_call_spread.csv' in html  # filename shown
        
        # Check that we're on results page (with form to adjust parameters)
        assert 'Adjust Parameters' in html
        
        # Check that no results table is shown (because simulation failed)
        # The results section should be hidden when show_error_only is True
        assert 'TradeMachine Backtest Results' not in html or html.count('TradeMachine Backtest Results') == 0


def test_historical_replay_displayed(client):
    """Test that historical replay results are displayed alongside Monte Carlo results."""
    # Use a test file with more trades to ensure proper simulation
    csv_path = os.path.join(os.path.dirname(__file__), 'test_data', 'CML TM Trades Long 60 Delta, Short 30 Delta Call 20260223.csv')

    with open(csv_path, 'rb') as f:
        data = {
            'csv_file': f,
            'initial_balance': '10000',
            'num_simulations': '10',
            'num_trades': '10',
            'option_commission': '0.50',
            'position_sizing_mode': 'dynamic-percent',
            'simulation_mode': 'iid',
            'block_size': '5',
            'risk_calculation_method': 'conservative_theoretical'
        }
        response = client.post('/', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        
        html = response.data.decode('utf-8')
        
        # Check that Monte Carlo results are displayed
        assert 'Monte Carlo Simulation Results' in html
        
        # Check that Historical Replay results are displayed
        assert 'Historical Trade Replay' in html
        assert 'actual sequence' in html
        
        # Check that both tables have contract and balance information
        assert 'Contracts' in html
        assert 'Final Balance' in html or 'Avg Final' in html
        
        # Check that explanatory text is present
        assert 'not' in html and 'simulation' in html  # "not a simulation"


def test_trajectory_data_integration(client):
    """
    Real integration test: verify trajectory data flows through to template.
    Uses real CSV, seeds RNG for determinism, minimal mocking.
    """
    # Seed for deterministic Monte Carlo results
    np.random.seed(42)
    
    # Use same CSV as other integration tests (known to work)
    csv_path = os.path.join(os.path.dirname(__file__), 'test_data', 'CML TM Trades Long 60 Delta, Short 30 Delta Call 20260223.csv')
    
    with open(csv_path, 'rb') as f:
        data = {
            'csv_file': f,
            'initial_balance': '10000',
            'num_simulations': '10',  # Small for speed, but enough to check percentiles
            'num_trades': '5',
            'option_commission': '0.50',
            'position_sizing_mode': 'dynamic-percent',
            'simulation_mode': 'iid',
            'block_size': '5',
            'risk_calculation_method': 'conservative_theoretical'
        }
        response = client.post('/', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        
        html = response.data.decode('utf-8')
        
        # Look for chart_data JavaScript variable in the HTML
        # Expected format: var chart_data = {...};
        chart_data_match = re.search(r'var\s+chart_data\s*=\s*({.*?});', html, re.DOTALL)
        assert chart_data_match is not None, "chart_data JavaScript variable not found in HTML"
        
        # Parse the JSON data
        chart_data_json = chart_data_match.group(1)
        chart_data = json.loads(chart_data_json)
        
        # Verify structure: monte_carlo, replay, trade_numbers
        assert 'monte_carlo' in chart_data, "chart_data missing 'monte_carlo' key"
        assert 'replay' in chart_data, "chart_data missing 'replay' key"
        assert 'trade_numbers' in chart_data, "chart_data missing 'trade_numbers' key"
        
        # Verify monte_carlo structure: dict of thresholds with percentile data
        monte_carlo = chart_data['monte_carlo']
        assert len(monte_carlo) > 0, "monte_carlo should have at least one threshold"
        
        # Check first threshold has percentile data
        first_threshold = list(monte_carlo.keys())[0]
        percentile_data = monte_carlo[first_threshold]
        
        assert 'p5' in percentile_data, f"Threshold {first_threshold} missing p5"
        assert 'p25' in percentile_data, f"Threshold {first_threshold} missing p25"
        assert 'p50' in percentile_data, f"Threshold {first_threshold} missing p50"
        assert 'p75' in percentile_data, f"Threshold {first_threshold} missing p75"
        assert 'p95' in percentile_data, f"Threshold {first_threshold} missing p95"
        
        # Each percentile should be a list of numbers (balance at each trade step)
        p5 = percentile_data['p5']
        p50 = percentile_data['p50']
        p95 = percentile_data['p95']
        
        assert isinstance(p5, list), "p5 should be a list"
        assert len(p5) > 0, "p5 should not be empty"
        
        # First element should be initial balance
        assert p5[0] == 10000, f"First p5 value should be initial_balance (10000), got {p5[0]}"
        assert p50[0] == 10000, f"First p50 value should be initial_balance (10000), got {p50[0]}"
        assert p95[0] == 10000, f"First p95 value should be initial_balance (10000), got {p95[0]}"
        
        # Verify percentile ordering at each step: p5 <= p50 <= p95
        for i in range(len(p5)):
            # Handle bankruptcy cases (None or 0)
            p5_val = p5[i] if p5[i] is not None else 0
            p50_val = p50[i] if p50[i] is not None else 0
            p95_val = p95[i] if p95[i] is not None else 0
            
            assert p5_val <= p50_val, f"At step {i}: p5 ({p5_val}) > p50 ({p50_val})"
            assert p50_val <= p95_val, f"At step {i}: p50 ({p50_val}) > p95 ({p95_val})"
        
        # Verify replay structure: dict of scenarios with balance arrays
        replay = chart_data['replay']
        assert len(replay) > 0, "replay should have at least one scenario"
        
        # Check first scenario has trade_history
        first_scenario = list(replay.keys())[0]
        trade_history = replay[first_scenario]
        
        assert isinstance(trade_history, list), "trade_history should be a list"
        assert len(trade_history) > 0, "trade_history should not be empty"
        assert trade_history[0] == 10000, f"First trade_history value should be initial_balance (10000), got {trade_history[0]}"
        
        # Verify trade_numbers is a list of integers
        trade_numbers = chart_data['trade_numbers']
        assert isinstance(trade_numbers, list), "trade_numbers should be a list"
        assert trade_numbers[0] == 0, "trade_numbers should start at 0"
        assert trade_numbers == list(range(len(trade_numbers))), "trade_numbers should be [0, 1, 2, ...]"
