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