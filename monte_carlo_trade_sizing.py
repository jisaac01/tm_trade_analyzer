import numpy as np
import pandas as pd
import random
import os
import argparse
import webbrowser
from html import escape

# DEPRECATED: This file is a museum piece and should never be touched.
# It is preserved for historical reference only. All new development should
# use simulator.py and trade_parser.py instead.

OPTION_COMMISSION_PER_CONTRACT = 0.495

# Define the trades with their parameters (will be updated with real data)
trades = [
    {"name": "Short Put Spread", "risk": 397, "reward": 103, "win_rate": 0.82},
    {"name": "Long Call Spread", "risk": 623, "reward": 447, "win_rate": 0.77}
]

# Knobs to tweak
initial_balance = 10000  # Starting account balance
num_simulations = 5000   # Number of Monte Carlo simulations
# num_trades will be set based on actual trade data below
DEFAULT_POSITION_SIZES = [1, 2, 5, 10, 15, 20]
DEFAULT_RISK_PCTS = [1, 2, 3, 5, 10, 15, 25, 50, 75, 100]


def parse_args(argv=None):
    """Parse CLI arguments for position sizing behavior."""
    parser = argparse.ArgumentParser(description='Monte Carlo trade sizing simulator')
    parser.add_argument(
        '--position-sizing',
        choices=['percent', 'contracts'],
        default='percent',
        help='Use percent of account risk targets (default) or contract count presets.'
    )
    parser.add_argument(
        '--dynamic-risk-sizing',
        dest='dynamic_risk_sizing',
        action='store_true',
        default=True,
        help='Recompute percent-risk contract count from current equity before each trade (default on).'
    )
    parser.add_argument(
        '--no-dynamic-risk-sizing',
        dest='dynamic_risk_sizing',
        action='store_false',
        help='Use initial contract count throughout each simulation (legacy behavior).'
    )
    parser.add_argument(
        '--simulation-mode',
        choices=['iid', 'moving-block-bootstrap'],
        default='iid',
        help='Use iid synthetic win/loss generation or moving-block bootstrap from realized trade P/L history.'
    )
    parser.add_argument(
        '--block-size',
        type=int,
        default=5,
        help='Block length for moving-block bootstrap sampling.'
    )
    parser.add_argument(
        '--output-html',
        default='scripts/monte_carlo_trade_sizing_report.html',
        help='Path to write the HTML report file.'
    )
    parser.add_argument(
        '--no-open-browser',
        dest='open_browser',
        action='store_false',
        default=True,
        help='Do not auto-open the HTML report in a browser.'
    )
    return parser.parse_args(argv)


def format_currency_whole(value):
    value_int = int(value)
    return f"-${abs(value_int)}" if value_int < 0 else f"${value_int}"


def format_percent_whole(value):
    """Format fraction as whole percent with no decimal places."""
    return f"{value:.0%}"


