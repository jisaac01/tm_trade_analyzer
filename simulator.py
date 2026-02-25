import numpy as np
import pandas as pd
import random
import os
from trade_parser import parse_trade_csv

OPTION_COMMISSION_PER_CONTRACT = 0.495

DEFAULT_POSITION_SIZES = [1, 2, 5, 10, 15, 20]
DEFAULT_RISK_PCTS = [1, 2, 3, 5, 10, 15, 25, 50, 75, 100]


def get_max_risk_per_spread(trade):
    """
    Determine the maximum risk per spread for position sizing calculations.
    
    This function prioritizes conservative theoretical loss estimates over realized losses
    to provide a more robust risk assessment for Monte Carlo simulations.
    
    Parameters:
    - trade (dict): Trade statistics dictionary containing risk metrics.
    
    Returns:
    - float: The maximum risk amount per spread in dollars.
    
    Priority order for risk determination:
    1. conservative_theoretical_max_loss (95th percentile of theoretical losses)
    2. max_theoretical_loss (maximum theoretical loss)
    3. abs(max_loss) (absolute value of maximum realized loss)
    """
    conservative_theoretical_loss = trade.get('conservative_theoretical_max_loss', 0)
    if conservative_theoretical_loss and conservative_theoretical_loss > 0:
        return float(conservative_theoretical_loss)

    max_theoretical_loss = trade.get('max_theoretical_loss', 0)
    if max_theoretical_loss and max_theoretical_loss > 0:
        return float(max_theoretical_loss)
    return float(abs(trade['max_loss']))


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


def build_position_size_plan(trade, initial_balance, position_sizing):
    """
    Generate a plan of position sizes for Monte Carlo simulation testing.
    
    Creates a list of position sizes (contract counts) with their corresponding
    target and actual risk percentages. Supports both fixed contract sizing
    and percentage-based risk sizing.
    
    Parameters:
    - trade (dict): Trade statistics dictionary containing risk metrics.
    - initial_balance (float): Starting account balance in dollars.
    - position_sizing (str): Sizing method - 'contracts' for fixed sizes or 'percent' for risk-based.
    
    Returns:
    - list[dict]: List of position size configurations, each containing:
        - 'contracts' (int): Number of contracts to trade
        - 'target_risk_pct' (float): Target risk percentage (for percent sizing)
        - 'actual_risk_pct' (float): Actual risk percentage based on max risk per spread
    
    For 'contracts' sizing, uses predefined contract counts: [1, 2, 5, 10, 15, 20]
    For 'percent' sizing, uses predefined risk percentages: [1, 2, 3, 5, 10, 15, 25, 50, 75, 100]%
    """
    max_risk_per_spread = get_max_risk_per_spread(trade)

    if position_sizing == 'contracts':
        return [
            {
                'contracts': contracts,
                'target_risk_pct': (max_risk_per_spread * contracts / initial_balance) * 100,
                'actual_risk_pct': (max_risk_per_spread * contracts / initial_balance) * 100
            }
            for contracts in DEFAULT_POSITION_SIZES
            if contracts > 0
        ]

    sizing_plan = []
    for target_risk_pct in DEFAULT_RISK_PCTS:
        contracts = choose_contract_count_for_risk_pct(
            max_risk_per_spread=max_risk_per_spread,
            account_balance=initial_balance,
            target_risk_pct=target_risk_pct
        )
        actual_risk_pct = (max_risk_per_spread * contracts / initial_balance) * 100
        sizing_plan.append(
            {
                'contracts': contracts,
                'target_risk_pct': float(target_risk_pct),
                'actual_risk_pct': float(actual_risk_pct)
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
    block_size=5
):
    """
    Run a single Monte Carlo simulation path for a given position size.
    
    Simulates a series of trades using either independent identically distributed (IID)
    outcomes or moving-block bootstrap sampling to preserve historical streak patterns.
    Tracks account balance, drawdown, and losing streaks across the simulation.
    
    Parameters:
    - trade (dict): Trade statistics dictionary containing win rates, avg losses, etc.
    - position_size (int): Number of contracts per trade.
    - initial_balance (float): Starting account balance in dollars.
    - num_trades (int): Number of trades to simulate in this path.
    - num_simulations (int): Total number of simulation paths (for context, not used here).
    - target_risk_pct (float, optional): Target risk percentage for dynamic sizing.
    - dynamic_risk_sizing (bool): Whether to adjust position size based on current balance.
    - simulation_mode (str): 'iid' for independent trades or 'moving-block-bootstrap' for streak preservation.
    - block_size (int): Block size for bootstrap sampling (only used in bootstrap mode).
    
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
    """
    avg_risk_per_spread = abs(trade['avg_loss'])
    max_risk_per_spread = get_max_risk_per_spread(trade)
    avg_reward_per_spread = trade['avg_win']
    conservative_realized_max_reward = trade.get('conservative_realized_max_reward', 0)
    max_reward_per_spread = conservative_realized_max_reward if conservative_realized_max_reward > 0 else trade['max_win']
    win_rate = trade['win_rate']
    
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
                risk = generate_risk(avg_risk, max_risk)
                reward = generate_reward(avg_reward, max_reward)

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
    commission_per_contract=OPTION_COMMISSION_PER_CONTRACT
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
    
    Returns:
    - list[dict]: List containing one trade report dictionary with:
        - 'trade_name' (str): Name of the trade strategy
        - 'summary' (dict): Original trade statistics
        - 'table_rows' (list[dict]): Position sizing results with metrics like:
            - Contracts, Target Risk %, Actual Risk %, Avg Final $, Bankruptcy Prob, etc.
        - 'pnl_preview' (list[str]): Formatted preview of first 10 P/L values
        - 'historical_max_losing_streak' (int): Longest losing streak in historical data
    
    Notes:
    - For 'percent' sizing, tests risk levels: 1%, 2%, 3%, 5%, 10%, 15%, 25%, 50%, 75%, 100%
    - For 'contracts' sizing, tests fixed counts: 1, 2, 5, 10, 15, 20
    - Each position size is simulated num_simulations times with num_trades per simulation
    - Minimum num_trades is 55 or actual historical trade count, whichever is larger
    """
    num_trades = max(55, trade_stats['num_trades'])
    
    # Create trade dict
    trade = {
        "name": "Simulated Trade",
        **trade_stats
    }
    
    position_size_plan = build_position_size_plan(
        trade=trade,
        initial_balance=initial_balance,
        position_sizing=position_sizing
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
                block_size=block_size
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
                block_size=block_size
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
            'Actual Risk %': f"{row['actual_risk_pct']:.2f}%",
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