"""
backtest.py - Historical Simulation & Formula Ranking Engine for Hanoi Lottery System.

Features:
  - F25: Backtest Simulator (Evaluates all 22 formulas across N draws without lookahead bias)
  - F26: Formula Ranking Engine (Ranks formulas by composite score, selects #1 formula)
"""

from typing import List, Dict, Any, Optional, Tuple

try:
    from formulas import ALL_FORMULAS
except ImportError:
    ALL_FORMULAS = []

ROUND_ORDER = {"special": 1, "normal": 2, "vip": 3}


def sort_chronological(draws: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sorts draw records chronologically (oldest to newest)."""
    def _safe_id(row: Dict[str, Any]) -> int:
        try:
            return int(row.get("id") or 0)
        except (ValueError, TypeError):
            return 0

    return sorted(
        draws,
        key=lambda d: (
            str(d.get("draw_date", "")),
            ROUND_ORDER.get(str(d.get("round_type", "")).lower(), 0),
            _safe_id(d)
        )
    )


def check_hit(pred: Any, draw: Dict[str, Any]) -> Tuple[bool, bool, bool]:
    """
    Evaluates whether prediction hit the draw.
    Returns (hit_top, hit_bottom, hit_any).
    """
    sp = str(draw.get("special_prize", ""))
    t2 = str(draw.get("top2", ""))
    if not t2 and len(sp) >= 2:
        t2 = sp[-2:]
    top2 = t2.zfill(2)[-2:] if t2 else ""

    b2 = str(draw.get("bottom2", ""))
    bot2 = b2.zfill(2)[-2:] if b2 else ""

    digit_str = None
    if hasattr(pred, "digit") and pred.digit is not None:
        digit_str = str(pred.digit).strip()
    elif isinstance(pred, dict) and "digit" in pred and pred["digit"] is not None:
        digit_str = str(pred["digit"]).strip()

    hit_top = False
    hit_bot = False

    if digit_str and digit_str.isdigit():
        hit_top = (digit_str in top2) if top2 else False
        hit_bot = (digit_str in bot2) if bot2 else False

    numbers_set = set()
    for attr in ["numbers", "pairs"]:
        raw_list = getattr(pred, attr, None)
        if raw_list is None and isinstance(pred, dict):
            raw_list = pred.get(attr)
        if raw_list:
            for n in raw_list:
                numbers_set.add(str(n).zfill(2)[-2:])

    if numbers_set:
        if top2 and top2 in numbers_set:
            hit_top = True
        if bot2 and bot2 in numbers_set:
            hit_bot = True

    hit_any = hit_top or hit_bot
    return hit_top, hit_bot, hit_any


def calculate_metrics(hits_seq: List[int]) -> Dict[str, Any]:
    """Calculates all backtest metrics from a chronological hit/miss sequence."""
    total = len(hits_seq)
    if total == 0:
        return {
            "total": 0, "hits": 0, "win_rate": 0.0,
            "streak": 0, "max_streak": 0,
            "recent_hits": [], "score": 0.0
        }

    hits = sum(hits_seq)
    win_rate = round((hits / total) * 100.0, 2)

    # Current streak (from newest backwards)
    streak = 0
    for h in reversed(hits_seq):
        if h == 1:
            streak += 1
        else:
            break

    # Max streak
    max_streak = 0
    cur_run = 0
    for h in hits_seq:
        if h == 1:
            cur_run += 1
            if cur_run > max_streak:
                max_streak = cur_run
        else:
            cur_run = 0

    recent_hits = hits_seq[-10:] if total >= 10 else list(hits_seq)
    recent_wr = (sum(recent_hits) / len(recent_hits) * 100.0) if recent_hits else win_rate

    # Composite Score
    score = round((0.60 * win_rate) + (0.25 * recent_wr) + (2.50 * streak) + (0.50 * max_streak), 2)

    return {
        "total": total,
        "hits": hits,
        "win_rate": win_rate,
        "streak": streak,
        "max_streak": max_streak,
        "recent_hits": recent_hits,
        "score": score
    }


def run_backtest(
    results: List[Dict[str, Any]],
    target_round: Optional[str] = None,
    num_eval: int = 50,
    formula_catalog: Optional[List[Any]] = None
) -> List[Dict[str, Any]]:
    """
    Runs historical simulation for all formulas across N draws without lookahead bias.
    Returns sorted leaderboard list.
    """
    if not results or len(results) < 2:
        return []

    catalog = formula_catalog if formula_catalog is not None else ALL_FORMULAS
    if not catalog:
        return []

    sorted_history = sort_chronological(results)
    L = len(sorted_history)

    # Identify eligible evaluation draw indices (index >= 1)
    eligible_indices = []
    norm_round = target_round.strip().lower() if target_round else None

    for i in range(1, L):
        draw_round = str(sorted_history[i].get("round_type", "")).strip().lower()
        if norm_round is None or draw_round == norm_round:
            eligible_indices.append(i)

    if not eligible_indices:
        return []

    # Take most recent num_eval draws
    eval_indices = eligible_indices[-num_eval:] if len(eligible_indices) > num_eval else eligible_indices

    # Evaluate each formula
    raw_leaderboard = []

    for formula in catalog:
        f_id = getattr(formula, "id", None) or (formula.get("id") if isinstance(formula, dict) else str(formula))
        f_name = getattr(formula, "name", None) or (formula.get("name") if isinstance(formula, dict) else f_id)
        f_cat = getattr(formula, "category", None) or (formula.get("category") if isinstance(formula, dict) else "")

        hits_seq = []
        for idx in eval_indices:
            target_draw = sorted_history[idx]
            hist_prior = sorted_history[:idx][::-1]  # STRICT NO-LOOKAHEAD BIAS (newest-first for formulas)
            r_type = target_draw.get("round_type", "special")

            try:
                if hasattr(formula, "predict"):
                    pred = formula.predict(hist_prior, r_type)
                elif isinstance(formula, dict) and "predict" in formula:
                    pred = formula["predict"](hist_prior, r_type)
                elif callable(formula):
                    pred = formula(hist_prior, r_type)
                else:
                    pred = None
            except Exception:
                pred = None

            if pred is not None:
                _, _, hit_any = check_hit(pred, target_draw)
                hits_seq.append(1 if hit_any else 0)
            else:
                hits_seq.append(0)

        metrics = calculate_metrics(hits_seq)
        metrics["formula_id"] = f_id
        metrics["formula_name"] = f_name
        metrics["category"] = f_cat
        raw_leaderboard.append(metrics)

    # Sort leaderboard
    sorted_lb = sorted(
        raw_leaderboard,
        key=lambda e: (-e["score"], -e["win_rate"], -e["streak"], -e["hits"], str(e["formula_id"]))
    )

    # Assign ranks
    for rank_idx, entry in enumerate(sorted_lb, 1):
        entry["rank"] = rank_idx

    return sorted_lb


def get_top_formula(
    results: List[Dict[str, Any]],
    target_round: Optional[str] = None,
    num_eval: int = 50,
    formula_catalog: Optional[List[Any]] = None
) -> Optional[Dict[str, Any]]:
    """Retrieves the #1 ranked formula dict for the given round and history."""
    lb = run_backtest(results, target_round=target_round, num_eval=num_eval, formula_catalog=formula_catalog)
    return lb[0] if lb else None


def format_leaderboard_table(leaderboard: List[Dict[str, Any]], limit: int = 10) -> str:
    """Formats formula backtest leaderboard into an ASCII/Unicode table for terminal display."""
    lines = [
        f"┌{'─' * 76}┐",
        f"│ {'🏆 ตารางจัดอันดับสูตรแม่นยำสูงสุด (Formula Leaderboard)':^66} │",
        f"├─────┬────────┬─────────────────────────────┬──────────┬──────────┬────────┬───────┤",
        f"│ อันดับ │ รหัสสูตร │ ชื่อสูตร                    │ Win Rate │ เข้า/งวด │ Streak │ คะแนน │",
        f"├─────┼────────┼─────────────────────────────┼──────────┼──────────┼────────┼───────┤"
    ]

    for item in leaderboard[:limit]:
        rank = item.get("rank", 0)
        fid = str(item.get("formula_id", ""))[:6]
        fname = str(item.get("formula_name", ""))[:20]
        wr = f"{item.get('win_rate', 0.0):.1f}%"
        hits_total = f"{item.get('hits', 0)}/{item.get('total', 0)}"
        streak = str(item.get("streak", 0))
        score = f"{item.get('score', 0.0):.1f}"
        lines.append(f"│ {rank:^3} │ {fid:^6} │ {fname:<27} │ {wr:>8} │ {hits_total:^8} │ {streak:^6} │ {score:>5} │")

    lines.append(f"└─────┴────────┴─────────────────────────────┴──────────┴──────────┴────────┴───────┘")
    return "\n".join(lines)
