"""رابط گرافیکی (ویندوز) برای فریلنس‌یار آرنا.

این فایل برای ساخت frilanser-gui.exe استفاده می‌شود: کاربر روی آن دوبار کلیک
می‌کند و یک پنجره با دکمه‌های فارسی باز می‌شود؛ نیازی به خط فرمان نیست.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

# اجرا از پوشه‌ی پرتابل: اگر کنار برنامه config.toml هست، همان‌جا می‌مانیم
if getattr(sys, "frozen", False):
    _exe_dir = Path(sys.executable).resolve().parent
    if (_exe_dir / "config.toml").exists() and os.access(_exe_dir, os.W_OK):
        os.chdir(_exe_dir)

if sys.stdout is None:  # حالت windowed
    sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")

from frilanser.cli import main as cli_main  # noqa: E402

MSG_QUEUE: "queue.Queue[str]" = queue.Queue()
DONE = "--پایان--"


class _Writer:
    """خروجی برنامه را به پنجره هدایت می‌کند."""

    def write(self, text: str) -> int:
        if text:
            MSG_QUEUE.put(text)
        return len(text)

    def flush(self) -> None:  # pragma: no cover
        pass

    def reconfigure(self, **_kwargs) -> None:  # سازگار با تابع UTF-8 برنامه
        pass

    def isatty(self) -> bool:
        return False


def build_window():
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("فریلنس‌یار آرنا")
    root.geometry("860x620")
    root.minsize(760, 520)
    try:
        root.call("tk", "scaling", 1.2)
    except tk.TclError:  # pragma: no cover
        pass

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:  # pragma: no cover
        pass

    top = tk.Frame(root, bg="#1e3a8a", height=74)
    top.pack(fill="x")
    tk.Label(top, text="فریلنس‌یار آرنا", bg="#1e3a8a", fg="#ffffff",
             font=("Segoe UI", 17, "bold")).pack(anchor="center", pady=6)
    tk.Label(top, text="پیدا کردن پروژه، ساخت پیش‌نمایش و آماده‌سازی پیشنهاد",
             bg="#1e3a8a", fg="#c7d2fe", font=("Segoe UI", 10)).pack()

    bar = tk.Frame(root, bg="#f4f6fb")
    bar.pack(fill="x", padx=10, pady=8)

    log_frame = tk.Frame(root)
    log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    text = tk.Text(log_frame, wrap="word", font=("Consolas", 10), bg="#0f172a", fg="#d7e3ff",
                   insertbackground="#d7e3ff", relief="flat")
    scroll = ttk.Scrollbar(log_frame, command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)

    status = tk.Label(root, text="آماده", anchor="w", bg="#e5e9f5", fg="#334155",
                      font=("Segoe UI", 9))
    status.pack(fill="x", side="bottom")

    buttons: list[ttk.Button] = []

    def say(msg: str) -> None:
        MSG_QUEUE.put(msg + "\n")

    def pump() -> None:
        try:
            while True:
                chunk = MSG_QUEUE.get_nowait()
                if chunk == DONE:
                    set_busy(False)
                    continue
                text.insert("end", chunk)
                text.see("end")
        except queue.Empty:
            pass
        root.after(120, pump)

    def set_busy(busy: bool) -> None:
        for b in buttons:
            b.configure(state="disabled" if busy else "normal")
        status.configure(text="در حال اجرا…" if busy else "آماده")
        root.update_idletasks()

    def run_cli(args: list[str]) -> None:
        if busy_flag["on"]:
            return
        set_busy(True)
        busy_flag["on"] = True

        def target():
            old_out, old_err = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = _Writer()
            try:
                code = cli_main(args)
                if code == 0:
                    try:
                        from frilanser.config import load_config
                        from frilanser.store import Store

                        st = Store(load_config().data_dir)
                        allp = st.all()
                        cand = [p for p in allp if p.verdict == "candidate"]
                        demos = [p for p in allp if p.demo]
                        say(f"\n✔ پایان اجرا — {len(allp)} آگهی، "
                            f"{len(cand)} کاندیدا، {len(demos)} پیش‌نمایش ساخته شد.")
                        say("برای دیدن نتایج روی «داشبورد در مرورگر» کلیک کنید.")
                    except Exception as exc:  # noqa: BLE001
                        say(f"\n✔ پایان اجرا ({exc})")
                else:
                    say(f"\n⚠ اجرا با کد {code} تمام شد؛ گزارش بالا را بخوانید "
                        f"(در صورت نیاز دکمه‌ی عیب‌یابی را بزنید).")
            except Exception as exc:  # noqa: BLE001
                say(f"\n✖ خطا: {exc}")
            finally:
                sys.stdout, sys.stderr = old_out, old_err
                MSG_QUEUE.put(DONE)
                busy_flag["on"] = False

        threading.Thread(target=target, daemon=True).start()

    busy_flag = {"on": False}

    def open_path(path: Path, what: str) -> None:
        try:
            if Path(path).exists():
                os.startfile(str(path))  # noqa: S606 - فقط روی ویندوز
            else:
                say(f"مسیر پیدا نشد ({what}): {path}")
        except Exception as exc:  # noqa: BLE001
            say(f"خطا در باز کردن {what}: {exc}")

    def paths():
        try:
            from frilanser.config import load_config
        except Exception:  # noqa: BLE001
            return Path.cwd(), Path.cwd() / "outbox", Path.cwd() / "outbox" / "reports"
        cfg = load_config()
        return cfg.root, cfg.outbox_dir, cfg.report_dir

    def open_outbox() -> None:
        _, outbox, _ = paths()
        open_path(outbox, "پوشه‌ی خروجی")

    def open_report() -> None:
        _, _, reports = paths()
        latest = reports / "latest.md"
        open_path(latest if latest.exists() else reports, "گزارش")

    def open_folder() -> None:
        root_dir, _, _ = paths()
        open_path(root_dir, "پوشه‌ی برنامه")

    server = {"running": False}

    def start_dashboard() -> None:
        if server["running"]:
            webbrowser.open("http://127.0.0.1:5000")
            return

        def target():
            try:
                from frilanser.config import load_config
                from frilanser.store import Store
                from frilanser.web.app import create_app

                cfg = load_config()
                app = create_app(cfg, Store(cfg.data_dir))
                say("داشبورد روی http://127.0.0.1:5000 در حال اجراست…")
                server["running"] = True
                app.run(host="127.0.0.1", port=5000, debug=False, threaded=True, use_reloader=False)
            except Exception as exc:  # noqa: BLE001
                say(f"خطا در اجرای داشبورد: {exc}")

        threading.Thread(target=target, daemon=True).start()
        root.after(1200, lambda: webbrowser.open("http://127.0.0.1:5000"))

    def check_update() -> None:
        """بررسی و نصب آخرین نسخه از داخل برنامه (بدون مراجعه به گیت‌هاب)."""
        def worker() -> None:
            try:
                from frilanser import updater
                from frilanser.config import load_config
                from frilanser.version import __version__

                cfg = load_config()
                say(f"نسخه‌ی فعلی: {__version__} — در حال بررسی…\n")
                info = updater.check_update(cfg)
                if not info["ok"]:
                    say(f"بررسی ناموفق بود: {info['error']}\n")
                    return
                if not info["has_update"]:
                    say(f"برنامه به‌روز است (آخرین نسخه: {info['latest']}) ✓\n")
                    return
                say(f"نسخه‌ی جدید {info['latest']} پیدا شد؛ در حال دریافت…\n")
                res = updater.update(cfg)
                if res.get("ok"):
                    say(f"{res.get('message') or 'به‌روزرسانی انجام شد'}\n")
                    if res.get("downloaded"):
                        say(f"فایل: {res['downloaded']}\n")
                else:
                    say(f"به‌روزرسانی ناموفق بود: {res.get('error') or res.get('message', '')}\n")
            except Exception as exc:  # noqa: BLE001
                say(f"خطا در به‌روزرسانی: {exc}\n")

        threading.Thread(target=worker, daemon=True).start()

    def open_cmd() -> None:
        exe = Path(sys.executable).with_name("frilanser.exe")
        if getattr(sys, "frozen", False) and exe.exists():
            subprocess.Popen(["cmd", "/k", str(exe), "--help"], cwd=str(exe.parent))
        else:  # حالت توسعه
            subprocess.Popen(["cmd", "/k", "python", "-m", "frilanser", "--help"])

    specs = [
        ("▶  اجرای کامل (اسکن + پیش‌نمایش + گزارش)", lambda: run_cli(["run"])),
        ("🌐  دریافت زنده از سایت‌ها", lambda: run_cli(["run", "--online"])),
        ("🖥  داشبورد در مرورگر", start_dashboard),
        ("📋  کارهایی که باید خودم انجام دهم", lambda: run_cli(["needs", "--full"])),
        ("🔄  به‌روزرسانی برنامه", check_update),
        ("📁  باز کردن پوشه‌ی خروجی", open_outbox),
        ("📄  باز کردن آخرین گزارش", open_report),
        ("📂  پوشه‌ی برنامه", open_folder),
        ("🩺  عیب‌یابی (چرا داده نمی‌آید؟)", lambda: run_cli(["doctor"])),
        ("⌨  خط فرمان (CLI)", open_cmd),
    ]
    for label, cmd in specs:
        btn = ttk.Button(bar, text=label, command=cmd)
        btn.pack(side="left", padx=4, pady=4)
        buttons.append(btn)

    def count_projects() -> int:
        try:
            from frilanser.config import load_config
            from frilanser.store import Store

            return len(Store(load_config().data_dir).all())
        except Exception:  # noqa: BLE001
            return -1

    def first_start() -> None:
        n = count_projects()
        if n == 0:
            say("هیچ داده‌ای در برنامه نیست؛ اسکن خودکار شروع می‌شود…\n")
            root.after(300, lambda: run_cli(["run"]))
        elif n > 0:
            say(f"{n} آگهی در برنامه وجود دارد. برای تازه‌سازی «اجرای کامل» را بزنید.\n")

    say("به فریلنس‌یار آرنا خوش آمدید.\n"
        "دکمه‌ی «اجرای کامل» آگهی‌ها را می‌خواند، غربال می‌کند و پیش‌نمایش می‌سازد؛\n"
        "نتیجه در همین پنجره نمایش داده می‌شود و در داشبورد هم می‌بینید.\n")
    pump()
    root.after(500, first_start)
    root.after(900, start_dashboard)
    return root


def main() -> int:
    try:
        root = build_window()
        root.mainloop()
    except Exception as exc:  # noqa: BLE001
        print(f"خطا در اجرای رابط گرافیکی: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
