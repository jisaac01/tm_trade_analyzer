"""
Tests for compute_signal_stats in trade_parser.py.

ALL expected values are derived from first principles (NYSE calendar arithmetic),
NOT from running the current code and asserting its output.

--- test_overlapping_trades.csv (OVERLAPPING_CSV) ---

File row order (jumbled): B (Jan 4), D (Jan 17), A (Jan 3), C (Jan 11).
parse_trade_csv sorts internally before analysis.

With PRIMARY DETECTION (new): trades are marked primary if their open_date is
>= all previously-seen open dates as they appear in file order.
  File order primary check:
    B (Jan 4): first seen → primary, max_seen = Jan 4
    D (Jan 17): Jan 17 >= Jan 4 → primary, max_seen = Jan 17
    A (Jan 3):  Jan 3  < Jan 17 → SECONDARY
    C (Jan 11): Jan 11 < Jan 17 → SECONDARY
  has_secondary = True → primary logic applies.
  Primary trades (B, D) are NEVER marked overlapping.

Sorted order for overlap / gap analysis:
  A (secondary, Jan 3,  idx 0): no prior trade → not overlapping
  B (primary,   Jan 4,  idx 1): primary → skip for overlap check
  C (secondary, Jan 11, idx 6): Jan 11 ∈ (A.open Jan3, A.close Jan13] → overlapping
  D (primary,   Jan 17, idx 9): primary → skip for overlap check

New overlap result:
  overlapping_signal_count = 1  (C only)
  overlapping_non_sequential  = {C}: count=1, wins=0, losses=1, pnl=-50
  overlapping_total           = {C}: count=1, wins=0, losses=1, pnl=-50
  sequential_total            = {B}: count=1, wins=1, losses=0, pnl=+100
   (sequential detection is independent of primary status)

Gaps between consecutive opens (sorted): A→B=1, B→C=5, C→D=3
Run positions: A=1, B=2 (seq after A), C=1, D=1

per_trade_overlap_type (in input/file order B,D,A,C → indices 0,1,2,3):
  B (idx 0): 'sequential'
  D (idx 1): ''
  A (idx 2): ''
  C (idx 3): 'overlapping_non_sequential'

Weekday:
  A (Jan 03) = Tuesday  (weekday 1)
  B (Jan 04) = Wednesday (weekday 2)
  C (Jan 11) = Wednesday (weekday 2)
  D (Jan 17) = Tuesday  (weekday 1)

--- test_primary_overlapping_trades.csv (PRIMARY_CSV) ---

Simulates merge_backtests.py output: a primary (chronological) block followed
by a secondary (non-chronological, appended-at-end) block.

File row order: P1 (Jan 3), P2 (Jan 23), S1 (Jan 4*), S2 (Jan 11*)
  * non-chronological: appended after P2 whose open_date is Jan 23

Primary detection:
  P1 (Jan 3):  primary, max_seen = Jan 3
  P2 (Jan 23): primary, max_seen = Jan 23
  S1 (Jan 4):  Jan 4  < Jan 23 → SECONDARY
  S2 (Jan 11): Jan 11 < Jan 23 → SECONDARY
  has_secondary = True → primary logic applies.

Sorted for analysis: P1 (prim, Jan3), S1 (sec, Jan4), S2 (sec, Jan11), P2 (prim, Jan23)
Gaps: P1→S1=1 (sequential!), S1→S2=5, S2→P2=8

Overlap check (primary → skip):
  S1 (sec): Jan4 ∈ (P1.open Jan3, P1.close Jan13] → overlapping; run_pos=2 → 'sequential_and_overlapping'
  S2 (sec): Jan11 ∈ (P1.open Jan3, P1.close Jan13] → overlapping; run_pos=1 → 'overlapping_non_sequential'

P/L:
  P1=+150, P2=-75, S1=+80, S2=-30
  primary_pnl    = +150 + (-75) = +75
  overlapping_pnl = +80 + (-30) = +50
  total_pnl       = +125
  total_pnl - overlapping_pnl = +75 = primary_pnl  ← key consistency check
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import trade_parser


OVERLAPPING_CSV = 'tests/test_data/test_overlapping_trades.csv'
PRIMARY_CSV     = 'tests/test_data/test_primary_overlapping_trades.csv'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_signal_stats():
    stats = trade_parser.parse_trade_csv(OVERLAPPING_CSV)
    return stats['signal_stats']


# ---------------------------------------------------------------------------
# parse_trade_csv integration: per_trade_close_dates is populated
# ---------------------------------------------------------------------------

class TestPerTradeCloseDates:
    def test_per_trade_close_dates_present(self):
        """parse_trade_csv must include per_trade_close_dates in output."""
        stats = trade_parser.parse_trade_csv(OVERLAPPING_CSV)
        assert 'per_trade_close_dates' in stats

    def test_per_trade_close_dates_length_matches_pnl(self):
        """per_trade_close_dates must have same length as pnl_distribution."""
        stats = trade_parser.parse_trade_csv(OVERLAPPING_CSV)
        assert len(stats['per_trade_close_dates']) == len(stats['pnl_distribution'])

    def test_per_trade_close_dates_are_iso_strings(self):
        """Each close date must be a 'YYYY-MM-DD' string."""
        stats = trade_parser.parse_trade_csv(OVERLAPPING_CSV)
        for d in stats['per_trade_close_dates']:
            assert d is not None
            # Attempt ISO parse - raises ValueError if format is wrong
            from datetime import date
            date.fromisoformat(d)  # will raise if not valid

    def test_close_dates_after_open_dates(self):
        """Every trade's close date must be >= its open date."""
        from datetime import date
        stats = trade_parser.parse_trade_csv(OVERLAPPING_CSV)
        for open_d, close_d in zip(stats['per_trade_dates'], stats['per_trade_close_dates']):
            assert date.fromisoformat(close_d) >= date.fromisoformat(open_d)


