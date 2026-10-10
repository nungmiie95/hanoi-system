"""
formulas.py - Complete 22 Deterministic Mathematical Prediction Formulas
and Deliverable Sets Generation Engine for Hanoi Lottery System.
"""

from dataclasses import dataclass, field
import datetime
from typing import Any, Dict, List, Optional, Tuple, Set


@dataclass
class FormulaPrediction:
    """Prediction output container supporting both attribute and dict-like access."""
    formula_id: str
    formula_name: str
    target_round: str
    digit: str                    # Single running digit '0'-'9'
    secondary_digit: str          # Secondary running digit '0'-'9'
    pairs: List[str]              # List of key two-digit strings ['47', '74', ...]
    category: str
    description: str = ""

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __str__(self) -> str:
        return f"{self.formula_id}:{self.digit}:{self.secondary_digit}:{','.join(self.pairs[:6])}"


class Formula:
    """Base abstract class for all deterministic prediction formulas."""
    def __init__(self, id: str, name: str, category: str, description: str):
        self.id = id
        self.name = name
        self.category = category
        self.description = description

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        raise NotImplementedError("Subclasses must implement predict()")

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


def _extract_last_draw_digits(history: List[Dict[str, Any]], round_filter: Optional[str] = None) -> Tuple[str, str, str, str]:
    """
    Safely extracts (special_prize, top3, top2, bottom2) from history.
    If round_filter is specified, searches backward for the latest matching round.
    Falls back gracefully if history is empty or keys are missing.
    """
    if not history:
        return "00000", "000", "00", "00"

    target_draw = None
    if round_filter:
        norm_filter = round_filter.strip().lower()
        for draw in history:
            if str(draw.get("round_type", "")).strip().lower() == norm_filter:
                target_draw = draw
                break

    if target_draw is None:
        target_draw = history[0] if history else {}

    special = str(target_draw.get("special_prize", "00000")).strip()
    digits_sp = "".join(ch for ch in special if ch.isdigit())
    if len(digits_sp) < 3:
        digits_sp = "00000"

    # top3
    t3 = str(target_draw.get("top3", "")).strip()
    t3_digits = "".join(ch for ch in t3 if ch.isdigit())
    if len(t3_digits) < 3:
        t3_digits = digits_sp[-3:] if len(digits_sp) >= 3 else "000"

    # top2
    t2 = str(target_draw.get("top2", "")).strip()
    t2_digits = "".join(ch for ch in t2 if ch.isdigit())
    if len(t2_digits) < 2:
        t2_digits = digits_sp[-2:] if len(digits_sp) >= 2 else "00"

    # bottom2
    b2 = str(target_draw.get("bottom2", "")).strip()
    b2_digits = "".join(ch for ch in b2 if ch.isdigit())
    if len(b2_digits) < 2:
        b2_digits = "00"

    return digits_sp, t3_digits, t2_digits, b2_digits


def _make_19_gates(digit: int) -> List[str]:
    """Generates the 19 two-digit combinations containing digit."""
    d_str = str(digit)
    gates: List[str] = []
    for i in range(10):
        gates.append(f"{d_str}{i}")
    for i in range(10):
        if i != digit:
            gates.append(f"{i}{d_str}")
    return gates


# --- Category 1: Digit Sums (F01 - F05) ---

