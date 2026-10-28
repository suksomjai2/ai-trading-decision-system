"""H1CON_AI_V1 building blocks shared by the live policy and the offline backtest/training.

Everything is computed from the closed-bar windows the MT5 EA sends (200 bars per timeframe),
so offline evaluation and the live server see exactly the same numbers.

Candidate (entry setup of the user's EA "H1_con_cool" v2.20, first entry only, no grid):
  H1 trend  = EMA50 vs EMA100 of the H1 window; no candidate on a cross bar.
  At a newly closed M15 bar:  bar[-2] is a pullback candle against the trend with RSI14[-2] < 48 (BUY)
  / > 52 (SELL) and bar[-1] confirms (closes beyond bar[-2] open), or the EA's bar[-3] alternative.
Exit: fixed 12.0 price units TP and SL (EA single-order target 12 USD at 0.01 lot = 12.0).
AI: gradient-boosted trees (exported from scikit-learn, evaluated here in pure Python) estimate
P(TP before SL); a candidate is taken when P > 1/(1+RR) + 0.05 (= 0.55 for RR 1).
"""
import json
import math
from datetime import datetime, timedelta, timezone

WINDOW = 200
TP_DISTANCE = 12.0
SL_DISTANCE = 12.0
MARGIN = 0.05
BANGKOK = timezone(timedelta(hours=7))

FEATURES = ['x_asia', 'x_atr_change', 'x_body', 'x_dist_ema20', 'x_dow', 'x_ema_spread', 'x_h1_atr_ratio',
            'x_h1_ema_spread', 'x_h1_trend', 'x_hour_cos', 'x_hour_sin', 'x_lower_wick', 'x_m15_trend', 'x_m5_body',
            'x_ny', 'x_outside', 'x_range_pos', 'x_range_width', 'x_ret_1h', 'x_ret_24h', 'x_ret_4h', 'x_risk_atr',
            'x_side', 'x_upper_wick', 'x_with_bias', 'x_asia_drift20', 'x_ny_drift20', 'x_own_drift20']


def ema_series(closes, n):
    out = [None] * len(closes)
    if len(closes) < n:
        return out
    v = sum(closes[:n]) / n
    out[n - 1] = v
    a = 2 / (n + 1)
    for i in range(n, len(closes)):
        v += a * (closes[i] - v)
        out[i] = v
    return out


