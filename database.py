"""
database.py - Database Layer for Hanoi Lottery Statistical Analysis System.
SQLite 3.50.4 / Python 3.14 Compatible.
"""

import csv
import datetime
import json
import os
import random
import re
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union

# Canonical Round Mapping
ROUND_NORMALIZATION_MAP = {
    'special': 'special',
    'hanoi_special': 'special',
    'hanoi-special': 'special',
    'hanoi special': 'special',
    'พิเศษ': 'special',
    'ฮานอยพิเศษ': 'special',
    'normal': 'normal',
    'hanoi_normal': 'normal',
    'hanoi-normal': 'normal',
    'hanoi normal': 'normal',
    'ปกติ': 'normal',
    'ฮานอยปกติ': 'normal',
    'ฮานอย': 'normal',
    'regular': 'normal',
    'vip': 'vip',
    'hanoi_vip': 'vip',
    'hanoi-vip': 'vip',
    'hanoi vip': 'vip',
    'วีไอพี': 'vip',
    'ฮานอย vip': 'vip',
    'ฮานอยvip': 'vip',
    'ฮานอย วีไอพี': 'vip',
    'ฮานอยวีไอพี': 'vip',
}

CANONICAL_ROUNDS = ('special', 'normal', 'vip')

THAI_DIGITS_MAP = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')

SPECIAL_ALIASES = {
    'special', 'hanoi_special', 'hanoi-special', 'hanoi special', 'hanoispecial',
    'พิเศษ', 'ฮานอยพิเศษ', 'ฮานอย พิเศษ', 'ฮานอย-พิเศษ',
}

NORMAL_ALIASES = {
    'normal', 'hanoi_normal', 'hanoi-normal', 'hanoi normal', 'hanoinormal',
    'ปกติ', 'ฮานอยปกติ', 'ฮานอย ปกติ', 'ฮานอย-ปกติ', 'ฮานอย',
    'regular', 'hanoiregular', 'hanoi_regular', 'hanoi regular',
}

VIP_ALIASES = {
    'vip', 'hanoi_vip', 'hanoi-vip', 'hanoi vip', 'hanoivip',
    'วีไอพี', 'ฮานอย vip', 'ฮานอยvip', 'ฮานอย วีไอพี', 'ฮานอยวีไอพี',
    'ฮานอย-vip', 'ฮานอย-วีไอพี',
}

CSV_HEADER_SYNONYMS = {
    'draw_date': ['draw_date', 'date', 'วันที่', 'งวดวันที่', 'งวดประจำวันที่'],
    'round_type': ['round_type', 'round', 'รอบ', 'ประเภท', 'รอบหวย', 'ชื่อรอบ'],
    'special_prize': ['special_prize', 'special', 'รางวัลพิเศษ', 'ผลรางวัล', 'เลขพิเศษ', 'รางวัลที่1', 'รางวัลที่ 1'],
    'top3': ['top3', '3ตัวบน', 'เลขบน3ตัว', '3บน', 'สามตัวบน'],
    'top2': ['top2', '2ตัวบน', 'เลขบน2ตัว', '2บน', 'สองตัวบน'],
    'bottom2': ['bottom2', 'bottom', '2ตัวล่าง', 'เลขล่าง2ตัว', '2ล่าง', 'สองตัวล่าง'],
}


def normalize_round_type(round_type: str) -> str:
    """
    Normalizes Thai and variant round strings into canonical codes ('special', 'normal', 'vip').
    Strict exact alias matching only; loose substring matches are rejected with ValueError.
    """
    if not round_type or not isinstance(round_type, str):
        raise ValueError(f"Invalid round_type: '{round_type}'")

    raw = round_type.strip()
    if not raw:
        raise ValueError("Empty round_type")

    cleaned = re.sub(r'\s+', ' ', raw.lower())
    no_space = cleaned.replace(' ', '')
    no_punct = re.sub(r'[\s_\-]+', '', raw.lower())

    for token in (cleaned, no_space, no_punct):
        if token in SPECIAL_ALIASES or ROUND_NORMALIZATION_MAP.get(token) == 'special':
            return 'special'
        if token in NORMAL_ALIASES or ROUND_NORMALIZATION_MAP.get(token) == 'normal':
            return 'normal'
        if token in VIP_ALIASES or ROUND_NORMALIZATION_MAP.get(token) == 'vip':
            return 'vip'

    raise ValueError(f"Unknown round_type '{round_type}'. Expected one of: {CANONICAL_ROUNDS}")