class FormulaF01(Formula):
    """F01: Formula F01 computes (Top3[0] + Top3[1]) mod 10."""
    def __init__(self):
        super().__init__("F01", "สูตรผลรวมหลักร้อย+สิบ", "Digit Sum", "ผลรวมหลักร้อยและหลักสิบของ 3 ตัวบน มอดุโล 10")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, t3, _, _ = _extract_last_draw_digits(history)
        d = (int(t3[0]) + int(t3[1])) % 10
        d_sec = (d + 1) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF02(Formula):
    """F02: Formula F02 computes (Top3[1] + Top3[2]) mod 10."""
    def __init__(self):
        super().__init__("F02", "สูตรผลรวมหลักสิบ+หน่วย", "Digit Sum", "ผลรวมหลักสิบและหลักหน่วยของ 3 ตัวบน มอดุโล 10")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, t3, _, _ = _extract_last_draw_digits(history)
        d = (int(t3[1]) + int(t3[2])) % 10
        d_sec = (d + 1) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF03(Formula):
    """F03: Formula F03 computes (Top3[0] + Top3[1] + Top3[2]) mod 10."""
    def __init__(self):
        super().__init__("F03", "สูตรผลรวม 3 ตัวบน", "Digit Sum", "ผลรวมทั้งสามหลักของ 3 ตัวบน มอดุโล 10")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, t3, _, _ = _extract_last_draw_digits(history)
        d = (int(t3[0]) + int(t3[1]) + int(t3[2])) % 10
        d_sec = (d + 3) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF04(Formula):
    """F04: Formula F04 computes (Bottom2[0] + Bottom2[1]) mod 10."""
    def __init__(self):
        super().__init__("F04", "สูตรผลรวม 2 ตัวล่าง", "Digit Sum", "ผลรวมหลักสิบและหลักหน่วยของ 2 ตัวล่าง มอดุโล 10")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, _, _, b2 = _extract_last_draw_digits(history)
        d = (int(b2[0]) + int(b2[1])) % 10
        d_sec = (d + 2) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF05(Formula):
    """F05: Formula F05 computes (Top2[1] + Bottom2[1]) mod 10."""
    def __init__(self):
        super().__init__("F05", "สูตรผลรวมบน+ล่าง", "Digit Sum", "ผลรวมหลักหน่วยบนและหลักหน่วยล่าง มอดุโล 10")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, _, t2, b2 = _extract_last_draw_digits(history)
        d = (int(t2[1]) + int(b2[1])) % 10
        d_sec = (d + 5) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


# --- Category 2: Constant Offsets (F06 - F09) ---

class FormulaF06(Formula):
    """F06: Formula F06 computes (Top3[2] + 3) mod 10."""
    def __init__(self):
        super().__init__("F06", "สูตรบวกคงที่ +3", "Constant Offset", "หลักหน่วย 3 ตัวบน บวกคงที่ 3 มอดุโล 10")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, t3, _, _ = _extract_last_draw_digits(history)
        d = (int(t3[2]) + 3) % 10
        d_sec = (d + 3) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF07(Formula):
    """F07: Formula F07 computes (Top3[2] + 5) mod 10."""
    def __init__(self):
        super().__init__("F07", "สูตรบวกคงที่ +5", "Constant Offset", "หลักหน่วย 3 ตัวบน บวกคงที่ 5 มอดุโล 10")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, t3, _, _ = _extract_last_draw_digits(history)
        d = (int(t3[2]) + 5) % 10
        d_sec = (d + 5) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF08(Formula):
    """F08: Formula F08 computes (Bottom2[1] + 7) mod 10."""
    def __init__(self):
        super().__init__("F08", "สูตรบวกคงที่ +7", "Constant Offset", "หลักหน่วย 2 ตัวล่าง บวกคงที่ 7 มอดุโล 10")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, _, _, b2 = _extract_last_draw_digits(history)
        d = (int(b2[1]) + 7) % 10
        d_sec = (d + 7) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF09(Formula):
    """F09: Formula F09 computes (Top2[0] - 2 + 10) mod 10."""
    def __init__(self):
        super().__init__("F09", "สูตรลบคงที่ -2", "Constant Offset", "หลักสิบ 2 ตัวบน ลบคงที่ 2 มอดุโล 10")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, _, t2, _ = _extract_last_draw_digits(history)
        d = (int(t2[0]) - 2 + 10) % 10
        d_sec = (d - 2 + 10) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


# --- Category 3: 19 Gates (F10 - F12) ---

