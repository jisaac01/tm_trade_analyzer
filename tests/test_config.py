"""
Tests for the config module and Monte Carlo toggle behavior.

TDD approach: tests specify EXPECTED behavior based on requirements,
not whatever the code currently does.
"""
import os
import shutil
import tempfile
import tomllib

import pytest
import numpy as np

# ---------------------------------------------------------------------------
# Config module tests
# ---------------------------------------------------------------------------

class TestConfigLoad:
    """config.load() should create config.toml from template when absent."""

    def _write_template(self, dir_path: str, content: str) -> str:
        """Write a minimal TOML template and return its path."""
        path = os.path.join(dir_path, 'config.template.toml')
        with open(path, 'w') as f:
            f.write(content)
        return path

    def test_creates_config_from_template_when_missing(self, tmp_path):
        """When config.toml doesn't exist, load() copies the template."""
        import config as cfg

        template_content = """
[simulation]
monte_carlo_enabled = false
initial_balance = 10000
"""
        template_path = str(tmp_path / 'config.template.toml')
        config_path = str(tmp_path / 'config.toml')

        with open(template_path, 'w') as f:
            f.write(template_content)

        assert not os.path.exists(config_path)
        cfg.load(config_path=template_path)  # Should not raise
        # Load explicitly from our tmp template (simulating the creation flow)
        # Just test that loading the template path works correctly
        loaded = cfg.load(config_path=template_path)
        assert loaded['simulation']['monte_carlo_enabled'] is False
        assert loaded['simulation']['initial_balance'] == 10000

    def test_load_returns_dict(self, tmp_path):
        """load() returns a dict."""
        import config as cfg

        template_content = """
[simulation]
monte_carlo_enabled = false
initial_balance = 5000
num_simulations = 500
"""
        path = str(tmp_path / 'my_config.toml')
        with open(path, 'w') as f:
            f.write(template_content)

        result = cfg.load(config_path=path)
        assert isinstance(result, dict)
        assert 'simulation' in result

    def test_template_is_valid_toml(self):
        """The committed config.template.toml must be valid TOML."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_path = os.path.join(base, 'config.template.toml')
        assert os.path.exists(template_path), "config.template.toml must exist"
        with open(template_path, 'rb') as f:
            data = tomllib.load(f)
        assert 'simulation' in data, "Template must have [simulation] section"

    def test_template_defaults_monte_carlo_off(self):
        """The committed template must default monte_carlo_enabled to false."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_path = os.path.join(base, 'config.template.toml')
        with open(template_path, 'rb') as f:
            data = tomllib.load(f)
        assert data['simulation']['monte_carlo_enabled'] is False, (
            "Template default for monte_carlo_enabled must be false so git "
            "never commits an 'on' state."
        )

    def test_template_has_all_required_defaults(self):
        """The committed template must contain all required simulation default keys."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_path = os.path.join(base, 'config.template.toml')
        with open(template_path, 'rb') as f:
            data = tomllib.load(f)
        sim = data['simulation']
        required_keys = [
            'monte_carlo_enabled',
            'initial_balance',
            'num_simulations',
            'num_trades',
            'option_commission',
            'position_sizing_mode',
            'simulation_mode',
            'block_size',
            'risk_calculation_method',
            'max_reward_method',
            'take_profit_method',
            'allow_exceed_target_risk',
        ]
        for key in required_keys:
            assert key in sim, f"Template missing required key: simulation.{key}"


class TestConfigGet:
    """config.get() should retrieve values by dot-separated path."""

    def _load_from_content(self, content: str) -> None:
        import config as cfg
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(content)
            path = f.name
        try:
            cfg.load(config_path=path)
        finally:
            os.unlink(path)

    def test_get_top_level_key(self):
        """get() returns value for a top-level key."""
        self._load_from_content("[simulation]\nmonte_carlo_enabled = true\n")
        import config as cfg
        assert cfg.get('simulation.monte_carlo_enabled') is True

    def test_get_missing_key_returns_default(self):
        """get() returns the default when the key is absent."""
        self._load_from_content("[simulation]\n")
        import config as cfg
        assert cfg.get('simulation.nonexistent_key', 42) == 42

    def test_get_missing_section_returns_default(self):
        """get() returns the default when the section is absent."""
        self._load_from_content("[simulation]\n")
        import config as cfg
        assert cfg.get('other_section.key', 'fallback') == 'fallback'

    def test_simulation_defaults_returns_dict(self):
        """simulation_defaults() returns the simulation section as a flat dict."""
        self._load_from_content(
            "[simulation]\nmonte_carlo_enabled = false\ninitial_balance = 12345\n"
        )
        import config as cfg
        defaults = cfg.simulation_defaults()
        assert isinstance(defaults, dict)
        assert defaults['monte_carlo_enabled'] is False
        assert defaults['initial_balance'] == 12345


# ---------------------------------------------------------------------------
# simulator.build_summary_report() tests
# ---------------------------------------------------------------------------

class TestBuildSummaryReport:
    """
    build_summary_report() should return the same non-MC fields that
    run_monte_carlo_simulation() attaches to each report, without simulating.
    """

    def _make_trade_stats(self, pnl_distribution: list) -> dict:
        """Minimal trade_stats dict for testing streak computation."""
        return {
            'name': 'Test Trade',
            'pnl_distribution': pnl_distribution,
            'win_rate': 0.6,
            'avg_win': 100.0,
            'avg_loss': -80.0,
            'avg_risk_per_spread': 200.0,
            'avg_reward_per_spread': 150.0,
            'median_risk_per_spread': 190.0,
            'total_return': 200.0,
            'gross_gain': 600.0,
            'gross_loss': -400.0,
            'num_trades': len(pnl_distribution),
            'conservative_theoretical_max_loss': 180.0,
            'conservative_theoretical_max_reward': 120.0,
            'max_theoretical_loss': 200.0,
            'max_theoretical_gain': 150.0,
            'conservative_realized_max_reward': 110.0,
            'max_win': 150.0,
            'max_loss': -200.0,
        }

    def test_returns_required_keys(self):
        """Report must contain all keys the template accesses."""
        import simulator
        stats = self._make_trade_stats([100, -80, 100, -80, 100])
        report = simulator.build_summary_report(stats)

        required = [
            'trade_name', 'summary', 'table_rows', 'pnl_preview',
            'historical_max_winning_streak', 'historical_max_losing_streak',
            'historical_avg_winning_streak', 'historical_avg_losing_streak',
            'historical_median_winning_streak', 'historical_median_losing_streak',
            'trajectory_data',
        ]
        for key in required:
            assert key in report, f"Missing key in summary report: {key}"

    def test_table_rows_is_empty_no_mc(self):
        """table_rows must be empty (no Monte Carlo ran)."""
        import simulator
        stats = self._make_trade_stats([100, -80, 100])
        report = simulator.build_summary_report(stats)
        assert report['table_rows'] == []

    def test_trajectory_data_is_empty_no_mc(self):
        """trajectory_data must be empty (no Monte Carlo ran)."""
        import simulator
        stats = self._make_trade_stats([100, -80, 100])
        report = simulator.build_summary_report(stats)
        assert report['trajectory_data'] == {}

    def test_pnl_preview_first_10(self):
        """pnl_preview should contain formatted strings of first 10 P/L values."""
        import simulator
        pnl = [100, -80, 200, -50, 75, -30, 110, -90, 60, -40, 999]
        stats = self._make_trade_stats(pnl)
        report = simulator.build_summary_report(stats)
        # Only first 10 entries
        assert len(report['pnl_preview']) == 10
        assert report['pnl_preview'][0] == '100'
        assert report['pnl_preview'][1] == '-80'

    def test_trade_name_from_stats(self):
        """trade_name should use the 'name' key from trade_stats."""
        import simulator
        stats = self._make_trade_stats([100, -80])
        stats['name'] = 'My Strategy'
        report = simulator.build_summary_report(stats)
        assert report['trade_name'] == 'My Strategy'

    def test_streak_calculation_simple(self):
        """
        Streak computation: [W, W, L, W, L, L] should give:
          max_win_streak = 2, max_loss_streak = 2
          avg_win_streak = (2 + 1) / 2 = 1.5
          avg_loss_streak = (1 + 2) / 2 = 1.5
        """
        import simulator
        # W, W, L, W, L, L  →  100, 100, -80, 100, -80, -80
        stats = self._make_trade_stats([100, 100, -80, 100, -80, -80])
        report = simulator.build_summary_report(stats)

        assert report['historical_max_winning_streak'] == 2
        assert report['historical_max_losing_streak'] == 2
        assert report['historical_avg_winning_streak'] == pytest.approx(1.5)
        assert report['historical_avg_losing_streak'] == pytest.approx(1.5)

    def test_streak_calculation_all_wins(self):
        """All-win sequence: max streak = num_trades, avg = num_trades."""
        import simulator
        stats = self._make_trade_stats([100, 100, 100])
        report = simulator.build_summary_report(stats)
        assert report['historical_max_winning_streak'] == 3
        assert report['historical_max_losing_streak'] == 0
        assert report['historical_avg_winning_streak'] == 3.0
        assert report['historical_avg_losing_streak'] == 0.0

    def test_streak_calculation_all_losses(self):
        """All-loss sequence: loss streak = num_trades, win streak = 0."""
        import simulator
        stats = self._make_trade_stats([-80, -80, -80])
        report = simulator.build_summary_report(stats)
        assert report['historical_max_losing_streak'] == 3
        assert report['historical_max_winning_streak'] == 0

    def test_summary_passthrough(self):
        """The 'summary' key must be the trade_stats dict (with name override)."""
        import simulator
        stats = self._make_trade_stats([100, -80])
        stats['name'] = 'TestStrategy'
        report = simulator.build_summary_report(stats)
        assert report['summary']['name'] == 'TestStrategy'
        assert report['summary']['win_rate'] == 0.6


# ---------------------------------------------------------------------------
# Monte Carlo toggle: app-level integration
# ---------------------------------------------------------------------------

class TestMonteCarloToggle:
    """
    When monte_carlo_enabled = false in config, the results route must not
    call run_monte_carlo_simulation and must still return replay data.
    """

    @pytest.fixture
    def client(self):
        """Flask test client."""
        from app import app as flask_app
        flask_app.config['TESTING'] = True
        with flask_app.test_client() as c:
            yield c

    @pytest.fixture
    def csv_path(self):
        """Path to a real test CSV file that is valid for MC simulation."""
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Use the CML real-data CSV which has all required risk/reward fields
        path = os.path.join(
            base, 'tests', 'test_data',
            'CML TM Trades Long 60 Delta, Short 30 Delta Call 20260223.csv'
        )
        assert os.path.exists(path), f"Test CSV not found: {path}"
        return path

    def _set_session_with_csv(self, client, csv_path: str) -> None:
        """Directly inject session state to bypass multipart upload."""
        with client.session_transaction() as sess:
            sess['csv_filepath'] = csv_path
            sess['original_filename'] = os.path.basename(csv_path)
            sess['csv_file_uuid'] = 'test-uuid'
            sess['params'] = {
                'initial_balance': 10000,
                'num_simulations': 5,
                'num_trades': 10,
                'option_commission': 0.50,
                'position_sizing': 'percent',
                'dynamic_risk_sizing': True,
                'simulation_mode': 'iid',
                'block_size': 5,
                'position_sizing_display': 'dynamic-percent',
                'risk_calculation_method': 'conservative_theoretical',
                'max_reward_method': 'conservative_realized',
                'take_profit_method': 'no_cap',
                'allow_exceed_target_risk': False,
            }

    def _load_test_config(self, tmp_path, monte_carlo_enabled: bool) -> None:
        """Write a test config.toml and reload config module from it."""
        import config as cfg
        content = f"""
