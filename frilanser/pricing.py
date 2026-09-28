"""محاسبه‌ی قیمت پیشنهادی و ساخت متن آماده‌ی پیشنهاد (پروپوزال) برای ثبت در سایت."""

from __future__ import annotations

import math

from .config import Config
from .models import Project
from .normalize import clean_text, split_sentences


def _round_to(value: float, step: int) -> int:
    return int(math.ceil(value / step) * step)


def quick_price(cfg: Config, hours: float, category: str) -> int:
    """برآورد سریع قیمت (برای استفاده در غربالگری، پیش از محاسبه‌ی کامل)."""
    mult = cfg.complexity(category)
    return max(cfg.min_price,
               int(math.ceil(hours * cfg.hourly_rate * mult
                             * (1 + cfg.commission + cfg.risk_buffer) / cfg.round_to)
                   * cfg.round_to))


def build_questions(project: Project, screening: dict) -> list[str]:
    """سوالات کلیدی که باید همراه پیشنهاد از کارفرما پرسیده شود."""
    questions: list[str] = []
    cat = screening.get("category")
    text = f"{project.title} {project.description}"

    if any(n["kind"] == "provide_access" for n in screening.get("needs_you", [])):
        questions.append("برای شروع، دسترسی‌های مورد نیاز (سایت/هاست/مخزن کد/پنل) چگونه در اختیارم قرار می‌گیرد؟")
    if cat in ("web_app", "landing", "plugin_cms"):
        questions.append("محتوا، تصاویر و متن‌های هر صفحه را شما تامین می‌کنید یا باید نمونه‌ی اولیه آماده کنم؟")
        questions.append("هدف اصلی سایت چیست؟ (جذب سرنخ/فروش آنلاین/معرفی خدمات)")
        questions.append("تحویل به‌صورت سایت اختصاصی سبک مدنظر است یا قالب/افزونه‌ی وردپرس؟")
    if cat == "data_pipeline":
        questions.append("فرمت دقیق خروجی مدنظر چیست؟ (JSON با چه ساختاری / Markdown / CSV)")
        questions.append("دقت مورد انتظار برای فرمول‌ها و جداول چه مقدار است و چگونه سنجیده می‌شود؟")
        questions.append("آیا یک نمونه فایل برای اجرای آزمایشی ارسال می‌کنید؟")
    if cat == "bot":
        questions.append("ربات روی کدام پلتفرم اجرا می‌شود و توکن/دسترسی چگونه تامین می‌گردد؟")
    if cat == "ai_app":
        questions.append("کلید API مدل زبانی را شما تامین می‌کنید یا باید در هزینه لحاظ شود؟")
    if cat in ("dashboard", "automation"):
        questions.append("منبع داده‌ها چیست؟ (فایل، پایگاه داده، یا API)")
    if cat == "data_entry":
        questions.append("آیا تماس تلفنی با سازمان‌ها هم لازم است یا فقط جستجوی اینترنتی کافی است؟")
    if screening.get("deadline_pressure"):
        questions.append("زمان پیشنهادی کارفرما کوتاه‌تر از برآورد من است؛ امکان افزایش مهلت وجود دارد؟")
    if not project.budget_toman:
        questions.append("سقف بودجه‌ی در نظر گرفته‌شده برای این پروژه چقدر است؟")

    text_l = text.lower()
    if "سئو" in text_l:
        questions.append("آیا دسترسی به Google Search Console و آنالیتیکس داده می‌شود؟")
    return questions[:6]


