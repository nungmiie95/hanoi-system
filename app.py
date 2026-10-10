"""
app.py - Production Flask Web Application for Hanoi Lottery Statistical Analysis System.
Full Responsive Web Dashboard & REST API Engine.
Python 3.14 / Flask 3.1.3 Compatible.
"""

import csv
import datetime
import io
import json
import os
import sqlite3
import tempfile
from typing import Any, Dict, List, Optional

from flask import (
    Flask,
    Response,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
)
from werkzeug.utils import secure_filename

import backtest
import database
import fetcher
import formulas
import stats

app = Flask(__name__)
app.config.setdefault("DATABASE", "hanoi.db")
app.config.setdefault("JSON_AS_ASCII", False)

if hasattr(app, "json") and hasattr(app.json, "ensure_ascii"):
    app.json.ensure_ascii = False

ROUNDS = ["special", "normal", "vip"]

ROUND_NAMES_THAI = {
    "special": "ฮานอยพิเศษ",
    "normal": "ฮานอยปกติ",
    "vip": "ฮานอย VIP",
}

ROUND_TIMES = {
    "special": "17:30",
    "normal": "18:30",
    "vip": "19:30",
}


def get_db_path() -> str:
    """Dynamically resolves SQLite path from Flask app config for test isolation."""
    try:
        if current_app and hasattr(current_app, "config") and "DATABASE" in current_app.config:
            return current_app.config["DATABASE"]
    except Exception:
        pass
    return app.config.get("DATABASE", "hanoi.db")


def ensure_db_initialized() -> None:
    """Ensures SQLite schema exists."""
    try:
        database.init_db(get_db_path())
    except Exception:
        pass


def get_round_schedule_info(
    target_round: Optional[str] = None,
    ref_time: Optional[datetime.datetime] = None,
) -> Dict[str, Any]:
    """Calculates upcoming Hanoi draw round, scheduled draw time, and countdown seconds."""
    now = ref_time or datetime.datetime.now()
    today = now.date()

    t_special = datetime.datetime.combine(today, datetime.time(17, 30, 0))
    t_normal = datetime.datetime.combine(today, datetime.time(18, 30, 0))
    t_vip = datetime.datetime.combine(today, datetime.time(19, 30, 0))
    t_tomorrow_special = datetime.datetime.combine(
        today + datetime.timedelta(days=1), datetime.time(17, 30, 0)
    )

    if target_round:
        try:
            norm = database.normalize_round_type(target_round)
        except ValueError:
            norm = "special"

        if norm == "special":
            target_dt = t_special if now < t_special else t_tomorrow_special
            target_time = "17:30"
        elif norm == "normal":
            target_dt = t_normal if now < t_normal else datetime.datetime.combine(
                today + datetime.timedelta(days=1), datetime.time(18, 30, 0)
            )
            target_time = "18:30"
        else:
            target_dt = t_vip if now < t_vip else datetime.datetime.combine(
                today + datetime.timedelta(days=1), datetime.time(19, 30, 0)
            )
            target_time = "19:30"
        next_round = norm
    else:
        if now < t_special:
            next_round = "special"
            target_time = "17:30"
            target_dt = t_special
        elif now < t_normal:
            next_round = "normal"
            target_time = "18:30"
            target_dt = t_normal
        elif now < t_vip:
            next_round = "vip"
            target_time = "19:30"
            target_dt = t_vip
        else:
            next_round = "special"
            target_time = "17:30"
            target_dt = t_tomorrow_special

    seconds_left = max(0, int((target_dt - now).total_seconds()))

    return {
        "next_round": next_round,
        "target_time": target_time,
        "seconds_left": seconds_left,
        "time": target_time,
        "round_name": ROUND_NAMES_THAI.get(next_round, next_round),
    }


@app.after_request
def add_charset_header(response):
    """Ensures UTF-8 charset is present in text responses to prevent mojibake."""
    if response.mimetype == "text/html":
        response.headers["Content-Type"] = "text/html; charset=utf-8"
    elif response.mimetype == "text/csv":
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return response


