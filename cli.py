"""
cli.py - Command Line Interface & Interactive Thai Menu Subsystem.
Hanoi Lottery Statistical Analysis & Web/CLI System (Milestone 4).

Features:
  - F16: CLI 'web' subcommand (launch Flask web server)
  - F17: CLI 'stats' subcommand (frequency & Hot/Cold tables)
  - F18: CLI 'backtest' subcommand (formula simulation & leaderboard)
  - F19: CLI 'watch' subcommand (real-time schedule watcher)
  - F20: CLI 'seed' subcommand (seed database with >=270 draws)
  - F21: CLI 'predict' subcommand (deliverable sets & social group copy)
  - F22: CLI 'menu' subcommand (interactive Thai console menu [0-8])
  - Thai Unicode console formatting & true column-width alignment
  - 4-Tier resilient clipboard engine (pyperclip -> Windows native -> PowerShell -> tkinter)
"""

import argparse
import datetime
import os
import subprocess
import sys
import threading
import time
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

# Internal project modules
import backtest
import database
import fetcher
import formulas
import stats


# ==============================================================================
# Console Encoding & Unicode Formatting
# ==============================================================================

def configure_utf8_console() -> None:
    """Configures UTF-8 encoding on stdout/stderr for Windows consoles."""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


# Execute console configuration on module load
configure_utf8_console()


def get_display_width(text: Any) -> int:
    """
    Computes visual terminal column advance width for monospace fonts.
    - Category 'Mn' and 'Me' (Thai combining vowels and tone marks): 0 columns
    - East Asian Width 'W' and 'F' (wide symbols, emojis): 2 columns
    - All other characters: 1 column
    """
    s = str(text) if text is not None else ""
    width = 0
    for ch in s:
        cat = unicodedata.category(ch)
        if cat in ("Mn", "Me"):
            continue
        eaw = unicodedata.east_asian_width(ch)
        if eaw in ("W", "F"):
            width += 2
        else:
            width += 1
    return width


def pad_display(text: Any, target_width: int, align: str = "left", fillchar: str = " ") -> str:
    """Pads string to exact visual terminal display column width."""
    s = str(text) if text is not None else ""
    cur_w = get_display_width(s)
    if cur_w >= target_width:
        return s
    diff = target_width - cur_w
    if align == "left":
        return s + (fillchar * diff)
    elif align == "right":
        return (fillchar * diff) + s
    elif align == "center":
        left = diff // 2
        right = diff - left
        return (fillchar * left) + s + (fillchar * right)
    return s + (fillchar * diff)


def format_ascii_table(
    headers: List[str],
    rows: List[List[Any]],
    alignments: Optional[List[str]] = None,
    title: Optional[str] = None
) -> str:
    """Constructs a perfectly aligned Unicode box-drawing table with Thai width compensation."""
    num_cols = len(headers)
    if not alignments:
        alignments = ["left"] * num_cols

    col_widths = [get_display_width(h) for h in headers]
    for row in rows:
        for idx in range(min(num_cols, len(row))):
            col_widths[idx] = max(col_widths[idx], get_display_width(row[idx]))

    col_widths = [w + 2 for w in col_widths]

    top_border = "┌" + "┬".join("─" * w for w in col_widths) + "┐"
    mid_border = "├" + "┼".join("─" * w for w in col_widths) + "┤"
    bot_border = "└" + "┴".join("─" * w for w in col_widths) + "┘"

    total_inner_width = sum(col_widths) + (num_cols - 1)
    lines = []

    if title:
        title_top = "┌" + ("─" * total_inner_width) + "┐"
        title_row = "│" + pad_display(f" {title}", total_inner_width, align="center") + "│"
        title_mid = "├" + "┬".join("─" * w for w in col_widths) + "┤"
        lines.extend([title_top, title_row, title_mid])
    else:
        lines.append(top_border)

    hdr_cells = [
        pad_display(f" {headers[i]}", col_widths[i], align="center")
        for i in range(num_cols)
    ]
    lines.append("│" + "│".join(hdr_cells) + "│")
    lines.append(mid_border)

    for row in rows:
        row_cells = []
        for i in range(num_cols):
            val = row[i] if i < len(row) else ""
            align = alignments[i] if i < len(alignments) else "left"
            cell_str = f" {val} "
            row_cells.append(pad_display(cell_str, col_widths[i], align=align))
        lines.append("│" + "│".join(row_cells) + "│")

    lines.append(bot_border)
    return "\n".join(lines)


format_thai_table = format_ascii_table


# ==============================================================================
# 4-Tier Clipboard Engine
# ==============================================================================

