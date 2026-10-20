#!/usr/bin/env python3
"""
SportyBet eBasketball (NBA2K) Web App — Over/Under Line Filter + Accumulator Generator

Run with:
    streamlit run sportybet_web_app.py

Features:
- Full set of selectors and toggles
- Live scan of SportyBet eBasketball markets
- Filter for Over or Under on lines ≤ threshold
- Build 3-fold (or custom) accumulator
- Generate anonymous booking code + one-click load link
- Easy to later wrap the core functions in a Telegram bot

WARNING:
- Uses undocumented SportyBet internal endpoints. Can change or be blocked.
- Booking code creation is anonymous and non-staking. You still confirm stake yourself.
- Only bet what you can afford to lose. Not financial advice.
- Works best from a Nigerian IP.
"""

import os
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional

import requests
import streamlit as st

# ===================== CONFIG DEFAULTS =====================
SPORTY_BASE = "https://www.sportybet.com"
REGION = "ng"
DEFAULT_SPORT_ID = "sr:sport:2"  # Adjust if needed for eBasketball
DEFAULT_MARKET_IDS = "1,18,10,29,11,26,36,14,60100,225,227"

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Current-Country": REGION.upper(),
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===================== CORE LOGIC (reusable for Telegram later) =====================

def fetch_upcoming_events(sport_id: str, market_ids: str, timeline_hours: int, page_size: int = 50) -> List[Dict]:
    url = f"{SPORTY_BASE}/api/{REGION}/factsCenter/pcUpcomingEvents"
    params = {
        "sportId": sport_id,
        "marketId": market_ids,
        "pageSize": page_size,
        "pageNum": 1,
        "todayGames": "false",
        "timeline": timeline_hours,
        "_t": int(time.time() * 1000),
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=25)
        r.raise_for_status()
        data = r.json()
        events = []
        for tourney in data.get("data", {}).get("tournaments", []):
            for event in tourney.get("events", []):
                event["tournament"] = tourney.get("name")
                events.append(event)
        return events
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        return []

def filter_candidates(
    events: List[Dict],
    target_line: float,
    side: str,  # "over" or "under"
    first_half_only: bool,
    min_odds: float,
    max_odds: float,
) -> List[Dict]:
    candidates = []
    half_keywords = ["1st half", "first half", "1h", "half total", "1st period"]
    total_keywords = ["over/under", "o/u", "total", "points"]

    for ev in events:
        home = ev.get("homeTeamName", "")
        away = ev.get("awayTeamName", "")
        match = f"{home} vs {away}"
        event_id = ev.get("eventId")
        tournament = ev.get("tournament", "")

        for market in ev.get("markets", []):
            desc = (market.get("desc") or "").lower()
            m_id = market.get("id")

            is_half = any(k in desc for k in half_keywords)
            is_total = any(k in desc for k in total_keywords)

            if first_half_only and not is_half:
                continue
            if not is_total and not is_half:
                continue

            for outcome in market.get("outcomes", []):
                o_desc = (outcome.get("desc") or "").lower()
                odds_str = outcome.get("odds")
                if not odds_str or not outcome.get("isActive", True):
                    continue

                if side == "over" and "over" not in o_desc:
                    continue
                if side == "under" and "under" not in o_desc:
                    continue

                try:
                    odds = float(odds_str)
                    if not (min_odds <= odds <= max_odds):
                        continue

                    line = None
                    cleaned = o_desc.replace("over", "").replace("under", "")
                    for token in cleaned.split():
                        try:
                            line = float(token)
                            break
                        except:
                            continue

                    if line is not None and line <= target_line:
                        candidates.append({
                            "match": match,
                            "tournament": tournament,
                            "eventId": event_id,
                            "marketId": m_id,
                            "market_desc": market.get("desc"),
                            "outcomeId": outcome.get("id"),
                            "selection": outcome.get("desc"),
                            "odds": odds,
                            "line": line,
                            "specifier": market.get("specifier"),
                        })
                except:
                    continue

    # Deduplicate and sort (lowest line first, then best odds)
    unique = {}
    for c in candidates:
        key = f"{c['eventId']}|{c['outcomeId']}"
        unique[key] = c
    return sorted(unique.values(), key=lambda x: (x.get("line") or 999, -x["odds"]))

def suggest_combo(candidates: List[Dict], combo_size: int, stake: float) -> Optional[Dict]:
    if len(candidates) < combo_size:
        return None
    selected = candidates[:combo_size]
    total_odds = 1.0
    for s in selected:
        total_odds *= s["odds"]
    return {
        "selections": selected,
        "total_odds": round(total_odds, 2),
        "potential": round(stake * total_odds, 2),
        "stake": stake,
        "timestamp": datetime.now().isoformat(),
    }

