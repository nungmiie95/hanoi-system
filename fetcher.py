"""
fetcher.py - Live Web Scraper and Fallback Mock Engine for Hanoi Lottery System.
3-Tier Resilient Fallback: Live HTTP Scraper -> Local SQLite DB Cache -> Mock Simulator.
Python 3.14 Compatible.
"""

import datetime
from html.parser import HTMLParser
import random
import re
from typing import Any, Dict, Optional, Tuple
import requests

from database import get_latest_result, normalize_round_type

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
}

# Live Feed URLs for Hanoi Lottery
ROUND_FEED_URLS = {
    "special": "https://www.lottery.co.th/hanoi-special",
    "normal": "https://www.lottery.co.th/hanoi",
    "vip": "https://www.lottery.co.th/hanoi-vip",
}


class HanoiHTMLParser(HTMLParser):
    """
    Standard-library zero-dependency HTML parser for Hanoi lottery pages.
    Extracts text tokens and finds prize patterns.
    """
    def __init__(self):
        super().__init__()
        self.text_tokens: list[str] = []

    def handle_data(self, data: str):
        cleaned = data.strip()
        if cleaned:
            self.text_tokens.append(cleaned)


def parse_lottery_html(html_text: str, round_type: str = "special") -> Optional[Dict[str, str]]:
    """
    Parses lottery HTML or raw text to extract special prize and bottom 2 numbers.
    Returns dict with keys 'special_prize', 'bottom2', 'draw_date' if found, else None.
    """
    if not html_text or not isinstance(html_text, str):
        return None

    # Parse tokens via HTMLParser
    parser = HanoiHTMLParser()
    try:
        parser.feed(html_text)
    except Exception:
        pass

    full_text = " ".join(parser.text_tokens) if parser.text_tokens else html_text

    # Search for special prize (5 or 6 digits) and bottom 2 (2 digits)
    # Patterns for Thai and Vietnamese lottery pages:
    # 1. Special prize
    sp_match = re.search(r"(?:รางวัลพิเศษ|รางวัลที่\s*1|special|đặc\s*biệt)[:\s]*([0-9]{5,6})", full_text, re.IGNORECASE)
    if not sp_match:
        # Fallback regex for 5-digit sequence near "พิเศษ" or "hanoi"
        sp_match = re.search(r"\b([0-9]{5})\b", full_text)

    # 2. Bottom 2 prize
    b2_match = re.search(r"(?:2\s*ตัวล่าง|เลขท้าย\s*2\s*ตัว|bottom2|รางวัล\s*2\s*ตัว|giải\s*tám)[:\s]*([0-9]{2})", full_text, re.IGNORECASE)
    if not b2_match:
        # Fallback regex for 2-digit sequence
        b2_match = re.search(r"(?:ล่าง|bottom)[:\s]*([0-9]{2})", full_text, re.IGNORECASE)

    # 3. Draw date (YYYY-MM-DD or DD/MM/YYYY)
    date_match = re.search(r"\b(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b", full_text)
    if date_match:
        draw_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
    else:
        draw_date = datetime.date.today().isoformat()

    if sp_match:
        special_prize = sp_match.group(1)
        bottom2 = b2_match.group(1) if b2_match else special_prize[:2]
        return {
            "draw_date": draw_date,
            "special_prize": special_prize,
            "bottom2": bottom2
        }

    return None


def simulate_mock_draw(round_type: str = "special", draw_date: Optional[str] = None) -> Dict[str, str]:
    """
    Generates a deterministic realistic mock draw result for simulation/offline mode.
    Guarantees consistent, realistic numbers for the same date and round.
    """
    canonical_round = normalize_round_type(round_type)
    if draw_date is None:
        draw_date = datetime.date.today().isoformat()

    # Deterministic seed based on date and round_type
    date_seed = int(draw_date.replace("-", ""))
    round_offset = {"special": 11, "normal": 22, "vip": 33}.get(canonical_round, 1)
    rng = random.Random(date_seed + round_offset)

    sp_int = rng.randint(10000, 99999)
    special_prize = f"{sp_int:05d}"
    top3 = special_prize[-3:]
    top2 = special_prize[-2:]
    b2_int = rng.randint(0, 99)
    bottom2 = f"{b2_int:02d}"

    return {
        "round_type": canonical_round,
        "draw_date": draw_date,
        "special_prize": special_prize,
        "top3": top3,
        "top2": top2,
        "bottom2": bottom2,
        "source": "mock_simulator"
    }


def fetch_latest_results(
    round_type: Optional[str] = None,
    fallback_mock: bool = False,
    db_path: str = "hanoi.db",
    timeout: float = 5.0
) -> Dict[str, Any]:
    """
    Fetches the latest draw result for a specific Hanoi round using 3-tier fallback hierarchy:
    Tier 1: Live HTTP Scraper (timeout=5.0s)
    Tier 2: Local SQLite DB Cache
    Tier 3: Realistic Mock Simulator
    
    Guaranteed NEVER to raise unhandled exceptions.
    """
    canonical_round = normalize_round_type(round_type) if round_type else "special"

    # If fallback_mock is explicitly True, jump directly to Tier 3
    if fallback_mock:
        return simulate_mock_draw(canonical_round)

    # -------------------------------------------------------------
    # Tier 1: Live Web Scraper
    # -------------------------------------------------------------
    url = ROUND_FEED_URLS.get(canonical_round, ROUND_FEED_URLS["special"])
    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        if resp.status_code == 200 and resp.text:
            parsed = parse_lottery_html(resp.text, canonical_round)
            if parsed and parsed.get("special_prize"):
                sp = parsed["special_prize"]
                top3 = sp[-3:]
                top2 = sp[-2:]
                b2 = parsed.get("bottom2", sp[:2]).zfill(2)
                return {
                    "round_type": canonical_round,
                    "draw_date": parsed.get("draw_date", datetime.date.today().isoformat()),
                    "special_prize": sp,
                    "top3": top3,
                    "top2": top2,
                    "bottom2": b2,
                    "source": "live_scraper"
                }
    except Exception:
        # Network outage, timeout, DNS failure, or parse failure -> proceed to Tier 2
        pass

    # -------------------------------------------------------------
    # Tier 2: Local SQLite Database Cache
    # -------------------------------------------------------------
    try:
        cached = get_latest_result(round_type=canonical_round, db_path=db_path)
        if cached:
            return {
                "round_type": cached["round_type"],
                "draw_date": cached["draw_date"],
                "special_prize": cached["special_prize"],
                "top3": cached["top3"],
                "top2": cached["top2"],
                "bottom2": cached["bottom2"],
                "source": "database_cache"
            }
    except Exception:
        # DB not initialized or unreadable -> proceed to Tier 3
        pass

    # -------------------------------------------------------------
    # Tier 3: Realistic Mock Simulator
    # -------------------------------------------------------------
    return simulate_mock_draw(canonical_round)


def fetch_all_latest_results(
    fallback_mock: bool = False,
    db_path: str = "hanoi.db",
    timeout: float = 5.0
) -> Dict[str, Any]:
    """
    Fetches the latest draw results for all 3 Hanoi rounds (special, normal, vip).
    Returns dict containing each round's result dict and overall status.
    """
    rounds = ["special", "normal", "vip"]
    results = {}
    sources = set()

    for r in rounds:
        res = fetch_latest_results(
            round_type=r,
            fallback_mock=fallback_mock,
            db_path=db_path,
            timeout=timeout
        )
        results[r] = res
        sources.add(res["source"])

    # Dominant source
    primary_source = "live_scraper" if "live_scraper" in sources else ("database_cache" if "database_cache" in sources else "mock_simulator")
    results["source"] = primary_source
    return results
