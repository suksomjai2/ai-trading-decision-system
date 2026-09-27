import math


class DecisionEngine:

    def __init__(self):
        pass


    def decide(self, state, features):

        # ==========================================
        # Input Features
        # ==========================================

        trend_direction = features.get(
            "trend_direction",
            "SIDEWAYS"
        )

        trend_strength = float(
            features.get(
                "trend_strength",
                0
            )
        )

        volume_state = features.get(
            "volume_state",
            "NORMAL"
        )

        momentum = float(
            features.get(
                "momentum",
                0
            )
        )

        candle_type = features.get(
            "candle_type",
            "NEUTRAL"
        )

        buying_pressure = float(
            features.get(
                "buying_pressure",
                0.5
            )
        )

        price_position = float(
            features.get(
                "price_position",
                0.5
            )
        )

        volatility = float(
            features.get(
                "volatility",
                0
            )
        )


        # ==========================================
        # Score
        # ==========================================

        score = 0.0


        # ==========================================
        # 1. Trend Direction
        # ==========================================

        if trend_direction == "UP":
            score += 2.0

        elif trend_direction == "DOWN":
            score -= 2.0


        # ==========================================
        # 2. Trend Strength
        #
        # Strength confirms direction.
        # Range contribution: -2 to +2
        # ==========================================

        strength_score = min(
            max(
                trend_strength / 2.5,
                0.0
            ),
            2.0
        )

        if trend_direction == "UP":
            score += strength_score

        elif trend_direction == "DOWN":
            score -= strength_score


        # ==========================================
        # 3. Momentum
        #
        # Positive momentum -> bullish
        # Negative momentum -> bearish
        # Range contribution: -2 to +2
        # ==========================================

        momentum_score = max(
            -2.0,
            min(
                momentum / 10.0,
                2.0
            )
        )

        score += momentum_score


        # ==========================================
        # 4. Candle Direction
        # ==========================================

        if candle_type == "BULLISH":
            score += 1.0

        elif candle_type == "BEARISH":
            score -= 1.0


        # ==========================================
        # 5. Buying Pressure
        #
        # 0.50 = neutral
        # > 0.50 bullish
        # < 0.50 bearish
        #
        # Range contribution: -1 to +1
        # ==========================================

        buying_pressure = max(
            0.0,
            min(
                buying_pressure,
                1.0
            )
        )

        pressure_score = (
            buying_pressure - 0.5
        ) * 2.0

        score += pressure_score


        # ==========================================
        # 6. Volume Confirmation
        #
        # Volume confirms existing direction.
        # It does NOT create direction by itself.
        # ==========================================

        if volume_state == "HIGH":

            if score > 0:
                score += 0.75

            elif score < 0:
                score -= 0.75


        # ==========================================
        # 7. Price Position
        #
        # 0 = near low
        # 1 = near high
        #
        # Avoid buying too close to high.
        # Avoid selling too close to low.
        # ==========================================

        price_position = max(
            0.0,
            min(
                price_position,
                1.0
            )
        )

        if score > 0:

            if price_position >= 0.90:
                score -= 1.0

            elif price_position >= 0.80:
                score -= 0.5

            elif price_position <= 0.60:
                score += 0.25


        elif score < 0:

            if price_position <= 0.10:
                score += 1.0

            elif price_position <= 0.20:
                score += 0.5

            elif price_position >= 0.40:
                score -= 0.25


        # ==========================================
        # 8. Volatility
        #
        # High volatility reduces signal strength.
        # It should not reverse direction.
        # ==========================================

        if volatility > 0.03:

            if score > 0:
                score -= 1.25

            elif score < 0:
                score += 1.25


        elif volatility > 0.02:

            if score > 0:
                score -= 0.75

            elif score < 0:
                score += 0.75


        elif volatility > 0.01:

            if score > 0:
                score -= 0.25

            elif score < 0:
                score += 0.25


        # ==========================================
        # Score Bound
        # ==========================================

        score = max(
            -10.0,
            min(
                score,
                10.0
            )
        )


        # ==========================================
        # Decision
        #
        # Positive score = BUY pressure
        # Negative score = SELL pressure
        # ==========================================

        buy_threshold = 4.0
        sell_threshold = -4.0

        if score >= buy_threshold:
            action = "BUY"

        elif score <= sell_threshold:
            action = "SELL"

        else:
            action = "HOLD"


        # ==========================================
        # Continuous Confidence
        #
        # IMPORTANT:
        # Confidence = strength of evidence.
        #
        # It is NOT:
        # score / max_score
        #
        # Sigmoid prevents confidence from
        # jumping directly to 1.0.
        # ==========================================

        score_magnitude = abs(score)

        confidence = 1.0 / (
            1.0
            + math.exp(
                -0.55
                * (
                    score_magnitude - 4.0
                )
            )
        )


        # ==========================================
        # Trend Strength Confidence Adjustment
        # ==========================================

        normalized_strength = min(
            max(
                trend_strength / 10.0,
                0.0
            ),
            1.0
        )

        confidence *= (
            0.85
            + (
                0.15
                * normalized_strength
            )
        )


        # ==========================================
        # Volatility Confidence Adjustment
        # ==========================================

        if volatility > 0.03:
            confidence *= 0.75

        elif volatility > 0.02:
            confidence *= 0.82

        elif volatility > 0.01:
            confidence *= 0.90


        # ==========================================
        # Price Position Confidence Adjustment
        # ==========================================

        if action == "BUY":

            if price_position >= 0.90:
                confidence *= 0.80

            elif price_position >= 0.80:
                confidence *= 0.90


        elif action == "SELL":

            if price_position <= 0.10:
                confidence *= 0.80

            elif price_position <= 0.20:
                confidence *= 0.90


        # ==========================================
        # HOLD Confidence
        #
        # HOLD should not show extremely high
        # confidence with the current rule model.
        # ==========================================

        if action == "HOLD":
            confidence = min(
                confidence,
                0.65
            )


        # ==========================================
        # Final Confidence Bounds
        #
        # Never report exactly 0 or 1.
        # ==========================================

        confidence = max(
            0.01,
            min(
                confidence,
                0.99
            )
        )


        # ==========================================
        # Final Output
        # ==========================================

        return {
            "action": action,
            "score": round(
                score,
                3
            ),
            "confidence": round(
                confidence,
                3
            )
        }