def create_booking_code(selections: List[Dict]) -> Optional[str]:
    url = f"{SPORTY_BASE}/api/{REGION}/orders/share"
    payload = {
        "selections": [
            {
                "eventId": s["eventId"],
                "marketId": str(s["marketId"]),
                "specifier": s.get("specifier"),
                "outcomeId": str(s["outcomeId"]),
            }
            for s in selections
        ]
    }
    try:
        r = requests.post(url, json=payload, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("data", {}).get("shareCode")
    except Exception as e:
        logger.error(f"Booking error: {e}")
        return None

# ===================== STREAMLIT UI =====================

st.set_page_config(page_title="SportyBet eBasketball Accumulator", page_icon="🏀", layout="wide")

st.title("🏀 SportyBet eBasketball (NBA2K) Accumulator Builder")
st.caption("Filter low total lines → build combo → generate booking code. Core logic is reusable for a Telegram bot later.")

# Sidebar — all relevant selectors and toggles
with st.sidebar:
    st.header("Filters & Settings")

    side = st.radio("Side to bet", ["Over", "Under"], index=0, help="Prioritize Over or Under on the total line")
    target_line = st.number_input("Max line threshold", min_value=20.0, max_value=200.0, value=59.5, step=0.5)
    first_half_only = st.checkbox("First half / period only", value=False, help="Restrict to 1st half totals when available")
    
    col1, col2 = st.columns(2)
    with col1:
        min_odds = st.number_input("Min odds", min_value=1.01, max_value=10.0, value=1.20, step=0.05)
    with col2:
        max_odds = st.number_input("Max odds", min_value=1.10, max_value=20.0, value=3.50, step=0.05)

    combo_size = st.slider("Accumulator size", min_value=1, max_value=8, value=3)
    stake = st.number_input("Suggested stake (₦)", min_value=100, max_value=100000, value=1000, step=100)

    st.divider()
    st.subheader("API / Scan settings")
    sport_id = st.text_input("Sport ID", value=DEFAULT_SPORT_ID, help="Change if eBasketball uses a different ID")
    market_ids = st.text_input("Market IDs", value=DEFAULT_MARKET_IDS)
    timeline = st.slider("Hours ahead to scan", min_value=6, max_value=72, value=24)

    scan_btn = st.button("🔍 Scan Markets", type="primary", use_container_width=True)

# Main area
if "candidates" not in st.session_state:
    st.session_state.candidates = []
if "combo" not in st.session_state:
    st.session_state.combo = None
if "booking_code" not in st.session_state:
    st.session_state.booking_code = None

if scan_btn:
    with st.spinner("Scanning SportyBet..."):
        events = fetch_upcoming_events(sport_id, market_ids, timeline)
        st.session_state.candidates = filter_candidates(
            events,
            target_line=target_line,
            side=side.lower(),
            first_half_only=first_half_only,
            min_odds=min_odds,
            max_odds=max_odds,
        )
        st.session_state.combo = None
        st.session_state.booking_code = None
    st.success(f"Found {len(st.session_state.candidates)} matching markets")

candidates = st.session_state.candidates

if candidates:
    st.subheader(f"Matching {side} markets (line ≤ {target_line})")
    display_data = []
    for c in candidates[:20]:
        display_data.append({
            "Match": c["match"],
            "Tournament": c.get("tournament", ""),
            "Selection": c["selection"],
            "Line": c.get("line"),
            "Odds": c["odds"],
            "Market": c.get("market_desc", ""),
        })
    st.dataframe(display_data, use_container_width=True, hide_index=True)

    if st.button(f"Build {combo_size}-fold Accumulator", type="primary"):
        st.session_state.combo = suggest_combo(candidates, combo_size, stake)
        st.session_state.booking_code = None

    if st.session_state.combo:
        combo = st.session_state.combo
        st.subheader("Suggested Accumulator")
        st.metric("Total Odds", combo["total_odds"])
        st.metric("Potential Return", f"₦{combo['potential']:,.0f}")

        for i, s in enumerate(combo["selections"], 1):
            st.write(f"**{i}.** {s['match']} — {s['selection']} @ {s['odds']} (line {s.get('line')})")

        if st.button("Generate Booking Code", type="secondary"):
            with st.spinner("Creating anonymous booking code..."):
                code = create_booking_code(combo["selections"])
                st.session_state.booking_code = code

        if st.session_state.booking_code:
            code = st.session_state.booking_code
            load_url = f"https://www.sportybet.com/ng/?shareCode={code}"
            st.success(f"Booking code: **{code}**")
            st.markdown(f"[Open one-click load link]({load_url})")
            st.code(load_url)
            st.info("Open the link, review the live odds, enter your stake, and place the bet.")
else:
    st.info("Adjust filters on the left and click **Scan Markets** to begin.")

st.divider()
st.caption(
    "⚠️ Internal API — may change. Verify odds before placing. "
    "Booking codes are non-staking. Only bet what you can lose. "
    "Core functions can be imported into a Telegram bot later."
)
