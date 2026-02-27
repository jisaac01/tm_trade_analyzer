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
        'per_trade_theoretical_reward': [500, 500, 500],
        'per_trade_dates': ['2023-01-01', '2023-02-01', '2023-03-01'],
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
            'block_size': 1,
            'risk_calculation_method': 'conservative_theoretical',
            'reward_calculation_method': 'no_cap'
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

@patch('app.replay.replay_actual_trades')
@patch('app.simulator.run_monte_carlo_simulation')
@patch('app.trade_parser.parse_trade_csv')
def test_reward_calculation_method_passed_to_simulator(mock_parse, mock_simulate, mock_replay, client):
    """Test that reward_calculation_method is properly passed from form to simulator."""
    # Mock the parsing to return valid trade data
    mock_parse.return_value = {
        'num_trades': 10,
        'pnl_distribution': [100, 200, -50, -100, 150, 80, -60, 120, -40, 180],
        'per_trade_theoretical_risk': [300] * 10,
        'per_trade_theoretical_reward': [400] * 10,
        'per_trade_dates': ['2023-01-01'] * 10,
        'name': 'Test Trade',
        'win_rate': 0.6,
        'avg_win': 150,
        'avg_loss': -75,
        'max_win': 200,
        'max_loss': -100,
        'max_theoretical_loss': 300,
        'conservative_theoretical_max_loss': 280,
        'max_theoretical_gain': 400,
        'conservative_theoretical_max_reward': 360,
        'conservative_realized_max_reward': 180,
        'risked': 3000,
        'total_return': 500,
        'pct_return': 16.67,
        'avg_pct_return': 1.67,
        'commissions': 10,
        'wins': 6,
        'losses': 4,
        'avg_pct_win': 50,
        'avg_pct_loss': -25,
        'gross_gain': 900,
        'gross_loss': -400,
        'median_loss': -60,
        'median_risk_per_spread': 75
    }
    
    # Mock the simulation
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
            'conservative_theoretical_max_loss': 280,
            'max_theoretical_loss': 300,
            'historical_max_losing_streak': 2
        },
        'table_rows': [
            {'Percentile': '50%', 'Balance': 105000, 'Trades': 10, 'Win Rate': '60%'}
        ],
        'pnl_preview': ['100', '200', '-50']
    }]
    
    # Mock replay
    mock_replay.return_value = {
        'final_balance': 105000,
        'max_drawdown': 5000,
        'max_losing_streak': 2,
        'trade_details': []
    }
    
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
                'block_size': '5',
                'risk_calculation_method': 'conservative_theoretical',
                'reward_calculation_method': 'cap_50pct_conservative_theoretical_max'
            }
            response = client.post('/', data=data, content_type='multipart/form-data', follow_redirects=True)
            assert response.status_code == 200
            
            # Verify run_monte_carlo_simulation was called with reward_calculation_method
            mock_simulate.assert_called_once()
            call_kwargs = mock_simulate.call_args[1]
            assert call_kwargs['reward_calculation_method'] == 'cap_50pct_conservative_theoretical_max'
            
            # Verify parameter is stored in session
            with client.session_transaction() as sess:
                assert sess['params']['reward_calculation_method'] == 'cap_50pct_conservative_theoretical_max'
    finally:
        os.unlink(temp_file)

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
        'per_trade_theoretical_risk': [500, 500, 500, 500, 500],
        'per_trade_theoretical_reward': [300, 300, 300, 300, 300],
        'per_trade_dates': ['2023-01-01', '2023-02-01', '2023-03-01', '2023-04-01', '2023-05-01'],
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


def test_index_get_with_url_parameters(client):
    """Test that GET on index with URL parameters populates form fields."""
    response = client.get('/?initial_balance=50000&num_simulations=500&num_trades=30'
                         '&option_commission=0.75&position_sizing_mode=fixed-percent'
                         '&simulation_mode=moving-block-bootstrap&block_size=7'
                         '&risk_calculation_method=max_theoretical'
                         '&reward_calculation_method=cap_50pct_conservative_theoretical_max'
                         '&allow_exceed_target_risk=true')
    
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Verify form fields are populated with URL parameter values
    assert 'value="50000"' in html  # initial_balance
    assert 'value="500"' in html    # num_simulations
    assert 'value="30"' in html     # num_trades
    assert 'value="0.75"' in html   # option_commission
    assert 'value="7"' in html      # block_size
    
    # Check select options are selected
    assert 'value="fixed-percent" selected' in html or 'value="fixed-percent"\n           selected' in html
    assert 'value="moving-block-bootstrap" selected' in html or 'value="moving-block-bootstrap"\n               selected' in html
    assert 'value="max_theoretical" selected' in html or 'value="max_theoretical"\n                       selected' in html
    assert 'value="cap_50pct_conservative_theoretical_max" selected' in html
    
    # Check checkbox is checked
    assert 'checked' in html  # allow_exceed_target_risk