class FormulaF10(Formula):
    """F10: Formula F10 generates 19 gates based on Top2 units digit."""
    def __init__(self):
        super().__init__("F10", "สูตร 19 ประตูเด่นบน", "19 Gates", "รูด 19 ประตูจากหลักหน่วย 2 ตัวบน")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, _, t2, _ = _extract_last_draw_digits(history)
        d = int(t2[1])
        d_sec = (d + 1) % 10
        pairs = _make_19_gates(d)
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF11(Formula):
    """F11: Formula F11 generates 19 gates based on Bottom2 tens digit."""
    def __init__(self):
        super().__init__("F11", "สูตร 19 ประตูเด่นล่าง", "19 Gates", "รูด 19 ประตูจากหลักสิบ 2 ตัวล่าง")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, _, _, b2 = _extract_last_draw_digits(history)
        d = int(b2[0])
        d_sec = (d + 1) % 10
        pairs = _make_19_gates(d)
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF12(Formula):
    """F12: Formula F12 generates 19 gates based on sum modulo."""
    def __init__(self):
        super().__init__("F12", "สูตร 19 ประตูผลรวม", "19 Gates", "รูด 19 ประตูจากผลรวมหลักหน่วยบนและล่าง")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, _, t2, b2 = _extract_last_draw_digits(history)
        d = (int(t2[1]) + int(b2[1])) % 10
        d_sec = (d + 1) % 10
        pairs = _make_19_gates(d)
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


# --- Category 4: Combinatorial Vin & Patterns (F13 - F17) ---

class FormulaF13(Formula):
    """F13: Formula F13 predicts parity distribution trend."""
    def __init__(self):
        super().__init__("F13", "สูตรเลขคู่/คี่โมเมนตัม", "Parity Trend", "วิเคราะห์แนวโน้มโมเมนตัมตัวเลขคู่หรือคี่")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        even_cnt = 0
        odd_cnt = 0
        for draw in history[:10]:
            t2 = str(draw.get("top2", ""))
            b2 = str(draw.get("bottom2", ""))
            for ch in t2 + b2:
                if ch.isdigit():
                    if int(ch) % 2 == 0:
                        even_cnt += 1
                    else:
                        odd_cnt += 1
        d = 2 if even_cnt >= odd_cnt else 1
        d_sec = 8 if even_cnt >= odd_cnt else 7
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF14(Formula):
    """F14: Formula F14 generates combinations of hot digits."""
    def __init__(self):
        super().__init__("F14", "สูตรจับคู่เลขชนสถิติ", "Hot Pairs", "วินเลขชุดเด่นจากสถิติตัวเลขที่ออกบ่อยที่สุด")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        freq = {i: 0 for i in range(10)}
        for draw in history[:15]:
            t2 = str(draw.get("top2", ""))
            b2 = str(draw.get("bottom2", ""))
            for ch in t2 + b2:
                if ch.isdigit():
                    freq[int(ch)] += 1
        sorted_digits = sorted(range(10), key=lambda x: (freq[x], -x), reverse=True)
        top4 = sorted_digits[:4]
        d = top4[0]
        d_sec = top4[1]
        pairs = []
        for d1 in top4:
            for d2 in top4:
                pairs.append(f"{d1}{d2}")
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF15(Formula):
    """F15: Formula F15 computes shadow mirror (x + 5) mod 10."""
    def __init__(self):
        super().__init__("F15", "สูตรเลขกลับหัว (เงาตัวเลข)", "Shadow/Mirror", "คำนวณเลขเงากระจกคู่ขนาน บวก 5 มอดุโล 10")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, _, t2, _ = _extract_last_draw_digits(history)
        x = int(t2[1])
        d = x
        d_sec = (x + 5) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF16(Formula):
    """F16: Formula F16 computes absolute difference |Top2[1] - Bottom2[1]|."""
    def __init__(self):
        super().__init__("F16", "สูตรผลต่างบน-ล่าง", "Difference", "คำนวณค่าผลต่างสัมบูรณ์ระหว่างหลักหน่วยบนและล่าง")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, _, t2, b2 = _extract_last_draw_digits(history)
        d = abs(int(t2[1]) - int(b2[1]))
        d_sec = (d + 5) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF17(Formula):
    """F17: Formula F17 computes product (Top2[1] * Bottom2[1]) mod 10."""
    def __init__(self):
        super().__init__("F17", "สูตรผลคูณหลักหน่วย", "Product Mod", "ผลคูณระหว่างหลักหน่วยบนและหลักหน่วยล่าง มอดุโล 10")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, _, t2, b2 = _extract_last_draw_digits(history)
        d = (int(t2[1]) * int(b2[1])) % 10
        d_sec = (d + 1) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


