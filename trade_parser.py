import pandas as pd
import numpy as np
from datetime import date as _date
import pandas_market_calendars as _mcal

OPTION_COMMISSION_PER_CONTRACT = 0.495


# ---------------------------------------------------------------------------
# NYSE calendar helper (cached per year like merge_backtests.py)
# ---------------------------------------------------------------------------

_nyse_calendar = None
_nyse_day_cache: dict = {}


def _get_nyse():
    global _nyse_calendar
    if _nyse_calendar is None:
        _nyse_calendar = _mcal.get_calendar('NYSE')
    return _nyse_calendar


def _trading_day_index_map(start: _date, end: _date) -> dict:
    """
    Return {date: int_index} for all NYSE trading days in [start, end].
    Index 0 = start (or first trading day on/after start).
    """
    if start > end:
        return {}
    nyse = _get_nyse()
    schedule = nyse.schedule(
        start_date=start.strftime('%Y-%m-%d'),
        end_date=end.strftime('%Y-%m-%d'),
    )
    return {ts.date(): i for i, ts in enumerate(schedule.index)}


# ---------------------------------------------------------------------------
# Signal statistics
# ---------------------------------------------------------------------------

def _empty_signal_stats() -> dict:
    """Return a zeroed-out signal_stats dict (for empty or single-trade data)."""
    _weekday_names = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday'}
    return {
        'sequential_signal_count': 0,
        'overlapping_signal_count': 0,
        'max_sequential_run': 0,
        'max_gap_trading_days': 0,
        'median_gap_trading_days': 0.0,
        'sequential_by_position': {},
        'overlapping_non_sequential': {'count': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0},
        'signals_by_weekday': {
            wd: {'name': name, 'count': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0, 'pct': 0.0}
            for wd, name in _weekday_names.items()
        },
        'total_signals': 0,
        'gaps': [],
    }