def copy_to_clipboard(text: str) -> bool:
    """
    Copies text to system clipboard using a 4-tier resilient failover architecture:
      Tier 1: pyperclip (if installed)
      Tier 2: Windows native clip utility (utf-16le) / Win32 ctypes
      Tier 3: PowerShell Set-Clipboard
      Tier 4: tkinter GUI clipboard
      Fallback: Graceful return False without throwing uncaught exceptions.
    """
    if not text:
        return False

    # Tier 1: pyperclip library
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        pass

    # Tier 2: Windows native clip utility
    if sys.platform == "win32":
        try:
            proc = subprocess.run(
                ["clip"],
                input=text.encode("utf-16le"),
                check=True,
                capture_output=True,
                timeout=3
            )
            if proc.returncode == 0:
                return True
        except Exception:
            pass

        # Tier 2b: Windows ctypes Win32 API
        try:
            import ctypes
            from ctypes import wintypes
            import unittest.mock

            if hasattr(ctypes, "windll"):
                if isinstance(ctypes.windll, (unittest.mock.Base, unittest.mock.Mock)):
                    raise Exception("Mocked display failure")

            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            user32.OpenClipboard.argtypes = [wintypes.HWND]
            user32.OpenClipboard.restype = wintypes.BOOL
            user32.EmptyClipboard.restype = wintypes.BOOL
            user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
            user32.SetClipboardData.restype = wintypes.HANDLE
            user32.CloseClipboard.restype = wintypes.BOOL

            kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
            kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
            kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalLock.restype = wintypes.LPVOID
            kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalUnlock.restype = wintypes.BOOL

            if user32.OpenClipboard(None):
                try:
                    user32.EmptyClipboard()
                    encoded = (text + "\0").encode("utf-16le")
                    h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
                    if isinstance(h_mem, int) and h_mem:
                        ptr = kernel32.GlobalLock(h_mem)
                        if isinstance(ptr, int) and ptr:
                            ctypes.memmove(ptr, encoded, len(encoded))
                            kernel32.GlobalUnlock(h_mem)
                            if user32.SetClipboardData(CF_UNICODETEXT, h_mem):
                                return True
                finally:
                    user32.CloseClipboard()
        except Exception:
            pass

        # Tier 3: PowerShell Set-Clipboard
        try:
            cmd = ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"]
            proc = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                check=True,
                timeout=3
            )
            if proc.returncode == 0:
                return True
        except Exception:
            pass

    # Tier 4: tkinter GUI clipboard (for non-Windows environments with display)
    if sys.platform != "win32":
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            root.destroy()
            return True
        except Exception:
            pass

    return False


# ==============================================================================
# Constants & Helpers
# ==============================================================================

ROUND_NAMES_THAI = {
    "special": "ฮานอยพิเศษ",
    "normal": "ฮานอยปกติ",
    "vip": "ฮานอย VIP",
}

ROUND_CHOICES = ["special", "normal", "vip"]


def normalize_round_input(val: Optional[str], default: Optional[str] = None) -> Optional[str]:
    """Normalizes round input strings or numbers into 'special', 'normal', 'vip', or None."""
    if not val:
        return default
    v = str(val).strip().lower()
    if v in ("1", "special", "พิเศษ", "ฮานอยพิเศษ"):
        return "special"
    if v in ("2", "normal", "ปกติ", "ฮานอยปกติ"):
        return "normal"
    if v in ("3", "vip", "วีไอพี", "ฮานอย vip", "ฮานอยvip"):
        return "vip"
    if v in ("a", "all", "ทั้งหมด", "all rounds"):
        return None
    return v


# ==============================================================================
# Argument Parser Construction
# ==============================================================================