def derive_top_prizes(
    special_prize: Union[str, int],
    top3: Optional[str] = None,
    top2: Optional[str] = None
) -> Tuple[str, str, str]:
    """
    Auto-derives top3 and top2 from special_prize (last 3 and last 2 digits).
    Preserves zero-padding. Translates Thai digits (๐-๙) to ASCII (0-9).
    """
    sp_raw = str(special_prize).strip()
    sp_str = sp_raw.translate(THAI_DIGITS_MAP)
    if not sp_str.isdigit() or len(sp_str) < 5:
        raise ValueError(f"special_prize must be numeric with at least 5 digits: got '{special_prize}'")

    derived_top3 = sp_str[-3:]
    derived_top2 = sp_str[-2:]
    return sp_str, derived_top3, derived_top2


def normalize_bottom2(bottom2: Union[str, int]) -> str:
    """Normalizes bottom2 to 2-digit zero-padded string. Translates Thai digits to ASCII."""
    b2_raw = str(bottom2).strip()
    b2_str = b2_raw.translate(THAI_DIGITS_MAP)
    if not b2_str.isdigit():
        raise ValueError(f"bottom2 must be numeric: got '{bottom2}'")
    padded = b2_str.zfill(2)
    if len(padded) != 2:
        raise ValueError(f"bottom2 must be exactly 2 digits: got '{bottom2}'")
    return padded


def normalize_date(draw_date: Union[str, datetime.date]) -> str:
    """
    Validates and formats draw_date as YYYY-MM-DD.
    Supports Thai Buddhist Era (years > 2400) by subtracting 543 before Gregorian validation.
    Translates Thai digits (๐-๙) to ASCII (0-9).
    """
    if isinstance(draw_date, datetime.date):
        return draw_date.isoformat()

    raw_str = str(draw_date).strip().translate(THAI_DIGITS_MAP).replace('/', '-')
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', raw_str)
    if not m:
        raise ValueError(f"Invalid draw_date format: '{draw_date}'. Expected YYYY-MM-DD.")

    year = int(m.group(1))
    month = int(m.group(2))
    day = int(m.group(3))

    if year > 2400:
        year -= 543

    d_str = f"{year:04d}-{month:02d}-{day:02d}"

    # Validate that it is a genuine calendar date in Gregorian calendar
    try:
        datetime.datetime.strptime(d_str, '%Y-%m-%d')
    except ValueError as e:
        raise ValueError(f"Invalid calendar date '{draw_date}': {e}")

    return d_str