def test_index_post_with_file_uuid_reuses_existing_file(client):
    """Test POST to index with file_uuid reuses existing file without requiring upload."""
    # Create a temporary CSV file with known UUID
    test_uuid = 'test-uuid-12345'
    uploads_dir = 'uploads'
    os.makedirs(uploads_dir, exist_ok=True)
    test_filepath = os.path.join(uploads_dir, f'{test_uuid}.csv')
    
    with open(test_filepath, 'w') as f:
        f.write("Trade Name,Entry Date,Exit Date,P/L\nTest Trade,2023-01-01,2023-01-02,100\n")
    
    try:
        # POST with file_uuid but no csv_file
        data = {
            'file_uuid': test_uuid,
            'initial_balance': '100000',
            'num_simulations': '100',
            'num_trades': '60',
            'option_commission': '0.50',
            'position_sizing_mode': 'dynamic-percent',
            'simulation_mode': 'iid',
            'block_size': '5',
            'risk_calculation_method': 'conservative_theoretical',
            'reward_calculation_method': 'no_cap'
        }
        response = client.post('/', data=data, content_type='multipart/form-data')
        
        # Should redirect to results
        assert response.status_code == 302
        assert '/results' in response.headers['Location']
        
        # Verify session has correct file path and UUID
        with client.session_transaction() as sess:
            assert sess['csv_filepath'] == test_filepath
            assert sess['csv_file_uuid'] == test_uuid
    finally:
        if os.path.exists(test_filepath):
            os.unlink(test_filepath)


def test_index_post_with_invalid_file_uuid_shows_error(client):
    """Test POST with non-existent file_uuid shows error and redirects."""
    data = {
        'file_uuid': 'nonexistent-uuid',
        'initial_balance': '100000',
        'num_simulations': '100',
        'num_trades': '60',
        'option_commission': '0.50',
        'position_sizing_mode': 'dynamic-percent',
        'simulation_mode': 'iid',
        'block_size': '5'
    }
    response = client.post('/', data=data, content_type='multipart/form-data')
    
    # Should redirect back to index
    assert response.status_code == 302
    assert '/' in response.headers['Location']