def rsi_series(closes, n=14):
    """Wilder RSI (MT5 iRSI)."""
    out = [None] * len(closes)
    if len(closes) <= n:
        return out
    g = l = 0.0
    for i in range(1, n + 1):
        d = closes[i] - closes[i - 1]
        g += max(d, 0.0)
        l += max(-d, 0.0)
    g /= n
    l /= n
    out[n] = 100.0 if l == 0 else 100 - 100 / (1 + g / l)
    for i in range(n + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        g = (g * (n - 1) + max(d, 0.0)) / n
        l = (l * (n - 1) + max(-d, 0.0)) / n
        out[i] = 100.0 if l == 0 else 100 - 100 / (1 + g / l)
    return out


def wilder_atr(bars, n=14):
    tr = [max(c['high'] - c['low'], abs(c['high'] - bars[i - 1]['close']), abs(c['low'] - bars[i - 1]['close']))
          for i, c in enumerate(bars) if i]
    atr = sum(tr[:n]) / n
    for v in tr[n:]:
        atr = (13 * atr + v) / 14
    return atr


def _trend(f, tf):
    c = f[tf]['direction_checks']
    if c['ema20_above_ema50'] and c['ema20_rising']:
        return 1
    if not c['ema20_above_ema50'] and not c['ema20_rising']:
        return -1
    return 0


def h1_trend_50_100(h1):
    closes = [b['close'] for b in h1[-WINDOW:]]
    e50, e100 = ema_series(closes, 50), ema_series(closes, 100)
    if len(closes) < 102 or e100[-2] is None:
        return 0, None
    f0, s0, f1, s1 = e50[-1], e100[-1], e50[-2], e100[-2]
    if (f0 > s0 and f1 < s1) or (f0 < s0 and f1 > s1):
        return 0, f0 - s0
    return (1 if f0 > s0 else -1 if f0 < s0 else 0), f0 - s0


def signal(h1, m15):
    """'BUY' / 'SELL' / None from closed H1 and M15 windows (evaluate once per new M15 bar)."""
    trend, _ = h1_trend_50_100(h1)
    if trend == 0 or len(m15) < 20:
        return None
    rsi = rsi_series([b['close'] for b in m15[-WINDOW:]])
    b1, b2, b3 = m15[-1], m15[-2], m15[-3]
    r2, r3 = rsi[-2], rsi[-3]
    if r2 is None or r3 is None:
        return None
    if trend == 1:
        ok = b1['close'] > b1['open'] and b1['close'] > b2['open']
        if not ok and b3['close'] < b3['open'] and r3 < 48 and b1['close'] > b3['open']:
            ok = True
        if b2['close'] < b2['open'] and r2 < 48 and ok:
            return 'BUY'
    else:
        ok = b1['close'] < b1['open'] and b1['close'] < b2['open']
        if not ok and b3['close'] > b3['open'] and r3 > 52 and b1['close'] < b3['open']:
            ok = True
        if b2['close'] > b2['open'] and r2 > 52 and ok:
            return 'SELL'
    return None


def _session(t):
    d = datetime.fromtimestamp(t, BANGKOK)
    x = d.hour + d.minute / 60
    if 7 <= x < 14:
        return 'ASIA', 'BUY'
    if x >= 19.5 or x < 2:
        return 'NY', 'SELL'
    return None, None


def _session_mid(t):
    """Session of an H4 bar by its midpoint (H4 bars follow the broker clock, not Bangkok hours)."""
    return _session(t + 7200)[0]


def features(side, T, m5, m15, h1, h4, f):
    """Feature dict at decision time T (seconds). m5/m15/h1/h4: closed-bar windows; f: {'M15','H1'} with
    ema20, ema50, atr14, direction_checks (the server's FeatureEngine output for the same windows)."""
    s = 1 if side == 'BUY' else -1
    atr = f['M15']['atr14']
    close = m5[-1]['close']
    local = datetime.fromtimestamp(T, BANGKOK)
    hour = local.hour + local.minute / 60
    session, allowed = _session(T)
    last = m15[-1]
    w20 = m15[-20:]
    hi20, lo20 = max(b['high'] for b in w20), min(b['low'] for b in w20)
    pos = (close - lo20) / (hi20 - lo20) if hi20 > lo20 else 0.5
    old = m15[-WINDOW:-96]
    atr_old = wilder_atr(old) if len(old) >= 30 else atr
    asia = ny = 0.0
    for b in h4:                                        # ~20 trading days of session drift
        if not (T - 28 * 86400 <= b['time'] < T):
            continue
        name = _session_mid(b['time'])
        if name == 'ASIA':
            asia += b['close'] - b['open']
        elif name == 'NY':
            ny += b['close'] - b['open']
    asia /= atr
    ny /= atr
    own = asia if session == 'ASIA' else ny if session == 'NY' else 0.0
    return {
        'x_side': s, 'x_hour_sin': math.sin(2 * math.pi * hour / 24), 'x_hour_cos': math.cos(2 * math.pi * hour / 24),
        'x_dow': local.weekday(), 'x_asia': int(session == 'ASIA'), 'x_ny': int(session == 'NY'),
        'x_outside': int(session is None), 'x_with_bias': int(allowed == side),
        'x_h1_trend': s * _trend(f, 'H1'), 'x_m15_trend': s * _trend(f, 'M15'),
        'x_dist_ema20': s * (close - f['M15']['ema20']) / atr,
        'x_ema_spread': s * (f['M15']['ema20'] - f['M15']['ema50']) / atr,
        'x_h1_ema_spread': s * (f['H1']['ema20'] - f['H1']['ema50']) / atr,
        'x_h1_atr_ratio': f['H1']['atr14'] / atr,
        'x_body': s * (last['close'] - last['open']) / atr,
        'x_upper_wick': (last['high'] - max(last['open'], last['close'])) / atr,
        'x_lower_wick': (min(last['open'], last['close']) - last['low']) / atr,
        'x_m5_body': s * (m5[-1]['close'] - m5[-1]['open']) / atr,
        'x_ret_1h': s * (close - m5[-13]['close']) / atr, 'x_ret_4h': s * (close - m5[-49]['close']) / atr,
        'x_ret_24h': s * (close - m15[-97]['close']) / atr,
        'x_range_pos': pos if s == 1 else 1 - pos, 'x_range_width': (hi20 - lo20) / atr,
        'x_atr_change': math.log(atr / atr_old) if atr_old > 0 else 0.0,
        'x_risk_atr': SL_DISTANCE / atr,
        'x_asia_drift20': asia, 'x_ny_drift20': ny, 'x_own_drift20': s * own,
    }


class TreeModel:
    """Pure-Python evaluation of an exported scikit-learn HistGradientBoostingClassifier (binary)."""

    def __init__(self, spec):
        self.spec = spec
        self.features = spec['features']
        self.baseline = spec['baseline']
        self.trees = spec['trees']

    @classmethod
    def load(cls, path):
        with open(path, encoding='utf-8') as fh:
            return cls(json.load(fh))

    def raw(self, x):
        total = self.baseline
        for nodes in self.trees:
            i = 0
            while not nodes[i][0]:                      # [is_leaf, value, feature, threshold, missing_left, left, right]
                _, _, feat, thr, miss_left, left, right = nodes[i]
                v = x[feat]
                if v != v:                              # NaN
                    i = left if miss_left else right
                else:
                    i = left if v <= thr else right
            total += nodes[i][1]
        return total

    def proba(self, feats):
        x = [float(feats[n]) for n in self.features]
        z = self.raw(x)
        return 1.0 / (1.0 + math.exp(-z))
