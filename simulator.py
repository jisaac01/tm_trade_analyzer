import numpy as np
import pandas as pd
import random
import os
from trade_parser import parse_trade_csv

OPTION_COMMISSION_PER_CONTRACT = 0.495

DEFAULT_POSITION_SIZES = [1, 2, 5, 10, 15, 20]
DEFAULT_RISK_PCTS = [1, 2, 3, 5, 10, 15, 25, 50, 75, 100]


def get_position_sizing_risk_per_spread(trade, risk_calculation_method='conservative_theoretical'):
    """
    Get the maximum theoretical risk per spread for POSITION SIZING purposes.
    
    This represents the broker's margin requirement: the theoretical maximum loss
    that could occur on a single trade. Position sizing must be constrained by
    this value to prevent the account balance from going negative.
    
    CRITICAL: When the user selects max_theoretical as their risk calculation method,
    position sizing must ALSO use max_theoretical (not conservative). Otherwise,
    the position sizing constraint (based on conservative) would allow more contracts
    than the account can afford (based on max_theoretical losses).
    
    Parameters:
    - trade (dict): Trade statistics dictionary containing risk metrics.
    - risk_calculation_method (str): Method used for risk calculation in simulation.
        If 'max_theoretical' or 'fixed_theoretical_max', uses max_theoretical_loss.
        Otherwise, uses conservative_theoretical_max_loss (p95, default safe behavior).
    
    Returns:
    - float: The maximum theoretical loss per spread in dollars for position sizing.
    
    Raises:
    - ValueError: If required risk data is missing or invalid.
    """
    # If using max_theoretical for loss simulation, must also use it for position sizing
    if risk_calculation_method in ['max_theoretical', 'fixed_theoretical_max']:
        max_theoretical_loss = trade.get('max_theoretical_loss', 0)
        if max_theoretical_loss and max_theoretical_loss > 0:
            return float(max_theoretical_loss)
        raise ValueError(
            "Maximum theoretical loss data is missing or invalid. "
            "Required field: 'max_theoretical_loss'. "
            "This is needed for position sizing when using max_theoretical risk method."
        )
    
    # Default: Use conservative theoretical max (p95) for safety
    conservative_theoretical_loss = trade.get('conservative_theoretical_max_loss', 0)
    if conservative_theoretical_loss and conservative_theoretical_loss > 0:
        return float(conservative_theoretical_loss)
    raise ValueError(
        "Conservative theoretical loss data is missing or invalid. "
        "Required field: 'conservative_theoretical_max_loss'. "
        "This is needed for position sizing to ensure broker margin requirements are met."
    )


def get_max_risk_per_spread(trade, risk_calculation_method='conservative_theoretical'):
    """
    Determine the risk per spread for LOSS SIMULATION purposes.
    
    This function calculates the amount that will be lost when a trade loses,
    based on the specified risk calculation method. This is separate from
    position sizing constraints (which always use conservative theoretical max).
    
    Parameters:
    - trade (dict): Trade statistics dictionary containing risk metrics.
    - risk_calculation_method (str): Method for calculating loss amounts:
        - 'conservative_theoretical': 95th percentile of theoretical losses (variable losses up to this cap)
        - 'max_theoretical': Maximum theoretical loss (variable losses up to this cap)
        - 'median_realized': Median of realized losses (fixed loss amount)
        - 'average_realized': Average of realized losses (fixed loss amount)
        - 'average_realized_trimmed': Average of realized losses excluding top 5% (fixed loss amount)
        - 'fixed_conservative_theoretical_max': Conservative theoretical max as fixed loss amount
        - 'fixed_theoretical_max': Theoretical max as fixed loss amount
    
    Returns:
    - float: The risk amount per spread in dollars for simulation purposes.
    """
    if risk_calculation_method == 'conservative_theoretical':
        conservative_theoretical_loss = trade.get('conservative_theoretical_max_loss', 0)
        if conservative_theoretical_loss and conservative_theoretical_loss > 0:
            return float(conservative_theoretical_loss)
        raise ValueError("Conservative theoretical loss data is missing or invalid. Required field: 'conservative_theoretical_max_loss'")
    
    if risk_calculation_method == 'max_theoretical':
        max_theoretical_loss = trade.get('max_theoretical_loss', 0)
        if max_theoretical_loss and max_theoretical_loss > 0:
            return float(max_theoretical_loss)
        raise ValueError("Maximum theoretical loss data is missing or invalid. Required field: 'max_theoretical_loss'")
    
    if risk_calculation_method == 'median_realized':
        median_risk = trade.get('median_risk_per_spread', 0)
        if median_risk and median_risk > 0:
            return float(median_risk)
        raise ValueError("Median realized loss data is missing or invalid. Required field: 'median_risk_per_spread'")
    
    if risk_calculation_method == 'average_realized':
        avg_loss = abs(trade.get('avg_loss', 0))
        if avg_loss > 0:
            return float(avg_loss)
        raise ValueError("Average realized loss data is missing or invalid. Required field: 'avg_loss'")
    
    if risk_calculation_method == 'average_realized_trimmed':
        pnl_distribution = trade.get('pnl_distribution', [])
        if not pnl_distribution:
            raise ValueError("PNL distribution data is missing. Required field: 'pnl_distribution'")
        losses = [abs(pnl) for pnl in pnl_distribution if pnl < 0]
        if not losses:
            raise ValueError("No loss trades found in PNL distribution for trimmed average calculation")
        # Remove top 5% of losses as outliers
        losses_sorted = sorted(losses)
        trim_count = max(1, int(len(losses) * 0.05))
        trimmed_losses = losses_sorted[:-trim_count] if trim_count < len(losses) else losses_sorted
        return float(np.mean(trimmed_losses))

    if risk_calculation_method == 'fixed_conservative_theoretical_max':
        return get_max_risk_per_spread(trade, 'conservative_theoretical')

    if risk_calculation_method == 'fixed_theoretical_max':
        return get_max_risk_per_spread(trade, 'max_theoretical')
    
    raise ValueError(f"Unknown risk calculation method: '{risk_calculation_method}'")