def propose(project: Project, screening: dict, cfg: Config, demo_url: str | None = None) -> dict:
    """قیمت پیشنهادی، مراحل پرداخت و متن پیشنهاد را می‌سازد."""
    hours = float(screening.get("est_hours", 12))
    rate = cfg.hourly_rate
    mult = cfg.complexity(screening.get("category", "other"))

    base_price = hours * rate * mult
    adjusted = base_price * (1 + cfg.commission + cfg.risk_buffer)
    price = max(cfg.min_price, _round_to(adjusted, cfg.round_to))

    budget = project.budget_toman
    ratio = (budget / price) if budget else None
    anchor_share = float(cfg.pricing.get("anchor_budget_share", 0.70))

    pricing_notes: list[str] = [
        f"{hours:g} ساعت × {rate:,} تومان × ضریب پیچیدگی {mult:g} = {base_price:,.0f} تومان",
        f"با احتساب کمیسیون پلتفرم ({cfg.commission:.0%}) و حاشیه‌ی ریسک ({cfg.risk_buffer:.0%}) = {adjusted:,.0f} تومان",
    ]

    final_price = price
    budget_verdict = "unknown"
    if ratio is not None:
        if ratio >= 2:
            anchored = _round_to(min(budget * anchor_share, price * 2.5), cfg.round_to)
            if anchored > final_price:
                pricing_notes.append(
                    f"بودجه‌ی کارفرما ({budget:,} تومان) بسیار بالاتر از برآورد زمانی است؛ "
                    f"قیمت‌گذاری ارزش‌محور انجام شد ({anchored:,} تومان)"
                )
                final_price = anchored
            budget_verdict = "excellent"
        elif ratio >= 1.35:
            final_price = _round_to(min(budget * anchor_share, price * 1.4), cfg.round_to)
            pricing_notes.append(
                f"بودجه‌ی کارفرما از برآورد بیشتر است؛ قیمت با نگاه رقابتی "
                f"({final_price:,} تومان) تنظیم شد"
            )
            budget_verdict = "good"
        elif ratio >= 0.95:
            budget_verdict = "ok"
            pricing_notes.append("بودجه‌ی کارفرما با برآورد هم‌خوان است")
        elif ratio >= 0.75:
            budget_verdict = "negotiate"
            pricing_notes.append(
                f"بودجه ({budget:,} تومان) حدود {(1 - ratio) * 100:.0f}٪ کمتر از برآورد است — "
                f"یا محدوده کاهش یابد یا مبلغ به {final_price:,} تومان نزدیک شود"
            )
        else:
            budget_verdict = "low"
            pricing_notes.append(
                f"بودجه ({budget:,} تومان) بسیار کمتر از برآورد ({final_price:,} تومان) است"
            )
    else:
        pricing_notes.append("بودجه اعلام نشده؛ قیمت بر اساس برآورد زمان اعلام می‌شود")

    # پیشنهاد جایگزین در صورت کم بودن بودجه
    alternative = None
    if budget and ratio is not None and ratio < 0.95:
        fit_hours = max(2, round(hours * ratio * 0.95, 1))
        alternative = {
            "hours": fit_hours,
            "price": _round_to(budget * 0.98, cfg.round_to),
            "note": f"اجرای محدوده‌ی کاهش‌یافته در حدود {fit_hours:g} ساعت با مبلغ {_round_to(budget * 0.98, cfg.round_to):,} تومان",
        }

    if final_price < 8_000_000:
        milestones = [
            {"title": "پیش‌پرداخت", "share": 0.5, "when": "هنگام شروع پروژه (از طریق پلتفرم)"},
            {"title": "تسویه نهایی", "share": 0.5, "when": "پس از تحویل و تایید"},
        ]
    else:
        milestones = [
            {"title": "پیش‌پرداخت", "share": 0.4, "when": "هنگام شروع پروژه (از طریق پلتفرم)"},
            {"title": "پس از تحویل نسخه‌ی اولیه", "share": 0.3, "when": "تحویل دموی قابل استفاده"},
            {"title": "تسویه نهایی", "share": 0.3, "when": "پس از تایید نهایی"},
        ]

    questions = build_questions(project, screening)
    deliverables = screening.get("deliverables") or ["خروجی نهایی پروژه", "مستندات تحویل"]
    schedule_days = screening.get("schedule_days") or math.ceil(hours / cfg.work_hours_per_day)

    proposal_text = render_proposal(
        project=project,
        screening=screening,
        price=final_price,
        hours=hours,
        schedule_days=schedule_days,
        deliverables=deliverables,
        milestones=milestones,
        questions=questions,
        demo_url=demo_url,
        tech=screening.get("tech", []),
    )

    return {
        "hours": hours,
        "hourly_rate": rate,
        "complexity_multiplier": mult,
        "base_price": int(base_price),
        "price": final_price,
        "floor_price": price,
        "client_budget": budget,
        "budget_ratio": round(ratio, 2) if ratio else None,
        "budget_verdict": budget_verdict,
        "pricing_notes": pricing_notes,
        "alternative": alternative,
        "milestones": milestones,
        "deliverables": deliverables,
        "questions": questions,
        "proposal_text": proposal_text,
        "demo_url": demo_url,
        "schedule_days": schedule_days,
    }


def render_proposal(
    project: Project,
    screening: dict,
    price: int,
    hours: float,
    schedule_days: int,
    deliverables: list[str],
    milestones: list[dict],
    questions: list[str],
    tech: list[str],
    demo_url: str | None,
) -> str:
    """متن فارسی آماده برای کپی و ثبت به‌عنوان پیشنهاد در سایت."""
    sentences = split_sentences(project.description)
    summary = sentences[0] if sentences else clean_text(project.description)[:180]
    if len(summary) > 220:
        summary = summary[:217].rstrip() + "…"

    approach = " + ".join(tech) if tech else "طبق نیازمندی‌های پروژه"
    deliv = "\n".join(f"  - {d}" for d in deliverables)
    mile = "\n".join(
        f"  - {m['title']}: {int(m['share'] * 100)}٪ — {m['when']}" for m in milestones
    )
    q_text = "\n".join(f"  {i}. {q}" for i, q in enumerate(questions, 1)) or "  (سوال خاصی نیست)"

    lines = [
        f"سلام و احترام،",
        f"پروژه‌ی «{project.title}» را با دقت مطالعه کردم. برداشت من این است: {summary}",
        "",
        "رویکرد پیشنهادی:",
        f"  {approach}",
        "",
        "خروجی‌هایی که تحویل می‌دهم:",
        deliv,
        "",
        f"زمان‌بندی: حدود {hours:g} ساعت کار ({schedule_days} روز کاری)",
        f"مبلغ پیشنهادی: {price:,} تومان",
        "نحوه‌ی پرداخت (از طریق همین پلتفرم برای امنیت طرفین):",
        mile,
        "",
    ]
    if demo_url:
        lines += [
            "نمونه‌ی اولیه:",
            f"  برای این پروژه یک نسخه‌ی نمونه/دمو آماده کرده‌ام که می‌توانید همین حالا ببینید:",
            f"  {demo_url}",
            "",
        ]
    lines += [
        "چند سوال برای شروع دقیق‌تر:",
        q_text,
        "",
        "پیش از شروع، خروجیِ مرحله‌به‌مرحله را با شما به اشتراک می‌گذارم تا در مسیر اصلاح شود.",
        "با احترام",
    ]
    return "\n".join(lines)


def propose_all(projects: list[Project], cfg: Config, demo_dir: str | None = None) -> None:
    for p in projects:
        if not p.screening:
            continue
        demo_url = None
        if p.demo and p.demo.get("url"):
            demo_url = p.demo["url"]
        p.proposal = propose(p, p.screening, cfg, demo_url=demo_url)