# ---------------------------------------------------------------------------
# parse_trade_csv integration: signal_stats is populated
# ---------------------------------------------------------------------------

class TestSignalStatsPresent:
    def test_signal_stats_in_output(self):
        """parse_trade_csv must include signal_stats in output."""
        stats = trade_parser.parse_trade_csv(OVERLAPPING_CSV)
        assert 'signal_stats' in stats

    def test_signal_stats_has_required_keys(self):
        """signal_stats must contain all required keys."""
        ss = get_signal_stats()
        required_keys = [
            'sequential_signal_count',
            'overlapping_signal_count',
            'max_sequential_run',
            'max_gap_trading_days',
            'median_gap_trading_days',
            'sequential_by_position',
            'overlapping_non_sequential',
            'signals_by_weekday',
            'total_signals',
            'gaps',
        ]
        for key in required_keys:
            assert key in ss, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# compute_signal_stats: direct API
# ---------------------------------------------------------------------------

class TestComputeSignalStatsDirectAPI:
    """Tests calling compute_signal_stats directly with known inputs."""

    def test_empty_inputs_returns_safe_defaults(self):
        """Empty inputs should return zeroed-out struct without error."""
        ss = trade_parser.compute_signal_stats([], [], [])
        assert ss['sequential_signal_count'] == 0
        assert ss['overlapping_signal_count'] == 0
        assert ss['max_sequential_run'] == 0
        assert ss['total_signals'] == 0

    def test_single_trade_no_sequential_no_overlap(self):
        """Single trade: no sequential/overlap signals possible."""
        ss = trade_parser.compute_signal_stats(
            ['2023-01-03'],
            ['2023-01-13'],
            [150.0]
        )
        assert ss['sequential_signal_count'] == 0
        assert ss['overlapping_signal_count'] == 0
        assert ss['max_sequential_run'] == 1
        assert ss['gaps'] == []
        assert ss['total_signals'] == 1


# ---------------------------------------------------------------------------
# Sequential signal detection
# ---------------------------------------------------------------------------

