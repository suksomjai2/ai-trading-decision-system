class DecisionEngine:

    def __init__(self):
        pass

    def decide(
        self,
        state,
        features
    ):

        # ======================
        # Initial Score
        # ======================

        score = 0.0


        # ======================
        # Trend Direction
        # ======================

        trend_direction = features.get(
            "trend_direction",
            "NEUTRAL"
        )

        if trend_direction == "UP":

            score += 2.0

        elif trend_direction == "DOWN":

            score -= 2.0


        # ======================
        # Trend Strength
        # ======================

        trend_strength = float(
            features.get(
                "trend_strength",
                0
            )
        )

        trend_strength = max(
            0.0,
            min(
                trend_strength,
                10.0
            )
        )

        score += min(
            trend_strength / 2.0,
            2.0
        )


        # ======================
        # Volume
        # ======================

        volume_state = features.get(
            "volume_state",
            "NORMAL"
        )

        if volume_state == "HIGH":

            score += 1.0

        elif volume_state == "LOW":

            score -= 0.5


        # ======================
        # Momentum
        # ======================

        momentum = float(
            features.get(
                "momentum",
                0
            )
        )

        if momentum > 0:

            score += min(
                momentum / 10.0,
                2.0
            )

        elif momentum < 0:

            score += max(
                momentum / 10.0,
                -2.0
            )


        # ======================
        # Candle Type
        # ======================

        candle_type = features.get(
            "candle_type",
            "NEUTRAL"
        )

        if candle_type == "BULLISH":

            score += 1.0

        elif candle_type == "BEARISH":

            score -= 1.0


        # ======================
        # Price Position
        # ======================

        price_position = float(
            features.get(
                "price_position",
                0.5
            )
        )

        price_position = max(
            0.0,
            min(
                price_position,
                1.0
            )
        )

        if price_position < 0.8:

            score += 1.0

        else:

            score -= 0.5


        # ======================
        # Buying Pressure
        # ======================

        buying_pressure = float(
            features.get(
                "buying_pressure",
                0.5
            )
        )

        buying_pressure = max(
            0.0,
            min(
                buying_pressure,
                1.0
            )
        )

        score += (
            buying_pressure - 0.5
        ) * 2.0


        # ======================
        # Volatility
        # ======================

        volatility = float(
            features.get(
                "volatility",
                0
            )
        )

        # High volatility reduces confidence
        # but does not completely reverse the signal

        if volatility > 0.02:

            score -= 1.0

        elif volatility > 0.01:

            score -= 0.5


        # ======================
        # Score Bound
        # ======================

        # The theoretical score is approximately
        # between -10 and +10.

        score = max(
            -10.0,
            min(
                score,
                10.0
            )
        )


        # ======================
        # Continuous Confidence
        # ======================

        # Convert score into directional
        # confidence from 0 to 1.

        confidence = (
            score + 10.0
        ) / 20.0

        confidence = max(
            0.01,
            min(
                confidence,
                0.99
            )
        )


        # ======================
        # Decision
        # ======================

        if score >= 3.0:

            action = "BUY"

        elif score <= -3.0:

            action = "SELL"

        else:

            action = "HOLD"


        # ======================
        # Confidence Adjustment
        # ======================

        # HOLD should not report
        # extremely high confidence.

        if action == "HOLD":

            confidence = min(
                confidence,
                0.60
            )


        # ======================
        # Final Output
        # ======================

        return {

            "action": action,

            "score": round(
                score,
                2
            ),

            "confidence": round(
                confidence,
                3
            )

        }
