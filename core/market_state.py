from core.decision_engine import DecisionEngine


class MarketState:

    def __init__(self):

        self.decision_engine = DecisionEngine()


    # =========================
    # Market Analysis
    # =========================

    def analyze(self, market_data):

        features = self._extract_features(
            market_data
        )

        state = features.get(
            "trend_direction",
            "NEUTRAL"
        )

        decision = self.decision_engine.decide(
            state,
            features
        )

        return {
            "state": state,
            "features": features,
            "decision": decision
        }


    # =========================
    # Feature Extraction
    # =========================

    def _extract_features(
        self,
        market_data
    ):

        open_price = float(
            market_data.get(
                "open",
                0
            )
        )

        high = float(
            market_data.get(
                "high",
                0
            )
        )

        low = float(
            market_data.get(
                "low",
                0
            )
        )

        close = float(
            market_data.get(
                "close",
                0
            )
        )

        volume = float(
            market_data.get(
                "volume",
                0
            )
        )


        # =========================
        # Candle Structure
        # =========================

        body_size = abs(
            close - open_price
        )

        upper_shadow = max(
            0.0,
            high - max(
                open_price,
                close
            )
        )

        lower_shadow = max(
            0.0,
            min(
                open_price,
                close
            ) - low
        )

        price_range = max(
            0.0,
            high - low
        )


        # =========================
        # Trend Direction
        # =========================

        if close > open_price:

            trend_direction = "UP"

        elif close < open_price:

            trend_direction = "DOWN"

        else:

            trend_direction = "NEUTRAL"


        # =========================
        # Price Position
        # =========================

        if price_range > 0:

            price_position = (
                close - low
            ) / price_range

        else:

            price_position = 0.5


        price_position = max(
            0.0,
            min(
                price_position,
                1.0
            )
        )


        # =========================
        # Buying Pressure
        # =========================

        buying_pressure = (
            price_position
        )


        # =========================
        # Momentum
        # =========================

        momentum = (
            close - open_price
        )


        # =========================
        # Volatility
        # =========================

        if close != 0:

            volatility = (
                price_range /
                abs(close)
            )

        else:

            volatility = 0.0


        # =========================
        # Volume State
        # =========================

        if volume > 0:

            volume_state = "HIGH"

        else:

            volume_state = "LOW"


        # =========================
        # Candle Type
        # =========================

        if close > open_price:

            candle_type = "BULLISH"

        elif close < open_price:

            candle_type = "BEARISH"

        else:

            candle_type = "NEUTRAL"


        # =========================
        # Trend Strength
        # =========================

        trend_strength = (
            self._trend_strength(
                open_price,
                close,
                high,
                low
            )
        )


        # =========================
        # Feature Output
        # =========================

        return {

            "open": round(
                open_price,
                4
            ),

            "high": round(
                high,
                4
            ),

            "low": round(
                low,
                4
            ),

            "close": round(
                close,
                4
            ),

            "body_size": round(
                body_size,
                4
            ),

            "upper_shadow": round(
                upper_shadow,
                4
            ),

            "lower_shadow": round(
                lower_shadow,
                4
            ),

            "price_range": round(
                price_range,
                4
            ),

            "trend_direction":
                trend_direction,

            "trend_strength": round(
                trend_strength,
                4
            ),

            "volume_state":
                volume_state,

            "momentum": round(
                momentum,
                4
            ),

            "volatility": round(
                volatility,
                6
            ),

            "price_position": round(
                price_position,
                4
            ),

            "candle_type":
                candle_type,

            "buying_pressure": round(
                buying_pressure,
                4
            )
        }


    # =========================
    # Trend Strength
    # =========================

    def _trend_strength(
        self,
        open_price,
        close,
        high,
        low
    ):

        price_range = (
            high - low
        )

        if price_range <= 0:

            return 0.0


        body_size = abs(
            close - open_price
        )


        # Candle body relative to
        # total candle range.
        #
        # Output:
        # 0 = no directional strength
        # 10 = maximum strength

        strength = (
            body_size /
            price_range
        ) * 10.0


        strength = max(
            0.0,
            min(
                strength,
                10.0
            )
        )


        return strength