# --- Category 5: Cross-Round Momentum (F18 - F20) ---

class FormulaF18(Formula):
    """F18: Formula F18 cross-round Special -> Normal."""
    def __init__(self):
        super().__init__("F18", "สูตรส่งต่อ พิเศษ -> ปกติ", "Cross-Round", "ส่งต่อสัญญาณตัวเลขจากรอบพิเศษสู่รอบปกติ")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "normal") -> FormulaPrediction:
        _, t3, _, b2 = _extract_last_draw_digits(history, round_filter="special")
        d = (int(t3[2]) + int(b2[1])) % 10
        d_sec = (d + 1) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF19(Formula):
    """F19: Formula F19 cross-round Normal -> VIP."""
    def __init__(self):
        super().__init__("F19", "สูตรส่งต่อ ปกติ -> VIP", "Cross-Round", "ส่งต่อสัญญาณตัวเลขจากรอบปกติสู่รอบ VIP")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "vip") -> FormulaPrediction:
        _, t3, _, b2 = _extract_last_draw_digits(history, round_filter="normal")
        d = (int(t3[1]) + int(b2[0])) % 10
        d_sec = (d + 1) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF20(Formula):
    """F20: Formula F20 cross-round VIP -> Special."""
    def __init__(self):
        super().__init__("F20", "สูตรส่งต่อ VIP -> พิเศษ", "Cross-Round", "ส่งต่อสัญญาณตัวเลขจากรอบ VIP สู่รอบพิเศษวันถัดไป")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, t3, _, b2 = _extract_last_draw_digits(history, round_filter="vip")
        d = (int(t3[0]) + int(b2[1])) % 10
        d_sec = (d + 1) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


# --- Category 6: Statistical & Calendar Modulation (F21 - F22) ---

class FormulaF21(Formula):
    """F21: Formula F21 cold rebound based on overdue numbers."""
    def __init__(self):
        super().__init__("F21", "สูตรสถิติเลขค้างนาน (Cold Rebound)", "Statistical", "คำนวณการเด้งกลับของตัวเลขที่เว้นช่วงค้างนานที่สุด")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        gap = {i: len(history) for i in range(10)}
        for idx, draw in enumerate(history):
            t2 = str(draw.get("top2", ""))
            b2 = str(draw.get("bottom2", ""))
            for ch in t2 + b2:
                if ch.isdigit():
                    num = int(ch)
                    if gap[num] == len(history):
                        gap[num] = idx
        # Most overdue (highest gap)
        sorted_gap = sorted(range(10), key=lambda x: (gap[x], -x), reverse=True)
        d = sorted_gap[0]
        d_sec = sorted_gap[1]
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


class FormulaF22(Formula):
    """F22: Formula F22 astrological calendar day of week mod."""
    def __init__(self):
        super().__init__("F22", "สูตรกำลังวัน (Day of Week)", "Calendar Mod", "คำนวณกำลังวันโหราศาสตร์ประยุกต์มอดุโล 10")

    def predict(self, history: List[Dict[str, Any]], target_round: str = "special") -> FormulaPrediction:
        _, _, t2, _ = _extract_last_draw_digits(history)
        target_date_str = ""
        if history:
            target_date_str = str(history[0].get("draw_date", ""))
        try:
            dt = datetime.datetime.strptime(target_date_str, "%Y-%m-%d")
            weekday = dt.weekday()
        except Exception:
            weekday = 0
        base_power = [2, 3, 4, 5, 6, 7, 1][weekday]
        d = (base_power + int(t2[1])) % 10
        d_sec = (base_power + 1) % 10
        pairs = [f"{d}{d_sec}", f"{d_sec}{d}", f"{d}{d}", f"{d_sec}{d_sec}"]
        return FormulaPrediction(self.id, self.name, target_round, str(d), str(d_sec), pairs, self.category, self.description)


