"""
Trader Performance vs Market Sentiment — Interactive Dashboard
Primetrade.ai Data Science Intern Assignment — Bonus deliverable

Run with:
    pip install streamlit plotly
    streamlit run dashboard.py

Expects data/fear_greed_index.csv and data/historical_data.csv (same files used
by the main analysis notebook) to be present relative to this script.
"""

import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Sentiment vs Trader Performance", layout="wide")

SENTIMENT_ORDER = ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"]
SENTIMENT_COLORS = {
    "Extreme Fear": "#8B0000", "Fear": "#E67E22", "Neutral": "#95A5A6",
    "Greed": "#2ECC71", "Extreme Greed": "#145A32",
}


@st.cache_data
def load_data():
    fg = pd.read_csv("data/fear_greed_index.csv")
    hd = pd.read_csv("data/historical_data.csv")

    fg["date"] = pd.to_datetime(fg["date"])
    fg = fg[["date", "value", "classification"]].rename(
        columns={"value": "sentiment_value", "classification": "sentiment"}
    )

    hd["datetime"] = pd.to_datetime(hd["Timestamp IST"], format="%d-%m-%Y %H:%M")
    hd["date"] = hd["datetime"].dt.normalize()
    exotic = ["Spot Dust Conversion", "Auto-Deleveraging", "Liquidated Isolated Short", "Settlement"]
    hd = hd[~hd["Direction"].isin(exotic)].copy()

    merged = hd.merge(fg, on="date", how="inner")
    return merged


def kpi_row(df):
    total_pnl = df["Closed PnL"].sum()
    closed = df[df["Closed PnL"] != 0]
    win_rate = (closed["Closed PnL"] > 0).mean() if len(closed) else np.nan
    n_trades = len(df)
    n_traders = df["Account"].nunique()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Closed PnL", f"${total_pnl:,.0f}")
    c2.metric("Win Rate", f"{win_rate:.1%}" if pd.notna(win_rate) else "n/a")
    c3.metric("Trades", f"{n_trades:,}")
    c4.metric("Active Traders", f"{n_traders}")