class TestSequentialSignals:
    def test_sequential_signal_count(self):
        """
        Only Trade B opens on the next NYSE trading day after Trade A.
        B→C gap = 5 days (not sequential), C→D gap = 3 days (not sequential).
        Expected: 1 sequential signal (B only).
        """
        ss = get_signal_stats()
        assert ss['sequential_signal_count'] == 1

    def test_max_sequential_run(self):
        """
        Longest sequential run is [A, B] (2 consecutive trading days).
        Expected: 2.
        """
        ss = get_signal_stats()
        assert ss['max_sequential_run'] == 2

    def test_sequential_by_position_keys(self):
        """
        Only position 2 is present (B is the 2nd in the A→B run).
        Positions 3+ should not appear.
        """
        ss = get_signal_stats()
        by_pos = ss['sequential_by_position']
        assert 2 in by_pos
        assert 3 not in by_pos

    def test_sequential_position_2_count(self):
        """Position 2 has exactly 1 signal (Trade B)."""
        ss = get_signal_stats()
        assert ss['sequential_by_position'][2]['count'] == 1

    def test_sequential_position_2_win_loss(self):
        """
        Trade B (P/L = +$100) is the only sequential-day-2 signal.
        Expected: 1 win, 0 losses.
        """
        ss = get_signal_stats()
        pos2 = ss['sequential_by_position'][2]
        assert pos2['wins'] == 1
        assert pos2['losses'] == 0

    def test_sequential_position_2_pnl(self):
        """
        Trade B = +$100. That's the entire P/L for position 2.
        """
        ss = get_signal_stats()
        assert abs(ss['sequential_by_position'][2]['pnl'] - 100.0) < 0.01


# ---------------------------------------------------------------------------
# Overlapping signal detection
# ---------------------------------------------------------------------------

class TestOverlappingSignals:
    def test_overlapping_signal_count(self):
        """
        With primary detection applied to test_overlapping_trades.csv:
          File order: B(Jan4), D(Jan17), A(Jan3), C(Jan11)
          Primary: B, D. Secondary: A, C.
          Only secondary trades can be overlapping.
          A (secondary): no prior open trade → not overlapping.
          C (secondary): Jan 11 ∈ (A.open Jan3, A.close Jan13] → overlapping.
          B and D (primary): never overlapping.
        Expected: 1.
        """
        ss = get_signal_stats()
        assert ss['overlapping_signal_count'] == 1

    def test_overlapping_non_sequential_count(self):
        """
        C is overlapping and has run_pos=1 (not sequential) → non-sequential overlap.
        Expected: 1.
        """
        ss = get_signal_stats()
        assert ss['overlapping_non_sequential']['count'] == 1

    def test_overlapping_non_sequential_wins_losses(self):
        """
        C = -$50 (loss) only. Expected: 0 wins, 1 loss.
        """
        ons = get_signal_stats()['overlapping_non_sequential']
        assert ons['wins'] == 0
        assert ons['losses'] == 1

    def test_overlapping_non_sequential_pnl(self):
        """
        C only: P/L = -$50.
        """
        ons = get_signal_stats()['overlapping_non_sequential']
        assert abs(ons['pnl'] - (-50.0)) < 0.01


# ---------------------------------------------------------------------------
# Gap statistics
# ---------------------------------------------------------------------------

class TestGapStatistics:
    def test_gaps_list_length(self):
        """
        4 trades → 3 consecutive gaps (A→B, B→C, C→D).
        """
        ss = get_signal_stats()
        assert len(ss['gaps']) == 3

    def test_gap_a_to_b_is_sequential(self):
        """
        A (Jan 03) → B (Jan 04): 1 NYSE trading day apart.
        gap = 1 (sequential).
        """
        ss = get_signal_stats()
        assert ss['gaps'][0] == 1

    def test_gap_b_to_c(self):
        """
        B (Jan 04, idx=1) → C (Jan 11, idx=6): gap = 6 - 1 = 5.
        NYSE days between: Jan 05, 06, 09, 10 = 4 days between them,
        but ordinal distance = 5 positions apart.
        """
        ss = get_signal_stats()
        assert ss['gaps'][1] == 5

    def test_gap_c_to_d(self):
        """
        C (Jan 11, idx=6) → D (Jan 17, idx=9): gap = 9 - 6 = 3.
        (Jan 16 is MLK Day holiday, so Jan 17 is 3 positions after Jan 11.)
        """
        ss = get_signal_stats()
        assert ss['gaps'][2] == 3

    def test_max_gap(self):
        """gaps = [1, 5, 3]. max = 5."""
        ss = get_signal_stats()
        assert ss['max_gap_trading_days'] == 5

    def test_median_gap(self):
        """gaps = [1, 5, 3]. sorted = [1, 3, 5]. median = 3."""
        ss = get_signal_stats()
        assert ss['median_gap_trading_days'] == 3.0