# ------------------------------------------------------------------------------
# HTML VIEWS
# ------------------------------------------------------------------------------

@app.route("/")
def index():
    """Renders main dashboard homepage."""
    ensure_db_initialized()
    db_p = get_db_path()
    sp = database.get_latest_result("special", db_path=db_p)
    no = database.get_latest_result("normal", db_path=db_p)
    vp = database.get_latest_result("vip", db_path=db_p)
    cd = get_round_schedule_info()

    history = database.get_results(limit=100, db_path=db_p)
    top = backtest.get_top_formula(history, target_round=cd["next_round"]) if history else None

    sets, copy_txt = {}, ""
    if top and history:
        f_obj = next((f for f in formulas.ALL_FORMULAS if f.id == top["formula_id"]), None)
        if f_obj:
            pred = f_obj.predict(history, cd["next_round"])
            sets = formulas.generate_deliverable_sets(pred, history)
            copy_txt = formulas.format_copy_text(
                cd["round_name"], datetime.date.today().isoformat(), top["formula_name"], top["win_rate"], sets
            )

    return render_template(
        "index.html",
        active_page="index",
        latest_special=sp,
        latest_normal=no,
        latest_vip=vp,
        countdown=cd,
        next_round_info=cd,
        top_formula=top,
        sets=sets,
        top_sets=sets,
        copy_text=copy_txt,
        copy_text_formatted=copy_txt,
    )


@app.route("/stats")
def stats_view():
    """Renders statistics & Hot/Cold analytics view."""
    ensure_db_initialized()
    db_p = get_db_path()
    round_param = request.args.get("round") or request.args.get("round_type")
    limit = max(1, request.args.get("limit", 100, type=int))

    norm_round = None
    if round_param and round_param.lower() != "all":
        try:
            norm_round = database.normalize_round_type(round_param)
        except ValueError:
            norm_round = None

    results = database.get_results(round_type=norm_round, limit=limit, db_path=db_p)
    freq = stats.calculate_digit_frequencies(results)
    hc = stats.calculate_hot_cold(results, limit=10)
    metrics = stats.calculate_summary_metrics(results)

    return render_template(
        "stats.html",
        active_page="stats",
        results=results,
        frequencies=freq,
        stats=freq,
        hot_cold=hc,
        metrics=metrics,
        round_type=norm_round or "all",
        selected_round=norm_round or "all",
        limit=limit,
        total_draws=freq.get("total_draws", len(results)),
    )


@app.route("/leaderboard")
def leaderboard_view():
    """Renders formula backtest leaderboard."""
    ensure_db_initialized()
    db_p = get_db_path()
    round_param = request.args.get("round") or request.args.get("round_type")
    num_eval = max(10, request.args.get("num_eval", request.args.get("eval", 50, type=int), type=int))

    norm_round = None
    if round_param and round_param.lower() != "all":
        try:
            norm_round = database.normalize_round_type(round_param)
        except ValueError:
            norm_round = None

    results = database.get_results(limit=500, db_path=db_p)
    lb = backtest.run_backtest(results, target_round=norm_round, num_eval=num_eval)
    top = lb[0] if lb else None

    return render_template(
        "leaderboard.html",
        active_page="leaderboard",
        leaderboard=lb,
        top_formula=top,
        round_type=norm_round or "all",
        target_round=norm_round or "all",
        num_eval=num_eval,
    )


