import math


class DecisionEngine:

    def __init__(self):
        pass

    def decide(self, state, features):

        # -------------------------
        # Read features
        # -------------------------
        trend = features.get("trend_direction", state)
        strength = float(features.get("trend_strength", 0))
        momentum = float(features.get("momentum", 0))
        volatility = float(features.get("volatility", 0))
        position = float(features.get("price_position", 0.5))
        pressure = float(features.get("buying_pressure", 0.5))
        volume = features.get("volume_state", "LOW")
        candle = features.get("candle_type", "NEUTRAL")

        score = 0.0

        # -------------------------
        # 1. Trend
        # -------------------------
        if trend == "UP":
            score += 2.0
        elif trend == "DOWN":
            score -= 2.0

        # -------------------------
        # 2. Trend strength
        # -------------------------
        strength = max(0.0, min(strength, 10.0))

        if trend == "UP":
            score += strength * 0.25
        elif trend == "DOWN":
            score -= strength * 0.25

        # -------------------------
        # 3. Momentum
        # -------------------------
        if momentum > 0:
            score += min(abs(momentum) / 10.0, 1.5)
        elif momentum < 0:
            score -= min(abs(momentum) / 10.0, 1.5)

        # -------------------------
        # 4. Candle confirmation
        # -------------------------
        if candle == "BULLISH":
            score += 1.0
        elif candle == "BEARISH":
            score -= 1.0

        # -------------------------
        # 5. Buying pressure
        # -------------------------
        pressure = max(0.0, min(pressure, 1.0))

        score += (pressure - 0.5) * 2.0

        # -------------------------
        # 6. Volume confirmation
        # -------------------------
        if volume == "HIGH":
            if score > 0:
                score += 0.75
            elif score < 0:
                score -= 0.75

        # -------------------------
        # 7. Price position
        # Avoid BUY near high
        # Avoid SELL near low
        # -------------------------
        position = max(0.0, min(position, 1.0))

        if score > 0:
            if position >= 0.90:
                score -= 1.0
            elif position >= 0.80:
                score -= 0.5

        elif score < 0:
            if position <= 0.10:
                score += 1.0
            elif position <= 0.20:
                score += 0.5

        # -------------------------
        # 8. Volatility risk
        # -------------------------
        if volatility > 0.03:
            score *= 0.70
        elif volatility > 0.02:
            score *= 0.82
        elif volatility > 0.01:
            score *= 0.92

        # -------------------------
        # Score bounds
        # -------------------------
        score = max(-10.0, min(score, 10.0))

        # -------------------------
        # Decision
        # -------------------------
        if score >= 4.0:
            action = "BUY"
        elif score <= -4.0:
            action = "SELL"
        else:
            action = "HOLD"

        # -------------------------
        # Continuous confidence
        # -------------------------
        magnitude = abs(score)

        confidence = 1.0 / (
            1.0 + math.exp(
                -0.55 * (magnitude - 4.0)
            )
        )

        # Trend strength adjustment
        normalized_strength = strength / 10.0

        confidence *= (
            0.75 + 0.25 * normalized_strength
        )

        # Volatility adjustment
        if volatility > 0.03:
            confidence *= 0.75
        elif volatility > 0.02:
            confidence *= 0.82
        elif volatility > 0.01:
            confidence *= 0.90

        # HOLD should not appear
        # excessively confident
        if action == "HOLD":
            confidence = min(confidence, 0.65)

        # Final bounds
        confidence = max(
            0.01,
            min(confidence, 0.99)
        )

        return {
            "action": action,
            "score": round(score, 3),
            "confidence": round(confidence, 3)
        }
