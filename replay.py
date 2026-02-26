"""
Historical trade replay module.

This module provides functionality to replay actual historical trades with
specified position sizing rules, showing what would have happened with the
selected settings. Unlike Monte Carlo simulation, this uses actual P/L values
in their original order without sampling or randomization.
"""

from simulator import (
    get_position_sizing_risk_per_spread,
    get_max_risk_per_spread,
    choose_contract_count_for_risk_pct
)


def replay_actual_trades(
    trade_stats,
    initial_balance,
    position_sizing='percent',
    position_size=None,
    target_risk_pct=None,
    dynamic_risk_sizing=True,
    risk_calculation_method='conservative_theoretical'
):
    """
    Replay historical trades with specified position sizing rules.
    
    This function applies position sizing rules to the actual historical trade sequence
    (in order) to show what would have happened with the selected settings. Unlike Monte
    Carlo simulation, this uses the actual P/L values in their original order without
    sampling or randomization.
    
    CRITICAL: Position sizing is capped to ensure `position_sizing_risk * contracts <= balance`
    at all times, using the same risk_calculation_method as the Monte Carlo simulator.
    
    Parameters:
    - trade_stats (dict): Trade statistics from parse_trade_csv containing win rates, P/L distribution, etc.
    - initial_balance (float): Starting account balance in dollars.
    - position_sizing (str): 'percent' for risk-based sizing or 'contracts' for fixed sizing.
    - position_size (int, optional): Fixed number of contracts (used when position_sizing='contracts').
    - target_risk_pct (float, optional): Target risk percentage (used when position_sizing='percent').
    - dynamic_risk_sizing (bool): Whether to adjust position size based on current balance
        (only applies when position_sizing='percent').
    - risk_calculation_method (str): Method for calculating risk amount per trade AND
        position sizing constraints (same as Monte Carlo simulator).
    
    Returns:
    - dict: Replay results containing:
        - 'final_balance' (float): Account balance after all trades
        - 'max_drawdown' (float): Maximum drawdown experienced
        - 'max_losing_streak' (int): Longest losing streak
        - 'trade_history' (list[float]): Balance at each step (initial + after each trade)
        - 'trade_details' (list[dict]): Per-trade details with keys:
            - 'date' (str): Opening date of the trade
            - 'contracts' (int): Number of contracts used
            - 'pnl_per_contract' (float): P/L per contract
            - 'total_pnl' (float): Total P/L for the trade
            - 'theoretical_risk' (float): Theoretical max risk for this trade
            - 'theoretical_reward' (float): Theoretical max reward for this trade
            - 'balance_before' (float): Account balance before the trade
            - 'balance_after' (float): Account balance after the trade
    
    Raises:
    - ValueError: If pnl_distribution is empty or required parameters are missing.
    
    Notes:
    - For 'contracts' sizing, position_size must be provided
    - For 'percent' sizing, target_risk_pct must be provided
    - Replay stops if balance reaches zero (bankruptcy)
    - Uses the same position sizing logic as Monte Carlo simulator for consistency
    """
    pnl_distribution = trade_stats.get('pnl_distribution', [])
    if not pnl_distribution:
        raise ValueError("pnl_distribution cannot be empty for trade replay")
    
    # Get per-trade theoretical risk - REQUIRED, no fallback
    per_trade_risk = trade_stats.get('per_trade_theoretical_risk', [])
    if not per_trade_risk:
        raise ValueError("per_trade_theoretical_risk is required but missing from trade_stats")
    if len(per_trade_risk) != len(pnl_distribution):
        raise ValueError(
            f"per_trade_theoretical_risk length ({len(per_trade_risk)}) must match "
            f"pnl_distribution length ({len(pnl_distribution)})"
        )
    
    # Validate all theoretical risk values are positive
    for idx, risk in enumerate(per_trade_risk):
        if risk <= 0:
            trade_date = trade_stats.get('per_trade_dates', [None] * len(per_trade_risk))[idx]
            date_str = f" on {trade_date}" if trade_date else f" at index {idx}"
            raise ValueError(
                f"Invalid theoretical risk{date_str}: {risk}. "
                f"Theoretical risk must be positive. This indicates missing or invalid data in the CSV "
                f"(e.g., missing strike prices, invalid spread structure, or malformed trade data)."
            )
    
    # Get per-trade theoretical reward - REQUIRED, no fallback
    per_trade_reward = trade_stats.get('per_trade_theoretical_reward', [])
    if not per_trade_reward:
        raise ValueError("per_trade_theoretical_reward is required but missing from trade_stats")
    if len(per_trade_reward) != len(pnl_distribution):
        raise ValueError(
            f"per_trade_theoretical_reward length ({len(per_trade_reward)}) must match "
            f"pnl_distribution length ({len(pnl_distribution)})"
        )
    
    # Get per-trade dates - REQUIRED, no fallback
    per_trade_dates = trade_stats.get('per_trade_dates', [])
    if not per_trade_dates:
        raise ValueError("per_trade_dates is required but missing from trade_stats")
    if len(per_trade_dates) != len(pnl_distribution):
        raise ValueError(
            f"per_trade_dates length ({len(per_trade_dates)}) must match "
            f"pnl_distribution length ({len(pnl_distribution)})"
        )
    
    # Validate required parameters
    if position_sizing == 'contracts' and position_size is None:
        raise ValueError("position_size must be provided when using 'contracts' position sizing")
    if position_sizing == 'percent' and target_risk_pct is None:
        raise ValueError("target_risk_pct must be provided when using 'percent' position sizing")
    
    # Initialize tracking variables
    balance = initial_balance
    peak = initial_balance
    max_drawdown = 0
    current_losing_streak = 0
    max_losing_streak = 0
    trade_history = [balance]
    trade_details = []
    
    # Replay each trade in order
    for idx, pnl in enumerate(pnl_distribution):
        # Get this trade's actual theoretical risk, reward, and date
        trade_theoretical_risk = per_trade_risk[idx]
        trade_theoretical_reward = per_trade_reward[idx]
        trade_date = per_trade_dates[idx]
        
        # Check if we can afford to trade
        if balance <= 0:
            break
        
        # Calculate max affordable contracts (theoretical risk is guaranteed positive from validation)
        max_affordable_contracts = int(balance / trade_theoretical_risk)
        if max_affordable_contracts == 0:
            # Not enough balance to afford even 1 contract - stop trading
            # Don't modify balance, just stop
            break
        
        # Determine contract count for this trade
        if position_sizing == 'contracts':
            contracts = position_size
        else:
            # Dynamic or static percentage-based sizing
            # Use this trade's actual theoretical risk for sizing
            if dynamic_risk_sizing:
                contracts = choose_contract_count_for_risk_pct(
                    max_risk_per_spread=trade_theoretical_risk,
                    account_balance=max(balance, 1),
                    target_risk_pct=target_risk_pct
                )
            else:
                # Static percentage sizing based on initial balance
                contracts = choose_contract_count_for_risk_pct(
                    max_risk_per_spread=trade_theoretical_risk,
                    account_balance=initial_balance,
                    target_risk_pct=target_risk_pct
                )
        
        # CRITICAL: Cap contracts based on this trade's actual theoretical max loss
        contracts = min(contracts, max_affordable_contracts)
        
        # Save balance before trade
        balance_before = balance
        
        # Apply the actual P/L for this trade
        realized_pnl = pnl * contracts
        balance += realized_pnl
        
        # Track losing streaks
        if realized_pnl >= 0:
            current_losing_streak = 0
        else:
            current_losing_streak += 1
            max_losing_streak = max(max_losing_streak, current_losing_streak)
        
        # Track drawdown
        peak = max(peak, balance)
        max_drawdown = max(max_drawdown, peak - balance)
        
        # Prevent negative balance
        if balance < 0:
            balance = 0
        
        # Validate balance before recording (should never be <= 0 due to earlier break)
        if balance_before <= 0:
            raise ValueError(
                f"Logic error: balance_before is {balance_before} for trade on {trade_date}. "
                f"Trades should not execute when balance <= 0. This indicates a bug in replay logic."
            )
        
        # Record trade details (theoretical_risk is guaranteed positive from upfront validation)
        trade_details.append({
            'date': trade_date,
            'contracts': contracts,
            'pnl_per_contract': pnl,
            'total_pnl': realized_pnl,
            'theoretical_risk': trade_theoretical_risk,
            'theoretical_reward': trade_theoretical_reward,
            'pnl_pct': (pnl / trade_theoretical_risk) * 100,
            'risk_pct': (trade_theoretical_risk / balance_before) * 100,
            'balance_before': balance_before,
            'balance_after': balance
        })
        
        trade_history.append(balance)
    
    return {
        'final_balance': balance,
        'max_drawdown': max_drawdown,
        'max_losing_streak': max_losing_streak,
        'trade_history': trade_history,
        'trade_details': trade_details
    }