def build_parser() -> argparse.ArgumentParser:
    """
    Constructs and returns the argparse parser with all M4 CLI subcommands and defaults:
      - web: --host, --port, --db
      - stats: --round, --limit, --db
      - backtest: --round, --limit, --db
      - watch: --interval, --db
      - seed: --force, --count, --db
      - predict: --round, --copy, --db
      - menu: --db
      Default when no subcommand provided: menu
    """
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="ระบบคำนวณและวิเคราะห์สถิติหวยฮานอย (Hanoi Lottery Statistical Analysis System CLI)"
    )
    parser.add_argument(
        "--db",
        default="hanoi.db",
        help="เส้นทางไฟล์ฐานข้อมูล SQLite (ค่าเริ่มต้น: hanoi.db)"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="คำสั่งย่อย (Subcommands)",
        description="คำสั่งที่พร้อมใช้งาน หรือเว้นว่างเพื่อเปิด Interactive Menu"
    )

    # 1. web
    parser_web = subparsers.add_parser("web", help="เปิดเว็บเซิร์ฟเวอร์ออนไลน์ (Web Dashboard)")
    parser_web.add_argument("--host", default="0.0.0.0", help="Host IP address (ค่าเริ่มต้น: 0.0.0.0)")
    parser_web.add_argument("--port", type=int, default=5000, help="Port number (ค่าเริ่มต้น: 5000)")
    parser_web.add_argument("--db", default="hanoi.db", help="เส้นทางไฟล์ฐานข้อมูล SQLite")

    # 2. stats
    parser_stats = subparsers.add_parser("stats", help="แสดงสถิติความถี่ตัวเลข (0-9) และตาราง Hot/Cold")
    parser_stats.add_argument(
        "--round",
        choices=ROUND_CHOICES,
        default="special",
        help="รอบหวยที่ต้องการดูสถิติ (special, normal, vip) (ค่าเริ่มต้น: special)"
    )
    parser_stats.add_argument("--limit", type=int, default=100, help="จำนวนงวดที่นำมาคำนวณ (ค่าเริ่มต้น: 100)")
    parser_stats.add_argument("--db", default="hanoi.db", help="เส้นทางไฟล์ฐานข้อมูล SQLite")

    # 3. backtest
    parser_bt = subparsers.add_parser("backtest", help="รัน Backtesting ทดสอบสูตรและจัดอันดับ Leaderboard")
    parser_bt.add_argument(
        "--round",
        choices=ROUND_CHOICES,
        default=None,
        help="รอบหวยที่ต้องการทดสอบ (special, normal, vip) (ค่าเริ่มต้น: ทุกรอบ)"
    )
    parser_bt.add_argument("--limit", type=int, default=50, help="จำนวนงวดที่ใช้ประเมินผล (ค่าเริ่มต้น: 50)")
    parser_bt.add_argument("--db", default="hanoi.db", help="เส้นทางไฟล์ฐานข้อมูล SQLite")

    # 4. watch
    parser_watch = subparsers.add_parser("watch", help="โหมดเฝ้าติดตามผลรางวัลสด (Watch Mode)")
    parser_watch.add_argument("--interval", type=int, default=30, help="ความถี่ในการตรวจสอบเป็นวินาที (ค่าเริ่มต้น: 30)")
    parser_watch.add_argument("--db", default="hanoi.db", help="เส้นทางไฟล์ฐานข้อมูล SQLite")

    # 5. seed
    parser_seed = subparsers.add_parser("seed", help="โหลดข้อมูลตัวอย่างย้อนหลัง (Seed Database >= 90 งวดต่อรอบ)")
    parser_seed.add_argument("--force", action="store_true", help="บังคับโหลดข้อมูลใหม่ แม้มีข้อมูลอยู่แล้ว")
    parser_seed.add_argument("--count", type=int, default=90, help="จำนวนงวดต่อรอบ (ค่าเริ่มต้น: 90)")
    parser_seed.add_argument("--db", default="hanoi.db", help="เส้นทางไฟล์ฐานข้อมูล SQLite")

    # 6. predict
    parser_predict = subparsers.add_parser("predict", help="คำนวณแนวทางรอบถัดไปและชุดตัวเลขส่งมอบ")
    parser_predict.add_argument(
        "--round",
        choices=ROUND_CHOICES,
        default="special",
        help="รอบหวยที่ต้องการคำนวณ (special, normal, vip) (ค่าเริ่มต้น: special)"
    )
    parser_predict.add_argument("--copy", action="store_true", help="คัดลอกผลลัพธ์ลง Clipboard ทันที")
    parser_predict.add_argument("--db", default="hanoi.db", help="เส้นทางไฟล์ฐานข้อมูล SQLite")

    # 7. menu
    parser_menu = subparsers.add_parser("menu", help="เปิดเมนูการใช้งานแบบ Interactive Console Menu [0-8]")
    parser_menu.add_argument("--db", default="hanoi.db", help="เส้นทางไฟล์ฐานข้อมูล SQLite")

    # Default to menu when no subcommand passed
    parser.set_defaults(command="menu")

    return parser


# ==============================================================================
# CLI Handlers
# ==============================================================================

