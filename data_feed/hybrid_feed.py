"""Validate the wire contract before changing any persistent trading state."""
import math
import time

PERIODS = {"H4": 14400, "H1": 3600, "M15": 900, "M5": 300}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("NON_FINITE_NUMBER")
    return float(value)


def validate(payload, now=None):
    now = time.time() if now is None else now
    if payload.get("schema_version") != 2 or payload.get("symbol") != "XAUUSD":
        raise ValueError("UNSUPPORTED_FEED")
    quote = payload["quote"]
    stamp, bid, ask = (number(quote[key]) for key in ("time", "bid", "ask"))
    if not 0 <= now - stamp <= 30 or not 0 < bid <= ask:
        raise ValueError("STALE_OR_INVALID_QUOTE")
    if payload.get("bar_clock") != "UTC":
        raise ValueError("BAR_CLOCK_MUST_BE_UTC")
    histories = payload["candles"]
    for tf, period in PERIODS.items():
        bars = histories[tf]
        if not isinstance(bars, list) or not 60 <= len(bars) <= 500:
            raise ValueError("INSUFFICIENT_HISTORY:" + tf)
        previous = None
        for bar in bars:
            stamp_bar = number(bar["time"])
            o, h, l, c, v = (number(bar[k]) for k in ("open", "high", "low", "close", "volume"))
            if min(o, h, l, c) <= 0 or v < 0 or not l <= min(o, c) <= max(o, c) <= h:
                raise ValueError("INVALID_CANDLE:" + tf)
            if stamp_bar + period > stamp + 1 or (previous is not None and stamp_bar <= previous):
                raise ValueError("OPEN_OR_UNORDERED_CANDLE:" + tf)
            previous = stamp_bar
        # A gap is allowed in history (weekends); the most recent close must be fresh.
        if stamp - (bars[-1]["time"] + period) > period + 30:
            raise ValueError("STALE_HISTORY:" + tf)
    return payload