def get_reward_cap_per_spread(trade, reward_calculation_method='no_cap'):
    """
    Determine the reward cap per spread for profit-taking purposes.
    
    This function calculates the maximum reward amount that will be taken when
    a trade wins, based on the specified reward calculation method. The cap is
    applied as: actual_reward = min(generated_reward, cap).
    
    This allows testing how early profit-taking affects Monte Carlo simulations.
    For example, capping at 50% of theoretical max simulates taking profits at
    50% of the maximum possible gain, reducing upside but potentially improving
    risk-adjusted returns.
    
    Parameters:
    - trade (dict): Trade statistics dictionary containing reward metrics.
    - reward_calculation_method (str): Method for calculating reward caps:
        - 'no_cap': No capping (default - returns None)
        - 'cap_XXpct_conservative_theoretical_max': XX% of conservative theoretical max reward (p95 of theoretical gains)
        - 'cap_XXpct_theoretical_max': XX% of theoretical max reward
        - 'cap_XXpct_average_realized': XX% of average realized wins
        - 'cap_XXpct_conservative_realized_max': XX% of conservative realized max reward (p95 of historical wins)
        Where XX can be: 25, 40, 50, 75
    
    Returns:
    - float or None: The reward cap per spread in dollars, or None if no capping.
    
    Raises:
    - ValueError: If required reward data is missing or if method is unknown.
    """
    if reward_calculation_method == 'no_cap':
        return None
    
    # Parse method string: cap_XXpct_METRIC
    if not reward_calculation_method.startswith('cap_'):
        raise ValueError(f"Unknown reward calculation method: '{reward_calculation_method}'")
    
    parts = reward_calculation_method.split('_')
    if len(parts) < 3:
        raise ValueError(f"Unknown reward calculation method: '{reward_calculation_method}'")
    
    # Extract percentage (e.g., "25pct" -> 25)
    pct_str = parts[1]
    if not pct_str.endswith('pct'):
        raise ValueError(f"Unknown reward calculation method: '{reward_calculation_method}'")
    
    try:
        percentage = float(pct_str[:-3]) / 100  # Convert "25pct" to 0.25
    except ValueError:
        raise ValueError(f"Unknown reward calculation method: '{reward_calculation_method}'")
    
    # Reconstruct metric name from remaining parts
    metric = '_'.join(parts[2:])
    
    # Get base value based on metric
    if metric == 'conservative_theoretical_max':
        base_value = trade.get('conservative_theoretical_max_reward', 0)
        if not base_value or base_value <= 0:
            raise ValueError(
                "Conservative theoretical max reward data is missing or invalid. "
                "Required field: 'conservative_theoretical_max_reward'. "
                "This is calculated as the 95th percentile of theoretical gains from opening structure."
            )
        return float(base_value * percentage)
    
    if metric == 'theoretical_max':
        base_value = trade.get('max_theoretical_gain', 0)
        if not base_value or base_value <= 0:
            raise ValueError(
                "Theoretical max gain data is missing or invalid. "
                "Required field: 'max_theoretical_gain'. "
                "This is calculated from the opening spread structure."
            )
        return float(base_value * percentage)
    
    if metric == 'average_realized':
        base_value = trade.get('avg_win', 0)
        if not base_value or base_value <= 0:
            raise ValueError(
                "Average win data is missing or invalid. "
                "Required field: 'avg_win'. "
                "This is the mean of historical winning trades."
            )
        return float(base_value * percentage)
    
    if metric == 'conservative_realized_max':
        base_value = trade.get('conservative_realized_max_reward', 0)
        if not base_value or base_value <= 0:
            raise ValueError(
                "Conservative realized max reward data is missing or invalid. "
                "Required field: 'conservative_realized_max_reward'. "
                "This is calculated as the 95th percentile of historical winning trades."
            )
        return float(base_value * percentage)
    
    raise ValueError(f"Unknown reward calculation method: '{reward_calculation_method}'")