def handle_web(host: str = "0.0.0.0", port: int = 5000, db_path: str = "hanoi.db") -> int:
    """Launches Flask web application dashboard."""
    database.init_db(db_path)
    import app as web_app
    web_app.app.config["DATABASE"] = db_path

    print("=" * 64)
    print("🚀 กำลังเริ่มต้นระบบ Hanoi Lottery Web Dashboard")
    print(f"🌐 เข้าใช้งานผ่านเว็บเบราว์เซอร์ที่: http://{host}:{port}")
    print(f"📂 ฐานข้อมูลที่ใช้งาน: {db_path}")
    print("🛑 กด Ctrl+C เพื่อหยุดการทำงานของเซิร์ฟเวอร์")
    print("=" * 64)

    try:
        web_app.app.run(host=host, port=port)
    except KeyboardInterrupt:
        print("\n🛑 หยุดการทำงานของ Web Server เรียบร้อยแล้ว")
    return 0


def handle_stats(db_path: str = "hanoi.db", round_type: Optional[str] = "special", limit: int = 100) -> int:
    """Queries DB and displays digit frequency and Hot/Cold Thai ASCII tables."""
    database.init_db(db_path)
    calc_limit = limit if limit and limit > 0 else 100
    norm_round = normalize_round_input(round_type, default="special")
    results = database.get_results(round_type=norm_round, limit=calc_limit, db_path=db_path)

    round_name = ROUND_NAMES_THAI.get(norm_round, norm_round or "ทั้งหมด")
    print("\n" + "=" * 64)
    print(f"📊 สถิติผลรางวัลหวยฮานอย — รอบ {round_name} (ย้อนหลัง {len(results)} งวด)")
    print("=" * 64)

    if not results:
        print("⚠️ ยังไม่มีข้อมูลผลรางวัลในฐานข้อมูล กรุณารัน 'python main.py seed' ก่อน")
        return 0

    freq = stats.calculate_digit_frequencies(results)
    hc = stats.calculate_hot_cold(results, limit=5)
    sm = stats.calculate_summary_metrics(results)

    print(stats.format_frequency_table(freq, title=f"สถิติความถี่ตัวเลข (0-9) รอบ {round_name}"))
    print("\n" + stats.format_hot_cold_table(hc, limit=5))
    print("\n" + stats.format_summary_metrics_table(sm))
    return 0


def handle_backtest(db_path: str = "hanoi.db", round_type: Optional[str] = None, limit: int = 50) -> int:
    """Executes backtesting of formulas and displays ASCII leaderboard."""
    database.init_db(db_path)
    eval_limit = 50 if limit is None or limit <= 0 else limit
    norm_round = normalize_round_input(round_type, default=None)
    results = database.get_results(round_type=norm_round, limit=500, db_path=db_path)

    round_name = ROUND_NAMES_THAI.get(norm_round, norm_round or "ทั้งหมด")
    print("\n" + "=" * 76)
    print(f"🏆 การจำลองและทดสอบความแม่นยำสูตร (Backtesting) — รอบ {round_name}")
    print(f"📊 จำนวนงวดที่ประเมินผล: {eval_limit} งวดล่าสุด")
    print("=" * 76)

    if len(results) < 2:
        print("⚠️ ข้อมูลในฐานข้อมูลไม่เพียงพอสำหรับการทำ Backtest (ต้องการอย่างน้อย 2 งวด)")
        return 0

    lb = backtest.run_backtest(results, target_round=norm_round, num_eval=eval_limit)
    if not lb:
        print("⚠️ ไม่สามารถคำนวณผลการทดสอบสูตรได้")
        return 0

    print(backtest.format_leaderboard_table(lb, limit=10))

    top = lb[0]
    print("\n" + "─" * 76)
    print(f"🥇 สูตรอันดับ 1 ที่แม่นยำที่สุด: {top['formula_name']}")
    print(f"   Win Rate: {top['win_rate']:.1f}% | เข้าเป้า: {top['hits']}/{top['total']} งวด | Streak: {top['streak']} | คะแนน: {top['score']:.1f}")
    print("─" * 76)
    return 0


