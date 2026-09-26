import streamlit as st


st.set_page_config(
    page_title="AI Trading Decision System",
    layout="wide"
)


st.title("🧠 AI Trading Decision System v0.1")

st.subheader("XAUUSD Market Analysis")


# Market Overview

col1, col2, col3 = st.columns(3)


with col1:
    st.metric(
        "Current Price",
        "4282"
    )


with col2:
    st.metric(
        "H4 Trend",
        "DOWN"
    )


with col3:
    st.metric(
        "AI Confidence",
        "65%"
    )


st.divider()


# Indicators

st.subheader("Technical Indicators")


indicators = {

"EMA20":"4285",

"EMA50":"4290",

"RSI":"38",

"ATR":"18",

"Volume":"Normal"

}


for k,v in indicators.items():
    st.write(
        f"{k}: {v}"
    )



st.divider()


# Structure

st.subheader("Market Structure")


st.write(
"""
H4:
- Lower High
- Price below EMA
- Downtrend


M15:
- Looking for Technical Rebound
- Waiting Support Confirmation
"""
)



st.divider()


# AI Decision

st.subheader("AI Decision Engine")


st.warning(
"""
WAIT

เหตุผล:

Trend ใหญ่ยังลง

รอ:
- Support Zone
- Reversal Signal
- Momentum ลดลง

ก่อนเปิด Position
"""
)



st.divider()


# Trade Plan

st.subheader("Trade Plan")


st.write(
"""
Entry:
AI Calculate


Add Position:
Risk Management


Exit:
Technical Rebound Target

"""
)