def choose_contract_count_for_risk_pct(max_risk_per_spread, account_balance, target_risk_pct):
    """
    Select the optimal contract count that achieves the target account risk percentage.
    
    This function calculates the number of contracts needed to expose the account to a
    specific percentage of its balance as risk, based on the maximum risk per spread.
    It chooses the contract count whose actual risk percentage is closest to the target.
    
    Parameters:
    - max_risk_per_spread (float): Maximum potential loss per spread in dollars.
    - account_balance (float): Current account balance in dollars.
    - target_risk_pct (float): Target risk as a percentage of account balance (0-100).
    
    Returns:
    - int: Number of contracts to trade. Minimum of 1.
    
    Raises:
    - ValueError: If max_risk_per_spread or account_balance are not positive.
    
    Note:
    - Rounds to the nearest contract count that minimizes the difference between
      actual and target risk percentages.
    """
    if max_risk_per_spread <= 0:
        raise ValueError('max_risk_per_spread must be positive.')
    if account_balance <= 0:
        raise ValueError('account_balance must be positive.')

    target_risk_dollars = account_balance * (target_risk_pct / 100)
    if target_risk_dollars <= 0:
        return 1

    lower = max(1, int(np.floor(target_risk_dollars / max_risk_per_spread)))
    upper = max(1, int(np.ceil(target_risk_dollars / max_risk_per_spread)))

    lower_diff = abs((lower * max_risk_per_spread) - target_risk_dollars)
    upper_diff = abs((upper * max_risk_per_spread) - target_risk_dollars)
    return lower if lower_diff <= upper_diff else upper


def should_allow_trade_with_target_risk(
    risk_per_spread,
    account_balance,
    target_risk_pct=None,
    allow_exceed_target_risk=False,
    position_sizing='percent'
):
    """
    Determine if a trade should be allowed based on target risk % constraints.
    
    This function enforces strict target risk limits when allow_exceed_target_risk=False.
    In that mode, no trade is taken if even 1 contract would exceed the target risk %.
    This prevents forced trades that violate risk management rules.
    
    Parameters:
    - risk_per_spread (float): Risk amount per spread/contract in dollars.
    - account_balance (float): Current account balance in dollars.
    - target_risk_pct (float, optional): Target risk as a percentage of account balance (0-100).
        Only applies when position_sizing='percent'.
    - allow_exceed_target_risk (bool): If True, allows taking 1 contract even if it exceeds
        target risk %. If False (default), enforces strict target risk limits.
    - position_sizing (str): 'percent' for risk-based sizing or 'contracts' for fixed sizing.
        Target risk enforcement only applies to 'percent' mode.
    
    Returns:
    - bool: True if trade should be allowed, False if it violates target risk constraints.
    
    Notes:
    - Target risk enforcement only applies when position_sizing='percent' and target_risk_pct is set
    - For 'contracts' mode, always returns True (no target risk to enforce)
    - When allow_exceed_target_risk=True, always returns True (old behavior)
    - When allow_exceed_target_risk=False (default), enforces strict target risk limits
    """
    # Target risk enforcement only applies to percent-based sizing
    if position_sizing != 'percent' or target_risk_pct is None:
        return True
    
    # If exceeding is allowed, always proceed (old behavior)
    if allow_exceed_target_risk:
        return True
    
    # Calculate risk % for 1 contract
    if account_balance <= 0:
        return False
    
    one_contract_risk_pct = (risk_per_spread / account_balance) * 100
    
    # Allow trade only if 1 contract doesn't exceed target risk %
    return one_contract_risk_pct <= target_risk_pct


def cap_contracts_to_target_risk(
    contracts,
    risk_per_spread,
    account_balance,
    target_risk_pct,
    allow_exceed_target_risk=False,
    position_sizing='percent'
):
    """
    Cap number of contracts so total risk doesn't exceed target risk %.
    
    This function ensures that when strict target risk enforcement is enabled,
    the total risk from all contracts never exceeds the target risk percentage.
    This enforces a hard risk ceiling on position sizing.
    
    Parameters:
    - contracts (int): Desired number of contracts.
    - risk_per_spread (float): Risk amount per spread/contract in dollars.
    - account_balance (float): Current account balance in dollars.
    - target_risk_pct (float): Target risk as a percentage of account balance (0-100).
    - allow_exceed_target_risk (bool): If False (default), enforces strict ceiling.
        If True, returns contracts unchanged (old behavior).
    - position_sizing (str): 'percent' for risk-based sizing or 'contracts' for fixed sizing.
        Target risk enforcement only applies to 'percent' mode.
    
    Returns:
    - int: Capped number of contracts (0 or more) that respects target risk ceiling.
    
    Notes:
    - Returns 0 if no contracts can be taken without exceeding target risk %
    - Target risk enforcement only applies when position_sizing='percent'
    - When allow_exceed_target_risk=True, returns original contracts unchanged
    """
    # Target risk enforcement only applies to percent-based sizing
    if position_sizing != 'percent' or target_risk_pct is None:
        return contracts
    
    # If exceeding is allowed, return unchanged (old behavior)
    if allow_exceed_target_risk:
        return contracts
    
    # Calculate how many contracts we can take without exceeding target risk %
    target_risk_dollars = account_balance * (target_risk_pct / 100)
    max_contracts_for_target = int(target_risk_dollars / risk_per_spread)
    
    return min(contracts, max_contracts_for_target)


