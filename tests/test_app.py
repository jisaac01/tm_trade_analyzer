import pytest
from app import app
import os

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_index_get(client):
    """Test that the index route returns 200 and contains expected content."""
    response = client.get('/')
    assert response.status_code == 200
    assert b'Monte Carlo Trade Sizing Report' in response.data
    assert b'Simulated Trade' in response.data  # Since the trade name is "Simulated Trade"

def test_format_currency_whole():
    """Test the format_currency_whole function."""
    from app import format_currency_whole
    assert format_currency_whole(1000) == '$1000'
    assert format_currency_whole(-500) == '-$500'
    assert format_currency_whole(0) == '$0'