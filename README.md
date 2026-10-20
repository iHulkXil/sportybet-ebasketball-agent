# SportyBet eBasketball (NBA2K) Accumulator Agent

Web app that scans SportyBet for eBasketball / NBA2K Over/Under markets with lines at or below a configurable threshold (default 59.5), prioritizes the **Over** side, builds a custom accumulator, and generates an anonymous SportyBet booking code with a one-click load link.

Designed so the core logic can later be wrapped in a Telegram bot.

## Features
- Full set of selectors and toggles (side, line threshold, first-half only, odds range, combo size, stake, sport ID, market IDs, timeline)
- Live scan of SportyBet internal API
- Accumulator builder
- Anonymous booking code generation
- Direct share link: `https://www.sportybet.com/ng/?shareCode=CODE`

## Quick Start

```bash
pip install -r requirements.txt
streamlit run sportybet_web_app.py
```

Open the URL Streamlit prints (usually http://localhost:8501).

## Important Warnings
- Uses undocumented SportyBet internal endpoints. They can change or be blocked without notice.
- Booking code creation is anonymous and **non-staking**. You still review the slip, enter your stake, and place the bet yourself on SportyBet.
- Works best from a Nigerian IP.
- Only bet what you can afford to lose. This is not financial advice.
- Odds can move after the code is generated — always verify on the site.

## Later Telegram Integration
The functions `fetch_upcoming_events`, `filter_candidates`, `suggest_combo`, and `create_booking_code` are self-contained and can be imported into a Telegram bot.

## License
MIT — use at your own risk.