def build_position_size_plan(
    trade,
    initial_balance,
    position_sizing,
    risk_calculation_method='conservative_theoretical',
    allow_exceed_target_risk=False
):
    """
    Generate a plan of position sizes for Monte Carlo simulation testing.
    
    Creates a list of position sizes (contract counts) with their corresponding
    target and actual risk percentages. Supports both fixed contract sizing
    and percentage-based risk sizing.
    
    CRITICAL: Position sizing uses the same risk_calculation_method as loss simulation
    to ensure the constraint `max_risk * contracts <= balance` is always maintained.
    If the user chooses max_theoretical, position sizing will also use max_theoretical
    to prevent trades that would exceed account balance on max loss.
    
    When allow_exceed_target_risk=False (default), enforces strict target risk ceiling:
    the starting_risk_pct will never exceed target_risk_pct.
    
    Parameters:
    - trade (dict): Trade statistics dictionary containing risk metrics.
    - initial_balance (float): Starting account balance in dollars.
    - position_sizing (str): Sizing method - 'contracts' for fixed sizes or 'percent' for risk-based.
    - risk_calculation_method (str): Method used to determine risk per spread for BOTH
        position sizing constraints and loss simulation. If 'max_theoretical' or
        'fixed_theoretical_max', uses max_theoretical_loss. Otherwise uses
        conservative_theoretical_max_loss (p95, default safe behavior).
    - allow_exceed_target_risk (bool): If False (default), enforces strict target risk ceiling.
        Starting risk % will never exceed target risk %. If True, allows the old behavior
        where starting risk % can exceed target risk % due to rounding.
    
    Returns:
    - list[dict]: List of position size configurations, each containing:
        - 'contracts' (int): Number of contracts to trade (capped to affordability by position_sizing_risk)
        - 'target_risk_pct' (float): Target risk percentage (for percent sizing)
        - 'starting_risk_pct' (float): Risk % at start based on simulation risk method (actual expected loss per trade)
        - 'max_risk_pct' (float): Maximum possible risk % based on position sizing risk method (caps to ensure safety)
    
    For 'contracts' sizing, uses predefined contract counts: [1, 2, 5, 10, 15, 20]
    For 'percent' sizing, uses predefined risk percentages: [1, 2, 3, 5, 10, 15, 25, 50, 75, 100]%
    """
    # Position sizing constraint uses risk_calculation_method to ensure consistency
    # If user chooses max_theoretical, position sizing must also use max_theoretical
    position_sizing_risk = get_position_sizing_risk_per_spread(trade, risk_calculation_method)
    
    # Loss simulation uses the selected risk calculation method
    simulation_risk = get_max_risk_per_spread(trade, risk_calculation_method)

    if position_sizing == 'contracts':
        max_affordable = int(initial_balance / position_sizing_risk)
        if max_affordable == 0:
            # Can't afford any contracts at all - return empty plan
            return []
        
        return [
            {
                'contracts': contracts,
                'target_risk_pct': (position_sizing_risk * contracts / initial_balance) * 100,
                'starting_risk_pct': (simulation_risk * min(contracts, max_affordable) / initial_balance) * 100,
                'max_risk_pct': (position_sizing_risk * min(contracts, max_affordable) / initial_balance) * 100
            }
            for contracts in DEFAULT_POSITION_SIZES
            if contracts > 0
        ]

    sizing_plan = []
    for target_risk_pct in DEFAULT_RISK_PCTS:
        contracts = choose_contract_count_for_risk_pct(
            max_risk_per_spread=simulation_risk,
            account_balance=initial_balance,
            target_risk_pct=target_risk_pct
        )
        # Apply position sizing constraint (broker margin requirement)
        max_affordable_contracts = int(initial_balance / position_sizing_risk)
        if max_affordable_contracts == 0:
            # Can't afford to trade - skip this risk level
            continue
        capped_contracts = min(contracts, max_affordable_contracts)
        
        # CRITICAL: When strict target risk enforcement is enabled,
        # cap contracts so starting risk never exceeds target risk %
        capped_contracts = cap_contracts_to_target_risk(
            contracts=capped_contracts,
            risk_per_spread=position_sizing_risk,
            account_balance=initial_balance,
            target_risk_pct=target_risk_pct,
            allow_exceed_target_risk=allow_exceed_target_risk,
            position_sizing=position_sizing
        )
        
        if capped_contracts == 0:
            # Cannot take any contracts without exceeding target risk - skip this risk level
            continue
        
        starting_risk_pct = (simulation_risk * capped_contracts / initial_balance) * 100
        max_risk_pct = (position_sizing_risk * capped_contracts / initial_balance) * 100
        sizing_plan.append(
            {
                'contracts': capped_contracts,
                'target_risk_pct': float(target_risk_pct),
                'starting_risk_pct': float(starting_risk_pct),
                'max_risk_pct': float(max_risk_pct)
            }
        )

    return sizing_plan


