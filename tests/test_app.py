import pytest
from app import app
import os
import tempfile
from unittest.mock import patch

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_index_get(client):
    """Test that the index route returns 200 and contains expected content."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Monte Carlo Trade Analyzer' in response.data
    assert b'Upload your trade data' in response.data

def test_index_post_valid_csv(client):
    """Test POST to / with valid CSV file."""
    # Create a temporary CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("Trade Name,Entry Date,Exit Date,P/L\nTest Trade,2023-01-01,2023-01-02,100\n")
        temp_file = f.name

    try:
        with open(temp_file, 'rb') as f:
            data = {
                'csv_file': f,
                'initial_balance': '100000',
                'num_simulations': '100',
                'option_commission': '1.0',
                'position_sizing_mode': 'percent',
                'dynamic_risk_sizing': 'on',
                'simulation_mode': 'iid',
                'block_size': '1'
            }
            response = client.post('/', data=data, content_type='multipart/form-data')
            assert response.status_code == 302  # Redirect to /results
            assert '/results' in response.headers['Location']
    finally:
        os.unlink(temp_file)

def test_index_post_invalid_file(client):
    """Test POST to / with invalid file (not CSV)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Not a CSV")
        temp_file = f.name

    try:
        with open(temp_file, 'rb') as f:
            data = {'csv_file': f}
            response = client.post('/', data=data, content_type='multipart/form-data')
            assert response.status_code == 302  # Redirect back to /
            # Check flash message, but since no flash display, perhaps check session or just status
    finally:
        os.unlink(temp_file)

def test_results_get_without_session(client):
    """Test GET /results without session should redirect."""
    response = client.get('/results')
    assert response.status_code == 302
    assert '/' in response.headers['Location']

@patch('app.simulator.run_monte_carlo_simulation')
@patch('app.trade_parser.parse_trade_csv')
def test_results_get_with_session(mock_parse, mock_simulate, client):
    """Test GET /results with session."""
    # Mock the parsing
    mock_parse.return_value = {
        'num_trades': 1,
        'pnl_distribution': [100, 200, -50],
        'name': 'Test Trade',
        'win_rate': 0.6,
        'avg_win': 200,
        'avg_loss': -100,
        'max_win': 200,
        'max_loss': -50,
        'max_theoretical_loss': 300,
        'conservative_theoretical_max_loss': 300,
        'max_theoretical_gain': 500,
        'conservative_realized_max_reward': 200,
        'risked': 300,
        'total_return': 250,
        'pct_return': 83.33,
        'avg_pct_return': 83.33,
        'commissions': 2,
        'wins': 2,
        'losses': 1,
        'avg_pct_win': 100,
        'avg_pct_loss': -50,
        'gross_gain': 300,
        'gross_loss': -50,
        'median_loss': -50,
        'median_risk_per_spread': 50
    }
    
    # Mock the simulation to return dummy data
    mock_simulate.return_value = [{
        'trade_name': 'Test Trade',
        'summary': {
            'total_return': 1000,
            'risked': 500,
            'pct_return': 10.0,
            'avg_pct_return': 5.0,
            'commissions': 10,
            'win_rate': 0.6,
            'wins': 6,
            'losses': 4,
            'avg_win': 200,
            'avg_loss': -100,
            'gross_gain': 1200,
            'gross_loss': -400,
            'conservative_theoretical_max_loss': 500,
            'max_theoretical_loss': 600,
            'historical_max_losing_streak': 2
        },
        'table_rows': [
            {'Percentile': '5%', 'Balance': 95000, 'Trades': 10, 'Win Rate': '60%', 'Avg Win': '$200', 'Avg Loss': '$-100', 'Total Return': '$1000'},
            {'Percentile': '50%', 'Balance': 105000, 'Trades': 10, 'Win Rate': '60%', 'Avg Win': '$200', 'Avg Loss': '$-100', 'Total Return': '$5000'},
            {'Percentile': '95%', 'Balance': 115000, 'Trades': 10, 'Win Rate': '60%', 'Avg Win': '$200', 'Avg Loss': '$-100', 'Total Return': '$15000'}
        ],
        'pnl_preview': ['100', '200', '-50', '150']
    }]

    # Set session
    with client.session_transaction() as sess:
        sess['csv_filepath'] = 'dummy.csv'
        sess['original_filename'] = 'dummy.csv'
        sess['params'] = {
            'initial_balance': 100000,
            'num_simulations': 100,
            'option_commission': 1.0,
            'position_sizing': 'percent',
            'dynamic_risk_sizing': True,
            'simulation_mode': 'iid',
            'block_size': 1
        }

    response = client.get('/results')
    assert response.status_code == 200
    assert b'Test Trade' in response.data
    assert b'Adjust Parameters' in response.data

def test_results_post_update_params(client):
    """Test POST /results to update params."""
    # Set session
    with client.session_transaction() as sess:
        sess['csv_filepath'] = 'dummy.csv'
        sess['original_filename'] = 'dummy.csv'
        sess['params'] = {
            'initial_balance': 100000,
            'num_simulations': 100,
            'option_commission': 1.0,
            'position_sizing': 'percent',
            'dynamic_risk_sizing': True,
            'simulation_mode': 'iid',
            'block_size': 1
        }

    data = {
        'initial_balance': '200000',
        'num_simulations': '200',
        'option_commission': '2.0',
        'position_sizing_mode': 'contracts',
        # 'dynamic_risk_sizing': '',  # omit to make it False
        'simulation_mode': 'moving-block-bootstrap',
        'block_size': '2'
    }
    response = client.post('/results', data=data)
    assert response.status_code == 302
    assert '/results' in response.headers['Location']

    # Check session updated
    with client.session_transaction() as sess:
        assert sess['params']['initial_balance'] == 200000
        assert sess['params']['num_simulations'] == 200
        assert sess['params']['option_commission'] == 2.0
        assert sess['params']['position_sizing'] == 'contracts'
        assert sess['params']['dynamic_risk_sizing'] == False
        assert sess['params']['simulation_mode'] == 'moving-block-bootstrap'
        assert sess['params']['block_size'] == 2

def test_format_currency_whole():
    """Test the format_currency_whole function."""
    from app import format_currency_whole
    assert format_currency_whole(1000) == '$1,000'
    assert format_currency_whole(-500) == '-$500'
    assert format_currency_whole(0) == '$0'