# ---------------------------------------------------------------------------
# Weekday distribution
# ---------------------------------------------------------------------------

class TestWeekdayDistribution:
    def test_weekday_keys_are_0_to_4(self):
        """signals_by_weekday must have keys 0-4 (Mon-Fri)."""
        ss = get_signal_stats()
        assert set(ss['signals_by_weekday'].keys()) == {0, 1, 2, 3, 4}

    def test_tuesday_count(self):
        """
        A (Jan 03 = Tue) and D (Jan 17 = Tue): 2 signals on Tuesday.
        """
        ss = get_signal_stats()
        assert ss['signals_by_weekday'][1]['count'] == 2  # Tuesday = weekday 1

    def test_wednesday_count(self):
        """
        B (Jan 04 = Wed) and C (Jan 11 = Wed): 2 signals on Wednesday.
        """
        ss = get_signal_stats()
        assert ss['signals_by_weekday'][2]['count'] == 2  # Wednesday = weekday 2

    def test_monday_zero_count(self):
        """No signals fell on a Monday in this dataset."""
        ss = get_signal_stats()
        assert ss['signals_by_weekday'][0]['count'] == 0

    def test_tuesday_pct(self):
        """2 of 4 signals on Tuesday = 50.0%."""
        ss = get_signal_stats()
        assert abs(ss['signals_by_weekday'][1]['pct'] - 50.0) < 0.01

    def test_tuesday_wins_and_losses(self):
        """
        A (+$150 win) and D (+$75 win) both on Tuesday.
        Expected: 2 wins, 0 losses.
        """
        ss = get_signal_stats()
        tue = ss['signals_by_weekday'][1]
        assert tue['wins'] == 2
        assert tue['losses'] == 0

    def test_wednesday_wins_and_losses(self):
        """
        B (+$100 win) and C (-$50 loss) both on Wednesday.
        Expected: 1 win, 1 loss.
        """
        ss = get_signal_stats()
        wed = ss['signals_by_weekday'][2]
        assert wed['wins'] == 1
        assert wed['losses'] == 1

    def test_tuesday_pnl(self):
        """A($150) + D($75) = $225 total P/L on Tuesday."""
        ss = get_signal_stats()
        assert abs(ss['signals_by_weekday'][1]['pnl'] - 225.0) < 0.01

    def test_wednesday_pnl(self):
        """B($100) + C(-$50) = $50 total P/L on Wednesday."""
        ss = get_signal_stats()
        assert abs(ss['signals_by_weekday'][2]['pnl'] - 50.0) < 0.01

    def test_weekday_names_present(self):
        """Each weekday entry must have a 'name' field."""
        ss = get_signal_stats()
        expected_names = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday'}
        for wd, expected_name in expected_names.items():
            assert ss['signals_by_weekday'][wd]['name'] == expected_name

    def test_total_signals(self):
        """total_signals = 4 (all trades in CSV)."""
        ss = get_signal_stats()
        assert ss['total_signals'] == 4

    def test_weekday_counts_sum_to_total(self):
        """Sum of all weekday counts must equal total_signals."""
        ss = get_signal_stats()
        total = sum(v['count'] for v in ss['signals_by_weekday'].values())
        assert total == ss['total_signals']


# ---------------------------------------------------------------------------
# Longer sequential run (3+ days)
# ---------------------------------------------------------------------------

