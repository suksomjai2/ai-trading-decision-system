class FeatureEngine:

    def __init__(self):
        pass


    def calculate_features(self, market_data):

        open_price = market_data["open"]
        high = market_data["high"]
        low = market_data["low"]
        close = market_data["close"]
        volume = market_data["volume"]


        features = {

            "open": open_price,
            "high": high,
            "low": low,
            "close": close,


            # Candle Structure

            "body_size": abs(close - open_price),

            "upper_shadow": high - max(open_price, close),

            "lower_shadow": min(open_price, close) - low,


            # Price Movement

            "price_range": self._price_range(
                high,
                low
            ),


            # Trend

            "trend_direction": self._trend_direction(
                close,
                high,
                low
            ),


            "trend_strength": self._trend_strength(
                close,
                high,
                low
            ),


            # Volume

            "volume_state": self._volume_state(
                volume
            ),


            # Momentum

            "momentum": close - open_price,


            # Volatility

            "volatility": self._volatility(
                high,
                low,
                close
            ),


            # Phase 2.3

            "price_position": self._price_position(
                close,
                high,
                low
            ),


            "candle_type": self._candle_type(
                open_price,
                close
            ),


            "buying_pressure": self._buying_pressure(
                close,
                high,
                low
            )

        }


        return features



    def _price_range(self, high, low):

        return high - low



    def _trend_direction(self, close, high, low):

        midpoint = (high + low) / 2


        if close > midpoint:
            return "UP"

        elif close < midpoint:
            return "DOWN"

        else:
            return "NEUTRAL"



    def _trend_strength(self, close, high, low):

        midpoint = (high + low) / 2

        return abs(
            close - midpoint
        )



    def _volatility(self, high, low, close):

        if close == 0:
            return 0


        return round(
            (high - low) / close,
            4
        )



    def _price_position(self, close, high, low):

        if high == low:
            return 0


        return round(
            (close - low) / (high - low),
            2
        )



    def _candle_type(self, open_price, close):

        body = close - open_price


        if body > 0:
            return "BULLISH"

        elif body < 0:
            return "BEARISH"

        else:
            return "DOJI"



    def _buying_pressure(self, close, high, low):

        if high == low:
            return 0


        return round(
            (close - low) / (high - low),
            2
        )



    def _volume_state(self, volume):

        if volume <= 0:

            return "UNKNOWN"


        elif volume > 100000:

            return "HIGH"


        else:

            return "NORMAL"

    def calculate_history(self, candles):
        """Closed bars only, in time order. EMA and Wilder ATR use history."""
        if len(candles) < 60:
            raise ValueError("INSUFFICIENT_HISTORY")
        closes = [c["close"] for c in candles]

        def ema(period):
            value = sum(closes[:period]) / period
            values = [value]
            alpha = 2 / (period + 1)
            for close in closes[period:]:
                value += alpha * (close - value)
                values.append(value)
            return values

        true_ranges = [max(c["high"] - c["low"],
                           abs(c["high"] - candles[i - 1]["close"]),
                           abs(c["low"] - candles[i - 1]["close"]))
                       for i, c in enumerate(candles) if i]
        atr = sum(true_ranges[:14]) / 14
        for value in true_ranges[14:]:
            atr = (13 * atr + value) / 14
        fast, slow = ema(20), ema(50)
        current, previous = candles[-5:], candles[-10:-5]
        higher = (max(c["high"] for c in current) > max(c["high"] for c in previous)
                  and min(c["low"] for c in current) > min(c["low"] for c in previous))
        lower = (max(c["high"] for c in current) < max(c["high"] for c in previous)
                 and min(c["low"] for c in current) < min(c["low"] for c in previous))
        direction = "NEUTRAL"
        if closes[-1] > fast[-1] > slow[-1] and fast[-1] > fast[-6] and higher:
            direction = "UP"
        elif closes[-1] < fast[-1] < slow[-1] and fast[-1] < fast[-6] and lower:
            direction = "DOWN"
        return {
            "price_action": self.price_action(candles, atr),
            "direction": direction, "ema20": fast[-1], "ema50": slow[-1],
            "atr14": atr, "structure": "HIGHER" if higher else "LOWER" if lower else "MIXED",
            "last_close": closes[-1], "last_time": candles[-1]["time"],
            "direction_checks": {
                "close_above_ema20": closes[-1] > fast[-1],
                "ema20_above_ema50": fast[-1] > slow[-1],
                "ema20_rising": fast[-1] > fast[-6],
                "higher_structure": higher, "lower_structure": lower,
            },
            # A recent structural break can precede an EMA50 crossover. Keep
            # short-term setup evidence separate from the slower trend label.
            "recent_high": max(c["high"] for c in candles[-6:-1]),
            "recent_low": min(c["low"] for c in candles[-6:-1]),
            "breakout_up": closes[-1] > max(c["high"] for c in candles[-6:-1]),
            "breakout_down": closes[-1] < min(c["low"] for c in candles[-6:-1]),
        }

    @staticmethod
    def price_action(candles, atr):
        """Describe known levels and reactions, never entry vetoes or a score.

        Pivots use only closed neighbours already supplied. No future bars,
        tick-volume buying/selling claims, or candle-size-only reversals.
        """
        bars = candles[-40:]
        tolerance = max(0.1 * atr, 1e-9)
        highs, lows = [], []
        for i in range(1, len(bars) - 1):
            left, bar, right = bars[i-1:i+2]
            if bar['high'] > left['high'] and bar['high'] >= right['high']:
                highs.append({'price': bar['high'], 'time': bar['time']})
            if bar['low'] < left['low'] and bar['low'] <= right['low']:
                lows.append({'price': bar['low'], 'time': bar['time']})

        def relation(points, high):
            if len(points) < 2:
                return 'UNKNOWN'
            difference = points[-1]['price'] - points[-2]['price']
            if abs(difference) <= tolerance:
                return 'EQUAL_HIGH' if high else 'EQUAL_LOW'
            return ('HH' if high else 'HL') if difference > 0 else ('LH' if high else 'LL')

        # These are candidate zones, not a claim that every level will hold.
        def levels(points):
            groups = []
            for point in points:
                group = next((g for g in groups if abs(g['price']-point['price']) <= tolerance), None)
                if group:
                    count = group['touches']
                    group['price'] = (group['price']*count+point['price'])/(count+1)
                    group['touches'] += 1
                    group['last_time'] = point['time']
                else:
                    groups.append({'price': point['price'], 'touches': 1, 'last_time': point['time']})
            return groups[-8:]

        latest = bars[-1]
        recent = bars[-6:-1]
        body = [b['close']-b['open'] for b in bars[-3:]]
        ranges = [b['high']-b['low'] for b in bars[-3:]]
        return {
            'swing_high': relation(highs, True), 'swing_low': relation(lows, False),
            'resistance': levels(highs), 'support': levels(lows),
            'reference_high': max(b['high'] for b in recent),
            'reference_low': min(b['low'] for b in recent),
            'last_bodies': body, 'last_ranges': ranges,
            'body_contracting': abs(body[-1]) < abs(body[-2]),
            'range_contracting': ranges[-1] < ranges[-2],
            'latest_high': latest['high'], 'latest_low': latest['low'],
            'advisory_only': True, 'no_level_proximity_penalty': True,
        }
