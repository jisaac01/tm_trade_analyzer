#!/usr/bin/env python3
"""
merge_backtests.py — Merge overlapping backtest CSV files into a master file.

Usage:
    python scripts/merge_backtests.py <new_file.csv> \\
        --start-date 2022-11-16 \\
        [--master <scripts>/master_trades.csv] \\
        [--registry <scripts>/backtest_registry.json] \\
        [--raw-dir <scripts>/raw/] \\
        [--diff-dir <scripts>/diffs/]

What it does:
  1. Parses the new backtest CSV into trade groups (open+close leg pairs).
  2. Deduplicates against the master CSV by trade identity key
     (open_date, expiration, long_strike, short_strike).
  3. Appends unique new trades to the master CSV.
  4. Updates a JSON registry with this backtest's start date and trade intervals
     (idempotent — re-running the same file replaces its registry entry).
  5. Computes covered NYSE trading days across ALL registry backtests and
     reports the first uncovered day. The coverage window always starts from
     the earliest --start-date ever recorded in the registry.

Coverage rules (conservative):
  - [start_date ... first_open - 1 trading day]  : covered (watching, no signal)
  - Each trade's open day                        : covered (signal fired)
  - [close + 1 ... next_open - 1]               : covered (gap, watching again)
  - Trade close day                              : NOT covered
  - Days while a trade is open (open+1 ... close): NOT covered (backtester busy)
  - ClosingMark (partial) last trade             : open day covered, then nothing

Empirically verified: no same-day close+open exists in the example data,
so the conservative "close day NOT covered" rule is safe.
"""

import argparse
import csv
import json
import sys
from datetime import date, datetime, timedelta
from itertools import groupby
from pathlib import Path
from typing import Optional

import pandas_market_calendars as mcal  # type: ignore


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

_DATE_FMTS = ("%d-%b-%Y", "%d-%b-%y", "%Y-%m-%d")


def parse_date(s: str) -> date:
    s = s.strip()
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Cannot parse date: {s!r}")


# ---------------------------------------------------------------------------
# NYSE calendar
# ---------------------------------------------------------------------------

_nyse_calendar = None
_nyse_day_cache: dict = {}  # int (year) -> set[date]


def _nyse():
    global _nyse_calendar
    if _nyse_calendar is None:
        _nyse_calendar = mcal.get_calendar("NYSE")
    return _nyse_calendar


def _trading_days_for_year(year: int) -> set:
    if year not in _nyse_day_cache:
        sched = _nyse().schedule(
            start_date=f"{year}-01-01", end_date=f"{year}-12-31"
        )
        _nyse_day_cache[year] = {ts.date() for ts in sched.index}
    return _nyse_day_cache[year]


def is_trading_day(d: date) -> bool:
    return d in _trading_days_for_year(d.year)


def trading_days_in_range(start: date, end: date) -> list:
    """Sorted NYSE trading days in [start, end] inclusive."""
    if start > end:
        return []
    all_days: set = set()
    for y in range(start.year, end.year + 1):
        all_days |= _trading_days_for_year(y)
    return sorted(d for d in all_days if start <= d <= end)


def prev_trading_day(d: date) -> date:
    """Last NYSE trading day strictly before d."""
    c = d - timedelta(days=1)
    while not is_trading_day(c):
        c -= timedelta(days=1)
    return c


def next_trading_day(d: date) -> date:
    """First NYSE trading day strictly after d."""
    c = d + timedelta(days=1)
    while not is_trading_day(c):
        c += timedelta(days=1)
    return c


# ---------------------------------------------------------------------------
# Trade parsing
# ---------------------------------------------------------------------------