class TestLongerSequentialRun:
    """
    3-trade run on consecutive NYSE days: Jan 03, 04, 05.
    Expected: sequential_signal_count=2, max_sequential_run=3.
    sequential_by_position = {2: {count=1, ...}, 3: {count=1, ...}}
    """

    def _stats_for_three_day_run(self):
        # Trade X: open Jan 03, close Jan 10, P/L = +$50 (Win)
        # Trade Y: open Jan 04, close Jan 11, P/L = -$30 (Loss)
        # Trade Z: open Jan 05, close Jan 12, P/L = +$20 (Win)
        return trade_parser.compute_signal_stats(
            ['2023-01-03', '2023-01-04', '2023-01-05'],
            ['2023-01-10', '2023-01-11', '2023-01-12'],
            [50.0, -30.0, 20.0]
        )

    def test_three_consecutive_days_sequential_count(self):
        """
        X→Y gap=1, Y→Z gap=1: both Y and Z are sequential.
        Expected: sequential_signal_count = 2.
        """
        ss = self._stats_for_three_day_run()
        assert ss['sequential_signal_count'] == 2

    def test_three_consecutive_days_max_run(self):
        """Run of 3 consecutive days. max_sequential_run = 3."""
        ss = self._stats_for_three_day_run()
        assert ss['max_sequential_run'] == 3

    def test_three_consecutive_days_position_2_present(self):
        """Position 2 (Y) must be in sequential_by_position."""
        ss = self._stats_for_three_day_run()
        assert 2 in ss['sequential_by_position']

    def test_three_consecutive_days_position_3_present(self):
        """Position 3 (Z) must be in sequential_by_position."""
        ss = self._stats_for_three_day_run()
        assert 3 in ss['sequential_by_position']

    def test_position_2_stats_in_three_day_run(self):
        """
        Y = -$30 (loss). Position 2: count=1, wins=0, losses=1, pnl=-30.
        """
        ss = self._stats_for_three_day_run()
        p2 = ss['sequential_by_position'][2]
        assert p2['count'] == 1
        assert p2['wins'] == 0
        assert p2['losses'] == 1
        assert abs(p2['pnl'] - (-30.0)) < 0.01

    def test_position_3_stats_in_three_day_run(self):
        """
        Z = +$20 (win). Position 3: count=1, wins=1, losses=0, pnl=+20.
        """
        ss = self._stats_for_three_day_run()
        p3 = ss['sequential_by_position'][3]
        assert p3['count'] == 1
        assert p3['wins'] == 1
        assert p3['losses'] == 0
        assert abs(p3['pnl'] - 20.0) < 0.01

    def test_three_day_run_overlapping_count(self):
        """
        Y overlaps X (Jan 04 ∈ (Jan03, Jan10]).
        Z overlaps X (Jan 05 ∈ (Jan03, Jan10]) AND overlaps Y (Jan05 ∈ (Jan04, Jan11]).
        But we count overlapping at the TRADE level (not pair level): Y and Z are each overlapping.
        Expected: overlapping_signal_count = 2.
        """
        ss = self._stats_for_three_day_run()
        assert ss['overlapping_signal_count'] == 2

    def test_three_day_run_overlapping_non_sequential_is_zero(self):
        """
        All overlapping trades (Y and Z) are also sequential.
        So overlapping_non_sequential count = 0.
        """
        ss = self._stats_for_three_day_run()
        assert ss['overlapping_non_sequential']['count'] == 0


# ---------------------------------------------------------------------------
# sequential_total and overlapping_total (OVERLAPPING_CSV)
# ---------------------------------------------------------------------------

class TestSequentialTotal:
    """
    sequential_total accumulates P/L across all sequential-day trades.
    For test_overlapping_trades.csv with primary detection:
      Sequential = {B}: B opened Jan 4 (next NYSE day after A Jan 3), run_pos=2.
      B = +$100 (Win).
    """

    def test_sequential_total_count(self):
        """Only B is sequential. Expected: count=1."""
        ss = get_signal_stats()
        assert ss['sequential_total']['count'] == 1

    def test_sequential_total_wins_losses(self):
        """B is a win (+$100). Expected: 1 win, 0 losses."""
        st = get_signal_stats()['sequential_total']
        assert st['wins'] == 1
        assert st['losses'] == 0

    def test_sequential_total_pnl(self):
        """B = +$100. Expected pnl = +100."""
        st = get_signal_stats()['sequential_total']
        assert abs(st['pnl'] - 100.0) < 0.01


class TestOverlappingTotal:
    """
    overlapping_total accumulates P/L across ALL overlapping trades
    (sequential + non-sequential).
    For test_overlapping_trades.csv with primary detection:
      Only C is overlapping → count=1, pnl=-50.
    """

    def test_overlapping_total_count(self):
        """Only C is overlapping. Expected: count=1."""
        ss = get_signal_stats()
        assert ss['overlapping_total']['count'] == 1

    def test_overlapping_total_wins_losses(self):
        """C = -$50 (loss). Expected: 0 wins, 1 loss."""
        ot = get_signal_stats()['overlapping_total']
        assert ot['wins'] == 0
        assert ot['losses'] == 1

    def test_overlapping_total_pnl(self):
        """C = -$50. Expected pnl = -50."""
        ot = get_signal_stats()['overlapping_total']
        assert abs(ot['pnl'] - (-50.0)) < 0.01


