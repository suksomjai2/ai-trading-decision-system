from core.market_state import MarketState


def test_bullish_decision():
    candles = [
        {"open":99,"high":101,"low":98,"close":100,"volume":10000},
        {"open":100,"high":103,"low":99,"close":102,"volume":11000},
        {"open":102,"high":106,"low":101,"close":105,"volume":12000},
    ]

    result = MarketState().analyze_history(candles)

    assert result["context"] == "ALIGNED"


def test_neutral_hold():
    candles = [
        {"open":100,"high":101,"low":99,"close":100,"volume":10000},
        {"open":100,"high":101,"low":99,"close":100,"volume":10000},
        {"open":100,"high":101,"low":99,"close":100,"volume":10000},
    ]

    result = MarketState().analyze_history(candles)

    assert result["context"] == "NEUTRAL"
