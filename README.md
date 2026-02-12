# Stock Market Bot (Alpaca Paper Trading)

Long-term SMA trend strategy:
- Rank symbols by short SMA − long SMA
- Buy top symbol when trend is positive and cooldown passed
- Sell when short SMA drops below long SMA

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create `.env` from the example (do not commit `.env`):
   ```bash
   copy .env.example .env
   ```

3. Set your Alpaca credentials in `.env`:
   - `ALPACA_API_KEY`
   - `ALPACA_API_SECRET`

## Run

```bash
python main.py
```

## Configuration

Optional `.env` variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `WATCHLIST` | PFE,T,AAPL | Comma-separated symbols |
| `CASH_START` | 10000 | Starting cash (paper only) |
| `ALPACA_DATA_FEED` | iex | Use `iex` for free data feed |
| `SHORT_WINDOW` | 50 | Short SMA window (days) |
| `LONG_WINDOW` | 200 | Long SMA window (days) |
| `WAIT_DAYS` | 5 | Cooldown between buys |
| `SHARES_PER_TRADE` | 50 | Shares per buy order |
| `MAX_SHARES` | 300 | Max shares per symbol |

## Troubleshooting

**401 Unauthorized** — Credentials invalid. Run:
```bash
python scripts/diagnose_alpaca.py
```

**403 "recent SIP data"** — Add to `.env`:
```
ALPACA_DATA_FEED=iex
```

## Notes

- Secrets load from `.env` (gitignored).
- Bot saves `state.json` for trade cooldown (gitignored).