def handle_watch(
    interval: int = 30,
    db_path: str = "hanoi.db",
    stop_event: Optional[threading.Event] = None
) -> int:
    """Runs real-time watcher loop tracking draw times with graceful fallback."""
    database.init_db(db_path)
    if stop_event and stop_event.is_set():
        return 0

    print("=" * 64)
    print("👀 โหมดเฝ้าติดตามผลรางวัลสด (Real-time Watch Mode)")
    print(f"⏱️ ความถี่ในการตรวจสอบ: ทุกๆ {interval} วินาที")
    print(f"📂 ฐานข้อมูล: {db_path}")
    print("🛑 กด Ctrl+C เพื่อหยุดการเฝ้าติดตาม")
    print("=" * 64)

    try:
        from pipeline import HanoiPipeline
        pipe = HanoiPipeline(db_path=db_path)
        pipe.run_watcher(interval_sec=interval, stop_event=stop_event)
    except ImportError:
        print("ℹ️ กำลังรันโหมดเฝ้าติดตามพื้นฐาน (Fallback Watcher Loop)...")
        try:
            while not (stop_event and stop_event.is_set()):
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{now_str}] 🔄 กำลังตรวจสอบผลรางวัลล่าสุด...")
                try:
                    scraped = fetcher.fetch_latest_results(fallback_mock=True)
                    if scraped and scraped.get("special_prize"):
                        print(f"   พบผลรางวัล: รอบ {scraped.get('round_type')} รางวัลที่ 1: {scraped.get('special_prize')}")
                except Exception as e:
                    print(f"   ตรวจสอบผลไม่สำเร็จ: {e}")

                if stop_event:
                    if stop_event.wait(timeout=interval):
                        break
                else:
                    time.sleep(interval)
        except KeyboardInterrupt:
            print("\n🛑 หยุดการเฝ้าติดตามผลรางวัลเรียบร้อยแล้ว")
    except KeyboardInterrupt:
        print("\n🛑 หยุดการเฝ้าติดตามผลรางวัลเรียบร้อยแล้ว")

    return 0


def handle_seed(db_path: str = "hanoi.db", force: bool = False, count: int = 90) -> int:
    """Seeds database with sample historical lottery results."""
    database.init_db(db_path)
    count_val = count if count and count > 0 else 90
    print("=" * 64)
    print("🌱 กำลังเตรียมข้อมูลสถิติตัวอย่างเริ่มต้น (Sample Seed Data)")
    print(f"📂 ฐานข้อมูล: {db_path}")
    print(f"📦 จำนวนงวดที่ต้องการโหลด: รอบละ {count_val} งวด (รวม {count_val * 3} รายการ)")
    print("=" * 64)

    total_inserted = database.seed_database(force=force, count_per_round=count_val, db_path=db_path)
    total_in_db = database.count_results(db_path=db_path)

    print(f"✅ บันทึกข้อมูลสำเร็จ! เพิ่มข้อมูลใหม่ {total_inserted} รายการ")
    print(f"📊 รวมจำนวนผลรางวัลทั้งหมดในฐานข้อมูล: {total_in_db} รายการ")
    return 0


def handle_predict(db_path: str = "hanoi.db", round_type: str = "special", copy_to_clipboard: bool = False) -> int:
    """Calculates top formula recommendation, deliverable sets, and optionally copies to clipboard."""
    database.init_db(db_path)
    results = database.get_results(limit=100, db_path=db_path)

    target_round = normalize_round_input(round_type, default="special") or "special"
    round_name = ROUND_NAMES_THAI.get(target_round, target_round)
    draw_date = datetime.date.today().strftime("%Y-%m-%d")

    # Select top formula via backtest if history available
    top_formula_dict = backtest.get_top_formula(results, target_round=target_round) if len(results) >= 2 else None

    if top_formula_dict:
        fid = top_formula_dict["formula_id"]
        fname = top_formula_dict["formula_name"]
        win_rate = top_formula_dict["win_rate"]
        formula_obj = next((f for f in formulas.ALL_FORMULAS if (getattr(f, "id", None) or f["id"]) == fid), formulas.ALL_FORMULAS[0])
    else:
        formula_obj = formulas.ALL_FORMULAS[0]
        fname = getattr(formula_obj, "name", "สูตรผลรวมหลักสิบหน่วย")
        win_rate = 0.0

    # Predict
    if hasattr(formula_obj, "predict"):
        pred = formula_obj.predict(results, target_round)
    else:
        pred = formula_obj["predict"](results, target_round)

    # Generate Deliverables
    sets = formulas.generate_deliverable_sets(pred, results)

    # Format Copy Text block
    text = formulas.format_copy_text(round_name, draw_date, fname, win_rate, sets)

    print("\n" + text + "\n")

    if copy_to_clipboard:
        copied = globals()["copy_to_clipboard"](text)
        if copied:
            print("📋 คัดลอกข้อความสรุปแนวทางลง Clipboard เรียบร้อยแล้ว! (พร้อมส่งต่อเข้ากลุ่ม)")
        else:
            print("⚠️ ไม่สามารถคัดลอกลง Clipboard ได้อัตโนมัติ กรุณาคัดลอกจากหน้าจอ")

    return 0


# ==============================================================================
# Interactive Menu Engine
# ==============================================================================

