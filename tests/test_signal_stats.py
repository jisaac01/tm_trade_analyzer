"""
Tests for compute_signal_stats in trade_parser.py.

ALL expected values are derived from first principles (NYSE calendar arithmetic),
NOT from running the current code and asserting its output.

Test scenario: 4 trades, given to the parser in jumbled order (B, D, A, C),
expected to be sorted by open_date before analysis.

NYSE trading days in Jan 2023 (relevant range):
  Jan 03=idx0, Jan 04=idx1, Jan 05=idx2, Jan 06=idx3, Jan 09=idx4,
  Jan 10=idx5, Jan 11=idx6, Jan 12=idx7, Jan 13=idx8, Jan 17=idx9,
  Jan 18=idx10, Jan 19=idx11, Jan 20=idx12, Jan 23=idx13, Jan 24=idx14,
  Jan 25=idx15

Trades (sorted by open_date):
  A: open 2023-01-03 (Tue, idx=0), close 2023-01-13 (Fri, idx=8),  P/L = +$150 [Win]
  B: open 2023-01-04 (Wed, idx=1), close 2023-01-06 (Fri, idx=3),  P/L = +$100 [Win]
  C: open 2023-01-11 (Wed, idx=6), close 2023-01-20 (Fri, idx=12), P/L = -$50  [Loss]
  D: open 2023-01-17 (Tue, idx=9), close 2023-01-25 (Wed, idx=15), P/L = +$75  [Win]

Gaps between consecutive opens: A→B=1, B→C=5, C→D=3
Run positions: A=1, B=2 (seq after A), C=1 (new run), D=1 (new run)

Overlapping:
  B overlaps A (Jan 04 ∈ (Jan03, Jan13])     → B is also sequential (run_pos=2)
  C overlaps A (Jan 11 ∈ (Jan03, Jan13])     → C is NOT sequential (run_pos=1)
  D overlaps C (Jan 17 ∈ (Jan11, Jan20])     → D is NOT sequential (run_pos=1)

Weekday:
  A (Jan 03) = Tuesday  (weekday 1)
  B (Jan 04) = Wednesday (weekday 2)
  C (Jan 11) = Wednesday (weekday 2)
  D (Jan 17) = Tuesday  (weekday 1)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import trade_parser


OVERLAPPING_CSV = 'tests/test_data/test_overlapping_trades.csv'

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
        B overlaps A (Jan 04 ∈ (Jan03, Jan13]).
        C overlaps A (Jan 11 ∈ (Jan03, Jan13]).
        D overlaps C (Jan 17 ∈ (Jan11, Jan20]).
        Expected: 3 overlapping signals.
        """
        ss = get_signal_stats()
        assert ss['overlapping_signal_count'] == 3

    def test_overlapping_non_sequential_count(self):
        """
        Overlapping but NOT sequential: C and D (run_pos=1, not 2nd day of a run).
        B is overlapping but IS sequential (run_pos=2) → excluded.
        Expected: 2.
        """
        ss = get_signal_stats()
        assert ss['overlapping_non_sequential']['count'] == 2

    def test_overlapping_non_sequential_wins_losses(self):
        """
        C = -$50 (loss), D = +$75 (win).
        Expected: 1 win, 1 loss.
        """
        ons = get_signal_stats()['overlapping_non_sequential']
        assert ons['wins'] == 1
        assert ons['losses'] == 1

    def test_overlapping_non_sequential_pnl(self):
        """
        C(-50) + D(+75) = +$25 total P/L.
        """
        ons = get_signal_stats()['overlapping_non_sequential']
        assert abs(ons['pnl'] - 25.0) < 0.01


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
