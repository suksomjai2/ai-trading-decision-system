"""Daily paper-trade report (07:00 Asia/Bangkok reset) from committed forward events; no broker P/L."""
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value is not None else None


def build_report(path, now, entry_kind='ENTRY', exit_kind='EXIT', shadow=False):
    local = datetime.fromtimestamp(now, timezone(timedelta(hours=7)))
    boundary = local.replace(hour=7, minute=0, second=0, microsecond=0)
    if local < boundary:
        boundary -= timedelta(days=1)
    start = boundary.timestamp()
    reset = (boundary + timedelta(days=1)).timestamp()
    report = {
        'schema_version': 1, 'mode': 'PAPER_ONLY', 'status': 'OK',
        'generated_at_utc': iso(now), 'window_start_utc': iso(start),
        'window_end_utc': iso(now), 'next_reset_utc': iso(reset),
        'reset_timezone': 'Asia/Bangkok', 'reset_local_time': '07:00',
        'audit_started_at_utc': None,
        'counts': {'buy_entries': 0, 'sell_entries': 0, 'tp_observed': 0,
                   'sl_observed': 0, 'exits_with_coverage_gap': 0,
                   'open_positions': 0, 'unresolved_positions': 0},
        'trades': [],
    }
    path = Path(path)
    if not path.exists():
        report['status'] = 'NO_AUDIT_DATABASE'
        return report
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
    try:
        connection.execute('BEGIN')
        first = connection.execute(
            "SELECT MIN(time) FROM events WHERE symbol=? AND kind='EVALUATION' AND time<=?",
            ('XAUUSD', now)).fetchone()[0]
        report['audit_started_at_utc'] = iso(first)
        # Indexed event kinds avoid reading the growing quote-evaluation audit.
        rows = connection.execute(
            "SELECT kind,value FROM events WHERE symbol=? AND kind IN (?,?,'AMBIGUOUS_OUTCOME') "
            'AND time>=? AND time<=? ORDER BY id', ('XAUUSD', entry_kind, exit_kind, start, now)).fetchall()
        state_row = connection.execute('SELECT value FROM engine_state WHERE symbol=?', ('XAUUSD',)).fetchone()
        state = json.loads(state_row[0]) if state_row else {}
        by_id = {}
        ambiguous = set()
        for kind, raw in rows:
            event = json.loads(raw)
            if kind == 'AMBIGUOUS_OUTCOME':
                ambiguous.add(event['trade_id'])
                continue
            trade = event['trade']
            # ENTRY and EXIT share one id: count one trade, retain exit evidence.
            by_id[trade['id']] = {**by_id.get(trade['id'], {}), **trade}
        live = (state.get('shadow') or {}).get('book') if shadow else state.get('trade')
        if live and live.get('entry_time', now + 1) <= now:
            by_id[live['id']] = {**by_id.get(live['id'], {}), **live}
        for trade in by_id.values():
            entered = start <= trade['entry_time'] <= now
            exited = trade.get('exit_time') is not None and start <= trade['exit_time'] <= now
            active = bool(live and live['id'] == trade['id'])
            if not (entered or exited or active):
                continue
            if entered:
                report['counts']['buy_entries' if trade['side'] == 'BUY' else 'sell_entries'] += 1
            outcome = trade.get('outcome')
            gap = bool(trade.get('coverage_gap'))
            unresolved = bool(trade.get('unresolved') or trade['id'] in ambiguous)
            if exited:
                if outcome == 'TP_TOUCHED':
                    report['counts']['tp_observed'] += 1
                elif outcome == 'SL_TOUCHED':
                    report['counts']['sl_observed'] += 1
                if gap:
                    report['counts']['exits_with_coverage_gap'] += 1
            if active:
                report['counts']['open_positions'] += 1
                if unresolved:
                    report['counts']['unresolved_positions'] += 1
            status = ('UNRESOLVED_TP_SL' if unresolved else
                      outcome if exited else 'OPEN' if active else 'MISSING_EXIT_RECORD')
            row = {
                'id': trade['id'], 'side': trade['side'],
                'entry_time_utc': iso(trade['entry_time']), 'entry_price': trade['entry_price'],
                'tp': trade['tp'], 'sl': trade['sl'], 'rr': trade.get('rr'),
                'exit_time_utc': iso(trade.get('exit_time')),
                'exit_observed_price': trade.get('exit_observed_price'),
                'status': status, 'coverage_gap': gap, 'unresolved': unresolved,
                'evidence': trade.get('outcome_evidence'),
                'entry_in_window': entered, 'exit_in_window': exited,
                'mfe_observed': trade.get('mfe_observed'),
                'mae_observed': trade.get('mae_observed'),
                'policy': trade.get('policy'), 'selection': trade.get('selection'),
                'setup_mode': trade.get('mode'),
            }
            # A quote observation is not a broker fill or realized money profit.
            row['observed_price_move'] = (
                (1 if trade['side'] == 'BUY' else -1) * (trade['exit_observed_price'] - trade['entry_price'])
                if exited and trade.get('exit_observed_price') is not None else None)
            report['trades'].append(row)
        report['trades'].sort(key=lambda row: row['entry_time_utc'], reverse=True)
        return report
    finally:
        connection.close()


