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
        'per_trade_theoretical_risk': [300, 300, 300],
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
            'avg_pct_win': 200,
            'avg_pct_loss': -100,
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


def test_risk_calculation_method_selector_labels_and_width(client):
    """Risk method selector should include readable prefixed labels and wider control."""
    response = client.get('/')
    assert response.status_code == 200

    html = response.data.decode('utf-8')
    assert 'value="conservative_theoretical"' in html
    assert 'value="max_theoretical"' in html
    assert 'value="median_realized"' in html
    assert 'value="average_realized"' in html
    assert 'value="average_realized_trimmed"' in html
    assert 'value="fixed_conservative_theoretical_max"' in html
    assert 'value="fixed_theoretical_max"' in html

    assert 'Variable: Conservative Theoretical Max' in html
    assert 'Variable: Theoretical Max' in html
    assert 'Fixed: Median Realized' in html
    assert 'Fixed: Average Realized' in html
    assert 'Fixed: Average Realized (Trimmed)' in html
    assert 'Fixed: Conservative Theoretical Max' in html
    assert 'Fixed: Theoretical Max' in html

    assert 'id="risk_calculation_method" name="risk_calculation_method" style="width: 320px;"' in html


@patch('app.trade_parser.parse_trade_csv')
def test_results_simulation_error_displays_and_preserves_state(mock_parse, client):
    """Test that simulation errors are displayed and form state is preserved."""
    # Mock the parsing to return valid data
    mock_parse.return_value = {
        'num_trades': 10,
        'pnl_distribution': [100, 200, -50, -100, 150],
        'name': 'Test Trade',
        'win_rate': 0.6,
        'avg_win': 150,
        'avg_loss': -75,
        'max_win': 200,
        'max_loss': -100,
        'max_theoretical_loss': 500,
        'conservative_theoretical_max_loss': 450,
        'max_theoretical_gain': 300,
        'conservative_realized_max_reward': 250,
        'risked': 500,
        'total_return': 300,
        'pct_return': 60.0,
        'avg_pct_return': 6.0,
        'commissions': 5,
        'wins': 6,
        'losses': 4,
        'avg_pct_win': 30,
        'avg_pct_loss': -15,
        'gross_gain': 900,
        'gross_loss': -300,
        'median_loss': -75,
        'median_risk_per_spread': 75
    }
    
    # Set session with very small balance that will trigger error
    with client.session_transaction() as sess:
        sess['csv_filepath'] = 'dummy.csv'
        sess['original_filename'] = 'test_trades.csv'
        sess['params'] = {
            'initial_balance': 10,  # Too small!
            'num_simulations': 100,
            'num_trades': 10,
            'option_commission': 0.50,
            'position_sizing': 'percent',
            'dynamic_risk_sizing': True,
            'simulation_mode': 'iid',
            'block_size': 5,
            'position_sizing_display': 'dynamic-percent',
            'risk_calculation_method': 'conservative_theoretical'
        }

    response = client.get('/results', follow_redirects=True)
    assert response.status_code == 200
    
    # Check that error message is displayed
    html = response.data.decode('utf-8')
    assert 'Error running simulation' in html
    assert 'insufficient' in html.lower() or 'balance' in html.lower()
    
    # Check that form is displayed with preserved values
    assert 'value="10"' in html  # initial_balance preserved
    assert 'value="100"' in html  # num_simulations preserved
    assert 'test_trades.csv' in html  # filename shown
    
    # Check that the results section is not shown
    assert 'Trade Stats' not in html or 'show_error_only' in html


@patch('app.trade_parser.parse_trade_csv')
def test_results_csv_parse_error_redirects_to_index(mock_parse, client):
    """Test that CSV parse errors redirect to index with error message."""
    # Mock the parsing to raise an error
    mock_parse.side_effect = ValueError("Invalid CSV format")
    
    # Set session
    with client.session_transaction() as sess:
        sess['csv_filepath'] = 'bad.csv'
        sess['original_filename'] = 'bad.csv'
        sess['params'] = {
            'initial_balance': 10000,
            'num_simulations': 100,
            'num_trades': 10,
            'option_commission': 0.50,
            'position_sizing': 'percent',
            'dynamic_risk_sizing': True,
            'simulation_mode': 'iid',
            'block_size': 5,
            'position_sizing_display': 'dynamic-percent',
            'risk_calculation_method': 'conservative_theoretical'
        }

    response = client.get('/results', follow_redirects=True)
    assert response.status_code == 200
    
    # Should redirect to index
    html = response.data.decode('utf-8')
    assert 'Upload your trade data' in html  # index page content
    assert 'Error parsing CSV' in html or 'Invalid CSV' in html


def test_flash_messages_have_categories(client):
    """Test that flash messages support categories for styling."""
    # Test that the app supports flash message categories
    with client.session_transaction() as sess:
        # Flash with category is handled by Flask, just verify template renders it
        pass
    
    response = client.get('/')
    html = response.data.decode('utf-8')
    # Check that flash message container exists in base template
    assert 'flash-message' in html or 'get_flashed_messages' in html
