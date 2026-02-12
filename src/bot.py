import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.common.exceptions import APIError


STATE_PATH = Path(__file__).resolve().parents[1] / "state.json"

# Dictionary (hash map) that models a few long-term companies we care about.
# This is used when printing rankings so we can show human-readable names/sectors.
COMPANIES: Dict[str, Dict[str, str]] = {
    "PFE": {"name": "Pfizer Inc.", "sector": "Healthcare"},
    "T": {"name": "AT&T Inc.", "sector": "Telecommunications"},
    "AAPL": {"name": "Apple Inc.", "sector": "Technology"},
}


@dataclass(frozen=True)
class Settings:
    api_key: str
    api_secret: str
    paper: bool
    data_feed: str
    watchlist: List[str]
    cash_start: float
    max_shares: int
    shares_per_trade: int
    wait_days: int
    short_window: int
    long_window: int


def _get_env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_settings() -> Settings:
    load_dotenv()

    api_key = os.getenv("ALPACA_API_KEY", "").strip()
    api_secret = os.getenv("ALPACA_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise RuntimeError(
            "Missing Alpaca credentials. Set ALPACA_API_KEY and ALPACA_API_SECRET in your environment or .env."
        )

    watchlist_raw = os.getenv("WATCHLIST", "PFE,T")
    watchlist = [s.strip().upper() for s in watchlist_raw.split(",") if s.strip()]
    if not watchlist:
        raise RuntimeError("WATCHLIST is empty.")

    return Settings(
        api_key=api_key,
        api_secret=api_secret,
        paper=_get_env_bool("ALPACA_PAPER", True),
        data_feed=os.getenv("ALPACA_DATA_FEED", "iex").strip().lower() or "iex",
        watchlist=watchlist,
        cash_start=float(os.getenv("CASH_START", "10000")),
        max_shares=int(os.getenv("MAX_SHARES", "300")),
        shares_per_trade=int(os.getenv("SHARES_PER_TRADE", "50")),
        wait_days=int(os.getenv("WAIT_DAYS", "5")),
        short_window=int(os.getenv("SHORT_WINDOW", "50")),
        long_window=int(os.getenv("LONG_WINDOW", "200")),
    )


def load_state() -> Dict:
    if not STATE_PATH.exists():
        return {"last_trade_day": {}}
    data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    # Only keep last_trade_day; cash comes from Alpaca
    return {"last_trade_day": data.get("last_trade_day", {})}


def save_state(state: Dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def sma(prices: List[float]) -> float:
    return sum(prices) / len(prices)


def get_last_n_closes(
    data_client: StockHistoricalDataClient, symbol: str, n: int, feed: str
) -> List[float]:
    # Use calendar days back to ensure we get enough trading bars.
    # Roughly ~252 trading days/year, so 400 calendar days is plenty for 200 trading days.
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=400)

    req = StockBarsRequest(
        symbol_or_symbols=[symbol],
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        adjustment="raw",
        feed=feed,
    )
    try:
        bars = data_client.get_stock_bars(req)
    except APIError as e:
        msg = str(e)
        if "subscription does not permit" in msg and "SIP" in msg:
            raise RuntimeError(
                "Alpaca rejected the market data request: subscription does not permit querying recent SIP data.\n\n"
                "Fix: use the free IEX feed by setting `ALPACA_DATA_FEED=iex` in your .env (recommended).\n"
                "If you have a paid SIP subscription, set `ALPACA_DATA_FEED=sip`.\n\n"
                "To confirm, run: python scripts/diagnose_alpaca.py"
            ) from e
        if "401" in msg or "Unauthorized" in msg or "Authorization Required" in msg:
            raise RuntimeError(
                "Alpaca market data request returned 401 Unauthorized.\n\n"
                "This means your .env credentials are being read, but Alpaca is rejecting them.\n"
                "Fixes:\n"
                "- Make sure you are using your Alpaca Trading API Key/Secret (not broker/OAuth keys).\n"
                "- Regenerate/rotate keys in Alpaca and update your local .env.\n"
                "- Restart the terminal after editing .env.\n\n"
                "To diagnose, run: python scripts/diagnose_alpaca.py"
            ) from e
        raise
    series = bars.data.get(symbol, [])
    closes = [float(b.close) for b in series]
    if len(closes) < n:
        raise RuntimeError(f"Not enough daily bars for {symbol}: need {n}, got {len(closes)}")
    return closes[-n:]


def current_position_qty(trading_client: TradingClient, symbol: str) -> int:
    try:
        pos = trading_client.get_open_position(symbol)
        return int(float(pos.qty))
    except Exception:
        return 0


