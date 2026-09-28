"""نرمال‌سازی متن و اعداد فارسی (تبدیل ارقام، پارس بودجه، مهلت، تعداد پیشنهادها)."""

from __future__ import annotations

import re

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"

_DIGIT_MAP = str.maketrans(PERSIAN_DIGITS + ARABIC_DIGITS, "0123456789" * 2)
_CHAR_MAP = str.maketrans({
    "ي": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه", "ؤ": "و",
    "إ": "ا", "أ": "ا", "آ": "آ", "ء": "", "ـ": "",
})

NUM = r"[0-9۰-۹٠-٩][0-9۰-۹٠-٩,\u066C\u060C.\s]*"

_PERSIAN_NUMBER_WORDS = {
    "یک": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5, "شش": 6,
    "هفت": 7, "هشت": 8, "نه": 9, "ده": 10, "چند": 3, "دو یا چند": 2,
}

UNIT_DAYS = {"ساعت": 1 / 24, "روز": 1, "هفته": 7, "ماه": 30}


def to_digits(text: str) -> str:
    return (text or "").translate(_DIGIT_MAP)


def normalize_chars(text: str) -> str:
    return (text or "").translate(_CHAR_MAP)


def clean_text(text: str) -> str:
    """نرمال‌سازی فاصله‌ها و نویسه‌های عربی/فارسی."""
    s = normalize_chars(text or "")
    s = s.replace("\u200c", " ").replace("\u200d", "").replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" ?\n ?", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _strip_separators(num_str: str) -> str:
    return re.sub(r"[,\u066C\u060C\s]", "", to_digits(num_str))


def parse_int(text) -> int | None:
    """اولین عدد داخل متن را به int برمی‌گرداند."""
    if text is None:
        return None
    m = re.search(NUM, str(text))
    if not m:
        return None
    raw = _strip_separators(m.group(0)).rstrip(".")
    if "." in raw:  # اعشاری
        try:
            return int(float(raw))
        except ValueError:
            return None
    return int(raw) if raw.isdigit() else None


def parse_toman(text: str) -> int | None:
    """استخراج مبلغ به تومان (پشتیبانی از تومان/ریال/میلیون/میلیارد)."""
    if not text:
        return None
    t = to_digits(clean_text(str(text)))

    m = re.search(r"(" + NUM + r")\s*(میلیارد|میلیون|هزار)\s*(?:تومان|تومن)?", t)
    if m:
        value = parse_int(m.group(1))
        if value is None:
            return None
        mult = {"هزار": 1_000, "میلیون": 1_000_000, "میلیارد": 1_000_000_000}[m.group(2)]
        return value * mult

    m = re.search(r"(" + NUM + r")\s*(?:تومان|تومن)", t)
    if m:
        return parse_int(m.group(1))

    m = re.search(r"(" + NUM + r")\s*(?:ریال|ريال)", t)
    if m:
        value = parse_int(m.group(1))
        return value // 10 if value else None

    return None


def parse_budget(text: str) -> int | None:
    """بودجه‌ی کارفرما را از متن کارت پروژه استخراج می‌کند."""
    if not text:
        return None
    t = clean_text(str(text))
    # «بودجه کارفرمابودجه 300,000,000 تومان» / «بودجه ۴,۵۰۰,۰۰۰ تومان»
    m = re.findall(r"بودجه[^\d۰-۹٠-٩]{0,40}?(" + NUM + r")\s*(?:تومان|تومن)", t)
    if m:
        return parse_int(m[-1])
    m = re.search(r"بودجه[^\d۰-۹٠-٩]{0,40}?(" + NUM + r")\s*(میلیون|میلیارد)", t)
    if m:
        return parse_toman(m.group(0))
    # fallback: هر عددی که با تومان آمده باشد
    m = re.findall(r"(" + NUM + r")\s*(?:تومان|تومن)", t)
    if m:
        return parse_int(m[-1])
    return None


def parse_duration_days(text: str) -> float | None:
    """زمان پیشنهادی/مهلت را به روز تبدیل می‌کند (مثلاً «۱۵ روز»، «۳ هفته»)."""
    if not text:
        return None
    t = to_digits(clean_text(str(text)))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(ساعت|روز|هفته|ماه)", t)
    if not m:
        return None
    try:
        value = float(m.group(1))
    except ValueError:
        return None
    return round(value * UNIT_DAYS[m.group(2)], 2)


