import streamlit as st

from core.market_state import MarketState
from core.feature_engine import FeatureEngine
from core.risk_engine import RiskEngine


# =========================
# Page Config
# =========================

st.set_page_config(
    page_title="AI Trading Decision System",
    layout="wide"
)


# =========================
# Title
# =========================

st.title("🧠 AI Trading Decision System")
st.subheader("XAUUSD AI Analysis Dashboard")


# =========================
# Initialize Engine
# =========================

market_engine = MarketState()
feature_engine = FeatureEngine()
risk_engine = RiskEngine()



# =========================
# Market Data
# =========================

market_data = {

    "open": 2650,
    "high": 2665,
    "low": 2645,
    "close": 2660,
    "volume": 1200000

}



# =========================
# Market Analysis
# =========================

market_result = market_engine.analyze(
    market_data
)



# =========================
# Extract Data
# =========================

features = market_result["features"]

decision = market_result["decision"]



# =========================
# Risk
# =========================

risk = risk_engine.evaluate(
    decision,
    features
)



# =========================
# Dashboard
# =========================

col1, col2, col3 = st.columns(3)



with col1:

    st.metric(
        "Market Trend",
        features.get(
            "trend_direction",
            "UNKNOWN"
        )
    )



with col2:

    st.metric(
        "Decision",
        decision.get(
            "action",
            "HOLD"
        )
    )



with col3:

    st.metric(
        "Confidence",
        decision.get(
            "confidence",
            0
        )
    )



# =========================
# Details
# =========================

st.divider()


st.write("### Market Features")

st.json(
    features
)



st.write("### Decision Detail")

st.json(
    decision
)



st.write("### Risk Detail")

st.json(
    risk
)