def market_buy(trading_client: TradingClient, symbol: str, qty: int) -> None:
    order = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
    )
    trading_client.submit_order(order_data=order)


def market_sell(trading_client: TradingClient, symbol: str, qty: int) -> None:
    order = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )
    trading_client.submit_order(order_data=order)


def _parse_day(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _format_day(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")


def days_since(last_day: Optional[str], today: datetime) -> int:
    last = _parse_day(last_day)
    if last is None:
        return 10**9
    return (today.date() - last.date()).days


def rank_symbols(
    data_client: StockHistoricalDataClient,
    symbols: List[str],
    short_window: int,
    long_window: int,
    feed: str,
) -> List[Tuple[str, float, float, float, float]]:
    ranked = []
    for sym in symbols:
        closes_long = get_last_n_closes(data_client, sym, long_window, feed=feed)
        closes_short = closes_long[-short_window:]
        short_avg = sma(closes_short)
        long_avg = sma(closes_long)
        trend = short_avg - long_avg
        latest = closes_long[-1]
        ranked.append((sym, trend, short_avg, long_avg, latest))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def run_once() -> None:
    settings = load_settings()
    state = load_state()

    today = datetime.now(timezone.utc)

    trading_client = TradingClient(settings.api_key, settings.api_secret, paper=settings.paper)
    data_client = StockHistoricalDataClient(settings.api_key, settings.api_secret)

    # Use actual Alpaca account (ensures correct paper account with 1M cash)
    account = trading_client.get_account()
    cash = float(account.cash)
    account_id = account.id
    mode = "PAPER" if settings.paper else "LIVE"
    print(f"Using {mode} account | ID: {account_id} | Cash: ${cash:,.2f}")

    ranked = rank_symbols(
        data_client=data_client,
        symbols=settings.watchlist,
        short_window=settings.short_window,
        long_window=settings.long_window,
        feed=settings.data_feed,
    )

    print("Ranked symbols (best first):")
    for sym, trend, short_avg, long_avg, latest in ranked:
        info = COMPANIES.get(sym, {})
        name = info.get("name", "Unknown")
        sector = info.get("sector", "Unknown")
        print(
            f"- {sym} ({name}, {sector}): "
            f"trend={trend:.4f} (short={short_avg:.2f}, long={long_avg:.2f}, last={latest:.2f})"
        )

    # Market must be open for orders to fill (9:30 AM - 4:00 PM ET, Mon-Fri)
    clock = trading_client.get_clock()
    if not clock.is_open:
        next_open = clock.next_open
        print(f"\n*** MARKET CLOSED *** Orders won't fill. Run during 9:30 AM - 4 PM ET (Mon-Fri).")
        if next_open:
            print(f"    Next open: {next_open.strftime('%a %b %d, %I:%M %p')} ET")
        save_state(state)
        return

    # SELL RULE: sell all positions where short < long (long-term decline)
    for sym, _, short_avg, long_avg, latest in ranked:
        qty = current_position_qty(trading_client, sym)
        if qty <= 0:
            continue
        if short_avg < long_avg:
            market_sell(trading_client, sym, qty)
            proceeds = qty * latest
            cash += proceeds
            state["last_trade_day"][sym] = _format_day(today)
            print(f"sell {sym} qty={qty} est_proceeds={proceeds:.2f}")

    # BUY RULE: buy ALL symbols with positive trend, cooldown passed, and limits allow
    for sym, trend, _, _, price in ranked:
        if trend <= 0:
            continue
        waited = days_since(state["last_trade_day"].get(sym), today)
        qty = current_position_qty(trading_client, sym)
        cost = settings.shares_per_trade * price
        can_afford = cash >= cost
        under_max = qty + settings.shares_per_trade <= settings.max_shares

        if waited >= settings.wait_days and under_max and can_afford:
            market_buy(trading_client, sym, settings.shares_per_trade)
            cash -= cost
            state["last_trade_day"][sym] = _format_day(today)
            print(f"buy {sym} qty={settings.shares_per_trade} est_cost={cost:.2f}")
        else:
            print(
                f"no buy {sym}:",
                f"waited={waited} (need {settings.wait_days})",
                f"under_max={under_max} (pos={qty})",
                f"can_afford={can_afford} (cash={cash:,.2f})",
            )

    print("\nState summary:")
    print(f"- account cash = ${cash:,.2f}")
    print(f"- last_trade_day = {state['last_trade_day']}")

    save_state(state)