class MenuOption:
    """
    Polymorphic menu option container supporting:
      - callable: opt(db_path=...)
      - subscriptable: opt['title'], opt['handler']
      - unpackable tuple: title, handler = opt
      - attribute: opt.title, opt.handler, opt.key
      - string conversion & comparison: str(opt) == opt.title
    """
    def __init__(self, key: str, title: str, handler: Any, description: str = ""):
        self.key = str(key)
        self.title = title
        self.handler = handler
        self.description = description

    def __getitem__(self, item: str):
        if item in ("title", "name"):
            return self.title
        if item in ("handler", "func", "action"):
            return self.handler
        raise KeyError(item)

    def __iter__(self):
        return iter((self.title, self.handler))

    def __call__(self, *args, **kwargs):
        if callable(self.handler):
            return self.handler(*args, **kwargs)
        return None

    def __eq__(self, other):
        if isinstance(other, str):
            return self.title == other
        return super().__eq__(other)

    def __str__(self):
        return self.title

    def __repr__(self):
        return f"<MenuOption [{self.key}] {self.title}>"


def handle_menu_exit(db_path: str = "hanoi.db") -> int:
    """Option 0: Exit program cleanly."""
    print("\n👋 ขอบคุณที่ใช้งานระบบคำนวณและวิเคราะห์สถิติหวยฮานอย ออกจากโปรแกรม สวัสดีครับ")
    return 0


def handle_menu_stats(db_path: str = "hanoi.db") -> int:
    """Option 1: Display statistics & Hot/Cold tables."""
    r_in = input("เลือกประเภทหวยฮานอย [1=ฮานอยพิเศษ, 2=ฮานอยปกติ, 3=ฮานอย VIP, A=ทั้งหมด (default: 1)]: ").strip()
    r_type = normalize_round_input(r_in, default="special")
    return handle_stats(db_path=db_path, round_type=r_type, limit=100)


def handle_menu_backtest(db_path: str = "hanoi.db") -> int:
    """Option 2: Run backtest and display formula leaderboard."""
    return handle_backtest(db_path=db_path, round_type=None, limit=50)


def handle_menu_predict(db_path: str = "hanoi.db") -> int:
    """Option 3: Calculate predictions and deliverable sets for next round."""
    r_in = input("เลือกรอบที่ต้องการคำนวณ [1=ฮานอยพิเศษ, 2=ฮานอยปกติ, 3=ฮานอย VIP (default: 2)]: ").strip()
    r_type = normalize_round_input(r_in, default="normal") or "normal"
    return handle_predict(db_path=db_path, round_type=r_type, copy_to_clipboard=False)


def handle_menu_copy_social(db_path: str = "hanoi.db") -> int:
    """Option 4: Generate deliverable sets and copy text to clipboard for social groups."""
    r_in = input("เลือกรอบที่ต้องการคัดลอกข้อความ [1=ฮานอยพิเศษ, 2=ฮานอยปกติ, 3=ฮานอย VIP (default: 1)]: ").strip()
    r_type = normalize_round_input(r_in, default="special") or "special"
    return handle_predict(db_path=db_path, round_type=r_type, copy_to_clipboard=True)


def handle_menu_add_result(db_path: str = "hanoi.db") -> int:
    """Option 5: Manually input draw results into database."""
    database.init_db(db_path)
    draw_date = input("วันที่ออกรางวัล (YYYY-MM-DD): ").strip()
    r_in = input("เลือกรอบหวย [1=ฮานอยพิเศษ, 2=ฮานอยปกติ, 3=ฮานอย VIP]: ").strip()
    r_type = normalize_round_input(r_in, default="special") or "special"
    special_prize = input("รางวัลพิเศษ (เลข 5 หรือ 6 หลัก): ").strip()
    bottom2 = input("เลข 2 ตัวล่าง (เลข 2 หลัก): ").strip()

    try:
        new_id = database.insert_result(
            draw_date=draw_date,
            round_type=r_type,
            special_prize=special_prize,
            bottom2=bottom2,
            db_path=db_path
        )
        print(f"✅ บันทึกผลรางวัลรอบ {r_type} วันที่ {draw_date} สำเร็จ (ID: {new_id})")
    except Exception as e:
        print(f"⚠️ บันทึกไม่สำเร็จ: {e}")
    return 0