def build_html_report(
    trade_reports,
    initial_balance,
    position_sizing,
    dynamic_risk_sizing,
    simulation_mode,
    block_size
):
    """Render simulation output as a styled HTML report."""
    report_parts = []
    for report in trade_reports:
        trade_name = escape(report['trade_name'])
        summary = report['summary']
        table_df = pd.DataFrame(report['table_rows'])
        table_html = table_df.to_html(index=False, classes='sim-table', border=0, escape=False)
        historical_max_losing_streak = report.get('historical_max_losing_streak', 0)
        pnl_preview = report.get('pnl_preview')
        if pnl_preview is None:
            pnl_preview = [round(x) for x in summary.get('pnl_distribution', [])[:10]]

        summary_html = f"""
        <div class=\"summary-grid\">
            <div class=\"summary-item\"><span>Risked</span><strong>${summary['risked']:.0f}</strong></div>
            <div class=\"summary-item\"><span>Total Return</span><strong>{format_currency_whole(summary['total_return'])}</strong></div>
            <div class=\"summary-item\"><span>% Return</span><strong>{summary['pct_return']:.1f}%</strong></div>
            <div class=\"summary-item\"><span>Avg % Return</span><strong>{summary['avg_pct_return']:.1f}%</strong></div>
            <div class=\"summary-item\"><span>Commissions</span><strong>${summary['commissions']:.0f}</strong></div>
            <div class=\"summary-item\"><span>Win Rate</span><strong>{summary['win_rate'] * 100:.1f}%</strong></div>
            <div class=\"summary-item\"><span>Wins / Losses</span><strong>{summary['wins']} / {summary['losses']}</strong></div>
            <div class=\"summary-item\"><span>Avg Win / Avg Loss</span><strong>{format_currency_whole(summary['avg_win'])} / {format_currency_whole(summary['avg_loss'])}</strong></div>
            <div class=\"summary-item\"><span>Gross Gain / Gross Loss</span><strong>{format_currency_whole(summary['gross_gain'])} / {format_currency_whole(summary['gross_loss'])}</strong></div>
            <div class=\"summary-item\"><span>Conservative Max Risk</span><strong>${round(summary['conservative_theoretical_max_loss'])}</strong></div>
            <div class=\"summary-item\"><span>Max Risk</span><strong>${round(summary['max_theoretical_loss'])}</strong></div>
            <div class=\"summary-item\"><span>Max Loss Streak in History</span><strong>{historical_max_losing_streak}</strong></div>
        </div>
        """

        report_parts.append(
            f"""
            <section class=\"trade-card\">
                <h2>{trade_name}</h2>
                <h3 class=\"section-label\">TradeMachine Backtest Results (from CSV file)</h3>
                {summary_html}
                <p class=\"distribution\">P/L Distribution (first 10): {pnl_preview}</p>
                <h3 class=\"section-label\">Monte Carlo Simulation Results (generated)</h3>
                {table_html}
            </section>
            """
        )

    mode_desc = "Dynamic per-trade % risk sizing ON" if dynamic_risk_sizing else "Dynamic per-trade % risk sizing OFF"
    block_desc = f"Block Size: {block_size}" if simulation_mode == 'moving-block-bootstrap' else ""

    return f"""
    <!doctype html>
    <html lang=\"en\">
    <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>Monte Carlo Trade Sizing Report</title>
        <style>
            :root {{
                --bg: #0f172a;
                --panel: #111827;
                --panel-2: #1f2937;
                --text: #e5e7eb;
                --muted: #9ca3af;
                --accent: #60a5fa;
                --good: #34d399;
                --warn: #fbbf24;
            }}
            body {{
                margin: 0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                background: linear-gradient(180deg, #020617 0%, var(--bg) 100%);
                color: var(--text);
            }}
            .container {{ max-width: 1240px; margin: 32px auto; padding: 0 20px 40px; }}
            .hero {{
                background: radial-gradient(circle at top right, rgba(96, 165, 250, 0.20), transparent 45%), var(--panel);
                border: 1px solid #243041;
                border-radius: 16px;
                padding: 24px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
            }}
            .hero h1 {{ margin: 0 0 6px; font-size: 30px; }}
            .hero p {{ margin: 2px 0; color: var(--muted); }}
            .hero .meta strong {{ color: var(--accent); }}
            .trade-card {{
                margin-top: 20px;
                background: var(--panel);
                border: 1px solid #253244;
                border-radius: 16px;
                padding: 20px;
            }}
            .trade-card h2 {{ margin: 0 0 14px; font-size: 22px; }}
            .section-label {{
                margin: 14px 0 8px;
                font-size: 13px;
                font-weight: 700;
                color: var(--accent);
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }}
            .summary-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
                gap: 10px;
                margin-bottom: 16px;
            }}
            .summary-item {{
                background: var(--panel-2);
                border: 1px solid #2f3d52;
                border-radius: 10px;
                padding: 10px 12px;
            }}
            .summary-item span {{ display: block; color: var(--muted); font-size: 12px; margin-bottom: 4px; }}
            .summary-item strong {{ color: var(--good); font-size: 16px; }}
            .distribution {{ color: var(--warn); margin: 8px 0 12px; }}
            .sim-table {{ width: 100%; border-collapse: collapse; background: #0b1320; border-radius: 10px; overflow: hidden; }}
            .sim-table th, .sim-table td {{ padding: 10px 12px; border-bottom: 1px solid #1f2b3d; text-align: right; }}
            .sim-table th:first-child, .sim-table td:first-child {{ text-align: left; }}
            .sim-table th {{ background: #0f1b2d; color: var(--accent); font-weight: 700; }}
            .footer-note {{ margin-top: 16px; color: var(--muted); font-size: 12px; }}
        </style>
    </head>
    <body>
        <main class=\"container\">
            <section class=\"hero\">
                <h1>Monte Carlo Trade Sizing Report</h1>
                <p class=\"meta\">Initial Balance: <strong>${initial_balance:,.0f}</strong></p>
                <p class=\"meta\">Position Sizing: <strong>{escape(position_sizing)}</strong> • {escape(mode_desc)} • Simulation Mode: <strong>{escape(simulation_mode)}</strong> {escape(block_desc)}</p>
            </section>
            {''.join(report_parts)}
            <p class=\"footer-note\">Generated by scripts/monte_carlo_trade_sizing.py</p>
        </main>
    </body>
    </html>
    """


