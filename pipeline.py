"""
pipeline.py - Real-Time Auto-Adaptive Pipeline & Background Scheduler for Hanoi Lottery System.
Coordinates scheduled polling, SQLite deduplication, automated backtest optimization,
and circular cross-round signal cascading across Hanoi Special, Normal, and VIP rounds.
Python 3.14 AMD64 / Windows 11 Compatible.
"""

import datetime
import logging
import sqlite3
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import backtest
import database
import fetcher
import formulas

logger = logging.getLogger("hanoi.pipeline")

DRAW_SCHEDULE = {
    "special": "17:30",
    "normal": "18:30",
    "vip": "19:30",
}
ROUND_SCHEDULE = DRAW_SCHEDULE

ROUND_SEQUENCE = ["special", "normal", "vip"]
ROUNDS = ["special", "normal", "vip"]

CASCADE_CHAIN = {
    "special": "normal",
    "normal": "vip",
    "vip": "special",
}

NEXT_ROUND_MAP = {
    "special": "normal",
    "normal": "vip",
    "vip": "special",
}

ROUND_NAMES_THAI = {
    "special": "ฮานอยพิเศษ",
    "normal": "ฮานอยปกติ",
    "vip": "ฮานอย VIP",
}

ROUND_SCHEDULE_TIMES = {
    "special": "17:30",
    "normal": "18:30",
    "vip": "19:30",
}


def calculate_next_scheduled_round(
    reference_time: Optional[Union[datetime.time, datetime.datetime]] = None
) -> Tuple[str, str, int]:
    """
    Calculates upcoming Hanoi draw round, scheduled time, and seconds left.
    Accepts reference_time as None, datetime.datetime, or datetime.time.
    Returns (round_type, time_str, seconds_remaining).
    """
    if reference_time is None:
        now = datetime.datetime.now()
    elif isinstance(reference_time, datetime.datetime):
        now = reference_time
    elif isinstance(reference_time, datetime.time):
        now = datetime.datetime.combine(datetime.date.today(), reference_time)
    else:
        now = datetime.datetime.now()

    today = now.date()
    t_special = datetime.datetime.combine(today, datetime.time(17, 30, 0))
    t_normal = datetime.datetime.combine(today, datetime.time(18, 30, 0))
    t_vip = datetime.datetime.combine(today, datetime.time(19, 30, 0))
    t_tomorrow_special = datetime.datetime.combine(
        today + datetime.timedelta(days=1), datetime.time(17, 30, 0)
    )

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
    return next_round, target_time, seconds_left


def get_next_round_info(
    reference_time: Optional[Union[datetime.time, datetime.datetime]] = None
) -> Dict[str, Any]:
    """
    Standalone function returning next round information dictionary.
    Keys: next_round, time, target_time, seconds_left, round_name.
    """
    r_type, t_str, sec_left = calculate_next_scheduled_round(reference_time=reference_time)
    return {
        "next_round": r_type,
        "time": t_str,
        "target_time": t_str,
        "seconds_left": sec_left,
        "round_name": ROUND_NAMES_THAI.get(r_type, r_type),
    }


