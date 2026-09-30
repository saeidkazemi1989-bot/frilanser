"""سرویسِ «زنده»: اسکنِ خودکار در پس‌زمینه + بررسیِ خودکارِ نسخه‌ی جدید.

هدف: داشبورد دیگر یک صفحه‌ی ایستا نباشد. این سرویس

  * هر ``[live] auto_scan_minutes`` دقیقه یک‌بار (اگر داده کهنه شده باشد) کل خط
    لوله را اجرا می‌کند: جمع‌آوری ← پیگیریِ پیشنهادها ← غربالگری ← دمو ← قیمت؛
  * هر ``[live] update_check_hours`` ساعت یک‌بار نسخه‌ی جدید برنامه را بررسی
    می‌کند تا دکمه‌ی «بروزرسانی» بدون دخالت شما از نسخه خبر دار باشد؛
  * یک «نشانه» (stamp) از وضعیت داده نگه می‌دارد تا رابط کاربری بفهمد چه زمانی
    چیزی عوض شده و خودش را بی‌نیاز از زدن دکمه، تازه کند.

هیچ استثنایی از این ماژول بیرون نمی‌رود: هر خطا در ``last_scan`` ثبت می‌شود تا
روی داشبورد دیده شود.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import traceback
from pathlib import Path

from .version import __version__, is_newer, platform_key

STATE_FILE = "live-state.json"

DEFAULT_INTERVAL_MIN = 20
DEFAULT_UPDATE_HOURS = 6
DEFAULT_POLL_SECONDS = 20


def _minutes_text(seconds: float) -> str:
    """نمایش فارسیِ گذر زمان: «چند لحظه پیش» / «۵ دقیقه پیش» / «۲ ساعت پیش»."""
    seconds = max(0, int(seconds))
    if seconds < 45:
        return "همین حالا"
    minutes = seconds // 60
    if minutes < 1:
        return f"{seconds} ثانیه پیش"
    if minutes < 60:
        return f"{minutes} دقیقه پیش"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} ساعت پیش"
    return f"{hours // 24} روز پیش"


class LiveService:
    """اسکنِ خودکار و بررسیِ نسخه در یک نخِ جداگانه (بدون قفل شدن رابط)."""

    def __init__(self, cfg, store):
        self.cfg = cfg
        self.store = store
        raw = (cfg.raw.get("live") or {}) if hasattr(cfg, "raw") else {}

        self.interval_minutes = int(raw.get("auto_scan_minutes", DEFAULT_INTERVAL_MIN) or 0)
        self.offline = bool(raw.get("auto_scan_offline", False))
        self.demo_limit = int(raw.get("auto_scan_demo_limit", 2) or 0)
        self.update_hours = float(raw.get("update_check_hours", DEFAULT_UPDATE_HOURS) or 0)
        self.poll_seconds = int(raw.get("poll_seconds", DEFAULT_POLL_SECONDS) or DEFAULT_POLL_SECONDS)
        self.auto_refresh = bool(raw.get("auto_refresh_page", True))
        self.scan_if_stale = bool(raw.get("scan_if_stale", True))

        self.state_path = Path(cfg.outbox_dir) / STATE_FILE
        self.base_url = ""

        self.auto = True
        self.scanning = False
        self.last_scan: dict | None = None
        self.last_result: dict | None = None
        self.last_update: dict | None = None
        self.next_scan_at: float | None = None
        self.stamp = self._compute_stamp()

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._scan_thread: threading.Thread | None = None
        self._load_state()

    # ------------------------------------------------------------------ state
    def _load_state(self) -> None:
        try:
            saved = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}
        self.auto = bool(saved.get("auto", True))
        self.last_scan = saved.get("last_scan") or None
        self.last_update = saved.get("last_update") or None
        self.next_scan_at = saved.get("next_scan_at") or None

    def _save_state(self) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(
                json.dumps(
                    {
                        "auto": self.auto,
                        "last_scan": self.last_scan,
                        "last_update": self.last_update,
                        "next_scan_at": self.next_scan_at,
                        "stamp": self.stamp,
                        "saved_at": time.time(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    # ------------------------------------------------------------------ stamp
    def _compute_stamp(self) -> str:
        """اثرانگشتِ داده: با هر تغییرِ آگهی/وضعیت/قیمت عوض می‌شود."""
        parts = []
        for pid in sorted(self.store.projects):
            p = self.store.projects[pid]
            parts.append(
                f"{pid}|{p.last_seen}|{p.verdict}|{p.proposal_state}|{p.status}|"
                f"{(p.proposal or {}).get('price', '')}|{(p.screening or {}).get('score', '')}"
            )
        parts.append(str(len(self.store.projects)))
        blob = "\n".join(parts).encode("utf-8")
        return hashlib.md5(blob).hexdigest()[:16]

    def refresh_stamp(self) -> str:
        self.stamp = self._compute_stamp()
        return self.stamp

    # ------------------------------------------------------------------ counts
    def counts(self) -> dict:
        projects = list(self.store.all())
        candidates = [p for p in projects if p.verdict == "candidate"]
        return {
            "total": len(projects),
            "candidate": len(candidates),
            "review": len([p for p in projects if p.verdict == "review"]),
            "rejected": len([p for p in projects if p.verdict == "rejected"]),
            "demos": len([p for p in projects if p.demo]),
            "open_tasks": len([i for i in self.store.needs_you() if not i.get("done")]),
            "budget_sum": sum(p.budget_toman or 0 for p in candidates),
            "price_sum": sum((p.proposal or {}).get("price", 0) or 0 for p in candidates),
        }

    # ------------------------------------------------------------------ scan
    def set_base_url(self, url: str) -> None:
        """آدرسِ فعلیِ داشبورد (برای ساخت لینک دمو در اسکنِ پس‌زمینه)."""
        if url:
            self.base_url = str(url).rstrip("/")

    def scan_now(self, trigger: str = "manual", offline: bool | None = None,
                 wait: bool = False) -> dict:
        """اجرای فوریِ اسکن. اگر اسکنی در جریان باشد، پیام می‌دهد (نه خطا)."""
        if self.scanning:
            return {"ok": False, "error": "یک اسکن در حال اجراست؛ چند لحظه دیگر دوباره ببینید",
                    "scanning": True}
        if wait:
            self._run_scan(trigger, offline)
            return {"ok": True, "started": True, "finished": True, "scan": self.last_scan}
        self._scan_thread = threading.Thread(
            target=self._run_scan, args=(trigger, offline), daemon=True)
        self._scan_thread.start()
        return {"ok": True, "started": True, "finished": False,
                "message": "اسکن در پس‌زمینه شروع شد"}

    def _record_ok(self, record: dict, result: dict, fell_back: bool = False) -> None:
        """نتیجه‌ی موفقِ یک اسکن را داخل رکورد می‌نویسد."""
        collect = result.get("collect") or {}
        tracking = result.get("tracking") or {}
        record.update({
            "ok": True,
            "offline": True if fell_back else record.get("offline", False),
            "fell_back": bool(fell_back),
            "error": "",
            "trace": "",
            "new": int(collect.get("new", 0) or 0),
            "updated": int(collect.get("updated", 0) or 0),
            "fetched": int(collect.get("fetched", 0) or 0),
            "closed": len(tracking.get("closed_by_miss") or [])
            + len(tracking.get("closed_by_text") or []),
            "kept": int(tracking.get("kept", 0) or 0),
        })
        self.last_result = result

    def _run_scan(self, trigger: str, offline: bool | None = None) -> None:
        from . import pipeline

        self.scanning = True
        started = time.time()
        use_offline = self.offline if offline is None else bool(offline)
        record: dict = {
            "ok": False, "at": time.time(), "trigger": trigger,
            "offline": use_offline, "new": 0, "updated": 0, "fetched": 0,
            "duration": 0.0, "error": "", "closed": 0,
        }
        try:
            try:
                result = pipeline.run_all(
                    self.cfg, self.store, offline=use_offline,
                    demo_limit=self.demo_limit, base_url=self.base_url,
                    refresh=False,
                )
                self._record_ok(record, result)
            except Exception as exc:  # noqa: BLE001 - هر خطا فقط ثبت می‌شود
                record["error"] = f"{type(exc).__name__}: {exc}"
                record["trace"] = traceback.format_exc()

            # اگر دریافتِ زنده ناموفق بود یا چیزی نیاورد، یک بار با اسنپ‌شات‌ها تلاش کن
            if (not record["ok"] or record["fetched"] == 0) and not use_offline:
                try:
                    self._record_ok(
                        record,
                        pipeline.run_all(
                            self.cfg, self.store, offline=True,
                            demo_limit=self.demo_limit, base_url=self.base_url,
                            refresh=False,
                        ),
                        fell_back=True,
                    )
                except Exception as exc:  # noqa: BLE001
                    record["error"] = (str(record.get("error") or "")
                                       + " | تلاشِ آفلاین هم ناموفق بود: "
                                       f"{type(exc).__name__}: {exc}").strip(" |")
        finally:
            record["duration"] = round(time.time() - started, 1)
            self.scanning = False
            self.last_scan = record
            self.refresh_stamp()
            self.next_scan_at = (
                time.time() + self.interval_minutes * 60
                if self.interval_minutes > 0 else None
            )
            self._save_state()

    # ------------------------------------------------------------------ update
    def check_update_now(self, wait: bool = False) -> dict:
        """بررسی نسخه‌ی جدید (در نخ جدا، مگر wait=True برای تست)."""
        if wait:
            self._run_update_check()
            return {"ok": True, "update": self.last_update}
        threading.Thread(target=self._run_update_check, daemon=True).start()
        return {"ok": True, "message": "بررسی نسخه در پس‌زمینه شروع شد"}

    def _run_update_check(self) -> None:
        try:
            from . import updater

            info = updater.check_update(self.cfg, timeout=15)
        except Exception as exc:  # noqa: BLE001
            info = {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                    "has_update": False, "latest": __version__}
        info = dict(info or {})
        info["checked_at"] = time.time()
        self.last_update = info
        self._save_state()

    def update_info(self) -> dict:
        """آخرین وضعیتِ به‌روزرسانی (از فایل وضعیتِ updater + آخرین بررسی)."""
        info: dict = {"current": __version__, "platform": platform_key(),
                      "has_update": False, "latest": "", "ok": False,
                      "error": "", "message": "", "downloading": False,
                      "percent": 0, "checked_at": None, "notes": []}
        try:
            from . import updater

            state = updater.read_state(self.cfg) or {}
        except Exception:  # noqa: BLE001
            state = {}
        for key in ("downloading", "percent", "message", "error", "installed",
                    "file", "downloaded", "total"):
            if key in state:
                info[key] = state[key]
        last = state.get("last_check")
        if isinstance(last, dict) and last:
            info.update({
                "ok": bool(last.get("ok")),
                "has_update": bool(last.get("has_update")),
                "latest": last.get("latest", ""),
                "notes": last.get("notes") or [],
                "error": last.get("error", "") or info.get("error", ""),
                "source": last.get("source", ""),
                "checked_at": last.get("checked_at"),
            })
        if self.last_update:
            info.update({
                "ok": bool(self.last_update.get("ok", info.get("ok"))),
                "latest": self.last_update.get("latest", info.get("latest", "")),
                "notes": self.last_update.get("notes") or info.get("notes") or [],
                "checked_at": self.last_update.get("checked_at") or info.get("checked_at"),
                "error": self.last_update.get("error", "") or info.get("error", ""),
            })
        # تصمیمِ نهایی را خودمان می‌گیریم تا نتیجه‌ی کهنه با تازه قاطی نشود
        latest = str(info.get("latest") or "").strip()
        info["latest"] = latest
        info["has_update"] = bool(latest) and is_newer(latest, info["current"])
        return info

    # ------------------------------------------------------------------ loop
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        now = time.time()
        if self.interval_minutes > 0 and self.next_scan_at is None:
            last_ok_at = float((self.last_scan or {}).get("at") or 0)
            stale = not (self.last_scan or {}).get("ok") or (
                now - last_ok_at >= self.interval_minutes * 60)
            if stale and self.scan_if_stale:
                # داده کهنه است: کمی بعد از بالا آمدن برنامه یک اسکن انجام بده
                self.next_scan_at = now + 15
            else:
                self.next_scan_at = last_ok_at + self.interval_minutes * 60
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._save_state()

    def set_auto(self, enabled: bool) -> bool:
        self.auto = bool(enabled)
        if self.auto and self.interval_minutes > 0:
            self.next_scan_at = time.time() + self.interval_minutes * 60
        else:
            self.next_scan_at = None
        self._save_state()
        return self.auto

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                now = time.time()
                # ---- اسکنِ خودکار
                if self.auto and self.interval_minutes > 0 and not self.scanning:
                    if self.next_scan_at is None:
                        self.next_scan_at = now + self.interval_minutes * 60
                    elif now >= self.next_scan_at:
                        self.scan_now(trigger="auto")
                # ---- بررسیِ خودکارِ نسخه
                if self.update_hours > 0:
                    last_at = (self.last_update or {}).get("checked_at") or 0
                    if now - float(last_at or 0) >= self.update_hours * 3600:
                        self.check_update_now()
                        # اگر بررسی ناموفق بود، زودتر دوباره تلاش نکنیم
                        self.last_update = dict(self.last_update or {})
                        self.last_update.setdefault("checked_at", time.time())
                        self._save_state()
            except Exception:  # noqa: BLE001 - نخِ پس‌زمینه هرگز نمی‌میرد
                pass
            if self._stop.wait(20):
                break

    # ------------------------------------------------------------------ api
    def snapshot(self) -> dict:
        """نگاهِ کاملِ وضعیت برای رابط کاربری (``/api/live``)."""
        now = time.time()
        self.refresh_stamp()
        last = self.last_scan or {}
        seconds_to_next = None
        if self.auto and self.next_scan_at:
            seconds_to_next = max(0, int(self.next_scan_at - now))
        return {
            "ok": True,
            "version": __version__,
            "platform": platform_key(),
            "server_time": now,
            "auto": self.auto,
            "interval_minutes": self.interval_minutes,
            "poll_seconds": self.poll_seconds,
            "auto_refresh": self.auto_refresh,
            "scanning": self.scanning,
            "last_scan": {
                "ok": last.get("ok", False),
                "at": last.get("at"),
                "age_text": _minutes_text(now - last["at"]) if last.get("at") else "",
                "trigger": last.get("trigger", ""),
                "offline": last.get("offline", False),
                "fell_back": last.get("fell_back", False),
                "new": last.get("new", 0),
                "updated": last.get("updated", 0),
                "fetched": last.get("fetched", 0),
                "closed": last.get("closed", 0),
                "kept": last.get("kept", 0),
                "duration": last.get("duration", 0),
                "error": last.get("error", ""),
            } if last else None,
            "next_scan_in": seconds_to_next,
            "next_scan_text": _minutes_text(seconds_to_next) if seconds_to_next else "",
            "stamp": self.stamp,
            "counts": self.counts(),
            "update": self.update_info(),
        }