def get_max_risk_per_spread(trade):
    conservative_theoretical_loss = trade.get('conservative_theoretical_max_loss', 0)
    if conservative_theoretical_loss and conservative_theoretical_loss > 0:
        return float(conservative_theoretical_loss)

    max_theoretical_loss = trade.get('max_theoretical_loss', 0)
    if max_theoretical_loss and max_theoretical_loss > 0:
        return float(max_theoretical_loss)
    return float(abs(trade['max_loss']))


def choose_contract_count_for_risk_pct(max_risk_per_spread, account_balance, target_risk_pct):
    """Select contract count whose conservative max risk is nearest target account risk %."""
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
    """Build simulation sizing rows as contract counts with target/actual risk percentages."""
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

# Function to simulate trades for a given trade type and position size
def sample_pnl_moving_blocks(pnl_distribution, num_trades, block_size):
    """Sample realized trade P/L values using moving blocks to preserve streak structure."""
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

def analyze_trade_file(file_path):
    """Analyze a CSV file of trade data to extract statistics for Monte Carlo simulation."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Trade file not found: {file_path}")
    
    df = pd.read_csv(file_path)
    
    # Clean money-like columns - remove $ and convert to float
    def clean_money(value):
        if isinstance(value, str):
            value = value.strip()
            if value == '' or value == ' ':
                return None
            value = value.replace('$', '').replace(',', '')
            return float(value)
        return float(value) if pd.notna(value) else None

    df['Profit/Loss'] = df['Profit/Loss'].apply(clean_money)
    df['Trade Price'] = df['Trade Price'].apply(clean_money)

    # Filter for close rows (rows with Profit/Loss)
    close_df = df[df['Profit/Loss'].notna()].copy()
    close_df = close_df[close_df['Profit/Loss'].notna()]
    
    # Group by Expiration to get net P/L per trade
    trade_pnl = close_df.groupby('Expiration')['Profit/Loss'].sum()
    
    pnl_values = trade_pnl.values
    
    if len(pnl_values) == 0:
        return {
            'num_trades': 0,
            'win_rate': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'max_win': 0,
            'max_loss': 0,
            'max_theoretical_loss': 0,
            'conservative_theoretical_max_loss': 0,
            'max_theoretical_gain': 0,
            'conservative_realized_max_reward': 0,
            'risked': 0,
            'total_return': 0,
            'pct_return': 0,
            'avg_pct_return': 0,
            'commissions': 0,
            'wins': 0,
            'losses': 0,
            'avg_pct_win': 0,
            'avg_pct_loss': 0,
            'gross_gain': 0,
            'gross_loss': 0,
            'pnl_distribution': []
        }

    # Compute theoretical risk/reward from opening legs per expiration
    open_df = df[
        df['Description'].fillna('').str.contains('Open')
        & df['Trade Price'].notna()
        & df['Size'].notna()
        & df['Strike'].notna()
    ].copy()

    max_theoretical_loss = 0
    conservative_theoretical_max_loss = 0
    max_theoretical_gain = 0
    if not open_df.empty:
        open_df['open_cashflow'] = -open_df['Size'] * open_df['Trade Price'] * 100
        theoretical = open_df.groupby('Expiration', sort=False).agg(
            net_open_cashflow=('open_cashflow', 'sum'),
            min_strike=('Strike', 'min'),
            max_strike=('Strike', 'max')
        )
        theoretical['width'] = (theoretical['max_strike'] - theoretical['min_strike']) * 100
        theoretical['theoretical_max_loss'] = np.where(
            theoretical['net_open_cashflow'] >= 0,
            theoretical['width'] - theoretical['net_open_cashflow'],
            -theoretical['net_open_cashflow']
        )
        theoretical['theoretical_max_gain'] = np.where(
            theoretical['net_open_cashflow'] >= 0,
            theoretical['net_open_cashflow'],
            theoretical['width'] + theoretical['net_open_cashflow']
        )

        theoretical_losses = theoretical['theoretical_max_loss'].clip(lower=0).values
        theoretical_gains = theoretical['theoretical_max_gain'].clip(lower=0).values

        if len(theoretical_losses) > 0:
            max_theoretical_loss = float(np.max(theoretical_losses))
            conservative_theoretical_max_loss = float(np.quantile(theoretical_losses, 0.95))
        if len(theoretical_gains) > 0:
            max_theoretical_gain = float(np.max(theoretical_gains))

    risked = 0
    if not open_df.empty:
        first_expiration = theoretical.index[0]
        first_trade_risk = float(theoretical.iloc[0]['theoretical_max_loss'])
        first_trade_entry_commission = float(
            open_df[open_df['Expiration'] == first_expiration]['Size'].abs().sum() * OPTION_COMMISSION_PER_CONTRACT
        )
        risked = first_trade_risk + first_trade_entry_commission
    total_return = float(np.sum(pnl_values))
    pct_return = (total_return / risked * 100) if risked > 0 else 0

    commissions = float(df['Size'].abs().sum() * OPTION_COMMISSION_PER_CONTRACT)

    joined = theoretical.join(trade_pnl.rename('pnl'), how='inner') if not open_df.empty else pd.DataFrame()
    avg_pct_return = 0
    avg_pct_win = 0
    avg_pct_loss = 0
    if not joined.empty:
        joined['pct_return'] = np.where(
            joined['theoretical_max_loss'] > 0,
            joined['pnl'] / joined['theoretical_max_loss'] * 100,
            0
        )
        avg_pct_return = float(joined['pct_return'].mean())
        avg_pct_win = float(joined.loc[joined['pnl'] > 0, 'pct_return'].mean()) if (joined['pnl'] > 0).any() else 0
        avg_pct_loss = float(joined.loc[joined['pnl'] < 0, 'pct_return'].mean()) if (joined['pnl'] < 0).any() else 0
    
    wins = pnl_values[pnl_values > 0]
    losses = pnl_values[pnl_values < 0]
    median_loss = float(np.median(losses)) if len(losses) > 0 else 0
    median_risk_per_spread = abs(median_loss)
    conservative_realized_max_reward = float(np.quantile(wins, 0.95)) if len(wins) > 0 else 0
    
    stats = {
        'num_trades': len(pnl_values),
        'win_rate': len(wins) / len(pnl_values) if len(pnl_values) > 0 else 0,
        'avg_win': np.mean(wins) if len(wins) > 0 else 0,
        'avg_loss': np.mean(losses) if len(losses) > 0 else 0,
        'median_loss': median_loss,
        'median_risk_per_spread': median_risk_per_spread,
        'max_win': np.max(wins) if len(wins) > 0 else 0,
        'max_loss': np.min(losses) if len(losses) > 0 else 0,  # Most negative
        'max_theoretical_loss': max_theoretical_loss,
        'conservative_theoretical_max_loss': conservative_theoretical_max_loss,
        'max_theoretical_gain': max_theoretical_gain,
        'conservative_realized_max_reward': conservative_realized_max_reward,
        'risked': risked,
        'total_return': total_return,
        'pct_return': pct_return,
        'avg_pct_return': avg_pct_return,
        'commissions': commissions,
        'wins': len(wins),
        'losses': len(losses),
        'avg_pct_win': avg_pct_win,
        'avg_pct_loss': avg_pct_loss,
        'gross_gain': float(np.sum(wins)) if len(wins) > 0 else 0,
        'gross_loss': float(np.sum(losses)) if len(losses) > 0 else 0,
        'pnl_distribution': pnl_values.tolist()
    }
    
    return stats

def generate_risk(avg_risk, max_risk):
    """Generate a risk amount that averages to avg_risk but can go up to max_risk.
    
    Uses a truncated normal distribution to simulate variable risk amounts.
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
    """Generate a reward amount that can go up to max_reward.
    
    Uses a distribution that favors smaller wins but allows occasional larger wins.
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

def main(argv=None):
    args = parse_args(argv)

    # Analyze actual trade files to inform simulation parameters
    call_file = 'scripts/CML TM Trades Long 60 Delta, Short 30 Delta Call 20260223.csv'
    put_file = 'scripts/CML TM Trades Short 50 Delta, Long 40 Delta Put 20260223.csv'

    call_stats = analyze_trade_file(call_file)
    put_stats = analyze_trade_file(put_file)

    # Set num_trades to the maximum of 55 or the number of trades in the files
    num_trades = max(55, call_stats['num_trades'], put_stats['num_trades'])

    # Update trades with analyzed data
    trades = [
        {
            "name": "Call Spread (60Δ Long, 30Δ Short)",
            **call_stats  # Include all stats from the analysis
        },
        {
            "name": "Put Spread (50Δ Short, 40Δ Long)",
            **put_stats  # Include all stats from the analysis
        }
    ]

    # Run simulations for each trade and position size
    trade_reports = []
    for trade in trades:
        position_size_plan = build_position_size_plan(
            trade=trade,
            initial_balance=initial_balance,
            position_sizing=args.position_sizing
        )

        data = []
        for row in position_size_plan:
            ps = row['contracts']
            if args.position_sizing == 'percent':
                sim_results = simulate_trades(
                    trade,
                    ps,
                    initial_balance,
                    num_trades,
                    num_simulations,
                    target_risk_pct=row['target_risk_pct'],
                    dynamic_risk_sizing=args.dynamic_risk_sizing,
                    simulation_mode=args.simulation_mode,
                    block_size=args.block_size
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
                    simulation_mode=args.simulation_mode,
                    block_size=args.block_size
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
                'Avg Final $': f"${avg_final_balance:.2f}",
                'Bankruptcy Prob': format_percent_whole(bankrupt_prob),
                'Avg Max Drawdown': f"${avg_max_drawdown:.2f}",
                'Max Drawdown': f"${max_drawdown:.2f}",
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

        trade_reports.append(
            {
                'trade_name': trade['name'],
                'summary': trade,
                'table_rows': data,
                'pnl_preview': [round(x) for x in trade['pnl_distribution'][:10]],
                'historical_max_losing_streak': historical_max_losing_streak
            }
        )

    html_report = build_html_report(
        trade_reports=trade_reports,
        initial_balance=initial_balance,
        position_sizing=args.position_sizing,
        dynamic_risk_sizing=args.dynamic_risk_sizing,
        simulation_mode=args.simulation_mode,
        block_size=args.block_size
    )

    output_path = os.path.abspath(args.output_html)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as report_file:
        report_file.write(html_report)

    if args.open_browser:
        webbrowser.open(f'file://{output_path}')

    print(f"HTML report written to {output_path}")


if __name__ == '__main__':
    main()