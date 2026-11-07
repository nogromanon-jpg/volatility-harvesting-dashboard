import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from itertools import combinations
from datetime import datetime, timedelta

st.set_page_config(page_title="Volatility Harvesting Dashboard", layout="wide", page_icon="⚡")

st.title("⚡ Volatility Harvesting Dashboard")
st.caption("Constant rebalancing + inverse-volatility weights to harvest the rebalancing bonus. Research-backed, tax-aware, and practical.")

# Sidebar controls
with st.sidebar:
    st.header("Settings")
    tax_advantaged = st.checkbox("Tax-advantaged account (0% tax)", value=True)
    cost_bps = st.slider("Transaction cost (bps)", 0, 20, 5)
    rebalance_method = st.selectbox("Rebalancing method", ["band", "monthly", "weekly"])
    band = st.slider("Band threshold (%)", 3, 20, 8) / 100
    initial_capital = st.number_input("Initial capital ($)", 10000, 1000000, 100000)
    lookback = st.slider("Lookback days for screening", 63, 504, 252)
    min_vol = st.slider("Min average vol", 0.15, 0.60, 0.25)
    max_corr = st.slider("Max correlation", 0.0, 0.8, 0.50)

class VolatilityHarvestingSystem:
    def __init__(self, tax_advantaged=False, cost_bps=5):
        self.tax_advantaged = tax_advantaged
        self.cost_bps = cost_bps

    def inverse_vol_weights(self, returns_window):
        vols = returns_window.std() * np.sqrt(252)
        inv = 1.0 / np.maximum(vols, 1e-6)
        return inv / inv.sum()

    def screen(self, tickers, start, lookback, min_vol, max_corr, top_n=10):
        data = yf.download(tickers, start=start, auto_adjust=True, progress=False)["Close"]
        data = data.dropna(how="all").ffill().dropna(axis=1)
        if data.empty or len(data) < lookback:
            return pd.DataFrame()
        recent = data.pct_change().tail(lookback)
        results = []
        for a, b in combinations(data.columns, 2):
            if a not in recent.columns or b not in recent.columns:
                continue
            va = recent[a].std() * np.sqrt(252)
            vb = recent[b].std() * np.sqrt(252)
            corr = recent[a].corr(recent[b])
            if np.isnan(corr):
                continue
            avg_vol = (va + vb) / 2
            score = avg_vol * (1 - corr)
            if avg_vol >= min_vol and corr <= max_corr:
                results.append({
                    "pair": f"{a}/{b}", "a": a, "b": b,
                    "vol_a": round(va, 2), "vol_b": round(vb, 2),
                    "corr": round(corr, 2), "score": round(score, 3)
                })
        if not results:
            return pd.DataFrame()
        return pd.DataFrame(results).sort_values("score", ascending=False).head(top_n)

    def backtest(self, prices, rebalance="band", band=0.08, initial=100000):
        if prices.empty or len(prices) < 30:
            return None
        returns = prices.pct_change().fillna(0)
        n_assets = prices.shape[1]
        shares = np.zeros(n_assets)
        cash = float(initial)
        values = []
        costs = 0.0
        rebalances = 0

        w = self.inverse_vol_weights(returns.iloc[:min(63, len(returns))])
        for i in range(n_assets):
            dollars = cash * w.iloc[i]
            shares[i] = dollars / prices.iloc[0, i]
            cash -= dollars * (1 + self.cost_bps / 10000)

        for t in range(1, len(prices)):
            px = prices.iloc[t].values
            val = (shares * px).sum() + cash
            curr_w = (shares * px) / max(val, 1e-8)

            if t >= 63:
                w = self.inverse_vol_weights(returns.iloc[max(0, t-63):t])
            w_arr = w.values

            do_rebal = False
            if rebalance == "monthly" and prices.index[t].month != prices.index[t-1].month:
                do_rebal = True
            elif rebalance == "weekly" and prices.index[t].weekday() == 0:
                do_rebal = True
            elif rebalance == "band" and np.abs(curr_w - w_arr).max() > band:
                do_rebal = True

            if do_rebal and t > 5:
                target = w_arr * val
                trade = target - shares * px
                cost = np.abs(trade).sum() * (self.cost_bps / 10000)
                costs += cost
                cash -= cost
                shares = target / np.maximum(px, 1e-8)
                rebalances += 1

            values.append(val)

        series = pd.Series(values, index=prices.index[1:])
        final = series.iloc[-1]
        years = len(series) / 252
        cagr = (final / initial) ** (1 / years) - 1 if years > 0 else 0
        return {
            "multiple": final / initial,
            "cagr": cagr,
            "costs": costs,
            "rebalances": rebalances,
            "series": series,
            "final": final
        }

# Default universe
default_universe = ["SPY", "QQQ", "GLD", "TLT", "IBIT", "EEM", "IWM", "ARKK", "SMH", "VNQ", "XLE", "XLF"]

st.subheader("1. Asset Universe")
custom = st.text_input("Add tickers (comma-separated)", "")
universe = default_universe + [t.strip().upper() for t in custom.split(",") if t.strip()]

if st.button("Run Screener", type="primary"):
    with st.spinner("Downloading data and screening pairs..."):
        system = VolatilityHarvestingSystem(tax_advantaged, cost_bps)
        start = (datetime.now() - timedelta(days=lookback + 100)).strftime("%Y-%m-%d")
        top = system.screen(universe, start, lookback, min_vol, max_corr)
        st.session_state["top"] = top
        st.session_state["system"] = system

if "top" in st.session_state and not st.session_state["top"].empty:
    st.subheader("2. Top Pairs (High Vol + Low Correlation)")
    st.dataframe(st.session_state["top"], use_container_width=True)

    selected = st.selectbox("Select pair to backtest", st.session_state["top"]["pair"].tolist())
    if selected and st.button("Run Backtest"):
        a, b = selected.split("/")
        with st.spinner(f"Backtesting {selected}..."):
            prices = yf.download([a, b], start="2021-01-01", auto_adjust=True, progress=False)["Close"].dropna()
            system = st.session_state["system"]
            res = system.backtest(prices, rebalance=rebalance_method, band=band, initial=initial_capital)
            if res:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Final Multiple", f"{res['multiple']:.2f}x")
                col2.metric("CAGR", f"{res['cagr']:.1%}")
                col3.metric("Total Costs", f"${res['costs']:,.0f}")
                col4.metric("Rebalances", res["rebalances"])

                # Chart
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=res["series"].index, y=res["series"], name="Strategy", line=dict(color="#00cc96")))
                # Buy & hold equal
                eq = np.ones(2) / 2
                shares_bh = (eq * initial_capital) / prices.iloc[0].values
                bah = (prices * shares_bh).sum(axis=1)
                fig.add_trace(go.Scatter(x=bah.index, y=bah, name="Buy & Hold Equal", line=dict(color="#636efa", dash="dash")))
                fig.update_layout(title=f"{selected} — {rebalance_method.title()} Rebalancing", height=500, template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)

                st.info("**Practical notes:** Band rebalancing (8%) usually gives the best trade-off of rebalancing bonus vs. costs/taxes. Run in a tax-advantaged account when possible. Real-world bonus is typically modest (0.5–2% in favorable conditions).")
else:
    st.info("Click 'Run Screener' to find high-volatility, low-correlation pairs.")

st.markdown("---")
st.caption("Built from research on Cover's Universal Portfolios, Shannon's Demon, and risk-parity rebalancing premium. Not financial advice.")
