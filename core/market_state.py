from enum import Enum


class MarketRegime(Enum):
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    TRANSITION = "TRANSITION"
    NO_TRADE = "NO_TRADE"


class MarketState:

    def __init__(self):
        self.current_state = MarketRegime.TRANSITION


    def classify(self, features):

        volatility = features.get("volatility", 0)
        trend_strength = features.get("trend_strength", 0)
        trend_direction = features.get("trend_direction", None)
        range_score = features.get("range_score", 0)


        # 1. Extreme volatility has priority
        if volatility >= 0.85:
            self.current_state = MarketRegime.HIGH_VOLATILITY


        # 2. Strong trend detection
        elif trend_strength >= 0.70:

            if trend_direction == "UP":
                self.current_state = MarketRegime.TREND_UP

            elif trend_direction == "DOWN":
                self.current_state = MarketRegime.TREND_DOWN


        # 3. Range condition
        elif range_score >= 0.70:
            self.current_state = MarketRegime.RANGE


        # 4. Unknown / changing condition
        else:
            self.current_state = MarketRegime.TRANSITION


        return self.current_state.value
