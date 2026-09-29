"""داشبورد وبِ فریلنس‌یار آرنا (Flask)."""

from __future__ import annotations

import json
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
from ..models import STATUS_LABELS, VERDICT_LABELS, Project
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
        projects = filtered(verdict, q, source)
        sources = sorted({(p.source, p.source_label) for p in store.all()})
        return render_template(
            "index.html",
            projects=projects,
            stats=summarize(),
            verdict=verdict,
            source=source,
            q=q,
            sources=sources,
            activity=store.activity(8),
            cfg=cfg,
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

    @app.get("/api/update")
    def api_update():
        """وضعیت به‌روزرسانی (نسخه‌ی فعلی، آخرین نسخه، درصد پیشرفت)."""
        from .. import updater
        from ..version import __version__, platform_key

        state = updater.read_state(cfg)
        state.setdefault("current", __version__)
        state.setdefault("platform", platform_key())
        return jsonify(state)

    @app.post("/api/update")
    def api_update_do():
        """بررسی یا دریافت و نصب نسخه‌ی جدید."""
        from .. import updater

        mode = (request.form.get("mode") or request.args.get("mode") or "check").strip()
        if mode == "check":
            return jsonify(updater.check_update(cfg))
        if mode == "install":
            return jsonify(updater.update_async(cfg))
        return jsonify({"ok": False, "error": "حالت نامعلوم"}), 400

    @app.context_processor
    def _inject_version():
        """نسخه و سکو را برای نمایش در همه‌ی صفحه‌ها در دسترس می‌گذارد."""
        from ..version import __version__, platform_key

        return {"app_version": __version__, "app_platform": platform_key()}

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