def sample_pnl_moving_blocks(pnl_distribution, num_trades, block_size):
    """
    Sample realized trade P/L values using moving blocks bootstrap to preserve streak structure.
    
    This method maintains the temporal dependencies and streak patterns from historical
    trade data by sampling contiguous blocks of trades rather than individual trades.
    This is more realistic for strategies where trade outcomes are not independent.
    
    Parameters:
    - pnl_distribution (list[float]): Historical P/L values for each trade.
    - num_trades (int): Number of trades to sample for the simulation.
    - block_size (int): Size of contiguous blocks to sample from historical data.
    
    Returns:
    - list[float]: Sampled P/L values maintaining historical streak patterns.
    
    Raises:
    - ValueError: If block_size is not positive or pnl_distribution is empty.
    
    Notes:
    - If pnl_distribution has only one value, returns that value repeated num_trades times.
    - Block size is automatically capped at the length of pnl_distribution.
    - Uses random block starting positions to create diverse but realistic sequences.
    """
    if num_trades <= 0:
        return []

    if block_size <= 0:
        raise ValueError('block_size must be positive.')

    if not pnl_distribution:
        raise ValueError('pnl_distribution must contain at least one value for moving-block bootstrap.')

    pnl_values = [float(value) for value in pnl_distribution]
    n = len(pnl_values)
    if n == 1:
        return [pnl_values[0]] * num_trades

    effective_block_size = min(block_size, n)
    max_start = n - effective_block_size

    sampled = []
    while len(sampled) < num_trades:
        start_idx = int(np.random.randint(0, max_start + 1))
        sampled.extend(pnl_values[start_idx:start_idx + effective_block_size])

    return sampled[:num_trades]


def generate_risk(avg_risk, max_risk):
    """
    Generate a variable risk amount for a losing trade using a truncated normal distribution.
    
    This function simulates realistic variability in loss amounts rather than using
    fixed average losses. It uses a normal distribution centered on the average risk
    but capped at the maximum risk to prevent unrealistic losses.
    
    Parameters:
    - avg_risk (float): Average risk amount per spread in dollars.
    - max_risk (float): Maximum possible risk amount per spread in dollars.
    
    Returns:
    - float: Simulated risk amount for this specific trade, between 0 and max_risk.
    
    Raises:
    - ValueError: If avg_risk or max_risk are not positive.
    
    Distribution Details:
    - Uses normal distribution with mean = avg_risk, std_dev = avg_risk/2
    - Truncated to [0, max_risk] range to ensure realistic bounds
    - Allows for natural variability while maintaining the target average risk
    """
    if max_risk <= 0 or avg_risk <= 0:
        raise ValueError(
            f"Invalid risk parameters: avg_risk={avg_risk}, max_risk={max_risk}. "
            "This indicates corrupted trade data or calculation errors. "
            "Average and maximum risk amounts must be positive values."
        )
    
    # Use truncated normal distribution with mean = avg_risk, std = avg_risk/2
    # This allows for realistic variability while keeping the average at target
    std_dev = avg_risk / 2
    
    # Generate normal sample and truncate
    sample = np.random.normal(avg_risk, std_dev)
    
    # Truncate to [0, max_risk] range
    truncated_sample = np.clip(sample, 0, max_risk)
    
    return truncated_sample


def generate_reward(avg_reward, max_reward):
    """
    Generate a variable reward amount for a winning trade using a beta distribution.
    
    This function simulates realistic variability in win amounts, favoring smaller
    wins but allowing occasional larger wins. It uses a beta distribution skewed
    toward smaller values to reflect typical market behavior.
    
    Parameters:
    - avg_reward (float): Average reward amount per spread in dollars.
    - max_reward (float): Maximum possible reward amount per spread in dollars.
    
    Returns:
    - float: Simulated reward amount for this specific trade, between 0 and max_reward.
    
    Raises:
    - ValueError: If avg_reward or max_reward are not positive.
    
    Distribution Details:
    - Uses beta distribution (alpha=1.5, beta=3) skewed toward smaller wins
    - Scales the beta sample and blends with avg_reward to maintain target mean
    - Weighted average: 70% scaled beta sample + 30% avg_reward
    - Ensures the result doesn't exceed max_reward
    """
    if max_reward <= 0 or avg_reward <= 0:
        raise ValueError(
            f"Invalid reward parameters: avg_reward={avg_reward}, max_reward={max_reward}. "
            "This indicates corrupted trade data or calculation errors. "
            "Average and maximum reward amounts must be positive values."
        )
    
    # Use beta distribution for rewards - allows full range but favors smaller wins
    # Alpha=1.5, Beta=3 creates a distribution skewed toward smaller values
    alpha, beta_param = 1.5, 3
    
    # Generate beta random variable and scale to our range
    beta_sample = np.random.beta(alpha, beta_param)
    
    # Scale to range from 0 to max_reward, but bias toward avg_reward
    # Use a weighted average to keep mean around avg_reward
    scaled_reward = 0.7 * (beta_sample * max_reward) + 0.3 * avg_reward
    
    # Ensure we don't exceed max_reward
    return min(scaled_reward, max_reward)