def parse_deadline_days(text: str) -> float | None:
    """مهلت باقیمانده برای ارسال پیشنهاد، مثل «۱۴ روز و ۱۳ ساعت»."""
    if not text:
        return None
    t = to_digits(clean_text(str(text)))
    if "بی\u200cنهایت" in t or "بینهایت" in t:
        return None
    m = re.search(r"(\d+)\s*روز(?:\s*و\s*(\d+)\s*ساعت)?", t)
    if not m:
        return parse_duration_days(t)
    days = int(m.group(1))
    hours = int(m.group(2)) if m.group(2) else 0
    return round(days + hours / 24, 2)


def parse_bids(text: str) -> int | None:
    """تعداد پیشنهادهای ثبت‌شده روی پروژه."""
    if not text:
        return None
    t = to_digits(clean_text(str(text)))
    m = re.search(r"پیشنهادها\s*(\d+)", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*پیشنهاد", t)
    if m:
        return int(m.group(1))
    return None


def parse_posted_at(text: str) -> str | None:
    """زمان انتشار آگهی، مثل «۷ ساعت پیش» (اعداد به فارسی نمایش داده می‌شوند)."""
    if not text:
        return None
    t = clean_text(str(text))
    m = re.search(r"(?:حدود\s*)?(\d+)\s*(دقیقه|ساعت|روز|هفته|ماه)\s*پیش", to_digits(t))
    if m:
        return f"{to_persian_digits(m.group(1))} {m.group(2)} پیش"
    return None


def to_persian_digits(value) -> str:
    """تبدیل ارقام انگلیسی به فارسی (برای نمایش در رابط کاربری)."""
    table = str.maketrans("0123456789", PERSIAN_DIGITS)
    return str(value).translate(table)


def parse_language_count(text: str) -> int:
    """تعداد زبان‌های درخواستی سایت (دو زبانه، ۴ زبانه، ...)."""
    t = clean_text(str(text or ""))
    m = re.search(r"(\d+)\s*زبانه", to_digits(t))
    if m:
        return int(m.group(1))
    m = re.search(r"(دو|سه|چهار|پنج|شش|هفت|هشت|ده|چند)\s*زبانه", t)
    if m:
        return _PERSIAN_NUMBER_WORDS.get(m.group(1), 2)
    m = re.search(r"(?:افزودن|اضافه کردن)\s*(?:زبان|زبان‌های)?\s*(\w+)", t)
    if m and "زبان" in t:
        return 2
    return 1


def parse_page_count(text: str) -> int | None:
    """تعداد صفحات سایت اگر در متن آمده باشد (مثلاً «۲۰ الی ۴۰ صفحه»)."""
    t = to_digits(clean_text(str(text or "")))
    m = re.search(r"(\d+)\s*(?:الی|تا|-)\s*(\d+)\s*صفحه", t)
    if m:
        return (int(m.group(1)) + int(m.group(2))) // 2
    m = re.search(r"(\d+)\s*صفحه", t)
    if m:
        return int(m.group(1))
    return None


def extract_bullets(text: str) -> list[str]:
    """خطوط بولت‌دار توضیحات پروژه را استخراج می‌کند."""
    out: list[str] = []
    for raw_line in (text or "").splitlines():
        line = clean_text(raw_line)
        if not line:
            continue
        if re.match(r"^(?:•|-|\*|–|—|▪|\u2022)\s*", line):
            item = re.sub(r"^(?:•|-|\*|–|—|▪|\u2022)\s*", "", line)
        elif re.match(r"^[\u06F0-\u06F90-9]{1,2}[.)]\s+", line):
            item = re.sub(r"^[\u06F0-\u06F90-9]{1,2}[.)]\s+", "", line)
        else:
            continue
        item = clean_text(item)
        if 3 <= len(item) <= 220:
            out.append(item)
    return out


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[\.\u06D4!\?])\s+|\n+", clean_text(text or ""))
    return [clean_text(p) for p in parts if len(clean_text(p)) > 20]


def toman(amount: int | None) -> str:
    """نمایش مبلغ با جداکننده‌ی هزارگان."""
    if amount is None:
        return "نامشخص"
    return f"{int(amount):,}".replace(",", ",")


def persian_number(value) -> str:
    return to_digits(str(value))


def slugify(text: str, fallback: str = "project") -> str:
    s = clean_text(text or "").lower()
    s = re.sub(r"[^\w\u0600-\u06FF]+", "-", s, flags=re.UNICODE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:60] or fallback
