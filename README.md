# Volatility Harvesting Dashboard

Interactive Streamlit app for screening high-volatility / low-correlation asset pairs and backtesting constant rebalancing (volatility harvesting) strategies with inverse-volatility weights.

## Features
- Automatic pair screening (high realized vol + low correlation)
- Inverse-volatility (risk-parity style) target weights
- Band, monthly, or weekly rebalancing
- Transaction cost modeling
- Tax-advantaged mode
- Interactive Plotly charts vs buy-and-hold

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL shown in the terminal (usually http://localhost:8501).

## Deploy (optional)
- Streamlit Community Cloud (free)
- Or any host that supports Python

## Disclaimer
This is a research and educational tool based on academic concepts (volatility harvesting / rebalancing bonus). Past results do not guarantee future performance. Transaction costs and taxes can significantly reduce or eliminate the edge. Not financial advice.