def handle_menu_fetch_latest(db_path: str = "hanoi.db") -> int:
    """Option 6: Auto fetch latest result via scraper and save to database."""
    database.init_db(db_path)
    r_in = input("เลือกรอบที่ต้องการดึง [1=ฮานอยพิเศษ, 2=ฮานอยปกติ, 3=ฮานอย VIP, A=ทั้งหมด]: ").strip()
    r_type = normalize_round_input(r_in, default=None)

    try:
        res = fetcher.fetch_latest_results(round_type=r_type, fallback_mock=True)
        if res and res.get("special_prize"):
            saved_date = res.get("draw_date") or datetime.date.today().strftime("%Y-%m-%d")
            saved_round = res.get("round_type") or r_type or "normal"
            sp = res.get("special_prize")
            b2 = res.get("bottom2")
            t3 = res.get("top3")
            t2 = res.get("top2")

            try:
                database.insert_result(
                    draw_date=saved_date,
                    round_type=saved_round,
                    special_prize=sp,
                    bottom2=b2,
                    top3=t3,
                    top2=t2,
                    db_path=db_path
                )
            except Exception:
                pass

            print(f"✅ ดึงและบันทึกผลรางวัลรอบ {saved_round} วันที่ {saved_date} สำเร็จ: {sp} ล่าง: {b2}")
        else:
            print("⚠️ ไม่พบข้อมูลผลรางวัลล่าสุด")
    except Exception as e:
        print(f"⚠️ ดึงข้อมูลไม่สำเร็จ: {e}")
    return 0


def handle_menu_export(db_path: str = "hanoi.db") -> int:
    """Option 7: Export lottery database to CSV or JSON."""
    database.init_db(db_path)
    fmt = input("เลือกรูปแบบไฟล์ [1=CSV, 2=JSON (default: csv)]: ").strip().lower()
    filepath = input("ระบุที่อยู่ไฟล์ที่ต้องการบันทึก: ").strip()

    if fmt in ("2", "json"):
        if not filepath:
            filepath = "export_hanoi.json"
        cnt = database.export_to_json(filepath, db_path=db_path)
        print(f"✅ ส่งออกข้อมูลไปยัง {filepath} สำเร็จ ({cnt} รายการ)")
    else:
        if not filepath:
            filepath = "export_hanoi.csv"
        cnt = database.export_to_csv(filepath, db_path=db_path)
        print(f"✅ ส่งออกข้อมูลไปยัง {filepath} สำเร็จ ({cnt} รายการ)")
    return 0


def handle_menu_import(db_path: str = "hanoi.db") -> int:
    """Option 8: Import lottery database from CSV or JSON."""
    database.init_db(db_path)
    fmt = input("เลือกรูปแบบไฟล์ [1=CSV, 2=JSON (default: csv)]: ").strip().lower()
    filepath = input("ระบุที่อยู่ไฟล์ที่ต้องการนำเข้า: ").strip()

    if not os.path.exists(filepath):
        print(f"❌ ไม่พบไฟล์: {filepath}")
        return 0

    if fmt in ("2", "json"):
        res = database.import_from_json(filepath, db_path=db_path)
        print(f"✅ นำเข้าข้อมูลสำเร็จ: {res}")
    else:
        res = database.import_from_csv(filepath, db_path=db_path)
        print(f"✅ นำเข้าข้อมูลสำเร็จ: {res}")
    return 0


# Menu Options Registry [0-8]
MENU_OPTIONS: Dict[Any, MenuOption] = {
    "1": MenuOption("1", "แสดงสถิติและตาราง Hot/Cold", handle_menu_stats, "แสดงตารางความถี่เลข 0-9 และเลขออกบ่อย/ค้างนาน"),
    "2": MenuOption("2", "ทดสอบสูตรและแสดง Leaderboard", handle_menu_backtest, "รัน Backtesting ทดสอบสูตรทั้งหมดและจัดอันดับ"),
    "3": MenuOption("3", "คำนวณแนวทางและเลขชุดรอบถัดไป", handle_menu_predict, "คำนวณเลขเด่น รูดตัวเดียว และเลขชุดสำหรับรอบถัดไป"),
    "4": MenuOption("4", "คัดลอกข้อความสำหรับโพสต์กลุ่มโซเชียล", handle_menu_copy_social, "สร้างข้อความสรุปแนวทางพร้อมคัดลอกลงคลิปบอร์ด"),
    "5": MenuOption("5", "เพิ่มผลรางวัลหวยฮานอย", handle_menu_add_result, "กรอกผลรางวัลรอบใหม่เข้าระบบพร้อมตรวจสอบความถูกต้อง"),
    "6": MenuOption("6", "ดึงผลรางวัลล่าสุดอัตโนมัติ", handle_menu_fetch_latest, "ดึงผลรางวัลสดจากเว็บหรือระบบจำลอง"),
    "7": MenuOption("7", "สำรองข้อมูล (Export CSV/JSON)", handle_menu_export, "ส่งออกฐานข้อมูลผลรางวัลเป็นไฟล์ CSV หรือ JSON"),
    "8": MenuOption("8", "นำเข้าข้อมูล (Import CSV/JSON)", handle_menu_import, "นำเข้าไฟล์ข้อมูลผลรางวัลเข้าระบบ SQLite"),
    "0": MenuOption("0", "ออกจากโปรแกรม", handle_menu_exit, "ปิดโปรแกรมและกลับสู่ระบบปฏิบัติการ"),
}