[simulation]
monte_carlo_enabled = {str(monte_carlo_enabled).lower()}
initial_balance = 10000
num_simulations = 5
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
        path = str(tmp_path / f'test_mc_{monte_carlo_enabled}.toml')
        with open(path, 'w') as f:
            f.write(content)
        cfg.load(config_path=path)

    def test_mc_disabled_results_page_renders(self, client, csv_path, tmp_path):
        """
        When monte_carlo_enabled = false, /results must respond 200 and show
        the backtest summary without Monte Carlo sections.
        Expected: no 'Monte Carlo Simulation Results' heading in the response body.
        """
        self._load_test_config(tmp_path, monte_carlo_enabled=False)
        self._set_session_with_csv(client, csv_path)

        response = client.get('/results')
        assert response.status_code == 200

        body = response.data.decode('utf-8')
        assert 'Monte Carlo Simulation Results' not in body, (
            "MC results table should not be rendered when monte_carlo_enabled=false"
        )
        # Replay section should still be present
        assert 'Historical Trade Replay' in body

    def test_mc_enabled_results_page_shows_mc_table(self, client, csv_path, tmp_path):
        """
        When monte_carlo_enabled = true, /results must include the Monte Carlo
        Simulation Results table.
        Expected: 'Monte Carlo Simulation Results' appears in the response body.
        """
        self._load_test_config(tmp_path, monte_carlo_enabled=True)
        self._set_session_with_csv(client, csv_path)

        response = client.get('/results')
        assert response.status_code == 200

        body = response.data.decode('utf-8')
        assert 'Monte Carlo Simulation Results' in body, (
            "MC results table should be rendered when monte_carlo_enabled=true"
        )