class TestPerTradeOverlapType:
    """
    per_trade_overlap_type is mapped back to original input order.
    For parse_trade_csv on test_overlapping_trades.csv:
      per_trade_dates / pnl_distribution are in open_date-sorted order: A, B, C, D.
      A = '' (secondary, not overlapping)
      B = 'sequential' (primary, sequential — but NOT overlapping)
      C = 'overlapping_non_sequential' (secondary, overlapping, not sequential)
      D = '' (primary, not sequential, not overlapping)
    """

    def test_per_trade_overlap_type_length(self):
        """Must have same length as pnl_distribution."""
        stats = trade_parser.parse_trade_csv(OVERLAPPING_CSV)
        assert len(stats['signal_stats']['per_trade_overlap_type']) == len(stats['pnl_distribution'])

    def test_per_trade_overlap_type_values(self):
        """
        Sorted order (open_date order): A(Jan3), B(Jan4), C(Jan11), D(Jan17).
        Expected types: ['', 'sequential', 'overlapping_non_sequential', ''].
        """
        stats = trade_parser.parse_trade_csv(OVERLAPPING_CSV)
        types = stats['signal_stats']['per_trade_overlap_type']
        # Verify A, B, C, D in order
        assert types[0] == '', f"A expected '', got {types[0]!r}"
        assert types[1] == 'sequential', f"B expected 'sequential', got {types[1]!r}"
        assert types[2] == 'overlapping_non_sequential', f"C expected 'overlapping_non_sequential', got {types[2]!r}"
        assert types[3] == '', f"D expected '', got {types[3]!r}"


# ---------------------------------------------------------------------------
# Primary overlap detection: test_primary_overlapping_trades.csv
# ---------------------------------------------------------------------------

