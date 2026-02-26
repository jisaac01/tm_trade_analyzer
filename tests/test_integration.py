import pytest
from app import app
import os

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

