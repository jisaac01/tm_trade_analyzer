"""Application configuration loader.

Loads config from config.toml. If config.toml does not exist, it is created
automatically from config.template.toml so that local overrides (e.g. enabling
Monte Carlo) never appear in ``git status``.

Usage::

    import config

    config.load()                                     # call once at app startup
    enabled = config.get('simulation.monte_carlo_enabled', False)
    defaults = config.simulation_defaults()
"""

import os
import shutil
import tomllib

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(_BASE_DIR, 'config.template.toml')
CONFIG_PATH = os.path.join(_BASE_DIR, 'config.toml')

_config: dict = {}


def _ensure_config_file() -> None:
    """Create config.toml from the template if it does not already exist."""
    if not os.path.exists(CONFIG_PATH):
        if not os.path.exists(TEMPLATE_PATH):
            raise FileNotFoundError(
                f"Config template not found: {TEMPLATE_PATH}. "
                "Cannot initialize config.toml."
            )
        shutil.copy(TEMPLATE_PATH, CONFIG_PATH)


def load(config_path: str | None = None) -> dict:
    """Load (or reload) the application configuration.

    Creates config.toml from config.template.toml if it does not yet exist.

    Parameters
    ----------
    config_path:
        Override the path to the TOML config file. Useful for tests.

    Returns
    -------
    dict
        The loaded configuration.
    """
    global _config
    path = config_path or CONFIG_PATH
    if path == CONFIG_PATH:
        _ensure_config_file()
    with open(path, 'rb') as f:
        _config = tomllib.load(f)
    return _config


def get(key_path: str, default=None):
    """Get a config value by dot-separated key path.

    Example::

        get('simulation.monte_carlo_enabled')
        get('simulation.initial_balance', 10000)
    """
    parts = key_path.split('.')
    node = _config
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def simulation_defaults() -> dict:
    """Return the ``[simulation]`` section as a flat dict of form defaults."""
    return dict(_config.get('simulation', {}))