def simulate_trades(
    trade,
    position_size,
    initial_balance,
    num_trades,
    num_simulations,
    target_risk_pct=None,
    dynamic_risk_sizing=True,
    simulation_mode='iid',
    block_size=5,
    risk_calculation_method='conservative_theoretical',
    reward_calculation_method='no_cap',
    allow_exceed_target_risk=False,
    position_sizing='percent'
):
    """
    Run a single Monte Carlo simulation path for a given position size.
    
    Simulates a series of trades using either independent identically distributed (IID)
    outcomes or moving-block bootstrap sampling to preserve historical streak patterns.
    Tracks account balance, drawdown, and losing streaks across the simulation.
    
    CRITICAL: Position sizing is capped to ensure `position_sizing_risk * contracts <= balance`
    at all times, where position_sizing_risk uses the same risk_calculation_method as
    loss simulation. This prevents trades that would exceed account balance on max loss.
    
    Parameters:
    - trade (dict): Trade statistics dictionary containing win rates, avg losses, etc.
    - position_size (int): Number of contracts per trade (will be capped to affordability).
    - initial_balance (float): Starting account balance in dollars.
    - num_trades (int): Number of trades to simulate in this path.
    - num_simulations (int): Total number of simulation paths (for context, not used here).
    - target_risk_pct (float, optional): Target risk percentage for dynamic sizing.
    - dynamic_risk_sizing (bool): Whether to adjust position size based on current balance.
    - simulation_mode (str): 'iid' for independent trades or 'moving-block-bootstrap' for streak preservation.
    - block_size (int): Block size for bootstrap sampling (only used in bootstrap mode).
    - risk_calculation_method (str): Method for calculating risk amount per trade AND
        position sizing constraints. Both use the same method to maintain safety invariant.
    - reward_calculation_method (str): Method for calculating reward caps. Options:
        - 'no_cap': No capping (default)
        - 'cap_XXpct_METRIC': Cap at XX% of METRIC (e.g., 'cap_50pct_conservative_theoretical_max')
        Note: Reward capping only applies to IID mode, not bootstrap mode (historical P/L used as-is).
    - allow_exceed_target_risk (bool): If False (default), stops trading if 1 contract would exceed
        target risk %. If True, allows taking 1 contract even if it exceeds target (old behavior).
    - position_sizing (str): 'percent' for risk-based sizing or 'contracts' for fixed sizing.
    
    Returns:
    - list[dict]: Simulation results for each path, each containing:
        - 'final_balance' (float): Account balance after all trades
        - 'max_drawdown' (float): Maximum drawdown experienced
        - 'max_losing_streak' (int): Longest losing streak in the path
    
    Notes:
    - In bootstrap mode, uses historical P/L distribution to sample realistic sequences
    - In IID mode, generates variable risk/reward amounts using statistical distributions
    - Dynamic sizing recalculates contract count each trade based on current balance
    - Simulation stops if balance reaches zero (bankruptcy)
    - When allow_exceed_target_risk=False, simulation stops if next trade would exceed target risk %
    """
    avg_risk_per_spread = abs(trade['avg_loss'])
    # Position sizing uses risk_calculation_method to ensure consistency
    # If user chooses max_theoretical, position sizing must also use max_theoretical
    position_sizing_risk = get_position_sizing_risk_per_spread(trade, risk_calculation_method)
    # Loss simulation uses selected risk calculation method
    max_risk_per_spread = get_max_risk_per_spread(trade, risk_calculation_method)
    avg_reward_per_spread = trade['avg_win']
    conservative_realized_max_reward = trade.get('conservative_realized_max_reward', 0)
    max_reward_per_spread = conservative_realized_max_reward if conservative_realized_max_reward > 0 else trade['max_win']
    win_rate = trade['win_rate']
    
    # Get reward cap per spread (None if no_cap)
    reward_cap_per_spread = get_reward_cap_per_spread(trade, reward_calculation_method)
    
    results = []
    for _ in range(num_simulations):
        sampled_trade_pnl = None
        if simulation_mode == 'moving-block-bootstrap':
            pnl_distribution = trade.get('pnl_distribution', [])
            if pnl_distribution:
                sampled_trade_pnl = sample_pnl_moving_blocks(
                    pnl_distribution=pnl_distribution,
                    num_trades=num_trades,
                    block_size=block_size
                )

        balance = initial_balance
        peak = initial_balance
        max_drawdown = 0
        current_losing_streak = 0
        max_losing_streak = 0
        for trade_idx in range(num_trades):
            contracts = position_size
            if dynamic_risk_sizing and target_risk_pct is not None:
                contracts = choose_contract_count_for_risk_pct(
                    max_risk_per_spread=max_risk_per_spread,
                    account_balance=max(balance, 1),
                    target_risk_pct=target_risk_pct
                )
            
            # CRITICAL: Cap contracts to ensure theoretical max loss never exceeds balance
            # This simulates broker margin requirements: cannot open a position whose
            # theoretical max loss would make the account balance negative.
            # Position sizing is based on conservative theoretical max, NOT risk_calculation_method.
            if balance <= 0:
                # Account is broke, stop simulation
                balance = 0
                break
            
            # Check if trade would violate target risk % constraint
            if not should_allow_trade_with_target_risk(
                risk_per_spread=position_sizing_risk,
                account_balance=balance,
                target_risk_pct=target_risk_pct,
                allow_exceed_target_risk=allow_exceed_target_risk,
                position_sizing=position_sizing
            ):
                # Stop trading - would exceed target risk %
                break
            
            max_affordable_contracts = int(balance / position_sizing_risk)
            if max_affordable_contracts == 0:
                # Not enough balance to afford even 1 contract
                # (balance < position_sizing_risk)
                # This should be caught by should_allow_trade_with_target_risk above,
                # but keep as safety check
                balance = 0
                break
            contracts = min(contracts, max_affordable_contracts)
            
            # CRITICAL: When strict target risk enforcement is enabled,
            # cap contracts so total risk never exceeds target risk %
            contracts = cap_contracts_to_target_risk(
                contracts=contracts,
                risk_per_spread=position_sizing_risk,
                account_balance=balance,
                target_risk_pct=target_risk_pct,
                allow_exceed_target_risk=allow_exceed_target_risk,
                position_sizing=position_sizing
            )
            
            if contracts == 0:
                # Cannot take any contracts without exceeding target risk - stop trading
                break

            max_risk = max_risk_per_spread * contracts
            avg_risk = min(avg_risk_per_spread * contracts, max_risk)
            avg_reward = avg_reward_per_spread * contracts
            max_reward = max_reward_per_spread * contracts

            if sampled_trade_pnl is not None:
                realized_pnl = sampled_trade_pnl[trade_idx] * contracts
                balance += realized_pnl
                if realized_pnl >= 0:
                    current_losing_streak = 0
                else:
                    current_losing_streak += 1
                    max_losing_streak = max(max_losing_streak, current_losing_streak)
            else:
                # Generate variable risk and reward for this specific trade
                fixed_risk_methods = {
                    'median_realized',
                    'average_realized',
                    'average_realized_trimmed',
                    'fixed_conservative_theoretical_max',
                    'fixed_theoretical_max'
                }
                if risk_calculation_method in fixed_risk_methods:
                    risk = max_risk
                else:
                    risk = generate_risk(avg_risk, max_risk)
                reward = generate_reward(avg_reward, max_reward)
                
                # Apply reward cap if set (only in IID mode, not bootstrap)
                if reward_cap_per_spread is not None:
                    reward_cap = reward_cap_per_spread * contracts
                    reward = min(reward, reward_cap)

                if random.random() < win_rate:
                    balance += reward
                    current_losing_streak = 0  # Reset streak on win
                else:
                    balance -= risk
                    current_losing_streak += 1
                    max_losing_streak = max(max_losing_streak, current_losing_streak)

            peak = max(peak, balance)
            max_drawdown = max(max_drawdown, peak - balance)
            if balance <= 0:
                balance = 0  # Set to 0 to indicate bankruptcy
                break

        results.append({'final_balance': balance, 'max_drawdown': max_drawdown, 'max_losing_streak': max_losing_streak})
    return results