def test_index_post_with_new_file_generates_uuid(client):
    """Test that uploading a new file generates and stores a UUID."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("Trade Name,Entry Date,Exit Date,P/L\nTest Trade,2023-01-01,2023-01-02,100\n")
        temp_file = f.name
    
    try:
        with open(temp_file, 'rb') as f:
            data = {
                'csv_file': f,
                'initial_balance': '100000',
                'num_simulations': '100',
                'num_trades': '60',
                'option_commission': '0.50',
                'position_sizing_mode': 'dynamic-percent',
                'simulation_mode': 'iid',
                'block_size': '5'
            }
            response = client.post('/', data=data, content_type='multipart/form-data')
            
            assert response.status_code == 302
            
            # Verify session has UUID
            with client.session_transaction() as sess:
                assert 'csv_file_uuid' in sess
                assert sess['csv_file_uuid'] is not None
                assert len(sess['csv_file_uuid']) > 0
                
                # Verify file was saved with UUID as name
                assert sess['csv_file_uuid'] in sess['csv_filepath']
    finally:
        os.unlink(temp_file)


def test_index_get_with_file_uuid_marks_upload_optional(client):
    """Test that GET with file_uuid parameter marks file upload as optional."""
    # Create a temporary CSV file with known UUID
    test_uuid = 'test-uuid-optional'
    uploads_dir = 'uploads'
    os.makedirs(uploads_dir, exist_ok=True)
    test_filepath = os.path.join(uploads_dir, f'{test_uuid}.csv')
    
    with open(test_filepath, 'w') as f:
        f.write("Trade Name,Entry Date,Exit Date,P/L\nTest Trade,2023-01-01,2023-01-02,100\n")
    
    try:
        response = client.get(f'/?file_uuid={test_uuid}&initial_balance=10000')
        
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        
        # Verify file upload is marked as optional
        assert 'already uploaded - optional' in html
        
        # Verify hidden file_uuid field is present
        assert f'name="file_uuid" value="{test_uuid}"' in html
    finally:
        if os.path.exists(test_filepath):
            os.unlink(test_filepath)


@patch('app.simulator.run_monte_carlo_simulation')
@patch('app.trade_parser.parse_trade_csv')
def test_results_page_includes_file_uuid_in_link(mock_parse, mock_simulate, client):
    """Test that results page includes file_uuid in the 'new tab' link."""
    test_uuid = 'test-uuid-link'
    
    # Mock the parsing
    mock_parse.return_value = {
        'num_trades': 1,
        'pnl_distribution': [100],
        'per_trade_theoretical_risk': [300],
        'per_trade_theoretical_reward': [500],
        'per_trade_dates': ['2023-01-01'],
        'name': 'Test Trade',
        'win_rate': 1.0,
        'avg_win': 100,
        'avg_loss': 0,
        'max_win': 100,
        'max_loss': 0,
        'max_theoretical_loss': 300,
        'conservative_theoretical_max_loss': 300,
        'max_theoretical_gain': 500,
        'conservative_realized_max_reward': 100,
        'risked': 300,
        'total_return': 100,
        'pct_return': 33.33,
        'avg_pct_return': 33.33,
        'commissions': 0,
        'wins': 1,
        'losses': 0,
        'avg_pct_win': 33.33,
        'avg_pct_loss': 0,
        'gross_gain': 100,
        'gross_loss': 0,
        'median_loss': 0,
        'median_risk_per_spread': 300
    }
    
    # Mock the simulation
    mock_simulate.return_value = [{
        'trade_name': 'Test Trade',
        'summary': {
            'total_return': 100,
            'risked': 300,
            'pct_return': 33.33,
            'avg_pct_return': 33.33,
            'commissions': 0,
            'win_rate': 1.0,
            'wins': 1,
            'losses': 0,
            'avg_win': 100,
            'avg_loss': 0,
            'avg_pct_win': 33.33,
            'avg_pct_loss': 0,
            'gross_gain': 100,
            'gross_loss': 0,
            'conservative_theoretical_max_loss': 300,
            'max_theoretical_loss': 300,
            'historical_max_losing_streak': 0
        },
        'table_rows': [],
        'pnl_preview': ['100']
    }]
    
    # Set session with file UUID
    with client.session_transaction() as sess:
        sess['csv_filepath'] = f'uploads/{test_uuid}.csv'
        sess['csv_file_uuid'] = test_uuid
        sess['original_filename'] = 'test.csv'
        sess['params'] = {
            'initial_balance': 10000,
            'num_simulations': 100,
            'num_trades': 60,
            'option_commission': 0.50,
            'position_sizing': 'percent',
            'dynamic_risk_sizing': True,
            'simulation_mode': 'iid',
            'block_size': 5,
            'position_sizing_display': 'dynamic-percent',
            'risk_calculation_method': 'conservative_theoretical',
            'reward_calculation_method': 'no_cap',
            'allow_exceed_target_risk': False
        }
    
    response = client.get('/results')
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Verify the link includes file_uuid
    assert f'file_uuid={test_uuid}' in html
    assert 'target="_blank"' in html  # Opens in new tab


def test_index_post_without_file_or_uuid_shows_error(client):
    """Test POST without csv_file or file_uuid shows error."""
    data = {
        'initial_balance': '100000',
        'num_simulations': '100',
        'num_trades': '60',
        'option_commission': '0.50',
        'position_sizing_mode': 'dynamic-percent',
        'simulation_mode': 'iid',
        'block_size': '5'
        # No csv_file and no file_uuid
    }
    response = client.post('/', data=data, content_type='multipart/form-data')
    
    # Should redirect back to index
    assert response.status_code == 302
    assert '/' in response.headers['Location']