class HanoiPipeline:
    """
    Real-time Auto-Adaptive Pipeline & Background Scheduler for Hanoi Lottery System.
    Provides zero-crash polling, SQLite deduplication, automated backtest optimization,
    cross-round signal cascading, and structured event dispatching.
    """

    def __init__(
        self,
        db_path: str = "hanoi.db",
        poll_interval: int = 30,
        on_new_result: Optional[Callable[..., Any]] = None,
        auto_init_db: bool = True,
        logger_instance: Optional[logging.Logger] = None,
        fetch_timeout: float = 5.0,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.on_new_result = on_new_result
        self.fetch_timeout = fetch_timeout
        self._logger = logger_instance or logger or logging.getLogger("hanoi.pipeline")

        # Public monitoring state attributes
        self.last_poll_time: Optional[str] = None
        self.last_error: Optional[str] = None
        self.last_retest_time: Optional[str] = None

        # Thread synchronization primitives
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # Cached in-memory leaderboards and recommendations
        self.cached_rankings: Dict[str, List[Dict[str, Any]]] = {}
        self.cached_top_formulas: Dict[str, Dict[str, Any]] = {}
        self.cached_recommendations: Dict[str, Dict[str, Any]] = {}
        self._top_formulas: Dict[str, Dict[str, Any]] = self.cached_top_formulas
        self._recommendations: Dict[str, Dict[str, Any]] = self.cached_recommendations

        # Counters & latest metrics
        self._total_polls: int = 0
        self._total_new_results: int = 0
        self._consecutive_errors: int = 0
        self._last_result: Optional[Dict[str, Any]] = None

        # Event callbacks registry
        self._callbacks: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {
            "on_draw_detected": [],
            "on_draw_saved": [],
            "on_retest_completed": [],
            "on_cascade": [],
            "on_step": [],
            "on_error": [],
        }

        # Initialize SQLite database if requested
        if auto_init_db:
            try:
                database.init_db(self.db_path)
            except Exception as e:
                self._logger.warning(f"[HanoiPipeline] DB init warning: {e}")

        # Lightweight warmup: populate cached formulas if database already has historical data
        try:
            self.retest(num_eval=50)
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # Lifecycle Management
    # --------------------------------------------------------------------------

    def start(self) -> None:
        """Starts background worker daemon thread idempotently."""
        with self._lock:
            if self.is_running():
                return
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="HanoiPipelineWorker",
                daemon=True,
            )
            self._thread = self._worker_thread
            self._worker_thread.start()

    def stop(self, timeout: Optional[float] = None) -> None:
        """
        Signals background worker thread to stop.
        If timeout is specified and thread is alive, blocks waiting for termination.
        """
        self._stop_event.set()
        if timeout is not None and self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)

    def is_running(self) -> bool:
        """Checks if background worker thread is currently active."""
        return bool(
            self._worker_thread is not None
            and self._worker_thread.is_alive()
            and not self._stop_event.is_set()
        )

    def join(self, timeout: Optional[float] = None) -> None:
        """Waits for background worker thread to terminate."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)

    def run_watcher(
        self,
        interval_sec: Optional[int] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Synchronous watcher loop used by CLI and test harnesses.
        Exits immediately if stop_event is pre-set or set during sleep.
        """
        database.init_db(self.db_path)
        effective_stop = stop_event if stop_event is not None else self._stop_event
        effective_interval = interval_sec if interval_sec is not None else self.poll_interval

        if effective_stop.is_set():
            return

        while not effective_stop.is_set():
            try:
                self.step_check(force_trigger=False)
            except Exception as err:
                self.last_error = str(err)
                self._dispatch_event("on_error", {
                    "source": "run_watcher",
                    "error": str(err),
                    "timestamp": datetime.datetime.now().isoformat(),
                })

            if effective_stop.wait(timeout=max(0.01, effective_interval)):
                break

    # --------------------------------------------------------------------------
    # Schedule & Status Introspection
    # --------------------------------------------------------------------------

    def get_next_scheduled_round(
        self,
        reference_time: Optional[Union[datetime.time, datetime.datetime]] = None,
    ) -> Tuple[str, str, int]:
        """Calculates upcoming round, time string, and seconds left."""
        return calculate_next_scheduled_round(reference_time=reference_time)

    def get_next_round_info(
        self,
        reference_time: Optional[Union[datetime.time, datetime.datetime]] = None,
    ) -> Dict[str, Any]:
        """Returns dictionary of next round schedule information."""
        return get_next_round_info(reference_time=reference_time)

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive runtime snapshot of pipeline status, schedule, and rankings."""
        with self._lock:
            sched = self.get_next_round_info()
            return {
                "is_running": self.is_running(),
                "db_path": self.db_path,
                "poll_interval": self.poll_interval,
                "last_poll_time": self.last_poll_time,
                "last_check_time": self.last_poll_time,
                "last_error": self.last_error,
                "last_retest_time": self.last_retest_time,
                "next_round_info": sched,
                "next_round": sched["next_round"],
                "next_time": sched["time"],
                "seconds_left": sched["seconds_left"],
                "round_name": sched["round_name"],
                "total_polls": self._total_polls,
                "total_new_results": self._total_new_results,
                "consecutive_errors": self._consecutive_errors,
                "latest_result": self._last_result,
                "top_formulas": self.cached_top_formulas,
                "cached_rankings": self.cached_rankings,
                "cached_recommendations": self.cached_recommendations,
                "active_formula_count": len(getattr(formulas, "ALL_FORMULAS", [])),
            }

    # --------------------------------------------------------------------------
    # Single-Step & Polling Execution
    # --------------------------------------------------------------------------

    def step_check(
        self,
        force_trigger: bool = False,
        round_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Executes a single polling and processing step.
        Guaranteed zero-crash exception containment.
        """
        with self._lock:
            self.last_poll_time = datetime.datetime.now().isoformat()
            self._total_polls += 1

            if not force_trigger:
                info = self.get_next_round_info()
                # If draw is more than 5 minutes away, remain idle
                if info["seconds_left"] > 300:
                    return None

                target_round = info["next_round"]
                fetched = self._fetch_safe(target_round)
                if not fetched or not fetched.get("special_prize"):
                    return None

                # Check SQLite deduplication
                d_date = fetched["draw_date"]
                r_type = fetched["round_type"]
                if self._is_draw_in_database(d_date, r_type):
                    return None

                return self._process_draw_cycle(fetched, is_forced=False)

            # force_trigger is True
            target_round = self._resolve_target_round(
                force_trigger=True, explicit_round=round_type
            )
            fetched = self._fetch_safe(target_round)
            if not fetched:
                return None

            d_date = fetched["draw_date"]
            r_type = fetched["round_type"]

            # Deduplication check in SQLite
            if self._is_draw_in_database(d_date, r_type):
                return {
                    "status": "duplicate",
                    "is_new": False,
                    "round_type": r_type,
                    "draw_date": d_date,
                    "special_prize": fetched.get("special_prize"),
                    "top3": fetched.get("top3"),
                    "top2": fetched.get("top2"),
                    "bottom2": fetched.get("bottom2"),
                    "source": fetched.get("source"),
                }

            return self._process_draw_cycle(fetched, is_forced=True)

    def step(
        self,
        force_trigger: bool = False,
        round_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Alias for step_check()."""
        return self.step_check(force_trigger=force_trigger, round_type=round_type)

    def poll_once(
        self,
        force_trigger: bool = False,
        round_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Alias for step_check()."""
        return self.step_check(force_trigger=force_trigger, round_type=round_type)

    def _process_draw_cycle(
        self, fetched: Dict[str, Any], is_forced: bool
    ) -> Dict[str, Any]:
        """
        Internal worker saving verified draw to SQLite, executing auto-retest,
        cascading statistical signals to next round, and firing event callbacks.
        """
        d_date = fetched["draw_date"]
        r_type = fetched["round_type"]

        # 1. Save draw to SQLite
        try:
            row_id = database.insert_result(
                draw_date=d_date,
                round_type=r_type,
                special_prize=fetched["special_prize"],
                bottom2=fetched.get("bottom2", ""),
                top3=fetched.get("top3"),
                top2=fetched.get("top2"),
                db_path=self.db_path,
            )
            fetched["id"] = row_id
            self._total_new_results += 1
            self._last_result = fetched
            self._dispatch_event("on_draw_detected", fetched)
            self._dispatch_event("on_draw_saved", fetched)
        except sqlite3.IntegrityError:
            # Race condition deduplication
            return {
                "status": "duplicate",
                "is_new": False,
                "round_type": r_type,
                "draw_date": d_date,
                "special_prize": fetched.get("special_prize"),
            }
        except Exception as err:
            self.last_error = str(err)
            self._logger.warning(f"[HanoiPipeline] Draw save error: {err}")
            return {
                "status": "error",
                "error": str(err),
                "is_new": False,
            }

        # 2. Auto-Retest formulas against updated dataset
        retest_res = self.retest(round_type=r_type)

        # 3. Cascade signals to next scheduled round
        cascade_res = self.cascade_signals(completed_round=r_type)

        # 4. Observer callback invocation
        if self.on_new_result and callable(self.on_new_result):
            try:
                self.on_new_result(
                    fetched,
                    cascade_res.get("top_formula"),
                    cascade_res.get("deliverable_sets"),
                )
            except Exception as cb_err:
                self._logger.warning(f"[HanoiPipeline] on_new_result callback error: {cb_err}")

        summary = {
            "status": "success",
            "is_new": True,
            "round_type": r_type,
            "draw_date": d_date,
            "special_prize": fetched["special_prize"],
            "top3": fetched.get("top3"),
            "top2": fetched.get("top2"),
            "bottom2": fetched.get("bottom2"),
            "source": fetched.get("source"),
            "cascaded_round": cascade_res.get("target_round"),
            "top_formula": cascade_res.get("top_formula") or self.get_top_formula(cascade_res.get("target_round")),
            "deliverable_sets": cascade_res.get("deliverable_sets"),
            "deliverables": cascade_res.get("deliverable_sets"),
            "sets": cascade_res.get("deliverable_sets"),
            "retest": retest_res,
            "cascade": cascade_res,
            "forced": is_forced,
        }
        self._dispatch_event("on_step", summary)
        return summary

    # --------------------------------------------------------------------------
    # Auto-Retest Optimizer & Leaderboard Caching (F29)
    # --------------------------------------------------------------------------

    def retest(
        self,
        round_type: Optional[str] = None,
        num_eval: int = 50,
    ) -> Dict[str, Any]:
        """
        Re-evaluates formulas across SQLite historical draws and updates cached leaderboards.
        Returns summary dictionary or empty dictionary if insufficient history.
        """
        try:
            history = database.get_results(limit=200, db_path=self.db_path)
        except Exception:
            history = []

        if not history or len(history) < 2:
            return {}

        rounds_to_update = (
            [database.normalize_round_type(round_type)]
            if round_type
            else ["special", "normal", "vip"]
        )

        for r in rounds_to_update:
            try:
                lb = backtest.run_backtest(history, target_round=r, num_eval=num_eval)
                if lb:
                    self.cached_rankings[r] = lb
                    self.cached_top_formulas[r] = lb[0]
                    self._top_formulas[r] = lb[0]
            except Exception as err:
                self._logger.warning(f"[HanoiPipeline] Backtest failed for round {r}: {err}")

        self.last_retest_time = datetime.datetime.now().isoformat()
        canonical_target = (
            database.normalize_round_type(round_type)
            if round_type
            else "all"
        )
        top = self.cached_top_formulas.get(canonical_target) or (
            list(self.cached_top_formulas.values())[0] if self.cached_top_formulas else None
        )
        lb_list = self.cached_rankings.get(canonical_target, [])

        retest_summary = {
            "round_type": canonical_target,
            "total_evaluated": num_eval,
            "top_formula": top,
            "leaderboard": lb_list,
            "leaderboard_size": len(lb_list),
            "timestamp": self.last_retest_time,
        }
        self._dispatch_event("on_retest_completed", retest_summary)
        return retest_summary

    def run_retest_optimizer(
        self,
        target_round: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Alias for retest() maintaining blueprint backwards compatibility."""
        return self.retest(round_type=target_round)

    def get_top_formula(
        self,
        round_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Returns the #1 ranked formula dict for the requested or upcoming round."""
        r = (
            database.normalize_round_type(round_type)
            if round_type
            else self.get_next_round_info()["next_round"]
        )

        if r in self.cached_top_formulas and self.cached_top_formulas[r]:
            return self.cached_top_formulas[r]

        try:
            history = database.get_results(limit=100, db_path=self.db_path)
            if history and len(history) >= 2:
                top = backtest.get_top_formula(history, target_round=r)
                if top:
                    self.cached_top_formulas[r] = top
                    self._top_formulas[r] = top
                    return top
        except Exception:
            pass

        return self.cached_top_formulas.get(r)

    def get_leaderboard(
        self,
        round_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieves cached ranked formula leaderboard list."""
        r = database.normalize_round_type(round_type) if round_type else "all"
        if r in self.cached_rankings:
            return self.cached_rankings[r]
        self.retest(round_type=r)
        return self.cached_rankings.get(r, [])

    # --------------------------------------------------------------------------
    # Cross-Round Signal Cascading & Social Deliverable Sets (F30)
    # --------------------------------------------------------------------------

    def cascade_signals(self, completed_round: str) -> Dict[str, Any]:
        """
        Propagates momentum and draw characteristics from completed round
        to the next scheduled round (Special -> Normal -> VIP -> Special).
        Generates full deliverable sets and 1-click clipboard copy text.
        """
        norm_completed = database.normalize_round_type(completed_round)
        target_round = CASCADE_CHAIN.get(norm_completed, "special")

        # Refresh backtest ranking for target round
        self.retest(round_type=target_round)
        top_formula_dict = self.get_top_formula(target_round)

        try:
            history = database.get_results(limit=100, db_path=self.db_path)
        except Exception:
            history = []

        if top_formula_dict:
            fid = top_formula_dict.get("formula_id")
            formula_obj = next(
                (f for f in formulas.ALL_FORMULAS if (getattr(f, "id", None) or f["id"]) == fid),
                formulas.ALL_FORMULAS[0] if getattr(formulas, "ALL_FORMULAS", None) else None,
            )
            formula_name = top_formula_dict.get("formula_name", "")
            win_rate = top_formula_dict.get("win_rate", 50.0)
        else:
            formula_obj = formulas.ALL_FORMULAS[0] if getattr(formulas, "ALL_FORMULAS", None) else None
            formula_name = getattr(formula_obj, "name", "สูตรเริ่มต้น")
            win_rate = 50.0
            top_formula_dict = {
                "formula_id": getattr(formula_obj, "id", "F01"),
                "formula_name": formula_name,
                "win_rate": win_rate,
                "score": 50.0,
                "rank": 1,
            }

        # Target date logic
        if norm_completed == "vip":
            target_date = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        else:
            target_date = datetime.date.today().isoformat()

        # Generate prediction & deliverable sets
        if formula_obj and hasattr(formula_obj, "predict"):
            pred = formula_obj.predict(history, target_round)
        elif formula_obj and isinstance(formula_obj, dict) and "predict" in formula_obj:
            pred = formula_obj["predict"](history, target_round)
        else:
            pred = None

        deliverable_sets = formulas.generate_deliverable_sets(pred, history)
        copy_text = formulas.format_copy_text(
            ROUND_NAMES_THAI.get(target_round, target_round),
            target_date,
            formula_name,
            win_rate,
            deliverable_sets,
        )

        cascade_payload = {
            "completed_round": norm_completed,
            "target_round": target_round,
            "target_date": target_date,
            "target_time": ROUND_SCHEDULE.get(target_round, "17:30"),
            "formula_id": top_formula_dict.get("formula_id", "F01"),
            "formula_name": formula_name,
            "win_rate": win_rate,
            "prediction": pred,
            "top_formula": top_formula_dict,
            "deliverable_sets": deliverable_sets,
            "deliverables": deliverable_sets,
            "sets": deliverable_sets,
            "recommendation": deliverable_sets,
            "copy_text": copy_text,
            "formatted_text": copy_text,
            "timestamp": datetime.datetime.now().isoformat(),
        }

        self.cached_recommendations[target_round] = cascade_payload
        self._recommendations[target_round] = cascade_payload
        self._dispatch_event("on_cascade", cascade_payload)
        return cascade_payload

    def get_recommendation(
        self, target_round: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Returns cached recommendation deliverable payload for a round."""
        r = (
            database.normalize_round_type(target_round)
            if target_round
            else self.get_next_round_info()["next_round"]
        )
        rec = self.cached_recommendations.get(r)
        if not rec:
            antecedent = {"special": "vip", "normal": "special", "vip": "normal"}.get(r, "vip")
            self.cascade_signals(completed_round=antecedent)
            rec = self.cached_recommendations.get(r)
        return rec

    # --------------------------------------------------------------------------
    # Event Listeners & Callback Dispatch System
    # --------------------------------------------------------------------------

    def register_callback(
        self, event_name: str, callback_fn: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Registers an event listener callback for a given pipeline lifecycle event."""
        with self._lock:
            norm_event = event_name.strip().lower()
            if norm_event not in self._callbacks:
                self._callbacks[norm_event] = []
            if callback_fn not in self._callbacks[norm_event]:
                self._callbacks[norm_event].append(callback_fn)

    def unregister_callback(
        self, event_name: str, callback_fn: Callable[[Dict[str, Any]], None]
    ) -> bool:
        """Removes a previously registered callback function."""
        with self._lock:
            norm_event = event_name.strip().lower()
            if norm_event in self._callbacks and callback_fn in self._callbacks[norm_event]:
                self._callbacks[norm_event].remove(callback_fn)
                return True
            return False

    def _dispatch_event(self, event_name: str, payload: Any) -> None:
        """
        Safely executes registered callbacks with zero-crash exception containment.
        Exceptions raised by observer callbacks are redirected to 'on_error' listeners.
        """
        norm_event = event_name.strip().lower()
        with self._lock:
            cbs = list(self._callbacks.get(norm_event, []))

        for cb in cbs:
            try:
                cb(payload)
            except Exception as e:
                if norm_event != "on_error":
                    self._dispatch_event("on_error", {
                        "event": norm_event,
                        "error": str(e),
                        "callback": getattr(cb, "__name__", str(cb)),
                        "timestamp": datetime.datetime.now().isoformat(),
                    })

    # --------------------------------------------------------------------------
    # Internal Helpers & Resilient Ingestion
    # --------------------------------------------------------------------------

    def _fetch_safe(self, round_type: str) -> Optional[Dict[str, Any]]:
        """
        Safely executes web scraper or fallback simulator.
        Guaranteed NEVER to raise unhandled exceptions.
        """
        try:
            res = fetcher.fetch_latest_results(
                round_type=round_type,
                fallback_mock=True,
                db_path=self.db_path,
                timeout=self.fetch_timeout,
            )
            if res and isinstance(res, dict) and res.get("special_prize"):
                self._consecutive_errors = 0
                return res
            return None
        except Exception as exc:
            self._consecutive_errors += 1
            self.last_error = str(exc)
            if self._logger:
                self._logger.warning(
                    f"[HanoiPipeline] Polling error for {round_type} (errors: {self._consecutive_errors}): {exc}"
                )
            self._dispatch_event("on_error", {
                "source": "fetch",
                "round_type": round_type,
                "error": str(exc),
                "timestamp": datetime.datetime.now().isoformat(),
            })
            return None

    def _is_draw_in_database(self, draw_date: str, round_type: str) -> bool:
        """Checks if a draw already exists in SQLite under compound unique constraint."""
        try:
            existing = database.get_results(
                round_type=round_type,
                start_date=draw_date,
                end_date=draw_date,
                limit=1,
                db_path=self.db_path,
            )
            return bool(existing and len(existing) > 0)
        except Exception:
            return False

    def _resolve_target_round(
        self, force_trigger: bool = False, explicit_round: Optional[str] = None
    ) -> str:
        """Determines the target round to evaluate."""
        if explicit_round:
            return database.normalize_round_type(explicit_round)

        today_str = datetime.date.today().isoformat()
        try:
            today_draws = database.get_results(
                start_date=today_str, end_date=today_str, limit=10, db_path=self.db_path
            )
            saved_rounds = {d.get("round_type") for d in today_draws}
        except Exception:
            saved_rounds = set()

        if force_trigger:
            for candidate in ROUND_SEQUENCE:
                if candidate not in saved_rounds:
                    return candidate

        return self.get_next_round_info()["next_round"]

    def _worker_loop(self) -> None:
        """Continuous background daemon loop calling step_check."""
        while not self._stop_event.is_set():
            try:
                self.step_check(force_trigger=False)
            except Exception as err:
                self.last_error = str(err)
                if self._logger:
                    self._logger.warning(f"[HanoiPipeline] Worker loop error: {err}")

            if self._stop_event.wait(timeout=max(0.01, self.poll_interval)):
                break


def run_pipeline(db_path: str = "hanoi.db", poll_interval: int = 30) -> None:
    """Convenience entry point to run HanoiPipeline from CLI or script."""
    pipe = HanoiPipeline(db_path=db_path, poll_interval=poll_interval)
    print(f"🚀 Starting HanoiPipeline (db: {db_path}, interval: {poll_interval}s)...")
    pipe.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping pipeline...")
        pipe.stop()
        pipe.join()
        print("✅ Pipeline stopped cleanly.")