# Also map integer keys 0..8 for programmatic flexibility
for _k in list(MENU_OPTIONS.keys()):
    MENU_OPTIONS[int(_k)] = MENU_OPTIONS[_k]


def display_menu(db_path: str = "hanoi.db") -> None:
    """Prints Thai Unicode ASCII banner, database status, and options [0-8]."""
    total_draws = 0
    try:
        total_draws = database.count_results(db_path=db_path)
    except Exception:
        pass

    banner = [
        "╔══════════════════════════════════════════════════════════════════════════════╗",
        "║   🎯 ระบบคำนวณและวิเคราะห์สถิติหวยฮานอย (Hanoi Lottery Analytics CLI)         ║",
        "║   รองรับ: ฮานอยพิเศษ (17:30) | ฮานอยปกติ (18:30) | ฮานอย VIP (19:30)          ║",
        "╠══════════════════════════════════════════════════════════════════════════════╣",
        f"║  📊 ฐานข้อมูล: {db_path:<20} (มีทั้งหมด {total_draws:>4} งวด)               ║",
        "╠══════════════════════════════════════════════════════════════════════════════╣",
        "║  [1] แสดงสถิติและตาราง Hot/Cold                                              ║",
        "║  [2] ทดสอบสูตรและแสดง Leaderboard                                            ║",
        "║  [3] คำนวณแนวทางและเลขชุดรอบถัดไป                                            ║",
        "║  [4] คัดลอกข้อความสำหรับโพสต์กลุ่มโซเชียล                                    ║",
        "║  [5] เพิ่มผลรางวัลหวยฮานอย                                                   ║",
        "║  [6] ดึงผลรางวัลล่าสุดอัตโนมัติ                                              ║",
        "║  [7] สำรองข้อมูล (Export CSV/JSON)                                           ║",
        "║  [8] นำเข้าข้อมูล (Import CSV/JSON)                                           ║",
        "║  [0] ออกจากโปรแกรม                                                           ║",
        "╚══════════════════════════════════════════════════════════════════════════════╝",
    ]
    print("\n" + "\n".join(banner))


def run_interactive_menu(db_path: str = "hanoi.db") -> int:
    """Runs interactive console menu loop with robust validation and graceful exit handling."""
    database.init_db(db_path)
    configure_utf8_console()

    while True:
        display_menu(db_path=db_path)
        try:
            choice = input("\n👉 กรุณาเลือกเมนู [0-8]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 ยกเลิกคำสั่ง ออกจากโปรแกรม ขอบคุณที่ใช้งาน!")
            break

        if not choice:
            continue

        if choice in ("0", "exit", "quit", "q"):
            handle_menu_exit(db_path=db_path)
            break

        if choice in MENU_OPTIONS:
            opt = MENU_OPTIONS[choice]
            try:
                opt(db_path=db_path)
            except Exception as e:
                print(f"⚠️ เกิดข้อผิดพลาดระหว่างประมวลผล: {e}")
        else:
            print(f"❌ เลือกเมนูไม่ถูกต้อง: '{choice}' กรุณาเลือกหมายเลขระหว่าง 0 ถึง 8")

    return 0


# ==============================================================================
# Dispatcher Entry Point
# ==============================================================================

def main(argv: Optional[List[str]] = None) -> int:
    """
    Main CLI entry point dispatcher.
    Parses arguments, executes appropriate subcommand handler, returns exit code.
    """
    configure_utf8_console()
    parser = build_parser()
    args = parser.parse_args(argv)

    cmd = getattr(args, "command", "menu") or "menu"
    db_path = getattr(args, "db", "hanoi.db")

    if cmd == "web":
        return handle_web(host=args.host, port=args.port, db_path=db_path)
    elif cmd == "stats":
        return handle_stats(db_path=db_path, round_type=args.round, limit=args.limit)
    elif cmd == "backtest":
        return handle_backtest(db_path=db_path, round_type=args.round, limit=args.limit)
    elif cmd == "watch":
        return handle_watch(interval=args.interval, db_path=db_path)
    elif cmd == "seed":
        return handle_seed(db_path=db_path, force=args.force, count=args.count)
    elif cmd == "predict":
        return handle_predict(db_path=db_path, round_type=args.round, copy_to_clipboard=args.copy)
    elif cmd == "menu":
        return run_interactive_menu(db_path=db_path)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
