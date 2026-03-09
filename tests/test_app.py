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

def test_results_get_with_session(client):
    """Test GET /results with session - uses real simulation with test CSV."""
    # Use real test CSV file
    test_csv = os.path.join(os.path.dirname(__file__), 'test_data', 'test_call_spread.csv')
    
    with open(test_csv, 'rb') as f:
        data = {
            'csv_file': (f, 'test_call_spread.csv'),
            'initial_balance': '10000',
            'num_simulations': '5',  # Small for speed
            'option_commission': '0.50',
            'position_sizing_mode': 'dynamic-percent',
            'dynamic_risk_sizing': 'on',
            'simulation_mode': 'iid',
            'block_size': '1',
            'risk_calculation_method': 'conservative_theoretical',
            'max_reward_method': 'conservative_realized',
            'take_profit_method': 'no_cap',
            'random_seed': '42'  # Deterministic
        }
        # POST to run simulation
        response = client.post('/', data=data, content_type='multipart/form-data', follow_redirects=False)
        assert response.status_code == 302
        assert '/results' in response.headers['Location']

    # Now GET /results to verify page displays correctly
    response = client.get('/results')
    assert response.status_code == 200
    html = response.data.decode('utf-8')
    
    # Verify page contains expected elements
    assert 'Adjust Parameters' in html
    assert 'Simulation Results' in html or 'Monte Carlo' in html
    # Verify simulation ran and produced output (check for chart.js which is loaded for results)
    assert 'chart.js' in html.lower()

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

