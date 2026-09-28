"""ساخت دموی تعاملی (یک فایل HTML مستقل) برای هر پروژه‌ی کاندید.

هر دمو:
  - راست‌چین و فارسی است و با داده‌های نمونه کار می‌کند
  - امکانات اصلیِ خروجی پروژه را به‌صورت واقعی و قابل کلیک نشان می‌دهد
  - برآورد زمان، قیمت پیشنهادی و برنامه‌ی تحویل را هم نمایش می‌دهد
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import Project
from .normalize import clean_text, slugify

CSS = """
*{box-sizing:border-box}
body{margin:0;background:#f5f6fb;color:#1d2130;font-family:"Vazirmatn","IRANSans","B Nazanin",Tahoma,"Segoe UI",sans-serif;direction:rtl;line-height:1.9;font-size:15px}
a{color:#3b5bdb;text-decoration:none}
.wrap{max-width:1080px;margin:0 auto;padding:0 18px 60px}
header.hero{background:linear-gradient(120deg,#2b3a67 0%,#3b5bdb 55%,#22b8cf 100%);color:#fff;padding:34px 0 30px;box-shadow:0 8px 30px rgba(43,58,103,.25)}
header.hero .wrap{padding-bottom:0}
.eyebrow{font-size:12.5px;opacity:.85;letter-spacing:.3px}
header.hero h1{margin:6px 0 10px;font-size:26px;line-height:1.5}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.chip{background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.25);padding:4px 12px;border-radius:999px;font-size:12.5px;backdrop-filter:blur(4px)}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:22px 0 8px}
.meta .box{background:#fff;border:1px solid #e5e8f0;border-radius:14px;padding:12px 14px}
.meta .box .k{font-size:12px;color:#6b7280}
.meta .box .v{font-weight:700;font-size:17px;margin-top:2px}
.notice{background:#fff8e6;border:1px solid #ffe08a;color:#7a5b00;border-radius:12px;padding:10px 14px;font-size:13px;margin:18px 0}
.card{background:#fff;border:1px solid #e5e8f0;border-radius:16px;padding:18px;margin-bottom:16px;box-shadow:0 2px 10px rgba(20,30,60,.04)}
.card h2{margin:0 0 12px;font-size:18px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
.feat{background:#f8f9fe;border:1px solid #e6e9f5;border-radius:12px;padding:14px}
.feat .t{font-weight:700;margin-bottom:4px}
.feat .d{color:#5b6478;font-size:13.5px}
.nav{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0}
.nav button{background:#fff;border:1px solid #d9deeb;border-radius:999px;padding:7px 16px;cursor:pointer;font:inherit;font-size:13.5px;color:#39405a}
.nav button.active{background:#3b5bdb;border-color:#3b5bdb;color:#fff}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{padding:9px 10px;border-bottom:1px solid #eceff7;text-align:right}
th{background:#f3f5fb;color:#4a5578;font-size:12.5px;white-space:nowrap}
tr:hover td{background:#fafbff}
input,select,textarea{font:inherit;padding:9px 12px;border:1px solid #d9deeb;border-radius:10px;width:100%;background:#fff;color:#1d2130}
.btn{background:#3b5bdb;color:#fff;border:0;border-radius:10px;padding:10px 18px;font:inherit;cursor:pointer}
.btn:hover{filter:brightness(1.07)}
.btn.ghost{background:#fff;color:#3b5bdb;border:1px solid #c9d2f0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.kpi{background:linear-gradient(160deg,#fff,#f4f6fd);border:1px solid #e5e8f0;border-radius:14px;padding:14px}
.kpi .k{font-size:12.5px;color:#6b7280}
.kpi .v{font-size:24px;font-weight:800;margin-top:2px}
.kpi .d{font-size:12px;color:#22a06b}
.bar{fill:url(#g)}
.rowflex{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.muted{color:#6b7280;font-size:13px}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;border:1px solid}
.b-ok{background:#e7f8ef;color:#1a7f4b;border-color:#b7e6cd}
.b-wait{background:#fff4e0;color:#8a5a00;border-color:#ffe0a8}
.b-run{background:#e8f0ff;color:#2b4cb8;border-color:#c5d5ff}
.b-bad{background:#fdeaea;color:#a02626;border-color:#f6c9c9}
.log{background:#111827;color:#c8f0d8;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;border-radius:12px;padding:12px;height:150px;overflow:auto;line-height:1.7}
.progress{height:9px;background:#e9edf7;border-radius:999px;overflow:hidden;margin:10px 0}
.progress i{display:block;height:100%;width:0;background:linear-gradient(90deg,#3b5bdb,#22b8cf);transition:width .25s}
.drop{border:2px dashed #c9d2f0;border-radius:14px;padding:26px;text-align:center;background:#fbfcff;cursor:pointer}
.drop.hover{background:#eef3ff;border-color:#3b5bdb}
pre.json{background:#0f172a;color:#d7e3ff;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;border-radius:12px;padding:14px;overflow:auto;max-height:260px;text-align:left;direction:ltr}
.phone{max-width:420px;margin:0 auto;background:#fff;border:14px solid #1d2130;border-radius:34px;overflow:hidden}
.chat{height:360px;overflow:auto;padding:12px;background:#eef1f8}
.msg{margin:6px 0;padding:8px 12px;border-radius:14px;max-width:78%;font-size:13.5px;line-height:1.8}
.me{background:#3b5bdb;color:#fff;margin-left:auto;border-bottom-left-radius:4px}
.you{background:#fff;border:1px solid #e2e7f2;border-bottom-right-radius:4px}
.steps{counter-reset:s}
.step{position:relative;padding:0 34px 16px 0;border-right:2px solid #e3e8f5}
.step:last-child{border-right-color:transparent}
.step:before{counter-increment:s;content:counter(s);position:absolute;right:-13px;top:0;width:24px;height:24px;border-radius:50%;background:#3b5bdb;color:#fff;font-size:12px;display:flex;align-items:center;justify-content:center}
footer.foot{border-top:1px solid #e5e8f0;margin-top:26px;padding-top:16px;color:#6b7280;font-size:12.5px}
@media(max-width:640px){header.hero h1{font-size:20px}.wrap{padding:0 12px 40px}}
"""

# ---------------------------------------------------------------- JS snippets
JS_PIPELINE = """
const FILES = __DATA__;
const zone = document.getElementById('zone');
const list = document.getElementById('filelist');
const runBtn = document.getElementById('run');
const bar = document.querySelector('.progress i');
const log = document.getElementById('log');
const results = document.getElementById('results');
const tbody = document.getElementById('tbody');
const jsonBox = document.getElementById('jsonbox');
let selected = FILES.slice(0,3);

function renderList(){
  list.innerHTML = FILES.map((f,i)=>`<tr>
    <td><input type="checkbox" data-i="${i}" ${selected.includes(f)?'checked':''}></td>
    <td>${f.name}</td><td>${f.size}</td><td>${f.pages} صفحه</td>
    <td><span class="badge ${f.badge}">${f.status}</span></td></tr>`).join('');
  list.querySelectorAll('input').forEach(cb=>cb.onchange=()=>{
    const f = FILES[+cb.dataset.i];
    selected = cb.checked ? [...selected, f] : selected.filter(x=>x!==f);
  });
}
renderList();
zone.onclick = ()=>{ const f = FILES[(Math.random()*FILES.length)|0]; if(!selected.includes(f)){selected.push(f);renderList();} };
zone.ondragover = e=>{e.preventDefault();zone.classList.add('hover')};
zone.ondragleave = ()=>zone.classList.remove('hover');
zone.ondrop = e=>{e.preventDefault();zone.classList.remove('hover');
  const f = FILES[(Math.random()*FILES.length)|0]; if(!selected.includes(f)){selected.push(f);} renderList();};

function say(t){ log.innerHTML += '<div>› '+t+'</div>'; log.scrollTop = log.scrollHeight; }
runBtn.onclick = ()=>{
  if(!selected.length){ say('هیچ فایلی انتخاب نشده است.'); return; }
  runBtn.disabled = true; results.style.display='none'; log.innerHTML=''; bar.style.width='0%';
  let p = 0, i = 0;
  say('شروع پردازش روی '+selected.length+' فایل…');
  const steps = ['خواندن فایل و تشخیص ساختار','استخراج متن و حفظ ترتیب پاراگراف‌ها',
    'استخراج جداول و تبدیل به JSON','شناسایی و ذخیره فرمول‌ها','خروجی تصاویر با کیفیت اصلی',
    'کنترل کیفیت و تولید گزارش'];
  const timer = setInterval(()=>{
    p += 4 + Math.random()*7;
    bar.style.width = Math.min(100,p)+'%';
    if(p > (i+1)*(100/steps.length) && i < steps.length){ say(steps[i]); i++; }
    if(p >= 100){
      clearInterval(timer);
      say('پردازش با موفقیت پایان یافت ✅');
      tbody.innerHTML = selected.map(f=>`<tr>
        <td>${f.name}</td><td>${f.pages}</td><td>${f.tables}</td><td>${f.formulas}</td><td>${f.images}</td>
        <td><span class="badge b-ok">${f.acc}٪ دقت</span></td>
        <td><button class="btn ghost" onclick="document.getElementById('jsonbox').style.display='block';document.getElementById('jsonbox').scrollIntoView({behavior:'smooth'})">JSON</button></td></tr>`).join('');
      results.style.display='block'; runBtn.disabled=false;
      window.__lastFiles = selected;
      jsonBox.textContent = JSON.stringify({
        source: selected.map(f=>f.name),
        output_format: "json",
        items: selected.map(f=>({
          file: f.name, pages: f.pages,
          chapters: [{title:"فصل اول", paragraphs: 42, tables: f.tables, formulas: f.formulas}],
          assets: {images: f.images, extracted_at: new Date().toISOString()}
        }))
      }, null, 2);
    }
  }, 180);
};
"""

JS_WEBAPP = """
const ITEMS = __DATA__;
const grid = document.getElementById('grid');
const chips = document.getElementById('chips');
const cats = ['همه', ...new Set(ITEMS.map(i=>i.cat))];
chips.innerHTML = cats.map((c,i)=>`<button class="${i===0?'active':''}" data-c="${c}">${c}</button>`).join('');
function render(cat){
  const rows = ITEMS.filter(i=> cat==='همه' || i.cat===cat);
  grid.innerHTML = rows.map(i=>`<div class="feat">
    <div class="t">${i.name}</div><div class="d">${i.desc}</div>
    <div class="rowflex" style="margin-top:10px"><span class="badge b-run">${i.tag}</span>
    <span class="muted">${i.meta}</span></div></div>`).join('');
}
render('همه');
chips.onclick = e=>{ if(e.target.tagName!=='BUTTON') return;
  chips.querySelectorAll('button').forEach(b=>b.classList.remove('active'));
  e.target.classList.add('active'); render(e.target.dataset.c); };
document.getElementById('quote').onsubmit = e=>{
  e.preventDefault();
  const name = document.getElementById('q-name').value.trim();
  const phone = document.getElementById('q-phone').value.trim();
  const msg = document.getElementById('q-msg');
  if(name.length<3){ msg.textContent='لطفاً نام کامل را وارد کنید.'; msg.style.color='#a02626'; return; }
  if(!/^(\\+98|0)?9\\d{9}$/.test(phone.replace(/[\\s-]/g,''))){ msg.textContent='شماره موبایل معتبر نیست.'; msg.style.color='#a02626'; return; }
  msg.style.color='#1a7f4b';
  msg.textContent='درخواست شما ثبت شد (نسخه نمونه) — همکاران ما با شما تماس می‌گیرند.';
  e.target.reset();
};
document.querySelectorAll('a[href^="#"]').forEach(a=>a.onclick=e=>{
  e.preventDefault(); const el=document.querySelector(a.getAttribute('href'));
  el && el.scrollIntoView({behavior:'smooth'});
});
"""

JS_DASHBOARD = """
const DATA = __DATA__;
const state = {period: 30};
function fmt(n){ return n.toLocaleString('fa-IR'); }
function render(){
  const d = DATA[state.period];
  document.getElementById('kpis').innerHTML = d.kpis.map(k=>
    `<div class="kpi"><div class="k">${k.k}</div><div class="v">${fmt(k.v)}</div><div class="d">${k.d}</div></div>`).join('');
  const max = Math.max(...d.chart.map(c=>c.v));
  document.getElementById('bars').innerHTML = d.chart.map(c=>`
    <g><text x="0" y="${0}" style="font-size:11px"></text>
    <rect x="0" y="0" width="100%" height="0"></rect></g>`).join('') +
    d.chart.map((c,i)=>`
    <g transform="translate(${i*62+14},0)">
      <rect class="bar" x="0" y="${150 - (c.v/max)*130}" width="42" height="${(c.v/max)*130}" rx="6"><title>${c.l}: ${fmt(c.v)}</title></rect>
      <text x="21" y="168" text-anchor="middle" style="font-size:11px;fill:#6b7280">${c.l}</text>
      <text x="21" y="${150 - (c.v/max)*130 - 6}" text-anchor="middle" style="font-size:10.5px;fill:#3b5bdb">${fmt(c.v)}</text>
    </g>`).join('');
  document.getElementById('tbody').innerHTML = d.rows.map(r=>
    `<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td><td><span class="badge ${r[3]}">${r[4]}</span></td></tr>`).join('');
  document.getElementById('nrows').textContent = d.rows.length;
}
document.getElementById('periods').onclick = e=>{
  if(e.target.tagName!=='BUTTON') return;
  document.querySelectorAll('#periods button').forEach(b=>b.classList.remove('active'));
  e.target.classList.add('active');
  state.period = +e.target.dataset.p; render();
};
document.getElementById('search').oninput = e=>{
  const q = e.target.value.trim();
  document.querySelectorAll('#tbody tr').forEach(tr=>
    tr.style.display = (tr.innerText.includes(q) || !q) ? '' : 'none');
};
render();
"""

JS_BOT = """
const REPLIES = __DATA__;
const chat = document.getElementById('chat');
const input = document.getElementById('msg');
function add(text, who){
  const d = document.createElement('div');
  d.className = 'msg ' + who; d.textContent = text; chat.appendChild(d);
  chat.scrollTop = chat.scrollHeight;
}
function respond(text){
  const t = text.toLowerCase();
  let reply = REPLIES.default;
  for(const item of REPLIES.rules){ if(item.k.some(k=>t.includes(k))){ reply = item.r; break; } }
  const typing = document.createElement('div');
  typing.className='msg you'; typing.textContent='…';
  chat.appendChild(typing); chat.scrollTop = chat.scrollHeight;
  setTimeout(()=>{ typing.remove(); add(reply,'you'); }, 700);
}
document.getElementById('send').onclick = ()=>{
  const v = input.value.trim(); if(!v) return;
  add(v,'me'); input.value=''; respond(v);
};
input.onkeydown = e=>{ if(e.key==='Enter'){ document.getElementById('send').click(); } };
document.getElementById('cmds').onclick = e=>{
  if(e.target.tagName!=='BUTTON') return;
  const v = e.target.textContent; add(v,'me'); respond(v);
};
"""


# ---------------------------------------------------------------- sample data
def _pipeline_rows(project: Project) -> list[dict]:
    return [
        {"name": "فصل‌ اول - مقدمات.pdf", "size": "۴.۲ مگابایت", "pages": 212, "tables": 18,
         "formulas": 46, "images": 31, "status": "در انتظار", "badge": "b-wait", "acc": 98},
        {"name": "کتاب مرجع (نسخه دوم).epub", "size": "۶.۸ مگابایت", "pages": 388, "tables": 27,
         "formulas": 112, "images": 54, "status": "در انتظار", "badge": "b-wait", "acc": 97},
        {"name": "مجموعه مقالات - جلد ۳.pdf", "size": "۹.۱ مگابایت", "pages": 140, "tables": 9,
         "formulas": 63, "images": 22, "status": "در انتظار", "badge": "b-wait", "acc": 99},
        {"name": "جزوه درسی - فصل ۵.pdf", "size": "۲.۴ مگابایت", "pages": 76, "tables": 6,
         "formulas": 21, "images": 12, "status": "در انتظار", "badge": "b-wait", "acc": 96},
        {"name": "گزارش سالانه - پیوست‌ها.pdf", "size": "۱۲.۵ مگابایت", "pages": 264, "tables": 41,
         "formulas": 8, "images": 76, "status": "در انتظار", "badge": "b-wait", "acc": 97},
    ]


def _webapp_items(project: Project, features: list[str]) -> list[dict]:
    generic = [
        {"cat": "خدمات", "name": "معرفی خدمات", "desc": "صفحه‌ی اختصاصی هر خدمت با توضیح، مزایا و مسیر اقدام", "tag": "صفحه", "meta": "لودینگ زیر ۱ ثانیه"},
        {"cat": "خدمات", "name": "دسته‌بندی محصولات", "desc": "نمایش دسته‌بندی‌شده با فیلتر و جستجوی سریع", "tag": "دینامیک", "meta": "جستجوی زنده"},
        {"cat": "محتوا", "name": "مقالات و اخبار", "desc": "بخش وبلاگ با امکان انتشار مطلب از پنل مدیریت", "tag": "CMS", "meta": "ویرایشگر ساده"},
        {"cat": "محتوا", "name": "درباره‌ی ما", "desc": "معرفی مجموعه، سوابق و تیم", "tag": "صفحه", "meta": "اعتمادساز"},
        {"cat": "ارتباط", "name": "فرم درخواست/استعلام", "desc": "ثبت درخواست با اعتبارسنجی و ارسال به پنل", "tag": "فرم", "meta": "اعلان فوری"},
        {"cat": "ارتباط", "name": "تماس با ما", "desc": "نقشه، شماره‌ها، واتساپ و فرم تماس", "tag": "صفحه", "meta": "واکنش‌گرا"},
    ]
    items: list[dict] = []
    for i, feat in enumerate(features[:6]):
        items.append({
            "cat": "نیازمندی‌های شما",
            "name": feat[:60],
            "desc": "پیاده‌سازی‌شده در نسخه‌ی نهایی — در این دمو با داده‌ی نمونه نمایش داده می‌شود",
            "tag": "از متن آگهی",
            "meta": f"مورد {i + 1}",
        })
    return (items + generic)[:9]


def _dashboard_data(project: Project) -> dict:
    def kpis(v1, v2, v3, v4):
        return [
            {"k": "بازدید امروز", "v": v1, "d": "↑ رشد نسبت به دوره قبل"},
            {"k": "درخواست جدید", "v": v2, "d": "↑ ثبت‌شده در همین بازه"},
            {"k": "نرخ تبدیل", "v": v3, "d": "درصد بازدیدکننده به مشتری"},
            {"k": "درآمد (تومان)", "v": v4, "d": "مجموع سفارش‌های تکمیل‌شده"},
        ]

    labels = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر"]
    return {
        "30": {
            "kpis": kpis(1240, 86, "۶.۹٪", "۴۸,۵۰۰,۰۰۰"),
            "chart": [{"l": l, "v": v} for l, v in zip(labels, [120, 165, 148, 210, 260, 305, 342])],
            "rows": [
                ["سارا احمدی", "درخواست مشاوره", "۱۴۰۴/۰۶/۲۲", "b-ok", "تکمیل‌شده"],
                ["شرکت پارس", "درخواست پیش‌فاکتور", "۱۴۰۴/۰۶/۲۱", "b-wait", "در انتظار"],
                ["مهدی رضایی", "رزرو نوبت", "۱۴۰۴/۰۶/۲۰", "b-ok", "تایید‌شده"],
                ["کلینیک نور", "سفارش عمده", "۱۴۰۴/۰۶/۱۹", "b-run", "در حال انجام"],
                ["زهرا کاظمی", "پیگیری سفارش", "۱۴۰۴/۰۶/۱۸", "b-ok", "پاسخ داده شد"],
            ],
        },
        "90": {
            "kpis": kpis(3890, 264, "۷.۴٪", "۱۶۲,۳۰۰,۰۰۰"),
            "chart": [{"l": l, "v": v} for l, v in zip(labels, [420, 505, 610, 700, 690, 810, 902])],
            "rows": [
                ["شرکت آریا", "قرارداد خدمات", "۱۴۰۴/۰۴/۱۱", "b-ok", "تکمیل‌شده"],
                ["مجموعه مهر", "سفارش عمده", "۱۴۰۴/۰۴/۰۸", "b-ok", "تکمیل‌شده"],
                ["نیما فرهاد", "درخواست مشاوره", "۱۴۰۴/۰۴/۰۲", "b-wait", "در انتظار"],
                ["سازمان نمونه", "درخواست همکاری", "۱۴۰۴/۰۳/۲۸", "b-run", "در حال انجام"],
                ["پژمان نوری", "شکایت/پیگیری", "۱۴۰۴/۰۳/۲۴", "b-bad", "نیاز به رسیدگی"],
            ],
        },
    }


def _bot_data(project: Project) -> dict:
    return {
        "default": "متوجه شدم. این قابلیت در نسخه‌ی نهایی ربات به‌صورت کامل پیاده‌سازی می‌شود. "
                   "برای اجرای دقیق‌تر، دستور مورد نظر را از دکمه‌های بالا انتخاب کنید.",
        "rules": [
            {"k": ["سلام", "درود", "hi", "hello"], "r": "سلام! 👋 من دستیار هوشمند شما هستم. چطور می‌توانم کمک کنم؟"},
            {"k": ["قیمت", "هزینه", "تعرفه"], "r": "لیست قیمت‌ها اینجا نمایش داده می‌شود. برای استعلام دقیق، نوع خدمت را انتخاب کنید."},
            {"k": ["نوبت", "رزرو", "وقت"], "r": "نزدیک‌ترین زمان‌های آزاد: یکشنبه ۱۰:۰۰، دوشنبه ۱۶:۳۰، سه‌شنبه ۱۱:۱۵. کدام را می‌خواهید؟"},
            {"k": ["سفارش", "خرید", "پیگیری"], "r": "سفارش شما با کد ۱۲۰۴ ثبت شد و در صف بررسی است. وضعیت را اینجا پیگیری کنید."},
            {"k": ["پشتیبانی", "مشکل", "خطا"], "r": "درخواست شما به واحد پشتیبانی ارجاع شد. همکاران ما حداکثر تا ۲ ساعت پاسخ می‌دهند."},
            {"k": ["آدرس", "نشانی", "کجاست"], "r": "آدرس روی نقشه نمایش داده می‌شود. همچنین از طریق دکمه‌ی زیر می‌توانید مسیریابی کنید."},
        ],
    }


# ---------------------------------------------------------------- HTML blocks
def _head(title: str, subtitle: str, chips: list[str]) -> str:
    chip_html = "".join(f'<span class="chip">{c}</span>' for c in chips)
    return f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — دمو</title>
<style>{CSS}</style></head>
<body>
<header class="hero"><div class="wrap">
<div class="eyebrow">نسخه‌ی نمونه (دمو) — آماده‌شده برای آگهی فریلنسری</div>
<h1>{title}</h1>
<div style="opacity:.9">{subtitle}</div>
<div class="chips">{chip_html}</div>
</div></header>
<div class="wrap">
"""


def _meta(project: Project, screening: dict, proposal: dict | None) -> str:
    price = f'{proposal["price"]:,} تومان' if proposal else "—"
    budget = f'{project.budget_toman:,} تومان' if project.budget_toman else "اعلام نشده"
    hours = screening.get("est_hours", "—")
    days = screening.get("schedule_days", "—")
    return f"""<div class="meta">
<div class="box"><div class="k">دسته‌بندی</div><div class="v">{screening['category_label']}</div></div>
<div class="box"><div class="k">زمان اجرا (برآورد)</div><div class="v">{hours} ساعت</div></div>
<div class="box"><div class="k">زمان تحویل</div><div class="v">{days} روز کاری</div></div>
<div class="box"><div class="k">قیمت پیشنهادی</div><div class="v">{price}</div></div>
<div class="box"><div class="k">بودجه کارفرما</div><div class="v">{budget}</div></div>
</div>
<div class="notice">⚠️ این صفحه یک <b>دموی تعاملی</b> است که با داده‌های نمونه ساخته شده تا خروجیِ نهایی پروژه
را پیش از عقد قرارداد نشان دهد. متن آگهی: «{project.title}»</div>
"""


def _deliverables(deliverables: list[str], milestones: list[dict]) -> str:
    if not deliverables:
        return ""
    items = "".join(f'<div class="feat"><div class="t">{d}</div></div>' for d in deliverables)
    steps = "".join(
        f'<div class="step"><b>{m["title"]}</b> — {int(m["share"] * 100)}٪<br>'
        f'<span class="muted">{m["when"]}</span></div>' for m in (milestones or [])
    )
    return f"""<div class="card"><h2>چه چیزی تحویل می‌دهید</h2><div class="grid">{items}</div></div>
<div class="card"><h2>برنامه‌ی تحویل و پرداخت</h2><div class="steps">{steps}</div></div>
"""


def _footer(project: Project) -> str:
    now = datetime.now().strftime("%Y/%m/%d %H:%M")
    return f"""<footer class="foot">
ساخته‌شده با «فریلنس‌یار آرنا» در تاریخ {now} — داده‌های این صفحه نمونه و غیرواقعی هستند.<br>
آگهی اصلی: <a href="{project.url}" target="_blank" rel="noopener">{project.source_label}</a>
</footer></div></body></html>
"""


def _body_pipeline(project: Project, screening: dict, proposal: dict | None) -> str:
    files = _pipeline_rows(project)
    return f"""<div class="card"><h2>۱. انتخاب ورودی</h2>
<div class="drop" id="zone">فایل‌های خود را اینجا بکشید یا کلیک کنید (در این دمو از فایل‌های نمونه استفاده می‌شود)</div>
<table style="margin-top:14px"><thead><tr><th></th><th>نام فایل</th><th>حجم</th><th>تعداد صفحه</th><th>وضعیت</th></tr></thead>
<tbody id="filelist"></tbody></table></div>

<div class="card"><h2>۲. اجرای pipeline</h2>
<div class="rowflex"><button class="btn" id="run">شروع استخراج</button>
<button class="btn ghost" onclick="document.querySelectorAll('#filelist input').forEach(c=>c.checked=true)">انتخاب همه</button></div>
<div class="progress"><i></i></div>
<div class="log" id="log">› منتظر شروع…</div></div>

<div class="card" id="results" style="display:none"><h2>۳. خروجی ساختاریافته</h2>
<table><thead><tr><th>فایل</th><th>صفحات</th><th>جداول</th><th>فرمول‌ها</th><th>تصاویر</th><th>کیفیت</th><th>خروجی</th></tr></thead>
<tbody id="tbody"></tbody></table>
<div class="notice" style="margin-top:14px">نمونه‌ی خروجی JSON (همان چیزی که تحویل می‌شود):</div>
<pre class="json" id="jsonbox" style="display:none"></pre></div>
<script>{JS_PIPELINE.replace("__DATA__", json.dumps(files, ensure_ascii=False))}</script>
"""


def _body_webapp(project: Project, screening: dict, proposal: dict | None) -> str:
    features = screening.get("features") or []
    items = _webapp_items(project, features)
    feat_cards = "".join(
        f'<div class="feat"><div class="t">{f[:70]}</div>'
        f'<div class="d">در نسخه‌ی نهایی پیاده‌سازی می‌شود</div></div>' for f in features[:6]
    ) or '<div class="muted">نیازمندی‌های پروژه از متن آگهی استخراج و در نسخه نهایی پیاده می‌شود.</div>'
    return f"""<div class="card"><h2>نیازمندی‌های استخراج‌شده از آگهی</h2>
<div class="grid">{feat_cards}</div></div>

<div class="card"><h2>پیش‌نمایش صفحات و امکانات</h2>
<div class="nav" id="chips"></div>
<div class="grid" id="grid"></div></div>

<div class="card"><h2>فرم درخواست / استعلام (نمونه‌ی واقعی)</h2>
<form id="quote" class="grid" style="gap:10px">
<div><label>نام و نام خانوادگی</label><input id="q-name" placeholder="مثال: علی محمدی"></div>
<div><label>شماره موبایل</label><input id="q-phone" placeholder="09xxxxxxxxx"></div>
<div><label>نوع درخواست</label><select><option>استعلام قیمت</option><option>درخواست مشاوره</option><option>رزرو نوبت</option></select></div>
<div style="display:flex;align-items:end;gap:10px"><button class="btn" type="submit">ارسال درخواست</button>
<span class="muted" id="q-msg"></span></div></form></div>
<script>{JS_WEBAPP.replace("__DATA__", json.dumps(items, ensure_ascii=False))}</script>
"""


def _body_dashboard(project: Project, screening: dict, proposal: dict | None) -> str:
    data = _dashboard_data(project)
    return f"""<div class="card"><h2>شاخص‌های کلیدی</h2>
<div class="rowflex" style="margin-bottom:12px">
<div class="nav" id="periods" style="margin:0">
<button class="active" data-p="30">۳۰ روز اخیر</button><button data-p="90">۹۰ روز اخیر</button></div>
<input id="search" placeholder="جستجو در جدول…" style="max-width:250px"></div>
<div class="kpis" id="kpis"></div></div>

<div class="card"><h2>روند عملکرد</h2>
<svg viewBox="0 0 460 180" style="width:100%;height:210px">
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#3b5bdb"/><stop offset="1" stop-color="#22b8cf"/></linearGradient></defs>
<g id="bars"></g></svg></div>

<div class="card"><h2>آخرین درخواست‌ها <span class="muted">(<span id="nrows">0</span> مورد)</span></h2>
<table><thead><tr><th>نام</th><th>نوع درخواست</th><th>تاریخ</th><th>وضعیت</th></tr></thead>
<tbody id="tbody"></tbody></table></div>
<script>{JS_DASHBOARD.replace("__DATA__", json.dumps(data, ensure_ascii=False))}</script>
"""


def _body_bot(project: Project, screening: dict, proposal: dict | None) -> str:
    data = _bot_data(project)
    cmds = "".join(f"<button>{r['k'][0].capitalize()}</button>" for r in data["rules"])
    return f"""<div class="grid">
<div class="card"><h2>گفتگو با ربات (نسخه نمونه)</h2>
<div class="phone"><div class="chat" id="chat">
<div class="msg you">سلام! من دستیار هوشمند شما هستم 👋 چطور می‌توانم کمک کنم؟</div>
</div>
<div class="rowflex" style="padding:10px;border-top:1px solid #eceff7">
<input id="msg" placeholder="پیام خود را بنویسید…"><button class="btn" id="send">ارسال</button></div></div>
<div class="nav" id="cmds">{cmds}</div></div>

<div class="card"><h2>امکانات پنل مدیریت</h2>
<div class="kpis">
<div class="kpi"><div class="k">کاربران فعال</div><div class="v">۱,۲۴۸</div><div class="d">↑ ۱۲٪ این هفته</div></div>
<div class="kpi"><div class="k">پیام‌های امروز</div><div class="v">۳۴۲</div><div class="d">میانگین پاسخ ۱.۲ ثانیه</div></div>
<div class="kpi"><div class="k">دستورات تعریف‌شده</div><div class="v">۱۸</div><div class="d">قابل افزودن از پنل</div></div>
</div>
<div class="grid" style="margin-top:14px">
<div class="feat"><div class="t">پاسخ‌گویی خودکار</div><div class="d">بر اساس کلمات کلیدی و قوانین تعریف‌شده</div></div>
<div class="feat"><div class="t">اتصال به پایگاه داده</div><div class="d">ذخیره‌ی کاربران و گفتگوها</div></div>
<div class="feat"><div class="t">گزارش‌گیری</div><div class="d">نمایش آمار استفاده و رضایت</div></div>
<div class="feat"><div class="t">اجرا روی سرور شما</div><div class="d">تحویل همراه فایل راه‌اندازی</div></div>
</div></div></div>
<script>{JS_BOT.replace("__DATA__", json.dumps(data, ensure_ascii=False))}</script>
"""


KIND_BY_CATEGORY = {
    "data_pipeline": "pipeline",
    "automation": "pipeline",
    "dashboard": "dashboard",
    "bot": "bot",
    "ai_app": "webapp",
    "web_app": "webapp",
    "landing": "webapp",
    "plugin_cms": "webapp",
    "mobile_app": "webapp",
    "chrome_extension": "webapp",
    "content": "dashboard",
    "data_entry": "pipeline",
    "other": "webapp",
}


def choose_kind(screening: dict) -> str:
    return KIND_BY_CATEGORY.get(screening.get("category", "other"), "webapp")


def build_demo(project: Project, screening: dict, proposal: dict | None, out_dir: Path,
               base_url: str = "") -> dict:
    """یک فایل HTML مستقل می‌سازد و مشخصات آن را برمی‌گرداند."""
    kind = choose_kind(screening)
    slug = slugify(f"{project.source}-{project.external_id}-{project.title}")
    folder = Path(out_dir) / slug
    folder.mkdir(parents=True, exist_ok=True)

    subtitle = (project.description or "")[:220].strip()
    if len((project.description or "")) > 220:
        subtitle += "…"
    chips = [
        f"منبع: {project.source_label}",
        f"دسته: {screening['category_label']}",
        f"امتیاز اجراپذیری: {screening['score']}/۱۰۰",
        f"نوع دمو: {kind}",
    ]

    body = {
        "pipeline": _body_pipeline,
        "webapp": _body_webapp,
        "dashboard": _body_dashboard,
        "bot": _body_bot,
    }[kind](project, screening, proposal)

    html = (
        _head(clean_text(project.title), subtitle or "بدون توضیح", chips)
        + _meta(project, screening, proposal)
        + body
        + _deliverables(screening.get("deliverables", []),
                        (proposal or {}).get("milestones", []))
        + _footer(project)
    )
    index = folder / "index.html"
    index.write_text(html, encoding="utf-8")

    meta = {
        "project_id": project.id,
        "title": project.title,
        "source": project.source,
        "kind": kind,
        "path": str(index),
        "rel": f"{slug}/index.html",
        "url": f"{base_url}/demos/{slug}/" if base_url else f"file://{index}",
        "built_at": datetime.now().isoformat(timespec="seconds"),
    }
    (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta
