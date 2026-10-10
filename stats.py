"""
stats.py - Statistical Calculation & Analysis Engine for Hanoi Lottery System.
Computes digit frequencies (0-9), Hot/Cold ranking, gap analysis, and descriptive metrics.
"""

from collections import Counter
from typing import Any, Dict, List, Optional, Tuple, Union


class DigitCountDict(dict):
    """
    Dictionary supporting transparent int and str key access for digits 0-9.
    Compatible with JSON serialization and direct dictionary access.
    """
    def __getitem__(self, key):
        if isinstance(key, str) and key.isdigit():
            int_k = int(key)
            if int_k in self:
                return super().__getitem__(int_k)
        elif isinstance(key, int):
            if key in self:
                return super().__getitem__(key)
            str_k = str(key)
            if str_k in self:
                return super().__getitem__(str_k)
        return super().__getitem__(key)

    def __contains__(self, key):
        if super().__contains__(key):
            return True
        if isinstance(key, str) and key.isdigit() and super().__contains__(int(key)):
            return True
        if isinstance(key, int) and super().__contains__(str(key)):
            return True
        return False

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def _clean_digit_string(val: Any, expected_len: Optional[int] = None) -> str:
    """Helper to convert value to zero-padded numeric string."""
    if val is None:
        return ""
    s = str(val).strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if expected_len and digits:
        digits = digits.zfill(expected_len)[-expected_len:]
    return digits


def calculate_digit_frequencies(results: List[Dict[str, Any]], position: str = "both") -> Dict[str, Any]:
    """
    Calculates digit frequency distributions (0-9) for top2, bottom2, and top3 prizes.
    
    Returns:
        {
            "top_digits": DigitCountDict({0..9: count}),
            "bottom_digits": DigitCountDict({0..9: count}),
            "top3_digits": DigitCountDict({0..9: count}),
            "top_percentages": {0..9: float},
            "bottom_percentages": {0..9: float},
            "top3_percentages": {0..9: float},
            "total_draws": int
        }
    """
    top_counts = DigitCountDict({d: 0 for d in range(10)})
    bottom_counts = DigitCountDict({d: 0 for d in range(10)})
    top3_counts = DigitCountDict({d: 0 for d in range(10)})

    total_draws = len(results) if results else 0

    if total_draws == 0:
        return {
            "top_digits": top_counts,
            "bottom_digits": bottom_counts,
            "top3_digits": top3_counts,
            "top_percentages": {d: 0.0 for d in range(10)},
            "bottom_percentages": {d: 0.0 for d in range(10)},
            "top3_percentages": {d: 0.0 for d in range(10)},
            "total_draws": 0
        }

    for r in results:
        # Extract top2
        t2 = _clean_digit_string(r.get("top2"), expected_len=2)
        if not t2 and r.get("special_prize"):
            sp = _clean_digit_string(r.get("special_prize"))
            if len(sp) >= 2:
                t2 = sp[-2:]
        for ch in t2:
            top_counts[int(ch)] += 1

        # Extract bottom2
        b2 = _clean_digit_string(r.get("bottom2"), expected_len=2)
        for ch in b2:
            bottom_counts[int(ch)] += 1

        # Extract top3
        t3 = _clean_digit_string(r.get("top3"), expected_len=3)
        if not t3 and r.get("special_prize"):
            sp = _clean_digit_string(r.get("special_prize"))
            if len(sp) >= 3:
                t3 = sp[-3:]
        for ch in t3:
            top3_counts[int(ch)] += 1

    top_pct = {d: round((top_counts[d] / (total_draws * 2)) * 100, 2) for d in range(10)}
    bottom_pct = {d: round((bottom_counts[d] / (total_draws * 2)) * 100, 2) for d in range(10)}
    top3_pct = {d: round((top3_counts[d] / (total_draws * 3)) * 100, 2) for d in range(10)}

    return {
        "top_digits": top_counts,
        "bottom_digits": bottom_counts,
        "top3_digits": top3_counts,
        "top_percentages": top_pct,
        "bottom_percentages": bottom_pct,
        "top3_percentages": top3_pct,
        "total_draws": total_draws
    }


def calculate_hot_cold(results: List[Dict[str, Any]], limit: int = 5) -> Dict[str, Any]:
    """
    Calculates Hot (most frequent) and Cold (most overdue) 2-digit numbers for top2 and bottom2.
    
    Returns:
        {
            "hot_top2": list[dict],
            "cold_top2": list[dict],
            "hot_bottom2": list[dict],
            "cold_bottom2": list[dict]
        }
    """
    if not results:
        return {
            "hot_top2": [],
            "cold_top2": [],
            "hot_bottom2": [],
            "cold_bottom2": []
        }

    # Ensure reverse chronological order (draw index 0 = latest draw)
    sorted_draws = list(results)
    if any("draw_date" in r for r in sorted_draws):
        round_rank = {"vip": 3, "normal": 2, "special": 1}
        sorted_draws.sort(
            key=lambda x: (
                str(x.get("draw_date", "")),
                round_rank.get(str(x.get("round_type", "")).lower(), 0),
                int(x.get("id", 0) or 0)
            ),
            reverse=True
        )

    n_draws = len(sorted_draws)

    def _process_series(key_name: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        counts = {f"{i:02d}": 0 for i in range(100)}
        last_seen = {f"{i:02d}": None for i in range(100)}

        for idx, r in enumerate(sorted_draws):
            val = _clean_digit_string(r.get(key_name), expected_len=2)
            if not val and key_name == "top2" and r.get("special_prize"):
                sp = _clean_digit_string(r.get("special_prize"))
                if len(sp) >= 2:
                    val = sp[-2:]
            if len(val) == 2:
                counts[val] += 1
                if last_seen[val] is None:
                    last_seen[val] = idx

        # Hot: pairs that actually appeared (count > 0), sorted by frequency descending
        hot_candidates = [p for p in counts if counts[p] > 0]
        hot_candidates.sort(
            key=lambda p: (-counts[p], last_seen[p] if last_seen[p] is not None else n_draws, p)
        )
        hot_list = [
            {
                "number": p,
                "count": counts[p],
                "frequency": round((counts[p] / n_draws) * 100, 2),
                "gap": last_seen[p] if last_seen[p] is not None else n_draws
            }
            for p in hot_candidates[:limit]
        ]

        # Cold: pairs sorted by gap descending (most overdue)
        cold_candidates = list(counts.keys())
        cold_candidates.sort(
            key=lambda p: (
                -(last_seen[p] if last_seen[p] is not None else n_draws),
                counts[p],
                p
            )
        )
        cold_list = [
            {
                "number": p,
                "gap": last_seen[p] if last_seen[p] is not None else n_draws,
                "count": counts[p],
                "frequency": round((counts[p] / n_draws) * 100, 2)
            }
            for p in cold_candidates[:limit]
        ]

        return hot_list, cold_list

    hot_top2, cold_top2 = _process_series("top2")
    hot_bottom2, cold_bottom2 = _process_series("bottom2")

    return {
        "hot_top2": hot_top2,
        "cold_top2": cold_top2,
        "hot_bottom2": hot_bottom2,
        "cold_bottom2": cold_bottom2
    }


def calculate_summary_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes descriptive summary metrics: average digits, odd/even balance, high/low balance, doubles.
    """
    n_draws = len(results) if results else 0

    empty_metrics = {
        "avg_digit": 0.0,
        "avg_sum": 0.0,
        "odd_count": 0,
        "even_count": 0,
        "odd_percentage": 0.0,
        "even_percentage": 0.0,
        "high_count": 0,
        "low_count": 0,
        "high_percentage": 0.0,
        "low_percentage": 0.0,
        "pattern_odd_even": {"even_even": 0, "even_odd": 0, "odd_even": 0, "odd_odd": 0},
        "pattern_high_low": {"low_low": 0, "low_high": 0, "high_low": 0, "high_high": 0},
        "double_count": 0,
        "double_percentage": 0.0
    }

    if n_draws == 0:
        return {
            "total_draws": 0,
            "top2": dict(empty_metrics),
            "bottom2": dict(empty_metrics),
            "top3": {
                "avg_digit": 0.0,
                "avg_sum": 0.0,
                "odd_count": 0,
                "even_count": 0,
                "high_count": 0,
                "low_count": 0,
                "odd_percentage": 0.0,
                "even_percentage": 0.0,
                "high_percentage": 0.0,
                "low_percentage": 0.0
            }
        }

    def _eval_2digit(key_name: str) -> Dict[str, Any]:
        all_digits = []
        sums = []
        odd_cnt = 0
        even_cnt = 0
        high_cnt = 0
        low_cnt = 0
        double_cnt = 0
        pattern_oe = {"even_even": 0, "even_odd": 0, "odd_even": 0, "odd_odd": 0}
        pattern_hl = {"low_low": 0, "low_high": 0, "high_low": 0, "high_high": 0}

        for r in results:
            val = _clean_digit_string(r.get(key_name), expected_len=2)
            if not val and key_name == "top2" and r.get("special_prize"):
                sp = _clean_digit_string(r.get("special_prize"))
                if len(sp) >= 2:
                    val = sp[-2:]
            if len(val) == 2:
                d1, d2 = int(val[0]), int(val[1])
                all_digits.extend([d1, d2])
                sums.append(d1 + d2)

                # Odd/Even
                d1_odd = (d1 % 2 != 0)
                d2_odd = (d2 % 2 != 0)
                odd_cnt += int(d1_odd) + int(d2_odd)
                even_cnt += int(not d1_odd) + int(not d2_odd)
                if not d1_odd and not d2_odd:
                    pattern_oe["even_even"] += 1
                elif not d1_odd and d2_odd:
                    pattern_oe["even_odd"] += 1
                elif d1_odd and not d2_odd:
                    pattern_oe["odd_even"] += 1
                else:
                    pattern_oe["odd_odd"] += 1

                # High/Low (Low: 0-4, High: 5-9)
                d1_high = (d1 >= 5)
                d2_high = (d2 >= 5)
                high_cnt += int(d1_high) + int(d2_high)
                low_cnt += int(not d1_high) + int(not d2_high)
                if not d1_high and not d2_high:
                    pattern_hl["low_low"] += 1
                elif not d1_high and d2_high:
                    pattern_hl["low_high"] += 1
                elif d1_high and not d2_high:
                    pattern_hl["high_low"] += 1
                else:
                    pattern_hl["high_high"] += 1

                # Double
                if d1 == d2:
                    double_cnt += 1

        total_d = len(all_digits)
        avg_d = round(sum(all_digits) / total_d, 2) if total_d > 0 else 0.0
        avg_s = round(sum(sums) / len(sums), 2) if sums else 0.0
        odd_pct = round((odd_cnt / total_d) * 100, 2) if total_d > 0 else 0.0
        even_pct = round((even_cnt / total_d) * 100, 2) if total_d > 0 else 0.0
        high_pct = round((high_cnt / total_d) * 100, 2) if total_d > 0 else 0.0
        low_pct = round((low_cnt / total_d) * 100, 2) if total_d > 0 else 0.0
        double_pct = round((double_cnt / n_draws) * 100, 2) if n_draws > 0 else 0.0

        return {
            "avg_digit": avg_d,
            "avg_sum": avg_s,
            "odd_count": odd_cnt,
            "even_count": even_cnt,
            "odd_percentage": odd_pct,
            "even_percentage": even_pct,
            "high_count": high_cnt,
            "low_count": low_cnt,
            "high_percentage": high_pct,
            "low_percentage": low_pct,
            "pattern_odd_even": pattern_oe,
            "pattern_high_low": pattern_hl,
            "double_count": double_cnt,
            "double_percentage": double_pct
        }

    # Top3 metrics
    top3_digits = []
    top3_sums = []
    for r in results:
        val = _clean_digit_string(r.get("top3"), expected_len=3)
        if not val and r.get("special_prize"):
            sp = _clean_digit_string(r.get("special_prize"))
            if len(sp) >= 3:
                val = sp[-3:]
        if len(val) == 3:
            ds = [int(ch) for ch in val]
            top3_digits.extend(ds)
            top3_sums.append(sum(ds))

    t3_total = len(top3_digits)
    t3_odd = sum(1 for d in top3_digits if d % 2 != 0)
    t3_even = t3_total - t3_odd
    t3_high = sum(1 for d in top3_digits if d >= 5)
    t3_low = t3_total - t3_high

    top3_res = {
        "avg_digit": round(sum(top3_digits) / t3_total, 2) if t3_total > 0 else 0.0,
        "avg_sum": round(sum(top3_sums) / len(top3_sums), 2) if top3_sums else 0.0,
        "odd_count": t3_odd,
        "even_count": t3_even,
        "high_count": t3_high,
        "low_count": t3_low,
        "odd_percentage": round((t3_odd / t3_total) * 100, 2) if t3_total > 0 else 0.0,
        "even_percentage": round((t3_even / t3_total) * 100, 2) if t3_total > 0 else 0.0,
        "high_percentage": round((t3_high / t3_total) * 100, 2) if t3_total > 0 else 0.0,
        "low_percentage": round((t3_low / t3_total) * 100, 2) if t3_total > 0 else 0.0,
    }

    return {
        "total_draws": n_draws,
        "top2": _eval_2digit("top2"),
        "bottom2": _eval_2digit("bottom2"),
        "top3": top3_res
    }


def format_frequency_table(freq: Dict[str, Any], title: str = "สถิติความถี่ตัวเลข (0-9)") -> str:
    """Formats digit frequency data as a formatted ASCII Unicode Thai table for terminal display."""
    lines = [
        f"┌{'─' * 55}┐",
        f"│ {title:^51} │",
        f"├───────┬────────────┬────────────┬─────────────┬─────────────┤",
        f"│ ตัวเลข │ บน (ครั้ง) │ บน (%)     │ ล่าง (ครั้ง) │ ล่าง (%)    │",
        f"├───────┼────────────┼────────────┼─────────────┼─────────────┤"
    ]
    top_counts = freq.get("top_digits", {})
    bot_counts = freq.get("bottom_digits", {})
    top_pct = freq.get("top_percentages", {})
    bot_pct = freq.get("bottom_percentages", {})

    for d in range(10):
        tc = top_counts.get(d, 0)
        bc = bot_counts.get(d, 0)
        tp = top_pct.get(d, 0.0)
        bp = bot_pct.get(d, 0.0)
        lines.append(f"│   {d}   │    {tc:<7} │   {tp:>5.2f}%   │    {bc:<8} │   {bp:>5.2f}%   │")

    lines.append(f"└───────┴────────────┴────────────┴─────────────┴─────────────┘")
    lines.append(f"จำนวนงวดทั้งหมด: {freq.get('total_draws', 0)} งวด")
    return "\n".join(lines)


def format_hot_cold_table(hc: Dict[str, Any], limit: int = 5) -> str:
    """Formats Hot & Cold rankings as a terminal summary report."""
    lines = [
        "=" * 60,
        "  🔥 เลขเด่นมาแรง (Hot) & ❄️ เลขดับค้างนาน (Cold)",
        "=" * 60,
        "[2 ตัวบน (Top 2)]",
        "  🔥 เลขเด่น: " + (", ".join(f"{item['number']} ({item['count']} ครั้ง)" for item in hc.get("hot_top2", [])[:limit]) or "-"),
        "  ❄️ เลขค้าง: " + (", ".join(f"{item['number']} (เว้น {item['gap']} งวด)" for item in hc.get("cold_top2", [])[:limit]) or "-"),
        "",
        "[2 ตัวล่าง (Bottom 2)]",
        "  🔥 เลขเด่น: " + (", ".join(f"{item['number']} ({item['count']} ครั้ง)" for item in hc.get("hot_bottom2", [])[:limit]) or "-"),
        "  ❄️ เลขค้าง: " + (", ".join(f"{item['number']} (เว้น {item['gap']} งวด)" for item in hc.get("cold_bottom2", [])[:limit]) or "-"),
        "=" * 60
    ]
    return "\n".join(lines)


def format_summary_metrics_table(metrics: Dict[str, Any]) -> str:
    """Formats summary metrics into a readable Thai terminal block."""
    t2 = metrics.get("top2", {})
    b2 = metrics.get("bottom2", {})
    lines = [
        "=" * 60,
        "  📊 สรุปสถิติเชิงพรรณนา (Descriptive Statistics)",
        "=" * 60,
        f"จำนวนงวดที่คำนวณ: {metrics.get('total_draws', 0)} งวด",
        "",
        "[2 ตัวบน]",
        f"  - ค่าเฉลี่ยตัวเลข: {t2.get('avg_digit', 0.0)} | ค่าเฉลี่ยผลรวม: {t2.get('avg_sum', 0.0)}",
        f"  - คู่/คี่: คี่ {t2.get('odd_percentage', 0.0)}% ({t2.get('odd_count', 0)} ตัว) / คู่ {t2.get('even_percentage', 0.0)}% ({t2.get('even_count', 0)} ตัว)",
        f"  - สูง/ต่ำ: สูง {t2.get('high_percentage', 0.0)}% / ต่ำ {t2.get('low_percentage', 0.0)}%",
        f"  - เลขเบิ้ล: {t2.get('double_count', 0)} ครั้ง ({t2.get('double_percentage', 0.0)}%)",
        "",
        "[2 ตัวล่าง]",
        f"  - ค่าเฉลี่ยตัวเลข: {b2.get('avg_digit', 0.0)} | ค่าเฉลี่ยผลรวม: {b2.get('avg_sum', 0.0)}",
        f"  - คู่/คี่: คี่ {b2.get('odd_percentage', 0.0)}% ({b2.get('odd_count', 0)} ตัว) / คู่ {b2.get('even_percentage', 0.0)}% ({b2.get('even_count', 0)} ตัว)",
        f"  - สูง/ต่ำ: สูง {b2.get('high_percentage', 0.0)}% / ต่ำ {b2.get('low_percentage', 0.0)}%",
        f"  - เลขเบิ้ล: {b2.get('double_count', 0)} ครั้ง ({b2.get('double_percentage', 0.0)}%)",
        "=" * 60
    ]
    return "\n".join(lines)
