"""داشبورد وبِ فریلنس‌یار آرنا (Flask)."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
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
from ..version import __version__

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


def create_app(cfg: Config, store: Store, live: bool | None = None) -> Flask:
    """ساخت اپلیکیشن.

    ``live``=True سرویسِ «زنده» (اسکن خودکار + بررسی نسخه) را روشن می‌کند؛
    مقدار None یعنی «طبق متغیر محیطی FRILANSER_NO_LIVE» (پیش‌فرضِ برنامه واقعی).
    """
    if live is None:
        live = os.environ.get("FRILANSER_NO_LIVE", "") not in ("1", "true", "yes")
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

    # بازیابیِ نشانه‌گذاری‌های کاربر (پیشنهاد دادم / گرفتم / …) از پوشه‌های
    # پایدار و نسخه‌های پشتیبان — پیش از هر چیز، تا هیچ انتخابی از بین نرود.
    try:
        from .. import backup as _backup  # noqa: PLC0415
        _restore = _backup.restore(store)
        app.config["RESTORE_REPORT"] = _restore
        if _restore.get("applied") or _restore.get("restored_from_backup"):
            print(f"[frilanser] بازیابی: {len(_restore.get('applied', []))} مورد از "
                  f"{len(_restore.get('sources', []))} منبع"
                  + (f" + پایگاه داده از {_restore['restored_from_backup']}"
                     if _restore.get("restored_from_backup") else ""))
    except Exception as _exc:  # noqa: BLE001
        app.config["RESTORE_REPORT"] = {"error": str(_exc)}

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

    # --------------------------------------------- منابع (کدام سایت‌ها اسکن شوند)
    def source_info() -> list[dict]:
        """وضعیتِ هر سایت: انتخاب شده؟ چند آگهی دارد؟ در آخرین اسکن چه شد؟"""
        from ..sources.registry import source_states

        states = source_states(cfg)
        counts: dict[str, int] = {}
        for project in store.all():
            counts[project.source] = counts.get(project.source, 0) + 1
        svc = app.extensions.get("live")
        last_sources = ((svc.last_scan or {}) if svc else {}).get("sources") or {}

        items: list[dict] = []
        for key, scfg in (cfg.sources or {}).items():
            items.append({
                "key": key,
                "label": scfg.get("label", key) if isinstance(scfg, dict) else key,
                "enabled": bool(states.get(key, True)),
                "count": counts.get(key, 0),
                "last": last_sources.get(key),
                "listing_url": scfg.get("listing_url", "") if isinstance(scfg, dict) else "",
            })
        return items

    # --------------------------------------------------- متنِ داشبورد (مشترک)
    def dashboard_context() -> dict:
        """ورودی‌های قالبِ داشبورد — هم برای صفحه‌ی کامل، هم برای نوسازیِ زنده."""
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
        return {
            "source_info": source_info(),
            "projects": projects,
            "stats": summarize(),
            "version": __version__,
            "scan_attempts": _scan_attempts(),
            "scan_error": _scan_error(),
            "verdict": verdict,
            "source": source,
            "q": q,
            "state": state,
            "sort": sort,
            "sources": sources,
            "activity": store.activity(8),
            "cfg": cfg,
            "prop_states": PROPOSAL_STATES,
            "tracking": tracking_summary(),
            "last_scan": (((app.extensions.get("live").last_scan or {})
                           if app.extensions.get("live") else {}) or {}),
        }

    def _last_scan_record() -> dict:
        svc = app.extensions.get("live")
        return ((svc.last_scan or {}) if svc else {}) or {}

    def _scan_attempts() -> int:
        """جمعِ تلاش‌های دریافت در آخرین اسکن (۰ یعنی اصلاً تلاش نشده)."""
        total = 0
        for info in (_last_scan_record().get("sources") or {}).values():
            total += int(((info or {}).get("fetch") or {}).get("attempts") or 0)
        return total

    def _scan_error() -> str:
        record = _last_scan_record()
        if record.get("error"):
            return str(record["error"])
        for info in (record.get("sources") or {}).values():
            if (info or {}).get("error"):
                return str(info["error"])
        return ""

    # -------------------------------------------------------------- routes
    @app.get("/")
    def index():
        return render_template("index.html", **dashboard_context())

    @app.get("/fragment")
    def fragment():
        """تکه‌ی داشبورد برای نوسازیِ زنده (بدون بارگذاریِ دوباره‌ی صفحه)."""
        return render_template("dashboard.html", **dashboard_context())

    @app.get("/p/<path:pid>")
    def project_detail(pid: str):
        project = store.get(pid)
        if not project:
            abort(404)
        return render_template("project.html", p=project, stats=summarize(), cfg=cfg)

    # ------------------------------------------------------------------ #
    # پیوست‌های آگهی (فایلِ مشخصات، نمونه‌کار، فایلِ تحویل…)
    # ------------------------------------------------------------------ #
    ATTACH_MAX_BYTES = 25 * 1024 * 1024
    ATTACH_EXT = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".md",
                  ".zip", ".rar", ".7z", ".png", ".jpg", ".jpeg", ".gif", ".webp",
                  ".psd", ".ai", ".fig", ".sketch", ".mp4", ".mp3", ".json", ".xml"}

    def _attach_dir(pid: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(pid))[-60:]
        d = Path(cfg.data_dir) / "attachments" / safe
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _store_attachment(project, f, note: str = "") -> str | None:
        name = Path(f.filename or "").name.strip()
        if not name:
            return None
        data = f.read()
        if not data or len(data) > ATTACH_MAX_BYTES:
            return None
        d = _attach_dir(project.id)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = d / f"{stamp}-{name}"
        i = 1
        while target.exists():
            target = d / f"{stamp}-{i}-{name}"
            i += 1
        target.write_bytes(data)
        project.attachments.append({
            "name": name,
            "rel": str(target.relative_to(cfg.data_dir)).replace("\\", "/"),
            "size": len(data),
            "kind": Path(name).suffix.lower().lstrip("."),
            "note": note,
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        return name

    @app.post("/p/<path:pid>/attach")
    def project_attach(pid: str):
        """بارگذاریِ یک یا چند فایل و ضمیمه کردن به آگهی."""
        from flask import request as _rq

        project = store.get(pid)
        if project is None:
            abort(404)
        files = _rq.files.getlist("files") or []
        if not files:
            return redirect(url_for("project_detail", pid=pid, attach="empty"))

        note = (_rq.form.get("note") or "").strip()
        added: list[str] = []
        for f in files:
            got = _store_attachment(project, f, note=note)
            if got:
                added.append(got)
        if added:
            project.notes.append("پیوست اضافه شد: " + ", ".join(added))
            store.upsert_many([project])
            store.save()
            store.snapshot(force=True)
        return redirect(url_for("project_detail", pid=pid))

    @app.get("/attachments/<path:filename>")
    def serve_attachment(filename: str):
        """دانلودِ یک پیوست.

        ``filename`` همان ``rel``ِ ذخیره‌شده است که نسبت به پوشه‌ی داده‌ها است
        (مثل ``attachments/<pid>/<file>``)؛ برای سازگاری، اگر فقط نامِ فایل هم
        رسید آن را در پوشه‌ی پیوست‌ها جست‌وجو می‌کنیم.
        """
        from flask import send_file

        base = (Path(cfg.data_dir) / "attachments").resolve()
        rel = str(filename).replace("\\", "/").lstrip("/")
        if rel.startswith("attachments/"):
            rel = rel[len("attachments/"):]
        target = (base / rel).resolve()
        # ضدِ بیرون‌زدن از پوشه‌ی پیوست‌ها
        try:
            target.relative_to(base)
        except ValueError:
            abort(404)
        if not target.is_file():
            abort(404)
        return send_file(str(target), as_attachment=False,
                         download_name=target.name)

    @app.post("/p/<path:pid>/attachment/<int:idx>/delete")
    def project_attachment_delete(pid: str, idx: int):
        project = store.get(pid)
        if project is None:
            abort(404)
        if 0 <= idx < len(project.attachments):
            item = project.attachments.pop(idx)
            # فایل را پاک نمی‌کنیم (فقط از فهرست خارج می‌شود) تا چیزی از دست نرود
            project.notes.append(f"پیوست حذف شد: {item.get('name', '')}")
            store.upsert_many([project])
            store.save()
        return redirect(url_for("project_detail", pid=pid))

    @app.get("/p/<path:pid>/upsell")
    def upsell(pid: str):
        """پیشنهادِ بهتر: به‌جای آنچه کارفرما خواسته، چه چیزی بهتر است؟"""
        from .. import upsell as upsell_mod

        project = store.get(pid)
        if project is None:
            abort(404)
        proposal = getattr(project, "proposal", None) or {}
        info = upsell_mod.build_upsell(project, cfg, proposal)
        return render_template("upsell.html", p=project, up=info,
                               stats=summarize(), cfg=cfg)

    @app.post("/p/<path:pid>/edit")
    def edit_project(pid: str):
        """ویرایشِ دستیِ مشخصاتِ آگهی (تا هر تغییری بخواهید در آن بدهید)."""
        from ..normalize import clean_text, parse_amount, parse_days
        from ..pipeline import price_projects, screen_projects

        project = store.get(pid)
        if project is None:
            abort(404)

        title = (request.form.get("title") or "").strip()
        if title:
            project.title = clean_text(title)
        project.description = clean_text(request.form.get("description") or "")
        url = (request.form.get("url") or "").strip()
        if url:
            project.url = url
        budget_raw = (request.form.get("budget") or "").strip()
        if budget_raw:
            project.budget_toman = parse_amount(budget_raw)
        deadline = (request.form.get("deadline") or "").strip()
        if deadline:
            project.client_deadline_days = parse_days(deadline)
        skills_raw = (request.form.get("skills") or "").strip()
        if skills_raw:
            project.skills = [x.strip() for x in skills_raw.split(",") if x.strip()]

        store.upsert_many([project])
        store.save()
        # دوباره غربال و قیمت‌گذاری می‌کنیم چون مشخصات عوض شده
        screen_projects(cfg, store, force=True)
        price_projects(cfg, store, force=True)
        store.save()
        return redirect(url_for("project_detail", pid=pid))

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
        """اسکنِ دستی.

        پیش‌فرض **آنلاین** است (از سایت‌ها می‌خواند)؛ فقط اگر کاربر تیکِ
        «بدون اینترنت» را بزند سراغِ اسنپ‌شات‌های همراه می‌رویم. قبلاً برعکس
        بود و خیلی‌ها همان دکمه را می‌زدند و فکر می‌کردند برنامه آگهی نمی‌آورد،
        در حالی که اصلاً به اینترنت وصل نشده بود.
        """
        offline = request.form.get("offline") == "1"
        limit = int(request.form.get("demos", 3) or 3)
        base_url = request.host_url.rstrip("/")

        svc = app.extensions.get("live")
        if svc is not None and not offline:
            # از سرویسِ زنده استفاده می‌کنیم تا نتیجه در «گزارشِ اسکن» هم ثبت شود
            svc.scan_now(trigger="manual", refresh=True)
            # کمی صبر می‌کنیم تا اسکنِ تازه جای رکوردِ کهنه را بگیرد و کاربر
            # نتیجه‌ی واقعی را ببیند، نه گزارشِ به‌جامانده از نسخه‌ی قبل.
            for _ in range(60):
                time.sleep(1)
                if not getattr(svc, "scanning", False):
                    break
            return redirect(url_for("scan_report"))

        from .. import pipeline

        # وقتی کاربر می‌خواهد از سایت‌ها بخواند، کش را دور می‌زنیم تا آگهی‌های
        # تازه واقعاً بیایند (در غیر این صورت همان صفحه‌ی ذخیره‌شده خوانده می‌شد)
        pipeline.run_all(cfg, store, offline=offline, demo_limit=limit,
                         base_url=base_url, refresh=not offline)
        return redirect(url_for("index"))

    def _save_attachments(project) -> list[str]:
        """فایل‌های فرستاده‌شده را در data/attachments ذخیره و به پروژه وصل می‌کند."""
        files = request.files.getlist("files") if hasattr(request, "files") else []
        note = (request.form.get("note") or "").strip()
        added: list[str] = []
        for f in files:
            got = _store_attachment(project, f, note=note)
            if got:
                added.append(got)
        if added:
            project.notes.append("پیوست اضافه شد: " + ", ".join(added))
            store.upsert_many([project])
            store.save()
            store.snapshot(force=True)
        return added

    @app.get("/add")
    def add_listing_form():
        """فرمِ «آگهیِ دستی»: آگهی‌ای که خودتان در سایت دیده‌اید وارد کنید."""
        return render_template(
            "add_listing.html",
            stats=summarize(),
            cfg=cfg,
            source_info=source_info(),
            sources=sorted(set((p.source, p.source_label) for p in store.all())),
        )

    @app.post("/add")
    def add_listing():
        """آگهی را می‌گیرد، غربال می‌کند، قیمت می‌گذارد و (در صورت نیاز) دمو می‌سازد."""
        title = (request.form.get("title") or "").strip()
        if not title:
            return redirect(url_for("add_listing_form", err="عنوانِ آگهی را بنویسید"))

        from ..models import Project
        from ..normalize import parse_amount, parse_days
        from ..pipeline import price_projects, screen_projects

        description = (request.form.get("description") or "").strip()
        url = (request.form.get("url") or "").strip()
        source_key = (request.form.get("source") or "manual").strip() or "manual"
        skills = [x.strip() for x in (request.form.get("skills") or "").split(",")
                  if x.strip()]

        budget_raw = (request.form.get("budget") or "").strip()
        budget = parse_amount(budget_raw) if budget_raw else None
        deadline = parse_days(request.form.get("deadline") or "")

        # شناسه‌ی یکتا بر اساسِ عنوان (تا دوباره وارد کردن تکراری نسازد)
        import hashlib

        digest = hashlib.md5(f"{title}|{url}".encode("utf-8")).hexdigest()[:10]
        project = Project.from_scrape(
            source=source_key if source_key != "manual" else "manual",
            external_id=f"manual-{digest}",
            title=title,
            url=url,
            description=description,
            skills=skills,
            budget_toman=budget,
            client_deadline_days=deadline,
        )
        # برچسبِ منبع از روی کلید ساخته می‌شود؛ برای «manual» مدل خودش
        # «دستی (من اضافه کردم)» را برمی‌گرداند.
        store.upsert_many([project])
        store.save()

        # پیوست‌هایی که همراهِ فرم فرستاده شده
        _save_attachments(project)
        screen_projects(cfg, store, force=False)
        price_projects(cfg, store, force=False)
        store.save()

        wanted = request.form.get("demo") == "1"
        if wanted:
            try:
                from ..pipeline import build_demos

                build_demos(cfg, store, verdicts=("candidate", "review", "rejected"),
                            limit=1, base_url=request.host_url.rstrip("/"), force=True)
            except Exception:  # noqa: BLE001 - دمو نباید مانعِ ادامه شود
                pass

        return redirect(url_for("project_detail", pid=project.id))

    @app.get("/scan-report")
    def scan_report():
        """گزارشِ دقیقِ آخرین اسکن: هر سایت چه فرستاد (برای پیدا کردنِ علتِ آگهی نیامدن)."""
        svc = app.extensions.get("live")
        last = ((svc.last_scan or {}) if svc else {}) or {}
        sources = last.get("sources") or {}
        # وضعیتِ تنظیمات روی دستگاه (برای اینکه بدانیم چرا نشانی خالی است)
        diag = {}
        try:
            raw_sources = (cfg.raw.get("sources") or {}) if hasattr(cfg, "raw") else {}
            diag = {
                "config_path": str(getattr(cfg, "path", "") or ""),
                "config_exists": bool(getattr(cfg, "path", None)
                                      and Path(str(cfg.path)).exists()),
                "root": str(cfg.root),
                "sources_in_file": len(raw_sources),
                "sources_resolved": len(cfg.sources or {}),
                "urls": {k: (v.get("listing_url") or "— خالی —")
                         for k, v in sorted((cfg.sources or {}).items())},
                "live_offline": bool((cfg.raw.get("live") or {}).get(
                    "auto_scan_offline", False)) if hasattr(cfg, "raw") else False,
                "allow_network": bool(cfg.allow_network),
                "snapshot_files": len(list(cfg.raw_dir.glob("*")))
                if cfg.raw_dir.exists() else 0,
            }
        except Exception as exc:  # noqa: BLE001
            diag = {"error": f"{type(exc).__name__}: {exc}"}

        return render_template(
            "scan_report.html",
            stats=summarize(),
            last_scan=last,
            diag=diag,
            sources=sources or {},
            cfg=cfg,
            source_info=source_info(),
            has_live=svc is not None,
        )

    @app.post("/paste")
    def paste_page():
        """خواندنِ آگهی‌ها از متن/اچ‌تی‌ام‌الِ صفحه‌ای که خودتان کپی کرده‌اید.

        برای سایت‌هایی که فقط با اکانت آگهی نشان می‌دهند (یا روی اینترنتِ شما در
        دسترس نیستند): صفحه را در مرورگر باز کنید، همه را کپی کنید و اینجا
        بچسبانید تا برنامه همان آگهی‌ها را به فهرست اضافه کند.
        """
        from ..sources.registry import SOURCE_CLASSES

        key = (request.form.get("source") or "").strip()
        text = request.form.get("text") or ""
        url = (request.form.get("url") or "").strip()
        result: dict = {"ok": False, "parsed": 0, "added": 0, "updated": 0, "error": ""}
        try:
            scfg = (cfg.sources or {}).get(key) or {}
            cls = SOURCE_CLASSES.get(scfg.get("kind", key))
            if not cls:
                result["error"] = "سایت انتخاب نشده یا ناشناس است"
            elif len(text.strip()) < 50:
                result["error"] = "متن خیلی کوتاه است (صفحه را کامل کپی کنید)"
            else:
                source = cls(cfg, key)
                body = source.html_to_text(text) if ("<" in text and ">" in text) else text
                records = source.parse(body)
                projects = source.to_projects(records)
                if url:
                    for project in projects:
                        project.url = project.url or url
                new, updated = store.upsert_many(projects)
                store.save()
                from ..pipeline import price_projects, screen_projects

                screen_projects(cfg, store, force=False)
                price_projects(cfg, store, force=False)
                store.log("paste", key, f"{new} جدید از متنِ دستی ({len(records)} رکورد)")
                result.update({"ok": True, "parsed": len(records), "added": new,
                               "updated": updated,
                               "sample": (records[0].get("title", "") if records else "")})
        except Exception as exc:  # noqa: BLE001
            result["error"] = f"{type(exc).__name__}: {exc}"

        if request.headers.get("X-Requested-With") == "live":
            return jsonify(result)
        return redirect(url_for(
            "scan_report", pasted=result.get("added", 0), parsed=result.get("parsed", 0),
            err=(result.get("error") or "")[:140],
            sample=(result.get("sample") or "")[:80]))

    @app.post("/sources")
    def save_sources():
        """انتخابِ کاربر: کدام سایت‌ها اسکن شوند (در فایلِ جداگانه ذخیره می‌شود)."""
        from ..sources.registry import save_source_prefs, save_source_secrets

        chosen = set(request.form.getlist("source"))
        enabled = {key: (key in chosen) for key in (cfg.sources or {})}
        saved = save_source_prefs(cfg, enabled)

        # کوکیِ ورود (اگر کاربر برای سایتی که نیاز به اکانت دارد، پر کرده باشد)
        cookies = {}
        prefix = "cookie__"
        for field, value in request.form.items():
            if field.startswith(prefix) and str(value).strip():
                cookies[field[len(prefix):]] = str(value).strip()
        if cookies:
            save_source_secrets(cfg, cookies)
        if request.form.get("scan") == "1" and saved:
            svc = app.extensions.get("live")
            if svc is not None:
                svc.scan_now(trigger="manual", refresh=True)
        if request.headers.get("X-Requested-With") == "live":
            return jsonify({"ok": True, "saved": saved})
        return redirect(url_for("index"))

    @app.get("/demos")
    def demos_index():
        items = [p for p in store.all() if p.demo]
        return render_template("demos.html", items=items, stats=summarize())

    @app.get("/demos/<path:filename>")
    def serve_demo(filename: str):
        return send_from_directory(str(cfg.demo_dir), filename)

    # ------------------------------------------------------------------ #
    # پشتیبان و بازیابیِ نشانه‌گذاری‌ها
    # ------------------------------------------------------------------ #
    @app.get("/backup")
    def backup_page():
        """نمایشِ وضعیتِ پشتیبان‌ها و بازیابیِ نشانه‌گذاری‌های کاربر."""
        from .. import backup as bk
        from ..backup import stable_dirs, legacy_dirs, writable_dirs, list_backups

        ledger, sources = bk.load_state(legacy_dirs(Path(cfg.data_dir)))
        marked_now = [p for p in store.all() if (p.proposal_state or "").strip()]
        return render_template(
            "backup.html",
            stats=summarize(),
            cfg=cfg,
            data_dir=str(cfg.data_dir),
            restore_report=app.config.get("RESTORE_REPORT") or {},
            ledger=ledger,
            ledger_sources=sources,
            marked=marked_now,
            backups=list_backups(Path(cfg.data_dir)),
            stable=[str(d) for d in stable_dirs()],
            writable=[str(d) for d in writable_dirs(Path(cfg.data_dir))],
            state_file=bk.STATE_FILE,
        )

    @app.get("/backup/export")
    def backup_export():
        """دریافتِ یک فایل از نشانه‌گذاری‌ها (برای نگه داشتن یا انتقال)."""
        from flask import Response

        from ..backup import export_payload

        payload = export_payload(store)
        body = json.dumps(payload, ensure_ascii=False, indent=2)
        return Response(
            body,
            mimetype="application/json",
            headers={"Content-Disposition":
                     'attachment; filename="frilanser-state.json"'},
        )

    @app.post("/backup/import")
    def backup_import():
        """بازگرداندنِ نشانه‌گذاری‌ها از یک فایلِ گرفته‌شده."""
        from ..backup import import_payload

        f = request.files.get("file")
        if f is None:
            return redirect(url_for("backup_page", err="هیچ فایلی انتخاب نشد"))
        try:
            payload = json.loads(f.read().decode("utf-8"))
            applied = import_payload(store, payload)
        except Exception as exc:  # noqa: BLE001
            return redirect(url_for("backup_page", err=f"فایل خوانده نشد: {exc}"))
        store.save()
        store.snapshot(force=True)
        return redirect(url_for("backup_page", ok=str(len(applied))))

    @app.post("/backup/restore")
    def backup_restore():
        """جست‌وجو در همه‌ی پوشه‌ها و بازگرداندنِ نشانه‌گذاری‌ها."""
        from .. import backup as bk

        try:
            rep = bk.restore(store)
            applied = len(rep.get("applied") or [])
        except Exception as exc:  # noqa: BLE001
            return redirect(url_for("backup_page", err=f"بازیابی ناموفق بود: {exc}"))
        return redirect(url_for("backup_page", ok=str(applied)))

    @app.post("/backup/now")
    def backup_now():
        """گرفتنِ یک نسخه‌ی پشتیبانِ فوری از کلِ پایگاه داده."""
        path = store.snapshot(force=True)
        return redirect(url_for("backup_page",
                                ok="نسخه گرفته شد" if path else "نسخه‌ای ساخته نشد"))

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
        if mode == "set-url":
            def _save():
                url = (request.form.get("url") or "").strip()
                saved = updater.save_update_config(cfg, manifest_url=url)
                info = updater.check_update(cfg, timeout=12)
                info["saved_url"] = saved.get("manifest_url", "")
                info["manifest_urls"] = updater.manifest_urls(cfg)
                return info

            return _api_guard(_save)
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

        from .. import http

        report = {
            "version": __version__, "platform": platform_key(),
            "python": _platform.python_version(),
            "home": str(cfg.root), "outbox": str(cfg.outbox_dir),
            "writable": os.access(str(cfg.outbox_dir), os.W_OK),
            "requests": False, "check": None, "trace": "",
            "http": http.describe(), "probes": [],
        }
        # وضعیتِ واقعیِ کتابخانه‌ها روی این دستگاه (bs4 بدون typing_extensions
        # ایمپورت نمی‌شود و این دقیقاً همان چیزی است که باید دیده شود).
        try:
            from .. import compat

            report.update(compat.describe())
        except Exception as exc:  # noqa: BLE001
            report["libs_error"] = f"{type(exc).__name__}: {exc}"
        try:
            import requests  # noqa: F401

            report["requests"] = True
        except Exception as exc:  # noqa: BLE001
            report["requests"] = f"{type(exc).__name__}: {exc}"

        # آزمایشِ واقعیِ دسترسی: کدام نشانی از روی دستگاه جواب می‌دهد؟
        for url in updater.manifest_urls(cfg)[:4]:
            try:
                got = http.get_text(url, timeout=8)
                report["probes"].append({
                    "url": url, "ok": bool(got.get("ok")),
                    "status": got.get("status"), "how": got.get("how"),
                    "error": (got.get("error") or "")[:200],
                    "head": (got.get("text") or "")[:100],
                })
            except Exception as exc:  # noqa: BLE001
                report["probes"].append({"url": url, "ok": False,
                                         "error": f"{type(exc).__name__}: {exc}"})
        # وضعیتِ تنظیمات: آیا config.toml خوانده شده و منبع‌ها نشانی دارند؟
        try:
            from ..sources.registry import build_sources

            raw_sources = (cfg.raw.get("sources") or {}) if hasattr(cfg, "raw") else {}
            report["config"] = {
                "path": str(getattr(cfg, "path", "") or ""),
                "exists": bool(getattr(cfg, "path", None)
                               and Path(str(cfg.path)).exists()),
                "root": str(cfg.root),
                "sections": sorted((cfg.raw or {}).keys()) if hasattr(cfg, "raw") else [],
                "sources_in_file": sorted(raw_sources.keys()),
                "sources_resolved": sorted((cfg.sources or {}).keys()),
                "missing_listing_url": [k for k, v in (cfg.sources or {}).items()
                                        if not str(v.get("listing_url") or "").strip()],
                "live_offline": bool((cfg.raw.get("live") or {}).get("auto_scan_offline", False)),
                "allow_network": bool(cfg.allow_network),
                "urls": {k: (v.get("listing_url") or "")
                         for k, v in sorted((cfg.sources or {}).items())},
                "built_sources": sorted(build_sources(cfg).keys()),
                "raw_snapshot_files": len(list(cfg.raw_dir.glob("*")))
                if cfg.raw_dir.exists() else 0,
            }
        except Exception as exc:  # noqa: BLE001
            report["config_error"] = f"{type(exc).__name__}: {exc}"

        # آزمایشِ واقعیِ «سایت‌های آگهی»: مستقیم و از راهِ واسطه‌ها.
        # فقط با ?sites=1 اجرا می‌شود چون ممکن است چند ثانیه طول بکشد.
        if request.args.get("sites"):
            try:
                from ..sources.registry import build_sources

                report["sites"] = []
                for src in build_sources(cfg):
                    url = getattr(src, "listing_url", "") or src.scfg.get("listing_url", "")
                    if not url:
                        continue
                    got = http.get_text(url, timeout=8, allow_relay=True)
                    text = got.get("text") or ""
                    report["sites"].append({
                        "key": src.key, "url": url,
                        "ok": bool(got.get("ok")), "how": got.get("how"),
                        "status": got.get("status"),
                        "chars": len(text),
                        "error": (got.get("error") or "")[:200],
                        "relays": got.get("relay_errors") or [],
                        "head": text[:120],
                    })
            except Exception as exc:  # noqa: BLE001
                report["sites_error"] = f"{type(exc).__name__}: {exc}"

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

    # -------------------------------------------------- «زنده»: اسکن و بروزرسانی
    live_service = None
    if live:
        try:
            from ..live import LiveService

            live_service = LiveService(cfg, store)
            live_service.start()
        except Exception as exc:  # noqa: BLE001 - داشبورد بدون سرویسِ زنده هم کار می‌کند
            app.logger.warning("سرویس زنده فعال نشد: %s", exc)
            live_service = None
    app.extensions["live"] = live_service

    @app.before_request
    def _live_base_url():
        """آدرسِ فعلی را به سرویسِ زنده می‌دهیم (برای لینک دمو در اسکنِ خودکار)."""
        svc = app.extensions.get("live")
        if svc is not None:
            try:
                svc.set_base_url(request.host_url)
            except Exception:  # noqa: BLE001
                pass

    def _live_error(message: str, code: int = 503):
        return jsonify({"ok": False, "error": message, "enabled": False}), code

    @app.get("/api/live")
    def api_live():
        """نگاهِ کامل به وضعیتِ زنده: اسکن، داده، نسخه."""
        svc = app.extensions.get("live")
        if svc is None:
            return _live_error("سرویسِ به‌روزرسانیِ خودکار در این اجرا خاموش است")
        return _api_guard(svc.snapshot)

    @app.post("/api/live/scan")
    def api_live_scan():
        """اسکنِ فوری (در پس‌زمینه؛ جواب فوراً برمی‌گردد)."""
        svc = app.extensions.get("live")
        if svc is None:
            return _live_error("سرویسِ به‌روزرسانیِ خودکار در این اجرا خاموش است")

        def payload():
            offline = request.form.get("offline") or request.args.get("offline")
            offline_flag = None if offline is None else offline in ("1", "true", "yes")
            return svc.scan_now(trigger="manual", offline=offline_flag)

        return _api_guard(payload)

    @app.post("/api/live/auto")
    def api_live_auto():
        """روشن/خاموش کردنِ اسکنِ خودکار."""
        svc = app.extensions.get("live")
        if svc is None:
            return _live_error("سرویسِ به‌روزرسانیِ خودکار در این اجرا خاموش است")

        def payload():
            raw = request.form.get("enabled", request.args.get("enabled", "1"))
            enabled = str(raw).strip().lower() in ("1", "true", "yes", "on")
            return {"ok": True, "auto": svc.set_auto(enabled)}

        return _api_guard(payload)

    @app.post("/api/live/update-check")
    def api_live_update_check():
        """بررسیِ نسخه‌ی جدید (در پس‌زمینه)."""
        svc = app.extensions.get("live")
        if svc is not None:
            return _api_guard(svc.check_update_now)

        def payload():
            from .. import updater

            return updater.check_update(cfg)

        return _api_guard(payload)

    @app.post("/api/live/update-install")
    def api_live_update_install():
        """دریافت و نصبِ نسخه‌ی جدید (فقط آغاز می‌شود؛ پیشرفت با /api/update)."""
        def payload():
            from .. import updater

            return updater.update_async(cfg)

        return _api_guard(payload)

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