def compute_signal_stats(
    per_trade_open_dates: list,
    per_trade_close_dates: list,
    pnl_distribution: list,
) -> dict:
    """
    Compute signal timing statistics: sequential signals, overlapping signals,
    gap distributions, and weekday breakdowns.

    All three input lists must be the same length and correspond to the same
    trade (i.e. index i is the same trade across all three lists).
    Per-trade close dates may be None for trades with no recorded close date;
    such trades are skipped in overlap calculations.

    Parameters
    ----------
    per_trade_open_dates  : list[str] – 'YYYY-MM-DD' open dates
    per_trade_close_dates : list[str | None] – 'YYYY-MM-DD' close dates
    pnl_distribution      : list[float] – realized P/L per trade

    Returns
    -------
    dict with keys:
      sequential_signal_count   – # of trades that opened on the next NYSE
                                   trading day after the previous trade's open
      overlapping_signal_count  – # of trades that opened while at least one
                                   previous trade was still open
      max_sequential_run        – length of the longest consecutive-day run
      max_gap_trading_days      – largest ordinal gap between consecutive opens
      median_gap_trading_days   – median ordinal gap between consecutive opens
      sequential_by_position    – {pos: {count, wins, losses, pnl}} for pos≥2
      overlapping_non_sequential– {count, wins, losses, pnl} for trades that
                                   overlap a previous trade but are NOT the
                                   next sequential day
      signals_by_weekday        – {0..4: {name, count, wins, losses, pnl, pct}}
      total_signals             – total number of trades analysed
      gaps                      – list of ordinal gaps (length n-1 for n trades)
    """
    _weekday_names = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday'}

    if not per_trade_open_dates:
        return _empty_signal_stats()

    n = len(per_trade_open_dates)
    assert n == len(per_trade_close_dates) == len(pnl_distribution), (
        "per_trade_open_dates, per_trade_close_dates, and pnl_distribution "
        "must all be the same length."
    )

    # Sort everything by open_date; maintain stable order for ties.
    parsed_opens = [_date.fromisoformat(d) for d in per_trade_open_dates]
    parsed_closes = [
        (_date.fromisoformat(d) if d is not None else None)
        for d in per_trade_close_dates
    ]
    order = sorted(range(n), key=lambda i: parsed_opens[i])
    open_dates = [parsed_opens[i] for i in order]
    close_dates = [parsed_closes[i] for i in order]
    pnls = [float(pnl_distribution[i]) for i in order]

    # Build NYSE trading-day index map covering the full date range.
    all_known = [d for d in open_dates + close_dates if d is not None]
    td_map = _trading_day_index_map(min(all_known), max(all_known))

    # ── Gap calculation ──────────────────────────────────────────────────
    gaps: list[int] = []
    for i in range(n - 1):
        idx_curr = td_map.get(open_dates[i])
        idx_next = td_map.get(open_dates[i + 1])
        if idx_curr is not None and idx_next is not None:
            gaps.append(idx_next - idx_curr)
        else:
            # Dates outside market calendar (e.g. holiday opens) – treat as
            # non-sequential with a gap of 2 to be conservative.
            gaps.append(2)

    max_gap = int(max(gaps)) if gaps else 0
    median_gap = float(np.median(gaps)) if gaps else 0.0

    # ── Sequential run positions ─────────────────────────────────────────
    # run_positions[i] = ordinal position of trade i within its sequential run.
    # A run is a maximal sequence where every consecutive pair has gap == 1.
    run_positions = [1] * n
    for i in range(1, n):
        if gaps[i - 1] == 1:
            run_positions[i] = run_positions[i - 1] + 1
        else:
            run_positions[i] = 1

    max_sequential_run = max(run_positions) if run_positions else 1

    # Accumulate sequential-by-position stats (positions 2+)
    sequential_by_position: dict = {}
    for i, pos in enumerate(run_positions):
        if pos < 2:
            continue
        if pos not in sequential_by_position:
            sequential_by_position[pos] = {'count': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0}
        sequential_by_position[pos]['count'] += 1
        sequential_by_position[pos]['pnl'] += pnls[i]
        if pnls[i] > 0:
            sequential_by_position[pos]['wins'] += 1
        elif pnls[i] < 0:
            sequential_by_position[pos]['losses'] += 1

    sequential_signal_count = sum(v['count'] for v in sequential_by_position.values())

    # ── Overlapping signals ──────────────────────────────────────────────
    # Trade i is "overlapping" if some earlier trade j has:
    #   open_dates[j] < open_dates[i] <= close_dates[j]
    overlapping_indices: set = set()
    for i in range(1, n):
        for j in range(i - 1, -1, -1):
            if open_dates[j] >= open_dates[i]:
                continue  # same-day or later open – not a prior trade
            cj = close_dates[j]
            if cj is not None and open_dates[i] <= cj:
                overlapping_indices.add(i)
                break  # found one – no need to check further

    overlapping_signal_count = len(overlapping_indices)

    # Overlapping but NOT sequential (run_positions == 1 for that trade)
    ons: dict = {'count': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0}
    for i in overlapping_indices:
        if run_positions[i] < 2:  # not the next consecutive day
            ons['count'] += 1
            ons['pnl'] += pnls[i]
            if pnls[i] > 0:
                ons['wins'] += 1
            elif pnls[i] < 0:
                ons['losses'] += 1

    # ── Weekday distribution ─────────────────────────────────────────────
    _all_weekday_names = {
        0: 'Monday', 1: 'Tuesday', 2: 'Wednesday',
        3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday',
    }
    signals_by_weekday = {
        wd: {'name': name, 'count': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0, 'pct': 0.0}
        for wd, name in _weekday_names.items()
    }
    for i, d in enumerate(open_dates):
        wd = d.weekday()
        if wd not in signals_by_weekday:
            # Defensive: handle weekend dates in synthetic/test data
            signals_by_weekday[wd] = {
                'name': _all_weekday_names.get(wd, f'Weekday{wd}'),
                'count': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0, 'pct': 0.0,
            }
        signals_by_weekday[wd]['count'] += 1
        signals_by_weekday[wd]['pnl'] += pnls[i]
        if pnls[i] > 0:
            signals_by_weekday[wd]['wins'] += 1
        elif pnls[i] < 0:
            signals_by_weekday[wd]['losses'] += 1

    for wd in signals_by_weekday:
        cnt = signals_by_weekday[wd]['count']
        signals_by_weekday[wd]['pct'] = (cnt / n * 100.0) if n > 0 else 0.0

    return {
        'sequential_signal_count': sequential_signal_count,
        'overlapping_signal_count': overlapping_signal_count,
        'max_sequential_run': max_sequential_run,
        'max_gap_trading_days': max_gap,
        'median_gap_trading_days': median_gap,
        'sequential_by_position': sequential_by_position,
        'overlapping_non_sequential': ons,
        'signals_by_weekday': signals_by_weekday,
        'total_signals': n,
        'gaps': gaps,
    }


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

    # ── Assign _trade_key = "Expiration|open_date" ───────────────────────────
    # This allows overlapping trades that share the same Expiration date to be
    # treated as separate trades. We identify which close rows belong to which
    # opening trade by matching on (Expiration, Strike, Type), then use the
    # matched opening date as part of the composite key.
    #
    # Limitation: if two overlapping trades share the SAME (Expiration, Strike,
    # Type) combination, both will be assigned to the first-seen opening date.
    # That edge case is rare and not supported by TradeMachine's CSV format.
    _open_eligible = df[
        df['Description'].fillna('').str.contains('Open')
        & df['Strike'].notna()
        & df['Type'].notna()
    ].sort_values('Date')
    _leg_to_open_date: dict = {}
    for _, _r in _open_eligible.iterrows():
        _leg = (str(_r['Expiration']), str(_r['Strike']), str(_r['Type']))
        if _leg not in _leg_to_open_date:
            _leg_to_open_date[_leg] = _r['Date']

    def _trade_open_date_for_row(row):
        """Return the opening date this row belongs to."""
        if 'Open' in str(row.get('Description', '')):
            return row['Date']
        _leg = (str(row['Expiration']), str(row['Strike']), str(row['Type']))
        return _leg_to_open_date.get(_leg, row['Date'])

    if not df.empty:
        df['_trade_open_date'] = df.apply(_trade_open_date_for_row, axis=1)
        df['_trade_key'] = (
            df['Expiration'].astype(str) + '|'
            + df['_trade_open_date'].dt.strftime('%Y-%m-%d')
        )
    else:
        df['_trade_open_date'] = pd.Series(dtype='datetime64[ns]')
        df['_trade_key'] = pd.Series(dtype=object)

    # Filter for close rows (rows with Profit/Loss)
    close_df = df[df['Profit/Loss'].notna()].copy()

    # Group by _trade_key to get net P/L per trade
    # sort=False preserves chronological order from file instead of alphabetical sorting
    trade_pnl = close_df.groupby('_trade_key', sort=False)['Profit/Loss'].sum()
    
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
            'conservative_theoretical_max_reward': 0,
            'conservative_realized_max_reward': 0,
            'avg_risk_per_spread': 0,
            'avg_reward_per_spread': 0,
            'max_win_pct': 0,
            'max_loss_pct': 0,
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
            'pnl_distribution': [],
            'per_trade_theoretical_reward': [],
            'per_trade_dates': [],
            'per_trade_close_dates': [],
            'signal_stats': _empty_signal_stats(),
            'raw_trade_data': []
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
    conservative_theoretical_max_reward = 0
    if not open_df.empty:
        open_df['open_cashflow'] = -open_df['Size'] * open_df['Trade Price'] * 100
        theoretical = open_df.groupby('_trade_key', sort=False).agg(
            net_open_cashflow=('open_cashflow', 'sum'),
            min_strike=('Strike', 'min'),
            max_strike=('Strike', 'max'),
            open_date=('Date', 'min')  # Get earliest opening date per trade
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
            conservative_theoretical_max_reward = float(np.quantile(theoretical_gains, 0.95))

    risked = 0
    if not open_df.empty:
        first_trade_key = theoretical.index[0]
        first_trade_risk = float(theoretical.iloc[0]['theoretical_max_loss'])
        first_trade_entry_commission = float(
            open_df[open_df['_trade_key'] == first_trade_key]['Size'].abs().sum() * OPTION_COMMISSION_PER_CONTRACT
        )
        risked = first_trade_risk + first_trade_entry_commission
    total_return = float(np.sum(pnl_values))
    pct_return = (total_return / risked * 100) if risked > 0 else 0

    commissions = float(df['Size'].abs().sum() * OPTION_COMMISSION_PER_CONTRACT)

    joined = theoretical.join(trade_pnl.rename('pnl'), how='inner') if not open_df.empty else pd.DataFrame()
    
    # Critical: If we have closing P/L but no matching opening data, we cannot proceed
    # This indicates a data integrity issue that would cause incorrect simulation results
    if joined.empty:
        raise ValueError(
            "CSV contains closing P/L data but no matching opening trade data. "
            "This likely means: (1) no opening legs found with valid Strike/Trade Price/Size, "
            "or (2) Expiration values don't match between opening and closing trades. "
            "The simulator requires opening data to calculate theoretical risk/reward metrics and dates."
        )
    
    # At this point, joined is guaranteed to be non-empty (error raised above if empty)

    # Join close dates (max close date per trade_key) onto joined
    close_date_by_key = close_df.groupby('_trade_key')['Date'].max().rename('close_date')
    joined = joined.join(close_date_by_key, how='left')

    # Sort by open_date so the replay table and all per-trade lists are in
    # chronological order regardless of how the rows appear in the source file.
    joined = joined.sort_values('open_date', kind='stable')

    joined['pct_return'] = np.where(        joined['theoretical_max_loss'] > 0,
        joined['pnl'] / joined['theoretical_max_loss'] * 100,
        0
    )
    avg_pct_return = float(joined['pct_return'].mean())
    avg_pct_win = float(joined.loc[joined['pnl'] > 0, 'pct_return'].mean()) if (joined['pnl'] > 0).any() else 0
    avg_pct_loss = float(joined.loc[joined['pnl'] < 0, 'pct_return'].mean()) if (joined['pnl'] < 0).any() else 0
    # Extract per-trade theoretical risk in the same order as pnl_distribution
    per_trade_theoretical_risk = joined['theoretical_max_loss'].tolist()
    # Extract per-trade theoretical reward in the same order as pnl_distribution
    per_trade_theoretical_reward = joined['theoretical_max_gain'].tolist()
    # Extract per-trade dates (opening date for each trade) in same order
    per_trade_dates = [d.strftime('%Y-%m-%d') for d in joined['open_date']]
    # Extract per-trade close dates in same order (None if not available)
    per_trade_close_dates = [
        d.strftime('%Y-%m-%d') if not pd.isna(d) else None
        for d in joined['close_date']
    ]
    raw_trade_data = []
    for trade_key in joined.index:
        # Get all rows for this trade (matched by composite key)
        trade_rows = df[df['_trade_key'] == trade_key].copy()
        # Extract the expiration from the trade rows
        expiration = trade_rows['Expiration'].iloc[0] if not trade_rows.empty else trade_key.split('|')[0]
        
        # Separate opening and closing legs
        opening_legs = trade_rows[trade_rows['Description'].fillna('').str.contains('Open')].copy()
        closing_legs = trade_rows[~trade_rows['Description'].fillna('').str.contains('Open') & 
                                  trade_rows['Profit/Loss'].notna()].copy()
        
        # Convert each row to a dict with formatted values
        def format_row(row):
            # Clean stock price (may have $ and comma)
            def clean_display_price(value):
                if pd.isna(value):
                    return ''
                if isinstance(value, str):
                    value = value.replace('$', '').replace(',', '').strip()
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return ''
                return float(value)
            
            stock_price = clean_display_price(row['Stock Price'])
            
            return {
                'date': row['Date'].strftime('%Y-%m-%d'),
                'description': str(row['Description']),
                'size': int(row['Size']) if pd.notna(row['Size']) else '',
                'symbol': str(row['Symbol']) if pd.notna(row['Symbol']) else '',
                'strike': float(row['Strike']) if pd.notna(row['Strike']) else '',
                'type': str(row['Type']) if pd.notna(row['Type']) else '',
                'trade_price': f"${row['Trade Price']:.2f}" if pd.notna(row['Trade Price']) else '',
                'profit_loss': f"${row['Profit/Loss']:.0f}" if pd.notna(row['Profit/Loss']) else '',
                'stock_price': f"${stock_price:.2f}" if stock_price != '' else '',
            }
        
        expiration_str = expiration.strftime('%Y-%m-%d') if isinstance(expiration, pd.Timestamp) else pd.to_datetime(expiration).strftime('%Y-%m-%d')
        trade_data = {
            'expiration': expiration_str,
            'opening_legs': [format_row(row) for _, row in opening_legs.iterrows()],
            'closing_legs': [format_row(row) for _, row in closing_legs.iterrows()]
        }
        raw_trade_data.append(trade_data)
    
    wins = pnl_values[pnl_values > 0]
    losses = pnl_values[pnl_values < 0]
    median_win = float(np.median(wins)) if len(wins) > 0 else 0
    median_loss = float(np.median(losses)) if len(losses) > 0 else 0
    median_risk_per_spread = abs(median_loss)
    median_reward_per_spread = float(np.median(per_trade_theoretical_reward))
    conservative_realized_max_reward = float(np.quantile(wins, 0.95)) if len(wins) > 0 else 0
    
    # Calculate average risk and reward per spread
    avg_risk_per_spread = float(np.mean(per_trade_theoretical_risk))
    avg_reward_per_spread = float(np.mean(per_trade_theoretical_reward))
    
    # Calculate median win/loss as percentage of average theoretical risk
    # Note: avg_risk_per_spread should never be 0 since we calculated it from per_trade_theoretical_risk
    # If it is 0, we have invalid data and should fail fast
    median_win_pct = median_win / avg_risk_per_spread * 100
    median_loss_pct = median_loss / avg_risk_per_spread * 100
    
    # Calculate max win/loss as percentage of PER-TRADE theoretical risk
    # Use the pct_return already calculated in joined dataframe (pnl / theoretical_max_loss * 100)
    max_win_pct = float(joined.loc[joined['pnl'] > 0, 'pct_return'].max()) if (joined['pnl'] > 0).any() else 0.0
    max_loss_pct = float(joined.loc[joined['pnl'] < 0, 'pct_return'].min()) if (joined['pnl'] < 0).any() else 0.0
    
    stats = {
        'num_trades': len(pnl_values),
        'win_rate': len(wins) / len(pnl_values) if len(pnl_values) > 0 else 0,
        'avg_win': np.mean(wins) if len(wins) > 0 else 0,
        'avg_loss': np.mean(losses) if len(losses) > 0 else 0,
        'median_win': median_win,
        'median_loss': median_loss,
        'median_risk_per_spread': median_risk_per_spread,
        'median_reward_per_spread': median_reward_per_spread,
        'median_win_pct': median_win_pct,
        'median_loss_pct': median_loss_pct,
        'max_win': np.max(wins) if len(wins) > 0 else 0,
        'max_loss': np.min(losses) if len(losses) > 0 else 0,  # Most negative
        'max_theoretical_loss': max_theoretical_loss,
        'conservative_theoretical_max_loss': conservative_theoretical_max_loss,
        'max_theoretical_gain': max_theoretical_gain,
        'conservative_theoretical_max_reward': conservative_theoretical_max_reward,
        'conservative_realized_max_reward': conservative_realized_max_reward,
        'avg_risk_per_spread': avg_risk_per_spread,
        'avg_reward_per_spread': avg_reward_per_spread,
        'max_win_pct': max_win_pct,
        'max_loss_pct': max_loss_pct,
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
        # Use chronologically-ordered P/L from joined dataframe to ensure alignment with dates
        # joined is guaranteed to be non-empty at this point (error raised earlier if not)
        'pnl_distribution': joined['pnl'].tolist(),
        'per_trade_theoretical_risk': per_trade_theoretical_risk,
        'per_trade_theoretical_reward': per_trade_theoretical_reward,
        'per_trade_dates': per_trade_dates,
        'per_trade_close_dates': per_trade_close_dates,
        'signal_stats': compute_signal_stats(
            per_trade_dates, per_trade_close_dates, joined['pnl'].tolist()
        ),
        'raw_trade_data': raw_trade_data,
        'min_date': min_date,
        'max_date': max_date
    }
    
    return stats