from enum import Enum


class MarketRegime(Enum):
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    RANGE = "RANGE"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    TRANSITION = "TRANSITION"
    NO_TRADE = "NO_TRADE"


class RegimeClassifier:
    """
    Market Regime Classification Engine

    Input:
        Market features from FeatureEngine

    Output:
        MarketRegime state
    """

    def __init__(self):
        pass


    def classify(self, features):
        """
        Determine current market regime
        """

        trend_direction = features.get(
            "trend_direction",
            "NEUTRAL"
        )

        volatility_state = features.get(
            "volatility_state",
            "NORMAL"
        )

        trend_strength = features.get(
            "trend_strength",
            0
        )


        # Extreme volatility protection
        if volatility_state == "HIGH":
            return MarketRegime.HIGH_VOLATILITY


        # Strong bullish structure
        if (
            trend_direction == "UP"
            and trend_strength >= 0.7
        ):
            return MarketRegime.TREND_UP


        # Strong bearish structure
        if (
            trend_direction == "DOWN"
            and trend_strength >= 0.7
        ):
            return MarketRegime.TREND_DOWN


        # Weak trend = transition
        if (
            trend_direction in ["UP", "DOWN"]
            and trend_strength < 0.7
        ):
            return MarketRegime.TRANSITION


        # Sideway condition
        if trend_direction == "NEUTRAL":
            return MarketRegime.RANGE


        return MarketRegime.NO_TRADE
