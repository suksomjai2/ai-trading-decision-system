from core.market_state import MarketState

def test_aligned_up():
    candles = [
        {"open":99,"high":101,"low":98,"close":100,"volume":10000},
        {"open":100,"high":103,"low":99,"close":102,"volume":11000},
        {"open":102,"high":106,"low":101,"close":105,"volume":12000},
    ]

    result = MarketState().analyze_history(candles)

    assert result["context"] == "ALIGNED"


def test_aligned_down():
    candles = [
        {"open":106,"high":107,"low":104,"close":105,"volume":12000},
        {"open":105,"high":106,"low":101,"close":102,"volume":11000},
        {"open":102,"high":103,"low":99,"close":100,"volume":10000},
    ]

    result = MarketState().analyze_history(candles)

    assert result["context"] == "ALIGNED"


def test_neutral():
    candles = [
        {"open":100,"high":101,"low":99,"close":100,"volume":10000},
        {"open":100,"high":101,"low":99,"close":100,"volume":10000},
        {"open":100,"high":101,"low":99,"close":100,"volume":10000},
    ]

    result = MarketState().analyze_history(candles)

    assert result["context"] == "NEUTRAL"