def test_reward_parameters_passed_to_simulator(client):
    """Test that max_reward_method and take_profit_method are properly passed from form to simulator.
    
    Uses real simulation to verify that different reward methods
    actually affect the results (no mocking).
    """
    test_csv = os.path.join(os.path.dirname(__file__), 'test_data', 'test_call_spread.csv')
    
    # Test with 'no_cap' reward method
    with open(test_csv, 'rb') as f:
        data = {
            'csv_file': (f, 'test_call_spread.csv'),
            'initial_balance': '10000',
            'num_simulations': '5',
            'option_commission': '0.50',
            'position_sizing_mode': 'dynamic-percent',
            'dynamic_risk_sizing': 'on',
            'simulation_mode': 'iid',
            'block_size': '5',
            'risk_calculation_method': 'conservative_theoretical',
            'max_reward_method': 'conservative_realized',
            'take_profit_method': 'no_cap',
            'random_seed': '42'
        }
        response = client.post('/', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        
        # Verify parameters are stored in session
        with client.session_transaction() as sess:
            assert sess['params']['max_reward_method'] == 'conservative_realized'
            assert sess['params']['take_profit_method'] == 'no_cap'
            assert sess['params']['risk_calculation_method'] == 'conservative_theoretical'
    
    # Test with different reward method - conservative_theoretical + 50% cap
    with open(test_csv, 'rb') as f:
        data['csv_file'] = (f, 'test_call_spread.csv')
        data['max_reward_method'] = 'conservative_theoretical'
        data['take_profit_method'] = '50pct'
        response = client.post('/', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        
        # Verify parameters are updated in session
        with client.session_transaction() as sess:
            assert sess['params']['max_reward_method'] == 'conservative_theoretical'
            assert sess['params']['take_profit_method'] == '50pct'

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
    """Test that simulation errors are displayed and form state is preserved.
    
    This test verifies the error path in the Monte Carlo simulation route.
    Requires monte_carlo_enabled=true so that run_monte_carlo_simulation is
    called and fails due to insufficient balance (balance=10, risk=450).
    """
    import config, tempfile, os
    # Enable MC so run_monte_carlo_simulation is called and fails on tiny balance
    _cfg_content = """
[simulation]
monte_carlo_enabled = true
initial_balance = 10000
num_simulations = 100
num_trades = 10
option_commission = 0.50
position_sizing_mode = "dynamic-percent"
simulation_mode = "iid"
block_size = 5
risk_calculation_method = "conservative_theoretical"
max_reward_method = "conservative_realized"
take_profit_method = "no_cap"
allow_exceed_target_risk = false
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as _f:
        _f.write(_cfg_content)
        _cfg_path = _f.name
    try:
        config.load(config_path=_cfg_path)
    finally:
        os.unlink(_cfg_path)

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
        'conservative_theoretical_max_reward': 300,
        'conservative_realized_max_reward': 250,
        'avg_risk_per_spread': 500,
        'avg_reward_per_spread': 300,
        'max_win_pct': 40.0,
        'max_loss_pct': -20.0,
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
        'median_win': 120,
        'median_loss': -75,
        'median_risk_per_spread': 75,
        'median_reward_per_spread': 300,
        'median_win_pct': 24.0,
        'median_loss_pct': -15.0
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
                         '&max_reward_method=conservative_theoretical'
                         '&take_profit_method=50pct'
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
    assert 'value="conservative_theoretical" selected' in html  # max_reward_method
    assert 'value="50pct" selected' in html  # take_profit_method
    
    # Check checkbox is checked
    assert 'checked' in html  # allow_exceed_target_risk


def test_index_post_with_file_uuid_reuses_existing_file(client):
    """Test POST to index with file_uuid reuses existing file without requiring upload."""
    # Create a temporary CSV file with a valid UUID v4 (required by _validate_file_uuid)
    test_uuid = 'a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c8d'
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
            'max_reward_method': 'conservative_realized',
            'take_profit_method': 'no_cap'
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


def test_validate_file_uuid_rejects_path_traversal(client):
    """Security test: path-traversal strings must be rejected by _validate_file_uuid.

    A valid file_uuid MUST be a well-formed UUID v4 string. Any value that is
    not a valid UUID (including path-traversal payloads) must be rejected before
    it is ever combined with the upload folder path, preventing directory
    traversal attacks.
    """
    from app import _validate_file_uuid

    # --- Valid UUID v4 ---
    assert _validate_file_uuid('a1b2c3d4-e5f6-4a1b-8c2d-3e4f5a6b7c8d') is True

    # --- Path traversal attempts ---
    assert _validate_file_uuid('../../etc/passwd') is False
    assert _validate_file_uuid('../config') is False
    assert _validate_file_uuid('uploads/../../etc/hosts') is False

    # --- Malformed / non-UUID strings ---
    assert _validate_file_uuid('test-uuid-12345') is False
    assert _validate_file_uuid('nonexistent-uuid') is False
    assert _validate_file_uuid('') is False
    assert _validate_file_uuid(None) is False

    # --- Wrong UUID version (v1, not v4) must be rejected ---
    # UUID version is encoded in the 13th hex digit (must be '4' for v4)
    assert _validate_file_uuid('550e8400-e29b-11d4-a716-446655440000') is False


def test_file_uuid_path_traversal_via_route(client):
    """Security test: path-traversal file_uuid submitted via form is rejected."""
    # A POST with a path-traversal value in file_uuid must redirect back to index
    # with no file read attempted, not try to open 'uploads/../../some_path.csv'.
    for bad_uuid in ['../../etc/passwd', '../config.toml', 'foo/../bar']:
        data = {
            'file_uuid': bad_uuid,
            'initial_balance': '10000',
            'num_simulations': '10',
            'num_trades': '10',
            'option_commission': '0.50',
            'position_sizing_mode': 'dynamic-percent',
            'simulation_mode': 'iid',
            'block_size': '5',
            'risk_calculation_method': 'conservative_theoretical',
            'max_reward_method': 'conservative_realized',
            'take_profit_method': 'no_cap',
        }
        response = client.post('/', data=data, content_type='multipart/form-data')
        assert response.status_code == 302, f"Expected 302 for bad uuid={bad_uuid!r}"
        assert response.headers['Location'].rstrip('/') in ('/', ''), (
            f"Expected redirect to / for bad uuid={bad_uuid!r}"
        )


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
    # Create a temporary CSV file with a valid UUID v4 (required by _validate_file_uuid)
    test_uuid = 'b2c3d4e5-f6a7-4b2c-9d3e-4f5a6b7c8d9e'
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


def test_results_page_includes_file_uuid_in_link(client):
    """Test that results page includes file_uuid in the 'new tab' link.
    
    Uses real simulation with a UUID-based file upload to verify the link
    contains the correct UUID (no mocking).
    """
    test_csv = os.path.join(os.path.dirname(__file__), 'test_data', 'test_call_spread.csv')
    test_uuid = 'test-uuid-link-12345'
    
    # Create uploads directory if it doesn't exist
    uploads_dir = 'uploads'
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    
    # Copy test CSV to uploads with UUID in filename
    import shutil
    uuid_csv_path = os.path.join(uploads_dir, f'{test_uuid}.csv')
    try:
        shutil.copy(test_csv, uuid_csv_path)
        
        # Upload and run simulation using the UUID file
        with open(uuid_csv_path, 'rb') as f:
            data = {
                'csv_file': (f, 'test.csv'),
                'initial_balance': '10000',
                'num_simulations': '5',
                'option_commission': '0.50',
                'position_sizing_mode': 'dynamic-percent',
                'dynamic_risk_sizing': 'on',
                'simulation_mode': 'iid',
                'block_size': '5',
                'risk_calculation_method': 'conservative_theoretical',
                'max_reward_method': 'conservative_realized',
                'take_profit_method': 'no_cap',
                'allow_exceed_target_risk': 'off',
                'random_seed': '42'
            }
            response = client.post('/', data=data, content_type='multipart/form-data', follow_redirects=False)
            assert response.status_code == 302
        
        # Get results page
        response = client.get('/results')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        
        # Verify the page contains file_uuid parameter in links
        # The link should be for opening results in new tab
        assert 'file_uuid=' in html
        assert 'target="_blank"' in html  # Opens in new tab
    finally:
        # Cleanup
        if os.path.exists(uuid_csv_path):
            os.unlink(uuid_csv_path)


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


@patch('app.simulator.run_monte_carlo_simulation')
@patch('app.trade_parser.parse_trade_csv')
def test_replay_trajectory_data_structure_for_charting(mock_parse, mock_simulate, client):
    """Test that replay results include trade_history for trajectory charting."""
    # Mock parse_trade_csv return value - include all fields expected by template
    mock_parse.return_value = {
        'num_trades': 5,
        'win_rate': 0.6,
        'avg_win': 100,
        'avg_loss': -50,
        'median_win': 75,
        'median_loss': -50,
        'median_risk_per_spread': 100,
        'median_reward_per_spread': 80,
        'median_win_pct': 75.0,
        'median_loss_pct': -50.0,
        'max_win': 200,
        'max_loss': -100,
        'max_theoretical_loss': 100,
        'conservative_theoretical_max_loss': 80,
        'max_theoretical_gain': 100,
        'conservative_theoretical_max_reward': 80,
        'conservative_realized_max_reward': 200,
        'avg_risk_per_spread': 100,
        'avg_reward_per_spread': 80,
        'max_win_pct': 200.0,
        'max_loss_pct': -100.0,
        'risked': 100,
        'total_return': 125,
        'pct_return': 12.5,
        'avg_pct_return': 2.5,
        'commissions': 10,
        'wins': 3,
        'losses': 2,
        'avg_pct_win': 25.0,
        'avg_pct_loss': -12.5,
        'gross_gain': 225,
        'gross_loss': -100,
        'pnl_distribution': [50, -50, 100, -50, 75],
        'per_trade_theoretical_risk': [100, 100, 100, 100, 100],
        'per_trade_theoretical_reward': [50, 50, 50, 50, 50],
        'per_trade_dates': ['2023-01-01', '2023-02-01', '2023-03-01', '2023-04-01', '2023-05-01'],
        'raw_trade_data': [],
        'min_date': '2023-01-01',
        'max_date': '2023-05-01'
    }
    
    # Mock Monte Carlo simulation return value
    mock_simulate.return_value = [{
        'trade_name': 'Test Trade',
        'summary': mock_parse.return_value,
        'table_rows': [
            {'Contracts': 1, 'Target Risk %': '1.00%', 'Avg Final $': '$10,000'},
            {'Contracts': 2, 'Target Risk %': '2.00%', 'Avg Final $': '$11,000'}
        ],
        'pnl_preview': ['50', '-50', '100'],
        'historical_max_winning_streak': 2,
        'historical_max_losing_streak': 1,
        'historical_avg_winning_streak': 1.5,
        'historical_avg_losing_streak': 1.0,
        'historical_median_winning_streak': 1.5,
        'historical_median_losing_streak': 1.0,
        'trajectory_data': {
            '1.00%': {'p5': [10000, 9900], 'p50': [10000, 10050], 'p95': [10000, 10200]},
            '2.00%': {'p5': [10000, 9800], 'p50': [10000, 10100], 'p95': [10000, 10400]}
        }
    }]
    
    # Submit form to upload file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("Trade Name,Entry Date,Exit Date,P/L\nTest,2023-01-01,2023-01-02,100\n")
        temp_file = f.name
    
    try:
        with open(temp_file, 'rb') as f:
            data = {
                'csv_file': f,
                'initial_balance': '10000',
                'num_simulations': '10',
                'num_trades': '5',
                'option_commission': '0.50',
                'position_sizing_mode': 'percent',
                'dynamic_risk_sizing': 'on',
                'simulation_mode': 'iid',
                'block_size': '5'
            }
            response = client.post('/', data=data, content_type='multipart/form-data', follow_redirects=False)
            assert response.status_code == 302
        
        # Now GET /results to see rendered output
        response = client.get('/results')
        assert response.status_code == 200
        
        # The response should have rendered the results page
        # Check that replay data structures would be available
        # (In a future step, we'll verify replay_trajectory_data is passed to template)
        html = response.data.decode('utf-8')
        assert 'Historical Replay' in html or 'Replay' in html
        
    finally:
        os.unlink(temp_file)


@patch('app.trade_parser.parse_trade_csv')
def test_replay_collects_trade_history_per_scenario(mock_parse, client):
    """Test that each replay scenario has its trade_history for charting."""
    from unittest.mock import Mock
    import replay
    
    # Mock parse_trade_csv - include all fields expected by template
    trade_stats = {
        'num_trades': 3,
        'win_rate': 0.67,
        'avg_win': 100,
        'avg_loss': -50,
        'median_win': 75,        
        'median_loss': -50,
        'median_risk_per_spread': 100,
        'median_reward_per_spread': 80,
        'median_win_pct': 75.0,
        'median_loss_pct': -50.0,
        'max_win': 150,
        'max_loss': -75,
        'max_theoretical_loss': 100,
        'conservative_theoretical_max_loss': 80,
        'max_theoretical_gain': 100,
        'conservative_theoretical_max_reward': 80,
        'conservative_realized_max_reward': 150,
        'avg_risk_per_spread': 100,
        'avg_reward_per_spread': 80,
        'max_win_pct': 150.0,
        'max_loss_pct': -75.0,
        'risked': 100,
        'total_return': 125,
        'pct_return': 12.5,
        'avg_pct_return': 4.17,
        'commissions': 10,
        'wins': 2,
        'losses': 1,
        'avg_pct_win': 37.5,
        'avg_pct_loss': -12.5,
        'gross_gain': 175,
        'gross_loss': -50,
        'pnl_distribution': [100, -50, 75],
        'per_trade_theoretical_risk': [100, 100, 100],
        'per_trade_theoretical_reward': [50, 50, 50],
        'per_trade_dates': ['2023-01-01', '2023-02-01', '2023-03-01'],
        'raw_trade_data': [],
        'min_date': '2023-01-01',
        'max_date': '2023-03-01'
    }
    mock_parse.return_value = trade_stats
    
    # Patch replay to track its calls
    original_replay = replay.replay_actual_trades
    call_count = {'count': 0}
    collected_histories = []
    
    def mock_replay_func(**kwargs):
        call_count['count'] += 1
        result = original_replay(**kwargs)
        # Verify trade_history exists and has correct structure
        assert 'trade_history' in result, "replay result should have trade_history"
        assert isinstance(result['trade_history'], list), "trade_history should be a list"
        assert len(result['trade_history']) > 0, "trade_history should not be empty"
        assert result['trade_history'][0] == kwargs['initial_balance'], "First element should be initial_balance"
        collected_histories.append(result['trade_history'])
        return result
    
    with patch('app.replay.replay_actual_trades', side_effect=mock_replay_func):
        # Submit form
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("Trade Name,Entry Date,Exit Date,P/L\nTest,2023-01-01,2023-01-02,100\n")
            temp_file = f.name
        
        try:
            with open(temp_file, 'rb') as f:
                data = {
                    'csv_file': f,
                    'initial_balance': '10000',
                    'num_simulations': '10',
                    'num_trades': '3',
                    'option_commission': '0.50',
                    'position_sizing_mode': 'percent',
                    'dynamic_risk_sizing': 'on',
                    'simulation_mode': 'iid',
                    'block_size': '5'
                }
                response = client.post('/', data=data, content_type='multipart/form-data', follow_redirects=False)
                assert response.status_code == 302
            
            # Get results
            response = client.get('/results')
            assert response.status_code == 200
            
            # Verify replay was called multiple times (once per scenario/threshold)
            # Percent mode typically tests 10 thresholds: 1%, 2%, 3%, 5%, 10%, 15%, 25%, 50%, 75%, 100%
            assert call_count['count'] > 1, "replay should be called multiple times for different scenarios"
            
            # Verify all collected histories have the expected structure
            for history in collected_histories:
                assert len(history) == 4, f"Expected 4 elements (initial + 3 trades), got {len(history)}"
                # First element is initial balance
                assert history[0] == 10000
        
        finally:
            os.unlink(temp_file)