def main():
    st.title("📊 Trader Performance vs Market Sentiment")
    st.caption("Hyperliquid trade data × Bitcoin Fear & Greed Index — interactive companion to the analysis notebook")

    try:
        merged = load_data()
    except FileNotFoundError:
        st.error(
            "Couldn't find `data/fear_greed_index.csv` or `data/historical_data.csv`. "
            "Place both files in a `data/` folder next to this script and reload."
        )
        return

    # ---- Sidebar filters ----
    st.sidebar.header("Filters")
    sentiments = st.sidebar.multiselect(
        "Sentiment regime", options=SENTIMENT_ORDER, default=SENTIMENT_ORDER
    )
    accounts = sorted(merged["Account"].unique())
    account_choice = st.sidebar.multiselect(
        "Accounts (leave empty = all)", options=accounts, default=[]
    )
    date_min, date_max = merged["date"].min(), merged["date"].max()
    date_range = st.sidebar.date_input(
        "Date range", value=(date_min.date(), date_max.date()),
        min_value=date_min.date(), max_value=date_max.date(),
    )

    filtered = merged[merged["sentiment"].isin(sentiments)]
    if account_choice:
        filtered = filtered[filtered["Account"].isin(account_choice)]
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
        filtered = filtered[(filtered["date"] >= start) & (filtered["date"] <= end)]

    if filtered.empty:
        st.warning("No rows match the current filters — widen your selection.")
        return

    kpi_row(filtered)
    st.divider()

    tab1, tab2, tab3 = st.tabs(["Sentiment Comparison", "Trader Segments", "Raw Data"])

    with tab1:
        col1, col2 = st.columns(2)

        summary = filtered.groupby("sentiment").agg(
            avg_pnl=("Closed PnL", "mean"),
            total_pnl=("Closed PnL", "sum"),
            win_rate=("Closed PnL", lambda s: (s[s != 0] > 0).mean() if (s != 0).any() else np.nan),
            trade_count=("Closed PnL", "size"),
            total_volume=("Size USD", "sum"),
        ).reindex([s for s in SENTIMENT_ORDER if s in filtered["sentiment"].unique()])

        with col1:
            fig1 = px.bar(
                summary, x=summary.index, y="avg_pnl",
                color=summary.index, color_discrete_map=SENTIMENT_COLORS,
                title="Average Closed PnL by Sentiment", labels={"avg_pnl": "Avg PnL (USD)", "x": "Sentiment"},
            )
            fig1.update_layout(showlegend=False)
            st.plotly_chart(fig1, use_container_width=True)

        with col2:
            fig2 = px.bar(
                summary, x=summary.index, y="win_rate",
                color=summary.index, color_discrete_map=SENTIMENT_COLORS,
                title="Win Rate by Sentiment", labels={"win_rate": "Win Rate", "x": "Sentiment"},
            )
            fig2.update_layout(showlegend=False, yaxis_tickformat=".0%")
            st.plotly_chart(fig2, use_container_width=True)

        col3, col4 = st.columns(2)
        with col3:
            fig3 = px.bar(
                summary, x=summary.index, y="trade_count",
                color=summary.index, color_discrete_map=SENTIMENT_COLORS,
                title="Trade Count by Sentiment",
            )
            fig3.update_layout(showlegend=False)
            st.plotly_chart(fig3, use_container_width=True)

        with col4:
            fig4 = px.bar(
                summary, x=summary.index, y="total_volume",
                color=summary.index, color_discrete_map=SENTIMENT_COLORS,
                title="Total Trade Volume (USD) by Sentiment",
            )
            fig4.update_layout(showlegend=False)
            st.plotly_chart(fig4, use_container_width=True)

        daily_pnl = filtered.groupby("date")["Closed PnL"].sum().reset_index()
        daily_pnl["cumulative"] = daily_pnl["Closed PnL"].cumsum()
        fig5 = go.Figure()
        fig5.add_trace(go.Scatter(x=daily_pnl["date"], y=daily_pnl["cumulative"], mode="lines", line=dict(color="royalblue")))
        fig5.update_layout(title="Cumulative Closed PnL Over Time (filtered selection)", yaxis_title="Cumulative PnL (USD)")
        st.plotly_chart(fig5, use_container_width=True)

        st.dataframe(summary.round(3), use_container_width=True)

    with tab2:
        st.subheader("Trader-level segmentation (based on current filters)")
        closed = filtered[filtered["Closed PnL"] != 0].copy()
        closed["is_win"] = closed["Closed PnL"] > 0

        trader_summary = filtered.groupby("Account").agg(
            total_pnl=("Closed PnL", "sum"),
            avg_pnl=("Closed PnL", "mean"),
            trade_count=("Closed PnL", "count"),
            avg_fee=("Fee", "mean"),
        ).round(2)
        trader_summary["win_rate"] = closed.groupby("Account")["is_win"].mean().round(3)

        if len(trader_summary) >= 2:
            median_fee = trader_summary["avg_fee"].median()
            median_freq = trader_summary["trade_count"].median()
            trader_summary["fee_segment"] = np.where(trader_summary["avg_fee"] > median_fee, "High Fee", "Low Fee")
            trader_summary["frequency_segment"] = np.where(trader_summary["trade_count"] > median_freq, "Frequent", "Infrequent")

            fig6 = px.scatter(
                trader_summary.reset_index(), x="avg_fee", y="avg_pnl",
                color="fee_segment", size="trade_count", hover_name="Account",
                title="Trader Segments: Avg Fee vs Avg PnL (bubble size = trade count)",
            )
            st.plotly_chart(fig6, use_container_width=True)

            seg1, seg2 = st.columns(2)
            seg1.write("**By fee level**")
            seg1.dataframe(trader_summary.groupby("fee_segment")[["avg_pnl", "win_rate"]].mean().round(3))
            seg2.write("**By trade frequency**")
            seg2.dataframe(trader_summary.groupby("frequency_segment")[["avg_pnl", "win_rate"]].mean().round(3))
        else:
            st.info("Select more accounts/date range to see segment comparisons.")

        st.write("**Full trader table**")
        st.dataframe(trader_summary.sort_values("total_pnl", ascending=False), use_container_width=True)

    with tab3:
        st.subheader("Filtered raw trades")
        st.dataframe(
            filtered[["Account", "date", "Coin", "Side", "Direction", "Size USD", "Closed PnL", "Fee", "sentiment"]]
            .sort_values("date", ascending=False)
            .head(1000),
            use_container_width=True,
        )
        st.caption(f"Showing up to 1,000 of {len(filtered):,} filtered rows.")


if __name__ == "__main__":
    main()