def run_monte_carlo_simulation(
    trade_stats,
    initial_balance,
    num_simulations,
    position_sizing='percent',
    dynamic_risk_sizing=True,
    simulation_mode='iid',
    block_size=5,
    commission_per_contract=OPTION_COMMISSION_PER_CONTRACT,
    num_trades=60,
    risk_calculation_method='conservative_theoretical',
    reward_calculation_method='no_cap',
    allow_exceed_target_risk=False
):
    """
    Execute a complete Monte Carlo simulation for trade position sizing analysis.
    
    Runs multiple simulation paths for various position sizes to determine optimal
    contract counts that balance risk and reward. Supports both fixed contract
    sizing and percentage-based risk sizing with dynamic position adjustment.
    
    Parameters:
    - trade_stats (dict): Trade statistics from parse_trade_csv containing win rates, P/L distribution, etc.
    - initial_balance (float): Starting account balance in dollars.
    - num_simulations (int): Number of Monte Carlo simulation paths to run.
    - position_sizing (str): 'percent' for risk-based sizing or 'contracts' for fixed sizing.
    - dynamic_risk_sizing (bool): Whether to adjust position size based on current balance during simulation.
    - simulation_mode (str): 'iid' for independent trades or 'moving-block-bootstrap' for streak preservation.
    - block_size (int): Block size for bootstrap sampling (only used in bootstrap mode).
    - commission_per_contract (float): Commission cost per contract (currently unused in calculations).
    - num_trades (int): Number of trades per simulation. Must be at least the number of historical trades.
    - risk_calculation_method (str): Method for calculating risk amount per trade.
    - reward_calculation_method (str): Method for calculating reward caps. 'no_cap' for no capping (default).
    - allow_exceed_target_risk (bool): If False (default), stops trading if 1 contract would exceed
        target risk %. If True, allows taking 1 contract even if it exceeds target (old behavior).
    
    Returns:
    - list[dict]: List containing one trade report dictionary with:
        - 'trade_name' (str): Name of the trade strategy
        - 'summary' (dict): Original trade statistics
        - 'table_rows' (list[dict]): Position sizing results with metrics like:
            - Contracts, Target Risk %, Starting Risk %, Max Risk %, Avg Final $, Bankruptcy Prob, etc.
        - 'pnl_preview' (list[str]): Formatted preview of first 10 P/L values
        - 'historical_max_losing_streak' (int): Longest losing streak in historical data
    
    Notes:
    - For 'percent' sizing, tests risk levels: 1%, 2%, 3%, 5%, 10%, 15%, 25%, 50%, 75%, 100%
    - For 'contracts' sizing, tests fixed counts: 1, 2, 5, 10, 15, 20
    - Each position size is simulated num_simulations times with num_trades per simulation
    """
    num_trades = max(num_trades, trade_stats['num_trades'])
    
    # Create trade dict
    trade = {
        "name": "Simulated Trade",
        **trade_stats
    }
    
    position_size_plan = build_position_size_plan(
        trade=trade,
        initial_balance=initial_balance,
        position_sizing=position_sizing,
        risk_calculation_method=risk_calculation_method,
        allow_exceed_target_risk=allow_exceed_target_risk
    )
    
    # Validate that we can afford to trade
    if not position_size_plan:
        position_sizing_risk = get_position_sizing_risk_per_spread(trade, risk_calculation_method)
        raise ValueError(
            f"Initial balance (${initial_balance:,.2f}) is insufficient to trade even 1 contract. "
            f"Required: ${position_sizing_risk:,.2f} per contract (based on {risk_calculation_method} risk method for position sizing). "
            f"Please increase your initial balance or review your trade risk parameters."
        )

    data = []
    for row in position_size_plan:
        ps = row['contracts']
        if position_sizing == 'percent':
            sim_results = simulate_trades(
                trade,
                ps,
                initial_balance,
                num_trades,
                num_simulations,
                target_risk_pct=row['target_risk_pct'],
                dynamic_risk_sizing=dynamic_risk_sizing,
                simulation_mode=simulation_mode,
                block_size=block_size,
                risk_calculation_method=risk_calculation_method,
                reward_calculation_method=reward_calculation_method,
                allow_exceed_target_risk=allow_exceed_target_risk,
                position_sizing=position_sizing
            )
        else:
            sim_results = simulate_trades(
                trade,
                ps,
                initial_balance,
                num_trades,
                num_simulations,
                target_risk_pct=None,
                dynamic_risk_sizing=False,
                simulation_mode=simulation_mode,
                block_size=block_size,
                risk_calculation_method=risk_calculation_method,
                reward_calculation_method=reward_calculation_method,
                allow_exceed_target_risk=allow_exceed_target_risk,
                position_sizing=position_sizing
            )
        final_balances = [r['final_balance'] for r in sim_results]
        drawdowns = [r['max_drawdown'] for r in sim_results]
        losing_streaks = [r['max_losing_streak'] for r in sim_results]

        avg_final_balance = np.mean(final_balances)
        bankrupt_prob = sum(1 for b in final_balances if b == 0) / num_simulations
        avg_max_drawdown = np.mean(drawdowns)
        avg_max_losing_streak = np.mean(losing_streaks)
        max_drawdown = np.max(drawdowns)
        max_losing_streak = np.max(losing_streaks)

        data.append({
            'Contracts': ps,
            'Target Risk %': f"{row['target_risk_pct']:.2f}%",
            'Starting Risk %': f"{row['starting_risk_pct']:.2f}%",
            'Max Risk %': f"{row['max_risk_pct']:.2f}%",
            'Avg Final $': f"${avg_final_balance:,.0f}",
            'Bankruptcy Prob': f"{bankrupt_prob:.0%}",
            'Avg Max Drawdown': f"${avg_max_drawdown:,.0f}",
            'Max Drawdown': f"${max_drawdown:,.0f}",
            'Avg Max Losing Streak': f"{avg_max_losing_streak:.1f}",
            'Max Losing Streak': f"{max_losing_streak:.0f}"
        })

    historical_max_losing_streak = 0
    current_loss_streak = 0
    for value in trade['pnl_distribution']:
        if value < 0:
            current_loss_streak += 1
            historical_max_losing_streak = max(historical_max_losing_streak, current_loss_streak)
        else:
            current_loss_streak = 0

    trade_report = {
        'trade_name': trade['name'],
        'summary': trade,
        'table_rows': data,
        'pnl_preview': [f"{round(x):,}" for x in trade['pnl_distribution'][:10]],
        'historical_max_losing_streak': historical_max_losing_streak
    }
    
    return [trade_report]