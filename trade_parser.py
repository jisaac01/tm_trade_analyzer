import pandas as pd
import numpy as np

OPTION_COMMISSION_PER_CONTRACT = 0.495


def parse_trade_csv(file_or_path):
    """
    Parse a CSV file of trade data and extract comprehensive statistics for Monte Carlo simulation.
    
    Analyzes option trade data to compute win rates, average gains/losses, theoretical risk/reward
    metrics, and P/L distributions. Handles both opening leg data (for theoretical calculations)
    and closing P/L data (for realized performance).
    
    Parameters:
    - file_or_path (str or file-like object): Path to CSV file or file object containing trade data.
    
    Returns:
    - dict: Comprehensive trade statistics dictionary containing:
        - Basic counts: num_trades, wins, losses
        - Performance metrics: win_rate, avg_win, avg_loss, max_win, max_loss
        - Risk metrics: max_theoretical_loss, conservative_theoretical_max_loss, median_risk_per_spread
        - Reward metrics: max_theoretical_gain, conservative_realized_max_reward
        - Financial metrics: total_return, pct_return, avg_pct_return, commissions
        - Distribution data: pnl_distribution (list of P/L values)
        - Date range: min_date, max_date
        - Percentage-based metrics: avg_pct_win, avg_pct_loss
    
    CSV Format Expected:
    - Date: Trade date in DD-MMM-YYYY format
    - Description: Trade description (contains 'Open' for opening legs)
    - Profit/Loss: Realized P/L for closing transactions
    - Trade Price: Price per contract for opening legs
    - Size: Number of contracts
    - Strike: Strike price for theoretical calculations
    - Expiration: Expiration date for grouping trades
    
    Notes:
    - Theoretical risk/reward calculated from opening leg structure (width between strikes)
    - P/L aggregated by expiration date to get per-trade results
    - Commissions calculated at $0.495 per contract
    - Conservative metrics use 95th percentile for robustness
    - Returns empty statistics dict if no valid trade data found
    """
    df = pd.read_csv(file_or_path)
    
    # Parse dates - support multiple formats
    df['Date'] = pd.to_datetime(df['Date'], format='mixed')
    min_date = df['Date'].min().strftime('%Y-%m-%d') if not df.empty else None
    max_date = df['Date'].max().strftime('%Y-%m-%d') if not df.empty else None
    
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
    per_trade_theoretical_risk = []
    if not joined.empty:
        joined['pct_return'] = np.where(
            joined['theoretical_max_loss'] > 0,
            joined['pnl'] / joined['theoretical_max_loss'] * 100,
            0
        )
        avg_pct_return = float(joined['pct_return'].mean())
        avg_pct_win = float(joined.loc[joined['pnl'] > 0, 'pct_return'].mean()) if (joined['pnl'] > 0).any() else 0
        avg_pct_loss = float(joined.loc[joined['pnl'] < 0, 'pct_return'].mean()) if (joined['pnl'] < 0).any() else 0
        # Extract per-trade theoretical risk in the same order as pnl_distribution
        per_trade_theoretical_risk = joined['theoretical_max_loss'].tolist()
    
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
        'pnl_distribution': pnl_values.tolist(),
        'per_trade_theoretical_risk': per_trade_theoretical_risk,
        'min_date': min_date,
        'max_date': max_date
    }
    
    return stats