class TestPrimaryOverlapDetection:
    """
    test_primary_overlapping_trades.csv simulates a merge_backtests.py output:
      Primary block (chronological): P1 (Jan 3), P2 (Jan 23)
      Secondary block (appended, non-chronological): S1 (Jan 4), S2 (Jan 11)

    Expected:
      P/L values: P1=+150, P2=-75, S1=+80, S2=-30
      Primary P&L = P1+P2 = +75
      Overlapping P&L = S1+S2 = +50
      total - overlapping = primary (key user scenario)

      overlapping_signal_count = 2 (S1 and S2 only; P1 and P2 are primary)
      sequential_signal_count = 1 (S1: opens Jan4, 1 NYSE day after P1 Jan3)
      sequential_total: count=1, wins=1, pnl=+80
      overlapping_non_sequential: count=1 (S2), wins=0, losses=1, pnl=-30
      overlapping_total: count=2, wins=1, losses=1, pnl=+50
    """

    def _stats(self):
        return trade_parser.parse_trade_csv(PRIMARY_CSV)

    def _ss(self):
        return self._stats()['signal_stats']

    def test_total_signals(self):
        """4 trades total (P1, P2, S1, S2)."""
        assert self._ss()['total_signals'] == 4

    def test_overlapping_signal_count(self):
        """
        Only secondary trades S1 and S2 can be overlapping.
        Both open while P1 (Jan3–Jan13) is still open.
        Expected: 2.
        """
        assert self._ss()['overlapping_signal_count'] == 2

    def test_primary_trades_not_overlapping(self):
        """
        P1 and P2 are primary → their overlap_type must not contain 'overlapping'.
        In sorted order: P1(idx0)='', S1(idx1)=sequential_and_overlapping,
        S2(idx2)=overlapping_non_sequential, P2(idx3)=''.
        """
        stats = self._stats()
        types = stats['signal_stats']['per_trade_overlap_type']
        # sorted order: P1, S1, S2, P2  (open dates Jan3, Jan4, Jan11, Jan23)
        assert 'overlapping' not in types[0], f"P1 should not be overlapping, got {types[0]!r}"
        assert 'overlapping' not in types[3], f"P2 should not be overlapping, got {types[3]!r}"

    def test_secondary_trades_are_overlapping(self):
        """
        S1 (idx1) and S2 (idx2) are secondary and both overlap P1.
        """
        stats = self._stats()
        types = stats['signal_stats']['per_trade_overlap_type']
        assert 'overlapping' in types[1], f"S1 expected overlapping, got {types[1]!r}"
        assert 'overlapping' in types[2], f"S2 expected overlapping, got {types[2]!r}"

    def test_sequential_signal_count(self):
        """
        S1 opens Jan 4, 1 NYSE day after P1 Jan 3 → sequential.
        No other sequential pairs. Expected: 1.
        """
        assert self._ss()['sequential_signal_count'] == 1

    def test_sequential_total_pnl(self):
        """S1 = +$80 is the only sequential signal. Expected pnl = +80."""
        st = self._ss()['sequential_total']
        assert st['count'] == 1
        assert st['wins'] == 1
        assert abs(st['pnl'] - 80.0) < 0.01

    def test_overlapping_total(self):
        """
        Overlapping (all) = {S1, S2}: count=2, wins=1(S1), losses=1(S2), pnl=+50.
        """
        ot = self._ss()['overlapping_total']
        assert ot['count'] == 2
        assert ot['wins'] == 1
        assert ot['losses'] == 1
        assert abs(ot['pnl'] - 50.0) < 0.01

    def test_overlapping_non_sequential(self):
        """
        S2 is overlapping and non-sequential (gap S1→S2 = 5 days).
        S2 = -$30 (loss). Expected: count=1, pnl=-30.
        """
        ons = self._ss()['overlapping_non_sequential']
        assert ons['count'] == 1
        assert ons['wins'] == 0
        assert ons['losses'] == 1
        assert abs(ons['pnl'] - (-30.0)) < 0.01

    def test_pnl_consistency(self):
        """
        Core user scenario: total_pnl - overlapping_pnl should equal primary_pnl.
        Primary P&L = P1(+150) + P2(-75) = +75.
        Overlapping P&L (from overlapping_total) = S1(+80) + S2(-30) = +50.
        Total P&L = +125.
        +125 - +50 = +75 = primary P&L.
        """
        stats = self._stats()
        total_pnl = sum(stats['pnl_distribution'])
        overlapping_pnl = stats['signal_stats']['overlapping_total']['pnl']
        expected_primary_pnl = 75.0
        residual = total_pnl - overlapping_pnl
        assert abs(residual - expected_primary_pnl) < 0.01, (
            f"total({total_pnl}) - overlapping({overlapping_pnl}) = {residual}, "
            f"expected primary P&L {expected_primary_pnl}"
        )


# ---------------------------------------------------------------------------
# All-chronological file → primary marking discarded, classic behavior intact
# ---------------------------------------------------------------------------

class TestAllChronologicalDiscardsPrimary:
    """
    When all per_trade_is_primary flags are True (or when the input list is
    chronological so no secondary trades exist), compute_signal_stats must
    discard primary marking and produce identical results to calling without it.
    """

    def _base_stats(self):
        return trade_parser.compute_signal_stats(
            ['2023-01-03', '2023-01-04', '2023-01-11', '2023-01-17'],
            ['2023-01-13', '2023-01-06', '2023-01-20', '2023-01-25'],
            [150.0, 100.0, -50.0, 75.0]
        )

    def _stats_all_primary(self):
        return trade_parser.compute_signal_stats(
            ['2023-01-03', '2023-01-04', '2023-01-11', '2023-01-17'],
            ['2023-01-13', '2023-01-06', '2023-01-20', '2023-01-25'],
            [150.0, 100.0, -50.0, 75.0],
            per_trade_is_primary=[True, True, True, True]
        )

    def test_overlapping_count_same_with_all_primary(self):
        """
        All-primary → discard primary marking → same overlap count as no-primary.
        Classic behavior: B, C, D all overlap → count=3.
        """
        assert self._base_stats()['overlapping_signal_count'] == 3
        assert self._stats_all_primary()['overlapping_signal_count'] == 3

    def test_sequential_count_same_with_all_primary(self):
        """Sequential count unchanged when all-primary (marking discarded)."""
        assert (
            self._base_stats()['sequential_signal_count']
            == self._stats_all_primary()['sequential_signal_count']
        )
