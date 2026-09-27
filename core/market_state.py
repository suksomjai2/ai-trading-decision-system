from core.decision_engine import DecisionEngine


class MarketState:

    def __init__(self):

        # ======================
        # Decision Engine
        # ======================

        self.decision_engine = DecisionEngine()


    def analyze(
        self,
        market_data
    ):

        # ======================
        # Extract Features
        # ======================

        features = self._extract_features(
            market_data
        )


        # ======================
        # Market State
        # ======================

        state = features.get(
            "trend_direction",
            "NEUTRAL"
        )


        # ======================
        # Decision
        # Single Source of Truth
        # ======================

        decision = self.decision_engine.decide(
            state,
            features
        )


        # ======================
        # Final Result
        # ======================

        return {

            "state": state,

            "features": features,

            "decision": decision

        }


    def _extract_features(
        self,
        market_data
    ):

        # ======================
        # Input Data
        # ======================

        open_price = float(
            market_data["open"]
        )

        high = float(
            market_data["high"]
        )

        low = float(
            market_data["low"]
        )

        close = float(
            market_data["close"]
        )

        volume = float(
            market_data["volume"]
        )


        # ======================
        # Candle Geometry
        # ======================

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


        # ======================
        # Trend Direction
        # ======================

        if close > open_price:

            trend_direction = "UP"

        elif close < open_price:

            trend_direction = "DOWN"

        else:

            trend_direction = "NEUTRAL"


        # ======================
        # Price Position
        #
        # 0.0 = Range Low
        # 0.5 = Range Middle
        # 1.0 = Range High
        # ======================

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


        # ======================
        # Buying Pressure
        # ======================

        buying_pressure = (
            price_position
        )


        # ======================
        # Momentum
        #
        # Positive = Bullish
        # Negative = Bearish
        # ======================

        if trend_direction == "UP":

            momentum = body_size

        elif trend_direction == "DOWN":

            momentum = -body_size

        else:

            momentum = 0.0


        # ======================
        # Volatility
        # Normalized by Price
        # ======================

        if close != 0:

            volatility = (
                price_range /
                abs(close)
            )

        else:

            volatility = 0.0


        # ======================
        # Volume State
        #
        # Temporary logic
        # Will improve later using
        # relative / average volume
        # ======================

        if volume > 0:

            volume_state = "HIGH"

        else:

            volume_state = "LOW"


        # ======================
        # Candle Type
        # ======================

        if close > open_price:

            candle_type = "BULLISH"

        elif close < open_price:

            candle_type = "BEARISH"

        else:

            candle_type = "NEUTRAL"


        # ======================
        # Trend Strength
        #
        # Normalized 0.0 - 1.0
        # ======================

        trend_strength = (
            self._trend_strength(
                open_price,
                close,
                high,
                low
            )
        )


        # ======================
        # Final Features
        # ======================

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


    def _trend_strength(
        self,
        open_price,
        close,
        high,
        low
    ):

        # ======================
        # Price Range
        # ======================

        price_range = (
            high - low
        )


        if price_range <= 0:

            return 0.0


        # ======================
        # Candle Body
        # ======================

        body_size = abs(
            close - open_price
        )


        # ======================
        # Normalized Strength
        #
        # 0.0 = Weak
        # 1.0 = Strong
        #
        # Example:
        #
        # body  = 10
        # range = 20
        #
        # strength = 0.5
        # ======================

        strength = (
            body_size /
            price_range
        )


        # ======================
        # Bound 0.0 - 1.0
        # ======================

        strength = max(
            0.0,
            min(
                strength,
                1.0
            )
        )


        return round(
            strength,
            4
        )