def build_comparison(path, now):
    """Cumulative main (H1CON_RAW_V1) vs shadow (H1CON_AI_V1) since the main policy started; price units."""
    out = {'schema_version': 1, 'mode': 'PAPER_ONLY', 'status': 'OK', 'generated_at_utc': iso(now),
           'since_utc': None, 'systems': {}}
    path = Path(path)
    if not path.exists():
        out['status'] = 'NO_AUDIT_DATABASE'
        return out
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
    try:
        connection.execute('BEGIN')
        row = connection.execute('SELECT value FROM engine_state WHERE symbol=?', ('XAUUSD',)).fetchone()
        state = json.loads(row[0]) if row else {}
        since = state.get('main_policy_since')
        if not since:
            out['status'] = 'NOT_STARTED'
            return out
        out['since_utc'] = iso(since)
        for name, kinds, policy, live in (
                ('main', ('ENTRY', 'EXIT'), 'H1CON_RAW_V1', state.get('trade')),
                ('shadow', ('SHADOW_ENTRY', 'SHADOW_EXIT'), 'H1CON_AI_V1', (state.get('shadow') or {}).get('book'))):
            trades = {}
            for (raw,) in connection.execute(
                    'SELECT value FROM events WHERE symbol=? AND kind IN (?,?) AND time>=? AND time<=? ORDER BY id',
                    ('XAUUSD', kinds[0], kinds[1], since, now)):
                t = json.loads(raw)['trade']
                if t.get('policy') == policy and t.get('entry_time', 0) >= since:
                    trades[t['id']] = {**trades.get(t['id'], {}), **t}
            closed = [t for t in trades.values() if t.get('exit_time') is not None]
            move = lambda t: (1 if t['side'] == 'BUY' else -1) * (t['exit_observed_price'] - t['entry_price'])
            tp = sum(t.get('outcome') == 'TP_TOUCHED' for t in closed)
            sl = sum(t.get('outcome') == 'SL_TOUCHED' for t in closed)
            net = sum(move(t) for t in closed if t.get('exit_observed_price') is not None)
            open_t = live if live and live.get('policy') == policy else None
            out['systems'][name] = {'policy': policy, 'closed': len(closed), 'tp': tp, 'sl': sl,
                                    'net_price_move': round(net, 2),
                                    'win_rate': round(tp / len(closed), 3) if closed else None,
                                    'open_side': open_t['side'] if open_t else None,
                                    'gaps': sum(bool(t.get('coverage_gap')) for t in closed)}
        return out
    finally:
        connection.close()
