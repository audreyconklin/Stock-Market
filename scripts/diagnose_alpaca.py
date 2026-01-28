import os
from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


def main() -> None:
    load_dotenv()

    key = os.getenv("ALPACA_API_KEY", "").strip()
    secret = os.getenv("ALPACA_API_SECRET", "").strip()
    paper = os.getenv("ALPACA_PAPER", "true").strip().lower() in {"1", "true", "yes", "y", "on"}
    feed = os.getenv("ALPACA_DATA_FEED", "iex").strip().lower() or "iex"
    sym = os.getenv("DIAG_SYMBOL", "PFE").strip().upper() or "PFE"

    if not key or not secret:
        raise SystemExit("Missing ALPACA_API_KEY/ALPACA_API_SECRET (check your .env).")

    print("Loaded env:")
    print(f"- ALPACA_PAPER={paper}")
    print(f"- ALPACA_DATA_FEED={feed}")
    print(f"- DIAG_SYMBOL={sym}")
    print("- ALPACA_API_KEY present? True")
    print("- ALPACA_API_SECRET present? True")

    print("\nTesting trading auth...")
    trading = TradingClient(key, secret, paper=paper)
    try:
        acct = trading.get_account()
        print(f"OK trading auth. account_id={acct.id} status={acct.status} equity={acct.equity}")
    except Exception as e:
        print("FAILED trading auth.")
        raise

    print("\nTesting market data auth (daily bars)...")
    data = StockHistoricalDataClient(key, secret)
    try:
        req = StockBarsRequest(symbol_or_symbols=[sym], timeframe=TimeFrame.Day, limit=5, feed=feed)
        bars = data.get_stock_bars(req)
        series = bars.data.get(sym, [])
        closes = [float(b.close) for b in series]
        print(f"OK data auth. received {len(closes)} bars. closes={closes}")
    except Exception as e:
        print("FAILED data auth.")
        raise


if __name__ == "__main__":
    main()
