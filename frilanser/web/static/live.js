/* داشبوردِ زنده: اسکنِ خودکار، نوسازیِ بی‌صدا و آگاهی از نسخه‌ی جدید.
   همه‌چیز فقط با یک فایلِ JSON در /api/live کار می‌کند؛ اگر سرور در دسترس
   نباشد، پیام می‌دهد و دوباره تلاش می‌کند (هرگز صفحه را خراب نمی‌کند). */
(function () {
  const bar = document.getElementById('livebar');
  if (!bar) return;

  const el = (id) => document.getElementById(id);
  const dot = el('live-dot'), status = el('live-status'), next = el('live-next');
  const btnScan = el('live-scan'), chkAuto = el('live-auto');
  const verEl = el('live-ver'), btnUpd = el('live-upd'), toast = el('live-toast');

  let state = null, lastStamp = null, pollMs = 20000;
  let scanningAsked = false, failures = 0, toastTimer = null;

  function fa(n, unit) {
    const v = Math.max(0, Math.round(n));
    if (unit === 'm') return v < 1 ? 'کمتر از یک دقیقه' : v + ' دقیقه';
    return v + ' ثانیه';
  }

  function showToast(html, link) {
    if (!toast) return;
    toast.innerHTML = html + (link ? ' <a href="' + link + '" style="color:#fff;font-weight:700">نمایش ↗</a>' : '');
    toast.style.display = '';
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.style.display = 'none'; }, 9000);
  }

  function setDot(cls) {
    if (!dot) return;
    dot.className = 'livedot ' + cls;
  }

  async function post(url, body) {
    const fd = new FormData();
    Object.keys(body || {}).forEach(k => fd.append(k, body[k]));
    const r = await fetch(url, { method: 'POST', body: fd });
    return await r.json();
  }

  function renderUpdate() {
    const u = (state && state.update) || {};
    if (verEl) verEl.textContent = 'نسخه ' + (u.current || (state && state.version) || '?');
    if (!btnUpd) return;
    if (u.downloading) {
      btnUpd.style.display = '';
      btnUpd.textContent = 'در حال دریافت… ' + (u.percent || 0) + '٪';
      btnUpd.disabled = true;
    } else if (u.has_update && u.latest) {
      btnUpd.style.display = '';
      btnUpd.textContent = 'نسخه‌ی جدید ' + u.latest + ' ↗';
      btnUpd.disabled = false;
      // اگر روی داشبورد هستیم، کارتِ به‌روزرسانی را هم پر می‌کنیم
      if (window.__frilanserShowUpdate) {
        window.__frilanserShowUpdate({ has_update: true, latest: u.latest, notes: u.notes, asset: { size: (u.size || 0) } });
      }
    } else {
      btnUpd.style.display = 'none';
    }
  }

  function render() {
    const s = state;
    if (!s) return;
    pollMs = Math.max(5000, (s.poll_seconds || 20) * 1000);
    if (chkAuto) chkAuto.checked = !!s.auto;

    if (s.scanning) {
      setDot('busy');
      status.textContent = 'در حال اسکنِ سایت‌ها… (چند ثانیه تا یک دقیقه)';
      if (next) next.textContent = '';
      if (btnScan) { btnScan.disabled = true; }
    } else {
      if (btnScan) btnScan.disabled = false;
      const ls = s.last_scan;
      if (!ls) {
        setDot('idle');
        status.textContent = 'هنوز اسکنی انجام نشده — «الان اسکن کن» را بزنید';
      } else if (!ls.ok) {
        setDot('err');
        status.textContent = 'آخرین اسکن ناموفق بود: ' + (ls.error || 'خطای ناشناخته');
      } else {
        setDot(s.auto ? 'ok' : 'idle');
        let txt = 'آخرین به‌روزرسانی: ' + (ls.age_text || '') +
          ' (' + (ls.fetched || 0) + ' آگهی بررسی شد';
        if (ls.new) txt += '، ' + ls.new + ' جدید';
        if (ls.closed) txt += '، ' + ls.closed + ' واگذار/بسته شد';
        txt += ')';
        if (ls.fell_back) txt += ' — دریافت زنده ناموفق بود، از نسخه‌ی ذخیره‌شده خوانده شد';
        status.textContent = txt;
      }
    }

    if (next) {
      if (!s.auto || s.next_scan_in === null || s.next_scan_in === undefined) {
        next.textContent = s.auto ? '' : 'به‌روزرسانیِ خودکار خاموش است';
      } else {
        next.textContent = 'اسکنِ بعدی: ' + fa(s.next_scan_in / 60, 'm') + ' دیگر' +
          (s.interval_minutes ? ' (هر ' + s.interval_minutes + ' دقیقه)' : '');
      }
    }
    renderUpdate();
  }

  function tickCountdown() {
    if (!state || state.scanning) return;
    if (state.auto && state.next_scan_in !== null && state.next_scan_in !== undefined) {
      state.next_scan_in = Math.max(0, state.next_scan_in - 1);
      if (next) {
        next.textContent = state.next_scan_in <= 0
          ? 'اسکنِ بعدی: همین حالا…'
          : 'اسکنِ بعدی: ' + fa(state.next_scan_in / 60, 'm') + ' دیگر' +
            (state.interval_minutes ? ' (هر ' + state.interval_minutes + ' دقیقه)' : '');
      }
    }
  }

  async function refreshBody(reason) {
    const root = el('live-root');
    if (!root) {
      // صفحه‌های دیگر (مثل جزئیات پروژه): فقط خبر می‌دهیم
      if (reason) showToast(reason, '/');
      return;
    }
    try {
      const r = await fetch('/fragment' + (location.search || ''), { headers: { 'X-Requested-With': 'live' } });
      const html = await r.text();
      root.innerHTML = html;
      if (reason) showToast(reason);
    } catch (e) {
      if (reason) showToast(reason + ' — برای دیدن آن صفحه را تازه کنید', '/');
    }
  }

  async function poll() {
    try {
      const r = await fetch('/api/live', { headers: { 'X-Requested-With': 'live' } });
      const s = await r.json();
      if (s && s.ok) {
        failures = 0;
        const wasScanning = state && state.scanning;
        state = s;
        render();

        // اسکن تمام شد → داشبورد را تازه کن
        if (wasScanning && !s.scanning && scanningAsked) {
          scanningAsked = false;
          const ls = s.last_scan || {};
          let reason = 'به‌روزرسانی انجام شد';
          if (ls.ok) {
            reason = (ls.new ? ls.new + ' آگهی جدید' : 'تغییری در آگهی‌ها نبود');
            if (ls.closed) reason += '، ' + ls.closed + ' پروژه واگذار/بسته شد';
          } else {
            reason = 'اسکن ناموفق بود: ' + (ls.error || 'خطای ناشناخته');
          }
          await refreshBody(reason);
        }

        // داده عوض شده (مثلاً اسکنِ خودکارِ زمان‌بندی‌شده) → نوسازیِ بی‌صدا
        if (lastStamp && s.stamp && s.stamp !== lastStamp && !s.scanning) {
          const c = (state.counts || {});
          const msg = 'داده‌ها عوض شد (' + (c.total || 0) + ' آگهی)';
          if (s.auto_refresh) await refreshBody(msg);
          else showToast(msg, '/');
        }
        lastStamp = s.stamp;
      } else {
        failures++;
        if (failures === 1 && status) {
          status.textContent = 'سرویسِ به‌روزرسانی در این اجرا خاموش است';
          setDot('idle');
        }
      }
    } catch (e) {
      failures++;
      setDot('err');
      if (status) status.textContent = 'ارتباط با برنامه قطع شد — دوباره تلاش می‌کنم…';
    }
  }

  if (btnScan) {
    btnScan.onclick = async () => {
      scanningAsked = true;
      btnScan.disabled = true;
      setDot('busy');
      status.textContent = 'در حال اسکنِ سایت‌ها… (چند ثانیه تا یک دقیقه)';
      try {
        const j = await post('/api/live/scan', {});
        if (j && j.ok === false && !j.scanning) {
          status.textContent = j.error || 'اسکن آغاز نشد';
          btnScan.disabled = false;
          scanningAsked = false;
        }
      } catch (e) {
        status.textContent = 'خطا در آغاز اسکن: ' + e.message;
        btnScan.disabled = false;
        scanningAsked = false;
      }
    };
  }

  if (chkAuto) {
    chkAuto.onchange = async () => {
      chkAuto.disabled = true;
      try { await post('/api/live/auto', { enabled: chkAuto.checked ? '1' : '0' }); await poll(); }
      catch (e) { /* تلاش بعدی */ }
      chkAuto.disabled = false;
    };
  }

  if (btnUpd) {
    btnUpd.onclick = () => {
      const u = (state && state.update) || {};
      if (el('upd-install')) {            // روی داشبورد: همان کارتِ به‌روزرسانی
        el('upd-install').click();
        el('upd-card').scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else {                            // صفحه‌های دیگر
        window.location.href = '/';
      }
      return;
    };
    // فقط برای جلوگیری از هشدارِ متغیرِ بلااستفاده
    void u_unused;
  }

  poll();
  setInterval(poll, pollMs);
  setInterval(tickCountdown, 1000);
})();
