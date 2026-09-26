import streamlit as st

from core.market_state import MarketState
from core.feature_engine import FeatureEngine
from core.decision_engine import DecisionEngine
from core.risk_engine import RiskEngine


st.set_page_config(
    page_title="AI Trading Decision System",
    layout="wide"
)


st.title("🧠 AI Trading Decision System")
st.subheader("XAUUSD AI Analysis Dashboard")


# Initialize engines

market_engine = MarketState()
feature_engine = FeatureEngine()
decision_engine = DecisionEngine()
risk_engine = RiskEngine()


# Sample market data
market_data = {
    "open": 2650,
    "high": 2665,
    "low": 2645,
    "close": 2660,
    "volume": 1200000
}


# Feature extraction

features = feature_engine.calculate_features(
    market_data
)


# Market state

market_state = market_engine.analyze(
    market_data
)


# Decision

decision = decision_engine.evaluate(
    market_state,
    features
)


# Risk

risk = risk_engine.evaluate(
    decision,
    features
)



col1, col2, col3 = st.columns(3)


with col1:
    st.metric(
        "Market State",
        market_state["state"]
    )


with col2:
    st.metric(
        "Decision",
        decision
    )


with col3:
    st.metric(
        "Risk Level",
        risk
    )


st.divider()


st.write("### Market Features")

st.json(features)