@app.route("/recommend")
def recommend_view():
    """Renders deliverable sets recommendation & copy text view."""
    ensure_db_initialized()
    db_p = get_db_path()
    round_param = request.args.get("round") or request.args.get("round_type") or request.args.get("target_round")
    cd = get_round_schedule_info()

    target_round = cd["next_round"]
    if round_param and round_param.lower() != "all":
        try:
            target_round = database.normalize_round_type(round_param)
        except ValueError:
            pass

    results = database.get_results(limit=100, db_path=db_p)
    top = backtest.get_top_formula(results, target_round=target_round) if results else None

    sets, copy_txt = {}, ""
    if top and results:
        f_obj = next((f for f in formulas.ALL_FORMULAS if f.id == top["formula_id"]), None)
        if f_obj:
            pred = f_obj.predict(results, target_round)
            sets = formulas.generate_deliverable_sets(pred, results)
            copy_txt = formulas.format_copy_text(
                ROUND_NAMES_THAI.get(target_round, target_round),
                datetime.date.today().isoformat(),
                top["formula_name"],
                top["win_rate"],
                sets,
            )

    return render_template(
        "recommend.html",
        active_page="recommend",
        top_formula=top,
        sets=sets,
        copy_text=copy_txt,
        formatted_copy_text=copy_txt,
        target_round=target_round,
        round_name=ROUND_NAMES_THAI.get(target_round, target_round),
        round_name_thai=ROUND_NAMES_THAI.get(target_round, target_round),
        draw_date=datetime.date.today().isoformat(),
    )


