from core.market_state import MarketState


def test_risk_exists():

    candles = [
        {
            "open":100,
            "high":102,
            "low":99,
            "close":101,
            "volume":10000
        },
        {
            "open":101,
            "high":104,
            "low":100,
            "close":103,
            "volume":12000
        },
        {
            "open":103,
            "high":106,
            "low":102,
            "close":105,
            "volume":15000
        }
    ]

    result = MarketState().analyze_history(candles)

    assert "risk" in result