# --- Global Formula Registry (All 22 Formulas) ---

ALL_FORMULAS: List[Formula] = [
    FormulaF01(), FormulaF02(), FormulaF03(), FormulaF04(), FormulaF05(),
    FormulaF06(), FormulaF07(), FormulaF08(), FormulaF09(),
    FormulaF10(), FormulaF11(), FormulaF12(),
    FormulaF13(), FormulaF14(), FormulaF15(), FormulaF16(), FormulaF17(),
    FormulaF18(), FormulaF19(), FormulaF20(),
    FormulaF21(), FormulaF22()
]


def generate_deliverable_sets(formula_prediction: Any, history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates exact deliverable sets conforming strictly to user requirements:
      - single_swipe: str (1 digit '0'-'9')
      - swipe_numbers: list[str] (exactly 19 two-digit strings)
      - both_sets: {'10': 10, '20': 20, '30': 30, '40': 40, '50': 50}
      - top_sets: {'10': 10, '20': 20, '30': 30, '40': 40, '50': 50}
      - bottom_sets: {'10': 10, '20': 20, '30': 30, '40': 40, '50': 50}
      - fight_sets: {'10': 10, '20': 20, '25': 25, '40': 40}
    """
    # 1. Single Swipe extraction
    raw_digit = getattr(formula_prediction, "digit", None)
    if raw_digit is None and isinstance(formula_prediction, dict):
        raw_digit = formula_prediction.get("digit")
    digit_chars = [ch for ch in str(raw_digit or "") if ch.isdigit()]
    single_swipe = digit_chars[0] if digit_chars else "5"
    d_int = int(single_swipe)

    raw_sec = getattr(formula_prediction, "secondary_digit", None)
    if raw_sec is None and isinstance(formula_prediction, dict):
        raw_sec = formula_prediction.get("secondary_digit")
    sec_chars = [ch for ch in str(raw_sec or "") if ch.isdigit()]
    sec_swipe = sec_chars[0] if sec_chars else str((d_int + 1) % 10)
    sec_int = int(sec_swipe)

    # 19 Numbers generation (strictly unique, exactly 19)
    swipe_numbers: List[str] = []
    for i in range(10):
        swipe_numbers.append(f"{single_swipe}{i}")
    for i in range(10):
        if str(i) != single_swipe:
            swipe_numbers.append(f"{i}{single_swipe}")

    # 2. Historical Frequency Mining
    top_counts = {i: 0 for i in range(10)}
    bot_counts = {i: 0 for i in range(10)}
    for draw in history[:30]:
        t2 = str(draw.get("top2", ""))
        b2 = str(draw.get("bottom2", ""))
        for ch in t2:
            if ch.isdigit():
                top_counts[int(ch)] += 1
        for ch in b2:
            if ch.isdigit():
                bot_counts[int(ch)] += 1

    # 3. Deterministic 100-number scoring engine
    raw_pairs = getattr(formula_prediction, "pairs", None)
    if raw_pairs is None and isinstance(formula_prediction, dict):
        raw_pairs = formula_prediction.get("pairs")
    pred_pairs = set(raw_pairs or [])

    def compute_scores(target_type: str) -> List[str]:
        scored: List[Tuple[float, str]] = []
        for n_val in range(100):
            n_str = f"{n_val:02d}"
            t_d, u_d = int(n_str[0]), int(n_str[1])
            score = 0.0

            # Priority 1: In formula's explicit prediction pairs
            if n_str in pred_pairs:
                score += 500.0

            # Priority 2: Contains primary swipe digit
            if t_d == d_int or u_d == d_int:
                score += 200.0

            # Priority 3: Contains secondary swipe digit
            if t_d == sec_int or u_d == sec_int:
                score += 100.0

            # Priority 4: Position-specific frequency weight
            if target_type == "top":
                score += (top_counts[t_d] * 2.0 + top_counts[u_d] * 2.0)
            elif target_type == "bottom":
                score += (bot_counts[t_d] * 2.0 + bot_counts[u_d] * 2.0)
            else:  # both
                score += (top_counts[t_d] + top_counts[u_d] + bot_counts[t_d] + bot_counts[u_d])

            # Deterministic tie-breaker
            tie_breaker = ((n_val * 37 + 13) % 100) / 100.0
            scored.append((score + tie_breaker, n_str))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored]

    ranked_both = compute_scores("both")
    ranked_top = compute_scores("top")
    ranked_bottom = compute_scores("bottom")

    both_sets = {
        "10": ranked_both[:10],
        "20": ranked_both[:20],
        "30": ranked_both[:30],
        "40": ranked_both[:40],
        "50": ranked_both[:50],
    }

    top_sets = {
        "10": ranked_top[:10],
        "20": ranked_top[:20],
        "30": ranked_top[:30],
        "40": ranked_top[:40],
        "50": ranked_top[:50],
    }

    bottom_sets = {
        "10": ranked_bottom[:10],
        "20": ranked_bottom[:20],
        "30": ranked_bottom[:30],
        "40": ranked_bottom[:40],
        "50": ranked_bottom[:50],
    }

    # 4. Elite Fight Sets (ชุดท็อปสู้ชีวิตสู้ทุกคน: 10, 20, 25, 40)
    core_digits = [single_swipe]
    if sec_swipe not in core_digits:
        core_digits.append(sec_swipe)

    sorted_digits = sorted(range(10), key=lambda d: (top_counts[d] + bot_counts[d], -d), reverse=True)
    for d in sorted_digits:
        s_d = str(d)
        if s_d not in core_digits:
            core_digits.append(s_d)
        if len(core_digits) == 5:
            break

    # 25 numbers: Complete Vin-5 Cartesian matrix (5x5 = 25 numbers with doubles)
    vin_25: List[str] = []
    for d1 in core_digits:
        for d2 in core_digits:
            vin_25.append(f"{d1}{d2}")
    vin_25 = list(dict.fromkeys(vin_25))
    for n in ranked_both:
        if len(vin_25) >= 25:
            break
        if n not in vin_25:
            vin_25.append(n)
    vin_25 = vin_25[:25]

    # 20 numbers: Vin-5 permutation matrix without doubles (5x4 = 20 numbers)
    vin_20: List[str] = []
    for d1 in core_digits:
        for d2 in core_digits:
            if d1 != d2:
                vin_20.append(f"{d1}{d2}")
    vin_20 = list(dict.fromkeys(vin_20))
    for n in ranked_both:
        if len(vin_20) >= 20:
            break
        if n not in vin_20:
            vin_20.append(n)
    vin_20 = vin_20[:20]

    # 10 numbers: Top 5 reciprocal pairs from core digits
    fight_10: List[str] = []
    for i in range(len(core_digits)):
        for j in range(i + 1, len(core_digits)):
            fight_10.append(f"{core_digits[i]}{core_digits[j]}")
            fight_10.append(f"{core_digits[j]}{core_digits[i]}")
            if len(fight_10) >= 10:
                break
        if len(fight_10) >= 10:
            break
    fight_10 = list(dict.fromkeys(fight_10))
    for n in ranked_both:
        if len(fight_10) >= 10:
            break
        if n not in fight_10:
            fight_10.append(n)
    fight_10 = fight_10[:10]

    # 40 numbers: 19 gates on single_swipe + 19 gates on sec_swipe (36) + supplementary
    fight_40: List[str] = list(swipe_numbers)
    for i in range(10):
        num = f"{sec_swipe}{i}"
        if num not in fight_40:
            fight_40.append(num)
    for i in range(10):
        if i != sec_int:
            num = f"{i}{sec_swipe}"
            if num not in fight_40:
                fight_40.append(num)
    for n in ranked_both:
        if len(fight_40) >= 40:
            break
        if n not in fight_40:
            fight_40.append(n)
    fight_40 = fight_40[:40]

    fight_sets = {
        "10": fight_10,
        "20": vin_20,
        "25": vin_25,
        "40": fight_40,
    }

    return {
        "single_swipe": single_swipe,
        "swipe_numbers": swipe_numbers,
        "both_sets": both_sets,
        "top_sets": top_sets,
        "bottom_sets": bottom_sets,
        "fight_sets": fight_sets,
    }


def format_copy_text(round_name: str, draw_date: str, formula_name: str, win_rate: float, sets: Dict[str, Any]) -> str:
    """
    Builds a beautifully structured Thai social copy text block ready for 1-click clipboard paste
    to LINE, Telegram, and Facebook lottery groups.
    Handles empty set lists gracefully without raising IndexError.
    """
    if not isinstance(sets, dict):
        sets = {}

    swipe = str(sets.get("single_swipe") or "-")
    fight = sets.get("fight_sets") or {}
    both = sets.get("both_sets") or {}
    top = sets.get("top_sets") or {}
    bot = sets.get("bottom_sets") or {}

    if not isinstance(fight, dict):
        fight = {}
    if not isinstance(both, dict):
        both = {}
    if not isinstance(top, dict):
        top = {}
    if not isinstance(bot, dict):
        bot = {}

    def _fmt(num_list: Any) -> str:
        if not num_list or not isinstance(num_list, (list, tuple)):
            return "-"
        return " ".join(num_list)

    win_rate_str = f"{float(win_rate):.1f}"

    lines = [
        f"🎯 แนวทางหวยฮานอย [รอบ: {round_name}] ประจำวันที่ {draw_date}",
        f"🏆 สูตรคำนวณอันดับ 1: {formula_name} (Win Rate: {win_rate_str}%)",
        "========================================",
        f"⭐ รูดตัวเดียว (บน-ล่าง): {swipe}",
        "========================================",
        "📌 [ชุดท็อปสู้ชีวิตสู้ทุกคน (บน-ล่าง)]",
        f"- 10 ตัว: {_fmt(fight.get('10'))}",
        f"- 20 ตัว: {_fmt(fight.get('20'))}",
        f"- 25 ตัว: {_fmt(fight.get('25'))}",
        f"- 40 ตัว: {_fmt(fight.get('40'))}",
        "----------------------------------------",
        "📌 [เลขชุดบน-ล่าง]",
        f"- 10 ตัว: {_fmt(both.get('10'))}",
        f"- 20 ตัว: {_fmt(both.get('20'))}",
        f"- 30 ตัว: {_fmt(both.get('30'))}",
        f"- 40 ตัว: {_fmt(both.get('40'))}",
        f"- 50 ตัว: {_fmt(both.get('50'))}",
        "----------------------------------------",
        "📌 [เลขชุดบน]",
        f"- 10 ตัวบน: {_fmt(top.get('10'))}",
        f"- 20 ตัวบน: {_fmt(top.get('20'))}",
        f"- 30 ตัวบน: {_fmt(top.get('30'))}",
        f"- 40 ตัวบน: {_fmt(top.get('40'))}",
        f"- 50 ตัวบน: {_fmt(top.get('50'))}",
        "----------------------------------------",
        "📌 [เลขชุดล่าง]",
        f"- 10 ตัวล่าง: {_fmt(bot.get('10'))}",
        f"- 20 ตัวล่าง: {_fmt(bot.get('20'))}",
        f"- 30 ตัวล่าง: {_fmt(bot.get('30'))}",
        f"- 40 ตัวล่าง: {_fmt(bot.get('40'))}",
        f"- 50 ตัวล่าง: {_fmt(bot.get('50'))}",
        "========================================",
        "คำเตือน: ตัวเลขเป็นการคำนวณทางสถิติย้อนหลัง โปรดใช้วิจารณญาณ",
    ]
    return "\n".join(lines)
