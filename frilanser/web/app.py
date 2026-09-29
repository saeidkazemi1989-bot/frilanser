"""داشبورد وبِ فریلنس‌یار آرنا (Flask)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from ..config import Config
from ..models import PROPOSAL_STATES, STATUS_LABELS, VERDICT_LABELS, Project
from ..store import Store

BUDGET_VERDICT_FA = {
    "excellent": ("بودجه عالی", "ok"),
    "good": ("بودجه خوب", "ok"),
    "ok": ("هم‌خوان", "ok"),
    "negotiate": ("نیاز به مذاکره", "warn"),
    "low": ("بودجه کم است", "bad"),
    "unknown": ("نامشخص", "warn"),
}

VERDICT_STYLE = {"candidate": "ok", "review": "warn", "rejected": "bad"}
FIT_FA = {"yes": "کاملاً قابل اجرا", "partial": "تا حدی", "no": "قابل اجرا نیست"}


def _resource_dir(name: str) -> str:
    """مسیر قالب‌ها/فایل‌های ثابت — چه در ریپو اجرا شویم چه در نسخه‌ی EXE."""
    from ..config import BUNDLE

    bundled = BUNDLE / "frilanser" / "web" / name
    if bundled.exists():
        return str(bundled)
    return str(Path(__file__).parent / name)


def create_app(cfg: Config, store: Store) -> Flask:
    app = Flask(__name__, template_folder=_resource_dir("templates"),
                static_folder=_resource_dir("static"))
    app.config["JSON_AS_ASCII"] = False
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.globals.update(
        STATUS_LABELS=STATUS_LABELS,
        VERDICT_LABELS=VERDICT_LABELS,
        VERDICT_STYLE=VERDICT_STYLE,
        FIT_FA=FIT_FA,
        BUDGET_VERDICT_FA=BUDGET_VERDICT_FA,
    )
    state = {"cfg": cfg, "store": store}

    # -------------------------------------------------------------- helpers
    def summarize() -> dict:
        projects = store.all()
        candidates = [p for p in projects if p.verdict == "candidate"]
        return {
            "total": len(projects),
            "candidate": len(candidates),
            "review": len([p for p in projects if p.verdict == "review"]),
            "rejected": len([p for p in projects if p.verdict == "rejected"]),
            "open_tasks": len([i for i in store.needs_you() if not i.get("done")]),
            "budget_sum": sum(p.budget_toman or 0 for p in candidates),
            "price_sum": sum((p.proposal or {}).get("price", 0) or 0 for p in candidates),
            "hours_sum": round(sum((p.screening or {}).get("est_hours", 0) for p in candidates), 1),
            "demos": len([p for p in projects if p.demo]),
        }

    def filtered(verdict: str = "", q: str = "", source: str = "") -> list[Project]:
        projects = store.all()
        if verdict:
            projects = [p for p in projects if p.verdict == verdict]
        if source:
            projects = [p for p in projects if p.source == source]
        if q:
            ql = q.lower()
            projects = [p for p in projects
                        if ql in p.title.lower() or ql in (p.description or "").lower()
                        or ql in " ".join(p.skills).lower()]
        return projects

    # -------------------------------------------------------------- routes
    @app.get("/")
    def index():
        verdict = request.args.get("verdict", "")
        source = request.args.get("source", "")
        q = request.args.get("q", "")
        state = request.args.get("state", "")
        sort = request.args.get("sort", "")
        projects = filtered(verdict, q, source)

        # فیلترِ وضعیتِ پیشنهاد (من روی کدام آگهی‌ها پیشنهاد داده‌ام؟)
        if state:
            projects = [p for p in projects if p.proposal_state == state]
        # مرتب‌سازی بر اساس احتمالِ واگذاری به تازه‌کار
        if sort == "beginner":
            projects = sorted(
                projects,
                key=lambda p: (p.beginner.get("score", 0), p.score),
                reverse=True,
            )

        sources = sorted({(p.source, p.source_label) for p in store.all()})
        return render_template(
            "index.html",
            projects=projects,
            stats=summarize(),
            verdict=verdict,
            source=source,
            q=q,
            state=state,
            sort=sort,
            sources=sources,
            activity=store.activity(8),
            cfg=cfg,
            prop_states=PROPOSAL_STATES,
            tracking=tracking_summary(),
        )

    @app.get("/p/<path:pid>")
    def project_detail(pid: str):
        project = store.get(pid)
        if not project:
            abort(404)
        return render_template("project.html", p=project, stats=summarize(), cfg=cfg)

    @app.post("/p/<path:pid>/decision")
    def project_decision(pid: str):
        from .. import pipeline
        decision = request.form.get("decision", "")
        note = request.form.get("note", "")
        project = pipeline.set_decision(store, pid, decision, note=note or None)
        if project:
            pipeline.notify(cfg, store)
        return redirect(url_for("project_detail", pid=pid))

    @app.post("/p/<path:pid>/proposal-state")
    def project_proposal_state(pid: str):
        """ثبت وضعیتِ پیشنهاد: داده‌ام / گرفتم / نگرفتم / بسته شد."""
        state = (request.form.get("state") or "").strip()
        price_raw = (request.form.get("price") or "").strip().replace(",", "")
        note = (request.form.get("note") or "").strip()
        price = None
        if price_raw:
            digits = "".join(ch for ch in price_raw if ch.isdigit())
            price = int(digits) if digits else None
        store.set_proposal_state(pid, state, price=price, note=note)
        try:
            from .. import pipeline

            pipeline.notify(cfg, store)
        except Exception:  # noqa: BLE001
            pass
        return redirect(url_for("project_detail", pid=pid))

    @app.get("/needs")
    def needs_you():
        items = store.needs_you()
        show_done = request.args.get("done") == "1"
        items = items if show_done else [i for i in items if not i.get("done")]
        return render_template("needs.html", items=items, stats=summarize(), show_done=show_done)

    @app.post("/needs/<path:key>/done")
    def needs_done(key: str):
        store.complete_needs_you(key)
        return redirect(request.referrer or url_for("needs_you"))

    @app.post("/rescan")
    def rescan():
        from .. import pipeline
        offline = request.form.get("online") != "1"
        limit = int(request.form.get("demos", 3) or 3)
        base_url = request.host_url.rstrip("/")
        pipeline.run_all(cfg, store, offline=offline, demo_limit=limit, base_url=base_url)
        return redirect(url_for("index"))

    @app.get("/demos")
    def demos_index():
        items = [p for p in store.all() if p.demo]
        return render_template("demos.html", items=items, stats=summarize())

    @app.get("/demos/<path:filename>")
    def serve_demo(filename: str):
        return send_from_directory(str(cfg.demo_dir), filename)

    @app.get("/activity")
    def activity():
        return render_template("activity.html", activity=store.activity(200), stats=summarize())

    @app.get("/api/summary.json")
    def api_summary():
        return jsonify(summarize())

    def _api_guard(payload_fn):
        """هر استثنای مسیرهای API را به JSON تبدیل می‌کند (نه صفحه‌ی HTML)."""
        import traceback as _tb

        try:
            return jsonify(payload_fn())
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("خطا در مسیر API")
            return jsonify({"ok": False, "error": f"{type(exc).__name__}: {exc}",
                            "trace": _tb.format_exc()}), 500

    @app.get("/api/update")
    def api_update():
        """وضعیت به‌روزرسانی (نسخه‌ی فعلی، آخرین نسخه، درصد پیشرفت)."""
        from .. import updater
        from ..version import __version__, platform_key

        def payload():
            state = updater.read_state(cfg)
            state.setdefault("current", __version__)
            state.setdefault("platform", platform_key())
            return state

        return _api_guard(payload)

    @app.post("/api/update")
    def api_update_do():
        """بررسی یا دریافت و نصب نسخه‌ی جدید."""
        from .. import updater

        mode = (request.form.get("mode") or request.args.get("mode") or "check").strip()
        if mode == "check":
            return _api_guard(lambda: updater.check_update(cfg))
        if mode == "install":
            return _api_guard(lambda: updater.update_async(cfg))
        return jsonify({"ok": False, "error": "حالت نامعلوم"}), 400

    @app.context_processor
    def _inject_version():
        """نسخه و سکو را برای نمایش در همه‌ی صفحه‌ها در دسترس می‌گذارد."""
        from ..version import __version__, platform_key

        return {"app_version": __version__, "app_platform": platform_key(),
                "PROPOSAL_STATES": PROPOSAL_STATES}

    @app.get("/crash-log")
    def crash_log():
        """نمایش آخرین خطای ثبت‌شده (برای ارسال به پشتیبانی)."""
        from ..config import ROOT

        path = Path(ROOT) / "crash.log"
        if not path.exists():
            return jsonify({"ok": True, "empty": True,
                            "message": "هیچ خطایی ثبت نشده است"})
        return jsonify({"ok": True, "empty": False, "path": str(path),
                        "text": path.read_text(encoding="utf-8")[-8000:]})

    @app.get("/api/selftest")
    def api_selftest():
        """گزارش کاملِ وضعیت برنامه و مسیر به‌روزرسانی (برای ارسال به پشتیبانی)."""
        import platform as _platform
        import traceback as _tb

        from .. import updater
        from ..version import __version__, platform_key

        report = {
            "version": __version__, "platform": platform_key(),
            "python": _platform.python_version(),
            "home": str(cfg.root), "outbox": str(cfg.outbox_dir),
            "writable": os.access(str(cfg.outbox_dir), os.W_OK),
            "requests": False, "check": None, "trace": "",
        }
        try:
            import requests  # noqa: F401

            report["requests"] = True
        except Exception as exc:  # noqa: BLE001
            report["requests"] = f"{type(exc).__name__}: {exc}"
        try:
            report["check"] = updater.check_update(cfg, timeout=8)
            report["manifest_urls"] = updater.manifest_urls(cfg)
        except Exception as exc:  # noqa: BLE001
            report["trace"] = _tb.format_exc()
            report["check_error"] = f"{type(exc).__name__}: {exc}"
        return jsonify(report)

    def tracking_summary() -> dict:
        """خلاصه‌ی پیشنهادهای کاربر (برای نمایش بالای داشبورد)."""
        counts = {"submitted": 0, "won": 0, "lost": 0, "closed": 0}
        for p in store.all():
            if p.proposal_state in counts:
                counts[p.proposal_state] += 1
        return {"counts": counts,
                "open": counts["submitted"], "won": counts["won"]}

    @app.get("/healthz")
    def healthz():
        return jsonify({"ok": True, "projects": len(store.projects)})

    # ------------------------------------------------ خطاها: هرگز بی‌توضیح نماند
    @app.errorhandler(Exception)
    def _handle_error(exc):  # pragma: no cover - فقط در زمان خطا اجرا می‌شود
        import html as _html
        import traceback
        from datetime import datetime as _dt

        tb = traceback.format_exc()
        code = getattr(exc, "code", 500) or 500
        if not isinstance(code, int):
            code = 500
        try:
            log_dir = cfg.outbox_dir
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / "web-error.log", "a", encoding="utf-8") as fh:
                fh.write(f"\n{'='*60}\n{_dt.now().isoformat(timespec='seconds')} — {request.path}\n{tb}")
        except OSError:
            pass
        app.logger.error("خطا در مسیر %s: %s", request.path, exc, exc_info=True)

        safe = _html.escape(f"{type(exc).__name__}: {exc}")
        hint = ("قالب صفحه یا داده‌ی آن مشکل دارد. جزئیات کامل در فایل outbox/web-error.log ثبت شد."
                if code == 500 else "این صفحه در دسترس نیست.")
        return (
            f"<html lang='fa' dir='rtl'><meta charset='utf-8'>"
            f"<div style='max-width:760px;margin:40px auto;font-family:Tahoma,sans-serif;line-height:2'>"
            f"<h2 style='color:#b91c1c'>خطا در نمایش این صفحه ({code})</h2>"
            f"<p>{hint}</p>"
            f"<pre dir='ltr' style='background:#0f172a;color:#d7e3ff;padding:12px;border-radius:12px;"
            f"overflow:auto;font-size:12.5px'>{safe}</pre>"
            f"<p><a href='/'>بازگشت به صفحه‌ی اصلی</a></p></div></html>",
            code,
        )

    return app


def run(cfg: Config, store: Store, host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    app = create_app(cfg, store)
    app.run(host=host, port=port, debug=debug, threaded=True)