@app.route("/manage")
def manage_view():
    """Renders historical data management CRUD table."""
    ensure_db_initialized()
    db_p = get_db_path()
    round_param = request.args.get("round") or request.args.get("round_type")
    page = max(1, request.args.get("page", 1, type=int))
    per_page = max(1, request.args.get("per_page", 50, type=int))

    norm_round = None
    if round_param and round_param.lower() != "all":
        try:
            norm_round = database.normalize_round_type(round_param)
        except ValueError:
            norm_round = None

    offset = (page - 1) * per_page
    results = database.get_results(round_type=norm_round, limit=per_page, offset=offset, db_path=db_p)
    total_count = database.count_results(round_type=norm_round, db_path=db_p)
    total_pages = max(1, (total_count + per_page - 1) // per_page)

    return render_template(
        "manage.html",
        active_page="manage",
        results=results,
        page=page,
        per_page=per_page,
        total_count=total_count,
        total_pages=total_pages,
        round_type=norm_round or "all",
        selected_round=norm_round or "all",
    )


# ------------------------------------------------------------------------------
# REST API ENDPOINTS
# ------------------------------------------------------------------------------

@app.route("/api/countdown", methods=["GET"])
def api_countdown():
    """Returns dynamic countdown to upcoming draw round."""
    target_round = request.args.get("round") or request.args.get("target_round")
    info = get_round_schedule_info(target_round)
    return jsonify(info)


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """Returns digit frequencies (0-9) and Hot/Cold tables."""
    ensure_db_initialized()
    db_p = get_db_path()
    round_param = request.args.get("round") or request.args.get("round_type")
    limit_val = request.args.get("limit", 100, type=int)
    limit = max(1, limit_val) if limit_val is not None else 100
    hc_val = request.args.get("hot_cold_limit", 5, type=int)
    hot_cold_limit = max(1, hc_val) if hc_val is not None else 5
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    norm_round = None
    if round_param and round_param.lower() != "all":
        try:
            norm_round = database.normalize_round_type(round_param)
        except ValueError:
            norm_round = None

    try:
        if (limit is not None and (limit > 9223372036854775807 or limit < -9223372036854775808)) or \
           (hot_cold_limit is not None and (hot_cold_limit > 9223372036854775807 or hot_cold_limit < -9223372036854775808)):
            raise OverflowError("Integer out of bounds")
        results = database.get_results(
            round_type=norm_round, limit=limit, start_date=start_date, end_date=end_date, db_path=db_p
        )
    except OverflowError:
        return jsonify({"error": "Integer out of bounds"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    freq = stats.calculate_digit_frequencies(results)
    hc = stats.calculate_hot_cold(results, limit=hot_cold_limit)

    return jsonify({
        "top_digits": {str(d): int(freq["top_digits"][d]) for d in range(10)},
        "bottom_digits": {str(d): int(freq["bottom_digits"][d]) for d in range(10)},
        "top_percentages": {str(d): float(freq.get("top_percentages", {}).get(d, 0.0)) for d in range(10)},
        "bottom_percentages": {str(d): float(freq.get("bottom_percentages", {}).get(d, 0.0)) for d in range(10)},
        "hot_top2": hc.get("hot_top2", []),
        "cold_top2": hc.get("cold_top2", []),
        "hot_bottom2": hc.get("hot_bottom2", []),
        "cold_bottom2": hc.get("cold_bottom2", []),
        "total_draws": freq.get("total_draws", len(results)),
    })


@app.route("/api/leaderboard", methods=["GET"])
def api_leaderboard():
    """Returns formula leaderboard ranking."""
    ensure_db_initialized()
    db_p = get_db_path()
    round_param = request.args.get("round") or request.args.get("round_type") or request.args.get("target_round")
    num_eval = max(10, request.args.get("num_eval", 50, type=int))
    limit = max(1, request.args.get("limit", 50, type=int))

    norm_round = None
    if round_param and round_param.lower() != "all":
        try:
            norm_round = database.normalize_round_type(round_param)
        except ValueError:
            norm_round = None

    results = database.get_results(limit=500, db_path=db_p)
    lb = backtest.run_backtest(results, target_round=norm_round, num_eval=num_eval)
    return jsonify(lb[:limit])


@app.route("/api/recommendations", methods=["GET"])
def api_recommendations():
    """Returns formula predictions and all deliverable sets."""
    ensure_db_initialized()
    db_p = get_db_path()
    round_param = request.args.get("round") or request.args.get("round_type") or request.args.get("target_round")
    cd = get_round_schedule_info()

    target_round = cd["next_round"]
    if round_param and round_param.lower() != "all":
        try:
            target_round = database.normalize_round_type(round_param)
        except ValueError:
            pass

    results = database.get_results(limit=100, db_path=db_p)
    top = backtest.get_top_formula(results, target_round=target_round) if results else None

    if top and results:
        f_obj = next((f for f in formulas.ALL_FORMULAS if f.id == top["formula_id"]), None)
        if f_obj:
            pred = f_obj.predict(results, target_round)
            sets = formulas.generate_deliverable_sets(pred, results)
            return jsonify({
                "next_round": target_round,
                "formula": top,
                "sets": {
                    "single_swipe": sets["single_swipe"],
                    "swipe_numbers": sets["swipe_numbers"],
                    "both_sets": sets["both_sets"],
                    "top_sets": sets["top_sets"],
                    "bottom_sets": sets["bottom_sets"],
                    "fight_sets": sets["fight_sets"],
                },
            })

    # Graceful default when DB is empty
    return jsonify({
        "next_round": target_round,
        "formula": {},
        "sets": {
            "single_swipe": "0",
            "swipe_numbers": [],
            "both_sets": {"10": [], "20": [], "30": [], "40": [], "50": []},
            "top_sets": {"10": [], "20": [], "30": [], "40": [], "50": []},
            "bottom_sets": {"10": [], "20": [], "30": [], "40": [], "50": []},
            "fight_sets": {"10": [], "20": [], "25": [], "40": []},
        },
    })


@app.route("/api/results", methods=["GET"])
def api_get_results():
    """Queries draw results with pagination and filtering."""
    ensure_db_initialized()
    db_p = get_db_path()
    round_param = request.args.get("round") or request.args.get("round_type")
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    limit = max(1, limit) if limit is not None else 100
    offset = max(0, offset) if offset is not None else 0
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    norm_round = None
    if round_param and round_param.lower() != "all":
        try:
            norm_round = database.normalize_round_type(round_param)
        except ValueError:
            norm_round = None

    try:
        if (limit is not None and (limit > 9223372036854775807 or limit < -9223372036854775808)) or \
           (offset is not None and (offset > 9223372036854775807 or offset < -9223372036854775808)):
            raise OverflowError("Integer out of bounds")
        results = database.get_results(
            round_type=norm_round, limit=limit, offset=offset, start_date=start_date, end_date=end_date, db_path=db_p
        )
    except OverflowError:
        return jsonify({"error": "Integer out of bounds"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(results)


@app.route("/api/results/<int:result_id>", methods=["GET"])
def api_get_result_by_id(result_id: int):
    """Retrieves single draw record by ID."""
    ensure_db_initialized()
    db_p = get_db_path()
    try:
        if result_id > 9223372036854775807 or result_id < -9223372036854775808:
            raise OverflowError("Integer out of bounds")
        record = database.get_result_by_id(result_id, db_path=db_p)
    except OverflowError:
        return jsonify({"error": "Integer out of bounds"}), 400
    if not record:
        return jsonify({"error": "Record not found"}), 404
    return jsonify(record)


api_get_result = api_get_result_by_id


@app.route("/api/results", methods=["POST"])
def api_post_result():
    """Creates a new draw record with validation and conflict detection."""
    ensure_db_initialized()
    db_p = get_db_path()

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    draw_date = data.get("draw_date")
    round_type = data.get("round_type")
    special_prize = data.get("special_prize")
    bottom2 = data.get("bottom2")

    if not draw_date:
        return jsonify({"error": "draw_date is required"}), 400
    if not round_type:
        return jsonify({"error": "round_type is required"}), 400
    if special_prize is None or special_prize == "":
        return jsonify({"error": "special_prize is required"}), 400
    if bottom2 is None or bottom2 == "":
        return jsonify({"error": "bottom2 is required"}), 400

    try:
        norm_date = database.normalize_date(draw_date)
    except Exception as e:
        return jsonify({"error": f"Invalid date: {e}"}), 400

    try:
        norm_round = database.normalize_round_type(round_type)
    except Exception as e:
        return jsonify({"error": f"Invalid round_type: {e}"}), 400

    try:
        sp_str, top3, top2 = database.derive_top_prizes(special_prize)
        b2_str = database.normalize_bottom2(bottom2)
    except Exception as e:
        if isinstance(special_prize, (str, int)) and str(special_prize).strip().isdigit() and 3 <= len(str(special_prize).strip()) < 5:
            try:
                sp_str, top3, top2 = database.derive_top_prizes(str(special_prize).strip().zfill(5))
                b2_str = database.normalize_bottom2(bottom2)
            except Exception as e2:
                return jsonify({"error": str(e2)}), 400
        else:
            return jsonify({"error": str(e)}), 400

    try:
        res_id = database.insert_result(
            draw_date=norm_date,
            round_type=norm_round,
            special_prize=sp_str,
            bottom2=b2_str,
            top3=top3,
            top2=top2,
            db_path=db_p,
        )
        return jsonify({"success": True, "id": res_id}), 201
    except sqlite3.IntegrityError as e:
        return jsonify({"error": "Duplicate entry for date and round", "message": str(e)}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/results/<int:result_id>", methods=["PUT"])
def api_put_result(result_id: int):
    """Updates an existing draw record."""
    ensure_db_initialized()
    db_p = get_db_path()

    try:
        if result_id > 9223372036854775807 or result_id < -9223372036854775808:
            raise OverflowError("Integer out of bounds")
        existing = database.get_result_by_id(result_id, db_path=db_p)
    except OverflowError:
        return jsonify({"error": "Integer out of bounds"}), 400

    if not existing:
        return jsonify({"error": "Record not found"}), 404

    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    update_kwargs = {}
    for field in ["draw_date", "round_type", "special_prize", "bottom2"]:
        if field in data:
            update_kwargs[field] = str(data[field])

    if "special_prize" in update_kwargs:
        try:
            sp, t3, t2 = database.derive_top_prizes(update_kwargs["special_prize"])
            update_kwargs["special_prize"] = sp
            update_kwargs["top3"] = t3
            update_kwargs["top2"] = t2
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    if "bottom2" in update_kwargs:
        try:
            update_kwargs["bottom2"] = database.normalize_bottom2(update_kwargs["bottom2"])
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    if "round_type" in update_kwargs:
        try:
            update_kwargs["round_type"] = database.normalize_round_type(update_kwargs["round_type"])
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    if "draw_date" in update_kwargs:
        try:
            update_kwargs["draw_date"] = database.normalize_date(update_kwargs["draw_date"])
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    try:
        success = database.update_result(result_id, db_path=db_p, **update_kwargs)
        return jsonify({"success": success})
    except OverflowError:
        return jsonify({"error": "Integer out of bounds"}), 400
    except sqlite3.IntegrityError:
        return jsonify({"error": "Conflict with existing record"}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/results/<int:result_id>", methods=["DELETE"])
def api_delete_result(result_id: int):
    """Deletes an existing draw record."""
    ensure_db_initialized()
    db_p = get_db_path()

    try:
        if result_id > 9223372036854775807 or result_id < -9223372036854775808:
            raise OverflowError("Integer out of bounds")
        existing = database.get_result_by_id(result_id, db_path=db_p)
    except OverflowError:
        return jsonify({"error": "Integer out of bounds"}), 400

    if not existing:
        return jsonify({"error": "Record not found"}), 404

    try:
        success = database.delete_result(result_id, db_path=db_p)
        return jsonify({"success": success})
    except OverflowError:
        return jsonify({"error": "Integer out of bounds"}), 400


@app.route("/api/fetch", methods=["POST"])
def api_fetch():
    """Triggers live scraper or mock simulator and auto-saves to database."""
    ensure_db_initialized()
    db_p = get_db_path()

    data = request.get_json(silent=True) or {}
    round_param = data.get("round_type") or data.get("round")
    fallback_mock = data.get("mock", False) or data.get("fallback_mock", False)

    try:
        scraped = fetcher.fetch_latest_results(
            round_type=round_param, fallback_mock=fallback_mock, db_path=db_p
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if scraped and scraped.get("special_prize"):
        try:
            database.insert_result(
                draw_date=scraped["draw_date"],
                round_type=scraped["round_type"],
                special_prize=scraped["special_prize"],
                bottom2=scraped["bottom2"],
                top3=scraped.get("top3"),
                top2=scraped.get("top2"),
                db_path=db_p,
            )
            scraped["saved"] = True
        except sqlite3.IntegrityError:
            scraped["saved"] = False
            scraped["note"] = "Record already exists"
        except Exception:
            scraped["saved"] = False

    return jsonify({"success": True, "data": scraped})


@app.route("/api/export/csv", methods=["GET"])
def api_export_csv():
    """Downloads database records as CSV stream."""
    ensure_db_initialized()
    db_p = get_db_path()

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    temp_path = temp_file.name
    temp_file.close()

    try:
        database.export_to_csv(temp_path, db_path=db_p)
        with open(temp_path, "r", encoding="utf-8") as f:
            csv_content = f.read()
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=hanoi_results.csv"},
    )


@app.route("/api/export/json", methods=["GET"])
def api_export_json():
    """Downloads database records as JSON stream."""
    ensure_db_initialized()
    db_p = get_db_path()

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    temp_path = temp_file.name
    temp_file.close()

    try:
        database.export_to_json(temp_path, db_path=db_p)
        with open(temp_path, "r", encoding="utf-8") as f:
            json_content = f.read()
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return Response(
        json_content,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=hanoi_results.json"},
    )


@app.route("/api/import/csv", methods=["POST"])
def api_import_csv():
    """Uploads and imports CSV records."""
    ensure_db_initialized()
    db_p = get_db_path()

    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    uploaded = request.files["file"]
    if not uploaded or uploaded.filename == "":
        return jsonify({"error": "No file selected"}), 400

    skip_existing = request.form.get("skip_existing", "true").lower() in ("true", "1", "yes")

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    temp_path = temp_file.name
    uploaded.save(temp_path)
    temp_file.close()

    try:
        if os.path.getsize(temp_path) == 0:
            return jsonify({"error": "Uploaded CSV file is empty"}), 400
        summary = database.import_from_csv(temp_path, skip_existing=skip_existing, db_path=db_p)
        if not summary.get("success", False) or summary.get("errors"):
            return jsonify({
                "error": "CSV import failed",
                "errors": summary.get("errors", []),
            }), 400
        return jsonify({
            "success": True,
            "imported": summary.get("imported", 0),
            "skipped": summary.get("skipped", 0),
            "errors": 0,
            "summary": summary,
        })
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.route("/api/import/json", methods=["POST"])
def api_import_json():
    """Uploads and imports JSON records."""
    ensure_db_initialized()
    db_p = get_db_path()

    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    uploaded = request.files["file"]
    if not uploaded or uploaded.filename == "":
        return jsonify({"error": "No file selected"}), 400

    skip_existing = request.form.get("skip_existing", "true").lower() in ("true", "1", "yes")

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
    temp_path = temp_file.name
    uploaded.save(temp_path)
    temp_file.close()

    try:
        if os.path.getsize(temp_path) == 0:
            return jsonify({"error": "Uploaded JSON file is empty"}), 400
        summary = database.import_from_json(temp_path, skip_existing=skip_existing, db_path=db_p)
        if not summary.get("success", False) or summary.get("errors"):
            return jsonify({
                "error": "JSON import failed",
                "errors": summary.get("errors", []),
            }), 400
        return jsonify({
            "success": True,
            "imported": summary.get("imported", 0),
            "skipped": summary.get("skipped", 0),
            "errors": 0,
            "summary": summary,
        })
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.route("/api/copy-text", methods=["GET"])
def api_copy_text():
    """Generates formatted social sharing text."""
    ensure_db_initialized()
    db_p = get_db_path()
    round_param = request.args.get("round") or request.args.get("round_type") or request.args.get("target_round")
    draw_date = request.args.get("draw_date") or datetime.date.today().isoformat()
    cd = get_round_schedule_info()

    target_round = cd["next_round"]
    if round_param and round_param.lower() != "all":
        try:
            target_round = database.normalize_round_type(round_param)
        except ValueError:
            pass

    results = database.get_results(limit=100, db_path=db_p)
    top = backtest.get_top_formula(results, target_round=target_round) if results else None

    if top and results:
        f_obj = next((f for f in formulas.ALL_FORMULAS if f.id == top["formula_id"]), None)
        if f_obj:
            pred = f_obj.predict(results, target_round)
            sets = formulas.generate_deliverable_sets(pred, results)
            text = formulas.format_copy_text(
                ROUND_NAMES_THAI.get(target_round, target_round),
                draw_date,
                top["formula_name"],
                top["win_rate"],
                sets,
            )
            return jsonify({
                "success": True,
                "round_type": target_round,
                "draw_date": draw_date,
                "text": text,
            })

    # Graceful fallback text
    dummy_sets = {
        "single_swipe": "-",
        "swipe_numbers": [],
        "both_sets": {"10": [], "20": [], "30": [], "40": [], "50": []},
        "top_sets": {"10": [], "20": [], "30": [], "40": [], "50": []},
        "bottom_sets": {"10": [], "20": [], "30": [], "40": [], "50": []},
        "fight_sets": {"10": [], "20": [], "25": [], "40": []},
    }
    text = formulas.format_copy_text(
        ROUND_NAMES_THAI.get(target_round, target_round), draw_date, "ระบบคำนวณอัตโนมัติ", 0.0, dummy_sets
    )
    return jsonify({"success": True, "round_type": target_round, "draw_date": draw_date, "text": text})


if __name__ == "__main__":
    ensure_db_initialized()
    app.run(host="0.0.0.0", port=5000, debug=True)