class Trade:
    """One spread position: 2 open legs + 2 close legs (or ClosingMark)."""

    def __init__(
        self,
        open_date: date,
        expiration: str,
        long_strike: str,
        short_strike: str,
        close_date: Optional[date],
        is_partial: bool,
        raw_rows: list,
    ):
        self.open_date = open_date
        self.expiration = expiration
        self.long_strike = long_strike
        self.short_strike = short_strike
        self.close_date = close_date      # None when is_partial
        self.is_partial = is_partial      # True = ClosingMark (no real close yet)
        self.raw_rows = raw_rows

    @property
    def identity_key(self) -> tuple:
        """Dedup key: same trade regardless of which backtest file it came from."""
        return (
            self.open_date.isoformat(),
            self.expiration,
            self.long_strike,
            self.short_strike,
        )

    def to_registry_dict(self) -> dict:
        return {
            "open": self.open_date.isoformat(),
            "close": self.close_date.isoformat() if self.close_date else None,
            "is_partial": self.is_partial,
        }


def _clean_rows(rows: list) -> list:
    return [{k.strip(): v.strip() for k, v in r.items()} for r in rows]


def parse_trades(csv_path: Path) -> list:
    """Parse a backtest CSV file into an ordered list of Trade objects."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = _clean_rows(list(csv.DictReader(f)))

    trades = []
    i = 0
    while i < len(rows):
        desc = rows[i].get("Description", "")
        if "Open" not in desc:
            i += 1
            continue

        # Collect all consecutive open-leg rows
        j = i
        while j < len(rows) and "Open" in rows[j].get("Description", ""):
            j += 1
        open_rows = rows[i:j]

        # Collect all consecutive close-leg rows
        k = j
        while k < len(rows):
            cd = rows[k].get("Description", "")
            if "Close" in cd or "ClosingMark" in cd:
                k += 1
            else:
                break
        close_rows = rows[j:k]

        if not close_rows:
            i = j
            continue

        open_date = parse_date(open_rows[0]["Date"])
        close_date: Optional[date] = None
        is_partial = any("ClosingMark" in r.get("Description", "") for r in close_rows)

        if not is_partial:
            close_date = parse_date(close_rows[0]["Date"])

        expiration = open_rows[0].get("Expiration", "")
        # Long leg: Size == 1, Short leg: Size == -1
        long_row = next((r for r in open_rows if r.get("Size") == "1"), open_rows[0])
        short_row = next(
            (r for r in open_rows if r.get("Size") == "-1"),
            open_rows[-1] if len(open_rows) > 1 else open_rows[0],
        )

        trades.append(
            Trade(
                open_date=open_date,
                expiration=expiration,
                long_strike=long_row.get("Strike", ""),
                short_strike=short_row.get("Strike", ""),
                close_date=close_date,
                is_partial=is_partial,
                raw_rows=open_rows + close_rows,
            )
        )
        i = k

    return trades


# ---------------------------------------------------------------------------
# Master CSV
# ---------------------------------------------------------------------------


def read_master_trades_map(master_path: Path) -> dict:
    """Return {identity_key: Trade} for all trades already in the master file."""
    if not master_path.exists():
        return {}
    try:
        return {t.identity_key: t for t in parse_trades(master_path)}
    except Exception:
        return {}


def append_to_master(master_path: Path, trades: list) -> None:
    """Append trade rows to master CSV, creating it with a header if needed."""
    if not trades:
        return
    new_rows = [r for t in trades for r in t.raw_rows]
    if not master_path.exists():
        fieldnames = list(new_rows[0].keys())
        with open(master_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(new_rows)
    else:
        with open(master_path, newline="", encoding="utf-8") as f:
            fieldnames = list(csv.DictReader(f).fieldnames or new_rows[0].keys())
        with open(master_path, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fieldnames).writerows(new_rows)


def upgrade_master_partials(master_path: Path, upgrades: list) -> None:
    """
    Rewrite master CSV in-place, replacing ClosingMark rows for each upgraded
    trade with its real close rows from the new file.
    """
    if not upgrades or not master_path.exists():
        return
    upgrade_map = {t.identity_key: t for t in upgrades}
    all_trades = parse_trades(master_path)
    result_trades = [upgrade_map.get(t.identity_key, t) for t in all_trades]
    all_rows = [r for t in result_trades for r in t.raw_rows]
    fieldnames = list(all_rows[0].keys())
    with open(master_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)


def upgrade_registry_partials(registry: dict, upgrades: list) -> int:
    """
    For every backtest entry in the registry that records one of the upgraded
    trades as partial, patch it to is_partial=False with the real close date.
    Returns the total number of trade-entries updated across all backtests.
    """
    # Key by open date string (close enough — two partials can't share an open day)
    upgrade_by_open = {
        t.open_date.isoformat(): t for t in upgrades
    }
    n_updated = 0
    for bt in registry.get("backtests", []):
        for trade_entry in bt.get("trades", []):
            open_str = trade_entry.get("open", "")
            if trade_entry.get("is_partial") and open_str in upgrade_by_open:
                u = upgrade_by_open[open_str]
                trade_entry["is_partial"] = False
                trade_entry["close"] = (
                    u.close_date.isoformat() if u.close_date else None
                )
                n_updated += 1
    return n_updated


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def load_registry(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "backtests": []}
    with open(path) as f:
        data = json.load(f)
    # Normalise old list-style registry if present
    if isinstance(data, list):
        return {"version": 1, "backtests": data}
    return data


def save_registry(path: Path, registry: dict) -> None:
    with open(path, "w") as f:
        json.dump(registry, f, indent=2)


def upsert_registry_entry(
    registry: dict,
    start_date: date,
    source_file: str,
    trades: list,
) -> None:
    """Add or replace the registry entry for this source file (idempotent)."""
    all_dates = [t.open_date for t in trades] + [
        t.close_date for t in trades if t.close_date
    ]
    end_date = max(all_dates) if all_dates else start_date

    entry = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "source_file": source_file,
        "merged_at": date.today().isoformat(),
        "trades": [t.to_registry_dict() for t in trades],
    }
    backtests: list = registry.setdefault("backtests", [])
    for i, existing in enumerate(backtests):
        if existing.get("source_file") == source_file:
            backtests[i] = entry
            return
    backtests.append(entry)


# ---------------------------------------------------------------------------
# Coverage computation
# ---------------------------------------------------------------------------


def covered_days_for_backtest(bt: dict) -> set:
    """
    Return all NYSE trading days covered by a single registry entry.

    Algorithm:
      covered = trading_days_in_range(start, end)
      For each fully-closed trade that opened ON OR AFTER start_date,
        remove (open, close] from covered.
        (open day stays covered; close day is removed = NOT covered.)
      Trades that opened before start_date are excluded — they represent
        pre-existing positions from before this backtest window; we don't
        count their close dates as "uncovered" within this backtest's scope.
      For a ClosingMark last trade, end = that trade's open day
        (signal fired; we don't know the close, so coverage ends there).
    """
    start = date.fromisoformat(bt["start_date"])
    # Only consider trades that opened on or after start_date
    all_bt_trades = bt.get("trades", [])
    bt_trades = [t for t in all_bt_trades if date.fromisoformat(t["open"]) >= start]

    if not bt_trades:
        end = date.fromisoformat(bt.get("end_date", bt["start_date"]))
        return set(trading_days_in_range(start, end))

    last = bt_trades[-1]
    if last.get("is_partial"):
        # Coverage stops at the partial trade's open day
        end = date.fromisoformat(last["open"])
    else:
        end = date.fromisoformat(bt["end_date"])

    covered = set(trading_days_in_range(start, end))

    # Carve out the "inside trade" window for each fully-closed trade:
    # remove (open_date, close_date] — i.e. open+1 through close inclusive
    for t in bt_trades:
        if t.get("is_partial") or not t.get("close"):
            continue
        o = date.fromisoformat(t["open"])
        c = date.fromisoformat(t["close"])
        day = o + timedelta(days=1)
        while day <= c:
            covered.discard(day)
            day += timedelta(days=1)

    return covered


def compute_all_covered(registry: dict) -> set:
    """Union of covered days across all backtests in the registry."""
    covered: set = set()
    for bt in registry.get("backtests", []):
        covered |= covered_days_for_backtest(bt)
    return covered


# ---------------------------------------------------------------------------
# ASCII timeline visualisation
# ---------------------------------------------------------------------------

_FULL    = "█"   # all trading days in the week are covered
_PARTIAL = "▒"   # some days covered (e.g. week straddles a trade boundary)
_EMPTY   = "·"   # no trading days covered


def render_coverage_timeline(
    window: list,
    covered: set,
    wrap: int = 80,
) -> str:
    """
    Return a multi-line ASCII timeline string.

    Each character = one ISO trading week. Rows are wrapped at `wrap` columns.
    A label row showing month/year markers is printed above each bar row.

    Legend:  █ = covered   ▒ = partial   · = uncovered
    """
    if not window:
        return ""

    # ── group trading days by ISO week ──────────────────────────────────────
    # Each entry: (iso_year, iso_week, [dates...])

    def iso_week_key(d: date):
        iso = d.isocalendar()
        return (iso[0], iso[1])

    weeks: list[tuple] = []  # (iso_year, iso_week, week_dates)
    for key, group in groupby(window, key=iso_week_key):
        weeks.append((key[0], key[1], list(group)))

    # ── build the bar string and month-label positions ──────────────────────
    bar_chars: list[str] = []
    label_positions: list[tuple] = []   # (position, "Mmm'YY")

    prev_month = None
    for pos, (iso_yr, iso_wk, wdates) in enumerate(weeks):
        # Classify the week
        n_covered = sum(1 for d in wdates if d in covered)
        n_total = len(wdates)
        if n_covered == n_total:
            bar_chars.append(_FULL)
        elif n_covered == 0:
            bar_chars.append(_EMPTY)
        else:
            bar_chars.append(_PARTIAL)

        # Record a label at the first week of each new calendar month
        # Use the Monday of the ISO week as the reference date
        first_day = wdates[0]
        month_key = (first_day.year, first_day.month)
        if month_key != prev_month:
            label = first_day.strftime("%b'%y")   # e.g. "Nov'22"
            label_positions.append((pos, label))
            prev_month = month_key

    # ── render in wrapped rows ───────────────────────────────────────────────
    LABEL_WIDTH = 8   # chars reserved for left-margin label on each row
    bar_width = wrap - LABEL_WIDTH

    lines: list[str] = []
    lines.append(f"  Legend: {_FULL}=covered  {_PARTIAL}=partial  {_EMPTY}=uncovered")
    lines.append("")

    total = len(bar_chars)
    row = 0
    while row * bar_width < total:
        start = row * bar_width
        end = min(start + bar_width, total)
        chunk = bar_chars[start:end]
        chunk_len = len(chunk)

        # Build label row: place month labels at their positions within this chunk,
        # skipping any that would collide with the previous one.
        label_row = [" "] * chunk_len
        next_available = 0
        for pos, label in label_positions:
            local = pos - start
            if 0 <= local < chunk_len and local >= next_available:
                for i, ch in enumerate(label):
                    if local + i < chunk_len:
                        label_row[local + i] = ch
                next_available = local + len(label) + 1  # +1 gap

        lines.append(" " * LABEL_WIDTH + "".join(label_row))
        lines.append(" " * LABEL_WIDTH + "".join(chunk))
        lines.append("")
        row += 1

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Diff output
# ---------------------------------------------------------------------------


def write_diff_csv(diff_dir: Path, trades: list, start_date: date) -> Optional[Path]:
    """Write newly added trades to a dated diff CSV. Returns the path written."""
    if not trades:
        return None

    all_dates = [t.open_date for t in trades] + [
        t.close_date for t in trades if t.close_date
    ]
    range_start = min(t.open_date for t in trades)
    range_end = max(all_dates)

    diff_dir.mkdir(parents=True, exist_ok=True)
    filename = f"diff_{range_start}_{range_end}.csv"
    path = diff_dir / filename

    rows = [r for t in trades for r in t.raw_rows]
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Merge a new backtest CSV into the master file and report "
            "the next uncovered NYSE trading day."
        )
    )
    parser.add_argument(
        "new_file",
        type=Path,
        nargs="?",
        default=None,
        help="New backtest CSV to merge. Omit to just show coverage report.",
    )
    parser.add_argument(
        "--start-date",
        required=False,
        default=None,
        metavar="YYYY-MM-DD",
        help="Date the backtester was started for this file (required when new_file is given).",
    )
    parser.add_argument(
        "--master",
        type=Path,
        default=_SCRIPTS_DIR / "master_trades.csv",
        metavar="PATH",
        help="Master CSV file (default: <scripts>/master_trades.csv).",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=_SCRIPTS_DIR / "backtest_registry.json",
        metavar="PATH",
        help="Registry JSON file (default: <scripts>/backtest_registry.json).",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=_SCRIPTS_DIR / "raw",
        metavar="PATH",
        help="Directory for raw input files after processing (default: <scripts>/raw/).",
    )
    parser.add_argument(
        "--diff-dir",
        type=Path,
        default=_SCRIPTS_DIR / "diffs",
        metavar="PATH",
        help="Directory for diff CSV output files (default: <scripts>/diffs/).",
    )
    args = parser.parse_args()

    # ── No-file mode: just show coverage report ─────────────────────────────
    if args.new_file is None:
        registry = load_registry(args.registry)
        all_starts = [
            date.fromisoformat(bt["start_date"])
            for bt in registry.get("backtests", [])
        ]
        if not all_starts:
            print("Registry is empty — no backtests recorded yet.")
            sys.exit(0)
        coverage_from = min(all_starts)
        today = date.today()
        covered = compute_all_covered(registry)
        window = trading_days_in_range(coverage_from, today)
        covered_in_window = [d for d in window if d in covered]
        uncovered_in_window = [d for d in window if d not in covered]
        n_backtests = len(registry.get("backtests", []))
        print(f"\n=== Coverage Report ({n_backtests} backtest(s) in registry) ===")
        print(f"=== from {coverage_from} ===")
        print(f"  Window:    {coverage_from} -> {today}  ({len(window)} NYSE trading days)")
        print(f"  Covered:   {len(covered_in_window)}")
        print(f"  Uncovered: {len(uncovered_in_window)}")
        print()
        print(render_coverage_timeline(window, covered))
        if uncovered_in_window:
            next_date = uncovered_in_window[0]
            print(f"\n  >>> Next required backtest start: {next_date} <<<")
            if len(uncovered_in_window) > 1:
                peek = uncovered_in_window[1:4]
                print(f"      Next few uncovered: {', '.join(str(d) for d in peek)}")
        else:
            print(f"\n  All NYSE days from {coverage_from} through {today} are covered.")
        return

    # ── File mode: validate --start-date ────────────────────────────────────
    if args.start_date is None:
        parser.error("--start-date is required when a new_file is provided")

    start_date = date.fromisoformat(args.start_date)

    # ── 1. Parse new file ───────────────────────────────────────────────────
    print(f"\nParsing: {args.new_file}")
    new_trades = parse_trades(args.new_file)
    if not new_trades:
        print("  ERROR: No trades found. Exiting.", file=sys.stderr)
        sys.exit(1)

    full = sum(1 for t in new_trades if not t.is_partial)
    partial = sum(1 for t in new_trades if t.is_partial)
    all_trade_dates = [t.open_date for t in new_trades] + [
        t.close_date for t in new_trades if t.close_date
    ]
    file_end_date = max(all_trade_dates)
    date_span = f"{new_trades[0].open_date} -> {file_end_date}"
    print(f"  Trades: {len(new_trades)} ({full} complete, {partial} partial/ClosingMark)")
    print(f"  Span:   {date_span}")

    # ── 2. Deduplicate (with ClosingMark upgrade detection) ─────────────────
    master_map = read_master_trades_map(args.master)
    to_add: list = []
    to_upgrade: list = []  # ClosingMark in master → real close in new file
    skipped = 0
    for t in new_trades:
        key = t.identity_key
        if key not in master_map:
            to_add.append(t)
        elif master_map[key].is_partial and not t.is_partial:
            # Existing entry is ClosingMark; new file has the real close → upgrade
            to_upgrade.append(t)
        else:
            skipped += 1

    print(f"\n=== Merge Summary ===")
    print(f"  File:       {args.new_file.name}  (start: {start_date})")
    print(f"  Added:      {len(to_add)} new trade(s)")
    print(f"  Upgraded:   {len(to_upgrade)} ClosingMark → real close")
    print(f"  Duplicates: {skipped} skipped")

    # Apply upgrades: rewrite master rows + patch registry entries
    registry = load_registry(args.registry)
    if to_upgrade:
        upgrade_master_partials(args.master, to_upgrade)
        n_reg_updated = upgrade_registry_partials(registry, to_upgrade)
        # Refresh map after rewrite so total count is accurate
        master_map = read_master_trades_map(args.master)
        print(f"  (Registry:  {n_reg_updated} partial trade-entries updated across all backtests)")

    append_to_master(args.master, to_add)
    if to_add or to_upgrade:
        total = len(read_master_trades_map(args.master))
        print(f"  Master:     {args.master}  ({total} unique trade(s) total)")
    else:
        print(f"  Master:     unchanged")

    # Write diff CSV for newly added trades only (not upgrades — they were already counted)
    diff_path = write_diff_csv(args.diff_dir, to_add, start_date)
    if diff_path:
        print(f"  Diff:       {diff_path}")
    else:
        print(f"  Diff:       (none — no new trades)")

    # Move input file to raw dir, renaming to encode start_date and end_date
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    raw_name = f"raw_{start_date}_thru_{file_end_date}.csv"
    raw_dest = args.raw_dir / raw_name
    if args.new_file.resolve() != raw_dest.resolve():
        args.new_file.rename(raw_dest)
        print(f"  Raw file:   {args.new_file.name} -> {raw_dest}")

    # ── 3. Registry (idempotent) ────────────────────────────────────────────
    upsert_registry_entry(
        registry,
        start_date=start_date,
        source_file=str(raw_dest),
        trades=new_trades,
    )
    save_registry(args.registry, registry)
    n_backtests = len(registry.get("backtests", []))
    print(f"  Registry:   {args.registry}  ({n_backtests} backtest(s) recorded)")

    # ── 4. Coverage analysis ────────────────────────────────────────────────
    # Anchor coverage to the earliest start_date ever recorded in the registry.
    all_starts = [
        date.fromisoformat(bt["start_date"])
        for bt in registry.get("backtests", [])
    ]
    coverage_from = min(all_starts) if all_starts else start_date

    print(f"\n=== Coverage Analysis (from {coverage_from}) ===")
    print("  Computing NYSE trading day coverage...")

    covered = compute_all_covered(registry)
    today = date.today()
    window = trading_days_in_range(coverage_from, today)
    covered_in_window = [d for d in window if d in covered]
    uncovered_in_window = [d for d in window if d not in covered]

    print(f"  Window:    {coverage_from} -> {today}  ({len(window)} NYSE trading days)")
    print(f"  Covered:   {len(covered_in_window)}")
    print(f"  Uncovered: {len(uncovered_in_window)}")
    print()
    print(render_coverage_timeline(window, covered))

    if uncovered_in_window:
        next_date = uncovered_in_window[0]
        print(f"\n  >>> Next required backtest start: {next_date} <<<")
        if len(uncovered_in_window) > 1:
            peek = uncovered_in_window[1:4]
            print(f"      Next few uncovered: {', '.join(str(d) for d in peek)}")
    else:
        print(f"\n  All NYSE days from {coverage_from} through {today} are covered.")


if __name__ == "__main__":
    main()