def get_db_connection(db_path: str = "hanoi.db") -> sqlite3.Connection:
    """
    Returns configured sqlite3.Connection object.
    Uses sqlite3.sqlite_version (Python 3.14 safe).
    """
    if db_path != ":memory:":
        parent_dir = os.path.dirname(os.path.abspath(db_path))
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def db_session(db_path: str = "hanoi.db"):
    """
    Context manager providing transactional scoping and deterministic connection cleanup.
    """
    conn = get_db_connection(db_path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(db_path: str = "hanoi.db") -> None:
    """Initializes the database schema and indexes."""
    with db_session(db_path) as conn:
        if db_path != ":memory:":
            try:
                conn.execute("PRAGMA journal_mode = WAL;")
            except sqlite3.DatabaseError:
                pass

        conn.execute("""
        CREATE TABLE IF NOT EXISTS lottery_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw_date TEXT NOT NULL,
            round_type TEXT NOT NULL,
            special_prize TEXT NOT NULL,
            top3 TEXT NOT NULL,
            top2 TEXT NOT NULL,
            bottom2 TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_date_round UNIQUE (draw_date, round_type)
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lottery_draw_date ON lottery_results(draw_date DESC);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lottery_round_type ON lottery_results(round_type);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lottery_date_round ON lottery_results(draw_date DESC, round_type);")


def insert_result(
    draw_date: str,
    round_type: str,
    special_prize: str,
    bottom2: str,
    top3: Optional[str] = None,
    top2: Optional[str] = None,
    db_path: str = "hanoi.db"
) -> int:
    """
    Inserts a lottery result. Auto-derives top3 and top2 from special_prize.
    Enforces compound unique constraint on (draw_date, round_type).
    Returns the newly inserted row ID.
    """
    norm_date = normalize_date(draw_date)
    norm_round = normalize_round_type(round_type)
    sp, d_top3, d_top2 = derive_top_prizes(special_prize, top3, top2)
    b2 = normalize_bottom2(bottom2)

    with db_session(db_path) as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO lottery_results (draw_date, round_type, special_prize, top3, top2, bottom2)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (norm_date, norm_round, sp, d_top3, d_top2, b2))
        return cur.lastrowid


def get_result_by_id(result_id: int, db_path: str = "hanoi.db") -> Optional[Dict[str, Any]]:
    """Retrieves a single lottery result by its ID."""
    if not isinstance(result_id, int) or result_id > 9223372036854775807 or result_id < -9223372036854775808:
        raise OverflowError("Integer out of bounds")
    with db_session(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM lottery_results WHERE id = ?", (result_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_results(
    round_type: Optional[str] = None,
    limit: Optional[int] = 100,
    offset: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: str = "hanoi.db"
) -> List[Dict[str, Any]]:
    """
    Retrieves a list of lottery results with filtering, pagination, and sorting.
    Sorted in reverse chronological order: draw_date DESC, VIP -> Normal -> Special.
    """
    if (limit is not None and (limit > 9223372036854775807 or limit < -9223372036854775808)) or \
       (offset is not None and (offset > 9223372036854775807 or offset < -9223372036854775808)):
        raise OverflowError("Integer out of bounds")
    with db_session(db_path) as conn:
        cur = conn.cursor()
        query = "SELECT * FROM lottery_results WHERE 1=1"
        params: List[Any] = []

        if round_type:
            query += " AND round_type = ?"
            params.append(normalize_round_type(round_type))

        if start_date:
            query += " AND draw_date >= ?"
            params.append(normalize_date(start_date))

        if end_date:
            query += " AND draw_date <= ?"
            params.append(normalize_date(end_date))

        query += " ORDER BY draw_date DESC, CASE round_type WHEN 'vip' THEN 3 WHEN 'normal' THEN 2 WHEN 'special' THEN 1 ELSE 0 END DESC, id DESC"

        if limit is not None and limit > 0:
            query += " LIMIT ?"
            params.append(limit)
            if offset > 0:
                query += " OFFSET ?"
                params.append(offset)
        elif offset > 0:
            query += " LIMIT -1 OFFSET ?"
            params.append(offset)

        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]


def get_latest_result(round_type: Optional[str] = None, db_path: str = "hanoi.db") -> Optional[Dict[str, Any]]:
    """
    Retrieves the latest draw result overall, or for a specific round.
    """
    with db_session(db_path) as conn:
        cur = conn.cursor()
        if round_type:
            norm_round = normalize_round_type(round_type)
            cur.execute("""
            SELECT * FROM lottery_results 
            WHERE round_type = ? 
            ORDER BY draw_date DESC, id DESC 
            LIMIT 1
            """, (norm_round,))
        else:
            cur.execute("""
            SELECT * FROM lottery_results 
            ORDER BY draw_date DESC, CASE round_type WHEN 'vip' THEN 3 WHEN 'normal' THEN 2 WHEN 'special' THEN 1 ELSE 0 END DESC, id DESC 
            LIMIT 1
            """)
        row = cur.fetchone()
        return dict(row) if row else None


def update_result(result_id: int, db_path: str = "hanoi.db", **kwargs) -> bool:
    """
    Updates an existing lottery result. Auto-recomputes top3 and top2 if special_prize changes.
    Returns True if updated, False if ID not found.
    """
    if not isinstance(result_id, int) or result_id > 9223372036854775807 or result_id < -9223372036854775808:
        raise OverflowError("Integer out of bounds")
    valid_fields = {'draw_date', 'round_type', 'special_prize', 'top3', 'top2', 'bottom2'}
    update_data = {k: v for k, v in kwargs.items() if k in valid_fields}
    if not update_data:
        return False

    if 'draw_date' in update_data:
        update_data['draw_date'] = normalize_date(update_data['draw_date'])

    if 'round_type' in update_data:
        update_data['round_type'] = normalize_round_type(update_data['round_type'])

    if 'special_prize' in update_data:
        sp, d_top3, d_top2 = derive_top_prizes(
            update_data['special_prize'],
            update_data.get('top3'),
            update_data.get('top2')
        )
        update_data['special_prize'] = sp
        if 'top3' not in kwargs:
            update_data['top3'] = d_top3
        if 'top2' not in kwargs:
            update_data['top2'] = d_top2

    if 'bottom2' in update_data:
        update_data['bottom2'] = normalize_bottom2(update_data['bottom2'])

    set_cols = ', '.join([f"{col} = ?" for col in update_data.keys()] + ["updated_at = CURRENT_TIMESTAMP"])
    sql = f"UPDATE lottery_results SET {set_cols} WHERE id = ?"
    values = list(update_data.values()) + [result_id]

    with db_session(db_path) as conn:
        cur = conn.cursor()
        cur.execute(sql, values)
        return cur.rowcount > 0


def delete_result(result_id: int, db_path: str = "hanoi.db") -> bool:
    """
    Deletes a lottery result by ID.
    Returns True if deleted, False if ID not found.
    """
    if not isinstance(result_id, int) or result_id > 9223372036854775807 or result_id < -9223372036854775808:
        raise OverflowError("Integer out of bounds")
    with db_session(db_path) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM lottery_results WHERE id = ?", (result_id,))
        return cur.rowcount > 0


def clear_all_results(db_path: str = "hanoi.db") -> int:
    """
    Deletes all lottery results from database and resets autoincrement sequence.
    Returns total count of deleted rows.
    """
    with db_session(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM lottery_results")
        count = cur.fetchone()[0]
        cur.execute("DELETE FROM lottery_results")
        try:
            cur.execute("DELETE FROM sqlite_sequence WHERE name = 'lottery_results'")
        except Exception:
            pass
        return count


def count_results(round_type: Optional[str] = None, db_path: str = "hanoi.db") -> int:
    """Counts total results, or results matching a specific round."""
    with db_session(db_path) as conn:
        cur = conn.cursor()
        if round_type:
            cur.execute("SELECT COUNT(*) FROM lottery_results WHERE round_type = ?", (normalize_round_type(round_type),))
        else:
            cur.execute("SELECT COUNT(*) FROM lottery_results")
        return cur.fetchone()[0]


def generate_seed_records(
    count_per_round: int = 90,
    end_date: Optional[Union[str, datetime.date]] = None,
    seed_value: int = 42
) -> List[Dict[str, str]]:
    """
    Generates deterministic, realistic Hanoi lottery draw records.
    90 calendar days x 3 rounds = 270 records by default.
    """
    if end_date is None:
        ref_date = datetime.date.today() - datetime.timedelta(days=1)
    elif isinstance(end_date, str):
        ref_date = datetime.date.fromisoformat(end_date)
    else:
        ref_date = end_date

    start_date = ref_date - datetime.timedelta(days=count_per_round - 1)
    rng = random.Random(seed_value)
    rounds = ["special", "normal", "vip"]

    records: List[Dict[str, str]] = []
    for day_offset in range(count_per_round):
        curr_date = start_date + datetime.timedelta(days=day_offset)
        curr_date_str = curr_date.isoformat()

        for r_type in rounds:
            sp_int = rng.randint(0, 99999)
            special_prize = f"{sp_int:05d}"
            top3 = special_prize[-3:]
            top2 = special_prize[-2:]
            bot_int = rng.randint(0, 99)
            bottom2 = f"{bot_int:02d}"

            records.append({
                "draw_date": curr_date_str,
                "round_type": r_type,
                "special_prize": special_prize,
                "top3": top3,
                "top2": top2,
                "bottom2": bottom2,
            })

    return records


def seed_database(
    force: bool = False,
    count_per_round: int = 90,
    db_path: str = "hanoi.db",
    end_date: Optional[Union[str, datetime.date]] = None
) -> int:
    """
    Populate the SQLite database with realistic seed records.
    Idempotent: skips existing (draw_date, round_type) when force=False.
    Overwrites/upserts matching records when force=True.
    Returns number of records inserted/affected.
    """
    init_db(db_path=db_path)
    records = generate_seed_records(count_per_round=count_per_round, end_date=end_date)

    conn = get_db_connection(db_path=db_path)
    total_affected = 0
    try:
        with conn:
            if force:
                sql = """
                    INSERT INTO lottery_results (
                        draw_date, round_type, special_prize, top3, top2, bottom2, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
                    ON CONFLICT(draw_date, round_type) DO UPDATE SET
                        special_prize = excluded.special_prize,
                        top3 = excluded.top3,
                        top2 = excluded.top2,
                        bottom2 = excluded.bottom2,
                        updated_at = excluded.updated_at
                """
            else:
                sql = """
                    INSERT INTO lottery_results (
                        draw_date, round_type, special_prize, top3, top2, bottom2
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(draw_date, round_type) DO NOTHING
                """

            for rec in records:
                cur = conn.execute(sql, (
                    rec["draw_date"],
                    rec["round_type"],
                    rec["special_prize"],
                    rec["top3"],
                    rec["top2"],
                    rec["bottom2"],
                ))
                if cur.rowcount > 0:
                    total_affected += 1
    finally:
        conn.close()

    return total_affected


def export_to_csv(filepath: str, db_path: str = "hanoi.db") -> int:
    """
    Exports all records in lottery_results to a CSV file.
    Always writes the header row.
    Returns the number of data records exported.
    """
    parent_dir = os.path.dirname(os.path.abspath(filepath))
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    records = get_results(limit=None, db_path=db_path)
    # Order: draw_date DESC, VIP -> Normal -> Special
    headers = ["draw_date", "round_type", "special_prize", "top3", "top2", "bottom2"]

    with open(filepath, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for r in records:
            writer.writerow([
                r["draw_date"],
                r["round_type"],
                r["special_prize"],
                r["top3"],
                r["top2"],
                r["bottom2"]
            ])

    return len(records)


def _map_header(raw_header: str) -> Optional[str]:
    """Maps a raw CSV column header to canonical column name using synonym aliases."""
    clean = raw_header.strip().lower()
    for col_key, synonyms in CSV_HEADER_SYNONYMS.items():
        for syn in synonyms:
            if clean == syn.lower():
                return col_key
    return None


def import_from_csv(filepath: str, skip_existing: bool = True, db_path: str = "hanoi.db") -> Dict[str, Any]:
    """
    Imports draw records from a CSV file.
    Supports Thai header aliases, Thai round names, UTF-8 BOM, and error reporting.
    Returns summary dict.
    """
    init_db(db_path=db_path)
    result = {
        "total_rows": 0,
        "imported": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "errors": [],
        "success": True
    }

    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return result

    # Try utf-8-sig first, then cp874 for Windows Thai
    content: Optional[str] = None
    for enc in ("utf-8-sig", "utf-8", "cp874"):
        try:
            with open(filepath, mode="r", encoding=enc) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        result["errors"].append(f"Failed to decode CSV file '{filepath}' with supported encodings.")
        result["success"] = False
        return result

    lines = [line for line in content.splitlines() if line.strip()]
    if not lines:
        return result

    reader = csv.reader(lines)
    try:
        raw_headers = next(reader)
    except StopIteration:
        return result

    col_map: Dict[int, str] = {}
    for idx, h in enumerate(raw_headers):
        canonical = _map_header(h)
        if canonical:
            col_map[idx] = canonical

    # Ensure required columns exist
    required_cols = {"draw_date", "round_type", "special_prize"}
    present_cols = set(col_map.values())
    if not required_cols.issubset(present_cols):
        result["errors"].append(f"CSV missing mandatory columns: {required_cols - present_cols}")
        result["success"] = False
        return result

    rows_to_process = list(reader)
    result["total_rows"] = len(rows_to_process)

    conn = get_db_connection(db_path=db_path)
    try:
        with conn:
            for row_idx, row in enumerate(rows_to_process, start=2):
                if not row or not any(field.strip() for field in row):
                    continue

                row_dict: Dict[str, str] = {}
                for idx, val in enumerate(row):
                    if idx in col_map:
                        row_dict[col_map[idx]] = val.strip()

                try:
                    norm_date = normalize_date(row_dict.get("draw_date", ""))
                    norm_round = normalize_round_type(row_dict.get("round_type", ""))
                    sp_raw = row_dict.get("special_prize", "")
                    t3_raw = row_dict.get("top3")
                    t2_raw = row_dict.get("top2")
                    sp, d_top3, d_top2 = derive_top_prizes(sp_raw, t3_raw, t2_raw)

                    b2_raw = row_dict.get("bottom2")
                    if b2_raw is None or b2_raw == "":
                        b2 = "00"
                    else:
                        b2 = normalize_bottom2(b2_raw)
                except Exception as ex:
                    result["errors"].append(f"Row {row_idx}: {ex}")
                    continue

                # Check existing
                cur = conn.execute(
                    "SELECT id FROM lottery_results WHERE draw_date = ? AND round_type = ?",
                    (norm_date, norm_round)
                )
                existing = cur.fetchone()

                if existing:
                    if skip_existing:
                        result["skipped"] += 1
                    else:
                        conn.execute("""
                        UPDATE lottery_results
                        SET special_prize = ?, top3 = ?, top2 = ?, bottom2 = ?, updated_at = datetime('now', 'localtime')
                        WHERE id = ?
                        """, (sp, d_top3, d_top2, b2, existing["id"]))
                        result["updated"] += 1
                        result["imported"] += 1
                else:
                    conn.execute("""
                    INSERT INTO lottery_results (draw_date, round_type, special_prize, top3, top2, bottom2)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (norm_date, norm_round, sp, d_top3, d_top2, b2))
                    result["inserted"] += 1
                    result["imported"] += 1
    finally:
        conn.close()

    result["success"] = len(result["errors"]) == 0
    return result


def export_to_json(filepath: str, db_path: str = "hanoi.db") -> int:
    """
    Exports all records in lottery_results to a JSON file.
    Writes empty array '[]' if database has no records.
    Returns record count.
    """
    parent_dir = os.path.dirname(os.path.abspath(filepath))
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)

    records = get_results(limit=None, db_path=db_path)
    with open(filepath, mode="w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    return len(records)


def import_from_json(filepath: str, skip_existing: bool = True, db_path: str = "hanoi.db") -> Dict[str, Any]:
    """
    Imports draw records from a JSON file (array of dicts or wrapped dict).
    Returns summary dict.
    """
    init_db(db_path=db_path)
    result = {
        "total_rows": 0,
        "imported": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "errors": [],
        "success": True
    }

    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return result

    try:
        with open(filepath, mode="r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        result["errors"].append(f"Failed to parse JSON file '{filepath}': {e}")
        result["success"] = False
        return result

    if isinstance(data, dict):
        if "results" in data and isinstance(data["results"], list):
            items = data["results"]
        elif "data" in data and isinstance(data["data"], list):
            items = data["data"]
        else:
            items = [data]
    elif isinstance(data, list):
        items = data
    else:
        result["errors"].append(f"Invalid JSON data format in '{filepath}': expected list or dict.")
        result["success"] = False
        return result

    result["total_rows"] = len(items)
    if not items:
        return result

    conn = get_db_connection(db_path=db_path)
    try:
        with conn:
            for idx, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    result["errors"].append(f"Item {idx}: Expected JSON object, got {type(item).__name__}")
                    continue

                try:
                    norm_date = normalize_date(item.get("draw_date", ""))
                    norm_round = normalize_round_type(item.get("round_type", ""))
                    sp_raw = item.get("special_prize", "")
                    t3_raw = item.get("top3")
                    t2_raw = item.get("top2")
                    sp, d_top3, d_top2 = derive_top_prizes(sp_raw, t3_raw, t2_raw)

                    b2_raw = item.get("bottom2")
                    if b2_raw is None or b2_raw == "":
                        b2 = "00"
                    else:
                        b2 = normalize_bottom2(b2_raw)
                except Exception as ex:
                    result["errors"].append(f"Item {idx}: {ex}")
                    continue

                cur = conn.execute(
                    "SELECT id FROM lottery_results WHERE draw_date = ? AND round_type = ?",
                    (norm_date, norm_round)
                )
                existing = cur.fetchone()

                if existing:
                    if skip_existing:
                        result["skipped"] += 1
                    else:
                        conn.execute("""
                        UPDATE lottery_results
                        SET special_prize = ?, top3 = ?, top2 = ?, bottom2 = ?, updated_at = datetime('now', 'localtime')
                        WHERE id = ?
                        """, (sp, d_top3, d_top2, b2, existing["id"]))
                        result["updated"] += 1
                        result["imported"] += 1
                else:
                    conn.execute("""
                    INSERT INTO lottery_results (draw_date, round_type, special_prize, top3, top2, bottom2)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (norm_date, norm_round, sp, d_top3, d_top2, b2))
                    result["inserted"] += 1
                    result["imported"] += 1
    finally:
        conn.close()

    result["success"] = len(result["errors"]) == 0
    return result
