/* Ya-KG · shared runtime: theme, command palette, toast, csv, table sort */
(function () {
  'use strict';

  var root = document.documentElement;
  var BASE = root.getAttribute('data-base') || './';

  var KG = (window.KG = {
    base: BASE,
    url: function (p) { return BASE + p; },
    conceptUrl: function (i) { return BASE + 'c/' + i + '/'; },
    T: [], TZH: {}, index: null, _idxP: null
  });

  /* ---------- tiny helpers ---------- */
  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  KG.$ = $; KG.$$ = $$; KG.esc = esc;

  KG.typeColor = function (name) {
    return getComputedStyle(root).getPropertyValue('--t-' + name).trim() || '#7a8794';
  };
  KG.chip = function (typeName) {
    var zh = (KG.TZH[typeName] || typeName);
    return '<span class="chip-t" style="background:' + KG.typeColor(typeName) + '">' + esc(zh) + '</span>';
  };

  /* ---------- theme ---------- */
  function applyTheme(t) {
    if (t === 'dark' || t === 'light') root.setAttribute('data-theme', t);
    else root.removeAttribute('data-theme');
    try { t ? localStorage.setItem('kg-theme', t) : localStorage.removeItem('kg-theme'); } catch (e) {}
    document.dispatchEvent(new CustomEvent('kg:theme', { detail: t }));
  }
  KG.applyTheme = applyTheme;
  KG.currentTheme = function () {
    var a = root.getAttribute('data-theme');
    if (a) return a;
    return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  };
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-theme-toggle]');
    if (!b) return;
    applyTheme(KG.currentTheme() === 'dark' ? 'light' : 'dark');
  });

  /* ---------- toast ---------- */
  var toastEl, toastT;
  KG.toast = function (msg) {
    if (!toastEl) { toastEl = document.createElement('div'); toastEl.className = 'toast'; document.body.appendChild(toastEl); }
    toastEl.textContent = msg;
    requestAnimationFrame(function () { toastEl.classList.add('on'); });
    clearTimeout(toastT);
    toastT = setTimeout(function () { toastEl.classList.remove('on'); }, 2100);
  };

  /* ---------- download helpers ---------- */
  /* Chromium silently discards a blob download's `download` filename when it
     contains non-ASCII characters — the file then lands as "download" with no
     extension. Keep export names ASCII, falling back to a generic stem. */
  KG.safeName = function (s, fallback) {
    var a = String(s || '').replace(/[^\x20-\x7E]/g, '')
      .replace(/[^A-Za-z0-9._-]+/g, '-').replace(/-{2,}/g, '-')
      .replace(/^[-.]+|[-.]+$/g, '').toLowerCase();
    return a.length >= 2 ? a : fallback;
  };
  function asciiFilename(name) {
    if (/^[\x20-\x7E]+$/.test(name)) return name;
    var dot = name.lastIndexOf('.');
    var ext = dot > 0 && /^[\x20-\x7E]+$/.test(name.slice(dot)) ? name.slice(dot) : '';
    return KG.safeName(dot > 0 ? name.slice(0, dot) : name, 'ya-kg-export') + ext;
  }
  KG.download = function (filename, text, mime) {
    filename = asciiFilename(filename);
    mime = mime || 'text/plain';
    // Excel needs a BOM to read UTF-8 CSV; a BOM would break strict JSON parsers
    var body = mime === 'text/csv' ? '﻿' + text : text;
    var blob = new Blob([body], { type: mime + ';charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 400);
    KG.toast('已下载 ' + filename);
  };
  KG.csv = function (filename, rows) {
    var body = rows.map(function (r) {
      return r.map(function (c) {
        c = c == null ? '' : String(c);
        return /[",\n]/.test(c) ? '"' + c.replace(/"/g, '""') + '"' : c;
      }).join(',');
    }).join('\r\n');
    KG.download(filename, body, 'text/csv');
  };
  KG.copy = function (text, label) {
    var done = function () { KG.toast(label || '已复制'); };
    if (navigator.clipboard && window.isSecureContext) { navigator.clipboard.writeText(text).then(done, fallback); }
    else fallback();
    function fallback() {
      var ta = document.createElement('textarea');
      ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); done(); } catch (e) { KG.toast('复制失败'); }
      ta.remove();
    }
  };
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-copy]');
    if (b) KG.copy(b.getAttribute('data-copy'), b.getAttribute('data-copy-label'));
  });

  /* ---------- search index ---------- */
  KG.loadIndex = function () {
    if (KG._idxP) return KG._idxP;
    KG._idxP = fetch(BASE + 'data/search.json', { cache: 'force-cache' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) {
        KG.T = d.T; KG.TZH = d.TZH;
        KG.index = d.I.map(function (r, i) {
          return { i: i, name: r[0], en: r[1] || '', t: r[2], al: r[3] || '', mt: r[4], deg: r[5], ch: r[6] };
        });
        return KG.index;
      });
    return KG._idxP;
  };

  /* score: higher = better */
  function score(n, q) {
    var name = n.name, lname = name.toLowerCase(), len = q.length;
    var s = -1, p;
    if (lname === q) s = 1000;
    else if (lname.indexOf(q) === 0) s = 820 - (name.length - len) * 0.4;
    else if ((p = lname.indexOf(q)) > 0) s = 660 - p * 6 - (name.length - len) * 0.3;
    if (s < 0 && n.al) {
      var la = n.al.toLowerCase();
      if ((p = la.indexOf(q)) >= 0) s = 520 - (p === 0 ? 0 : 40);
    }
    if (s < 0 && n.en) {
      var le = n.en.toLowerCase();
      if (le === q) s = 900;
      else if (le.indexOf(q) === 0) s = 470;
      else if ((p = le.indexOf(q)) > 0) s = 380 - p * 2;
    }
    if (s < 0) return -1;
    return s + Math.min(60, (n.deg + n.mt) * 0.55);
  }
  KG.search = function (q, limit) {
    q = (q || '').trim().toLowerCase();
    if (!q || !KG.index) return [];
    var out = [];
    for (var i = 0; i < KG.index.length; i++) {
      var s = score(KG.index[i], q);
      if (s >= 0) out.push([s, KG.index[i]]);
    }
    out.sort(function (a, b) { return b[0] - a[0] || a[1].name.length - b[1].name.length; });
    return out.slice(0, limit || 40).map(function (x) { return x[1]; });
  };

  function hl(text, q) {
    if (!text) return '';
    var i = text.toLowerCase().indexOf(q);
    if (i < 0) return esc(text);
    return esc(text.slice(0, i)) + '<mark>' + esc(text.slice(i, i + q.length)) + '</mark>' + esc(text.slice(i + q.length));
  }

  /* ---------- command palette ---------- */
  var pal = null, palIdx = 0, palRows = [];
  function recents() { try { return JSON.parse(localStorage.getItem('kg-recent') || '[]'); } catch (e) { return []; } }
  function pushRecent(n) {
    var r = recents().filter(function (x) { return x.i !== n.i; });
    r.unshift({ i: n.i, name: n.name, en: n.en, t: n.t });
    try { localStorage.setItem('kg-recent', JSON.stringify(r.slice(0, 8))); } catch (e) {}
  }

  KG.openPalette = function (prefill) {
    if (pal) return;
    pal = document.createElement('div');
    pal.className = 'pal-back';
    pal.innerHTML =
      '<div class="pal" role="dialog" aria-modal="true" aria-label="搜索概念">' +
        '<div class="pal-in">' +
          '<svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="9" cy="9" r="6"/><path d="m14 14 4 4" stroke-linecap="round"/></svg>' +
          '<input type="text" autocomplete="off" spellcheck="false" placeholder="搜索概念、英文术语或同义词…" aria-label="搜索">' +
          '<kbd>Esc</kbd>' +
        '</div>' +
        '<div class="pal-res" role="listbox"></div>' +
        '<div class="pal-foot"><b>↑↓</b> 选择 <b>↵</b> 打开 <b>Esc</b> 关闭 <span style="margin-left:auto" class="dimmer" id="palN"></span></div>' +
      '</div>';
    document.body.appendChild(pal);
    document.body.style.overflow = 'hidden';

    var input = $('input', pal), res = $('.pal-res', pal);
    if (prefill) input.value = prefill;

    function render() {
      var q = input.value.trim().toLowerCase();
      if (!q) {
        var rc = recents();
        palRows = rc.map(function (x) { return { i: x.i, name: x.name, en: x.en, t: x.t }; });
        res.innerHTML = palRows.length
          ? '<div class="tiny dimmer" style="padding:8px 12px 4px">最近查看</div>' + palRows.map(row.bind(null, '')).join('')
          : '<div class="empty" style="padding:34px 20px">输入关键词开始检索<br><span class="tiny">支持中文名、英文术语与同义词</span></div>';
        $('#palN', pal).textContent = KG.index ? KG.index.length + ' 个概念' : '';
      } else {
        palRows = KG.search(q, 40);
        res.innerHTML = palRows.length ? palRows.map(row.bind(null, q)).join('')
          : '<div class="empty" style="padding:34px 20px">没有匹配的概念</div>';
        $('#palN', pal).textContent = palRows.length ? palRows.length + ' 条结果' : '';
      }
      palIdx = 0; mark();
    }
    function row(q, n) {
      return '<a class="r" href="' + KG.conceptUrl(n.i) + '" role="option" data-i="' + n.i + '">' +
        '<span class="nm">' + hl(n.name, q) + '</span>' +
        (n.en ? '<span class="en">' + hl(n.en, q) + '</span>' : '') +
        '<span class="rt">' + KG.chip(KG.T[n.t] || '') + '</span></a>';
    }
    function mark() {
      var rows = $$('.r', res);
      rows.forEach(function (el, k) { el.classList.toggle('on', k === palIdx); });
      if (rows[palIdx]) rows[palIdx].scrollIntoView({ block: 'nearest' });
    }
    function close() {
      if (!pal) return;
      pal.remove(); pal = null; document.body.style.overflow = '';
    }
    KG.closePalette = close;

    input.addEventListener('input', render);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); palIdx = Math.min(palIdx + 1, palRows.length - 1); mark(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); palIdx = Math.max(palIdx - 1, 0); mark(); }
      else if (e.key === 'Enter') {
        var n = palRows[palIdx];
        if (n) { e.preventDefault(); pushRecent(n); location.href = KG.conceptUrl(n.i); }
      } else if (e.key === 'Escape') { close(); }
    });
    res.addEventListener('click', function (e) {
      var a = e.target.closest('.r');
      if (a) { var n = palRows.find(function (x) { return x.i === +a.dataset.i; }); if (n) pushRecent(n); }
    });
    pal.addEventListener('mousedown', function (e) { if (e.target === pal) close(); });

    KG.loadIndex().then(render, function () {
      res.innerHTML = '<div class="empty">搜索索引加载失败，请刷新重试</div>';
    });
    render();
    input.focus();
  };

  document.addEventListener('click', function (e) {
    if (e.target.closest('[data-palette]')) { e.preventDefault(); KG.openPalette(); }
  });
  document.addEventListener('keydown', function (e) {
    var tag = (e.target.tagName || '').toLowerCase();
    var typing = tag === 'input' || tag === 'textarea' || tag === 'select' || e.target.isContentEditable;
    if ((e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey)) { e.preventDefault(); KG.openPalette(); return; }
    if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey && !e.altKey) { e.preventDefault(); KG.openPalette(); }
  });

  /* ---------- sortable / filterable tables ---------- */
  KG.table = function (opts) {
    var wrap = $(opts.mount), tb = $('tbody', wrap), ths = $$('th.sortable', wrap);
    var data = opts.data.slice(), view = data, sortKey = opts.sortKey || null, dir = opts.dir || 'asc';
    var page = opts.page || 300, shown = page;

    function cmp(a, b) {
      var x = opts.value(a, sortKey), y = opts.value(b, sortKey), r;
      if (typeof x === 'number' && typeof y === 'number') r = x - y;
      else r = String(x).localeCompare(String(y), 'zh-Hans-CN', { numeric: true });
      return dir === 'asc' ? r : -r;
    }
    function apply() {
      view = opts.filter ? data.filter(opts.filter) : data;
      if (sortKey) view = view.slice().sort(cmp);
      shown = page; paint();
    }
    function paint() {
      tb.innerHTML = view.slice(0, shown).map(opts.row).join('') ||
        '<tr><td colspan="' + (opts.cols || 5) + '"><div class="empty">没有匹配的记录</div></td></tr>';
      ths.forEach(function (th) {
        if (th.dataset.key === sortKey) th.dataset.dir = dir; else th.removeAttribute('data-dir');
      });
      if (opts.onPaint) opts.onPaint(view, shown);
    }
    ths.forEach(function (th) {
      th.setAttribute('tabindex', '0');
      var go = function () {
        var k = th.dataset.key;
        dir = (sortKey === k && dir === 'asc') ? 'desc' : 'asc';
        sortKey = k; apply();
      };
      th.addEventListener('click', go);
      th.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
    });
    var api = {
      refresh: apply,
      more: function () { shown += page; paint(); },
      get view() { return view; },
      set data(d) { data = d; apply(); }
    };
    apply();
    return api;
  };

  /* ---------- service worker ---------- */
  if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0) {
    addEventListener('load', function () {
      navigator.serviceWorker.register(BASE + 'sw.js').catch(function () {});
    });
  }
  KG.unregisterSW = function () {
    if (!navigator.serviceWorker) return;
    navigator.serviceWorker.getRegistrations().then(function (rs) {
      rs.forEach(function (r) { r.unregister(); });
      caches.keys().then(function (k) { return Promise.all(k.map(function (x) { return caches.delete(x); })); })
        .then(function () { KG.toast('离线缓存已清除'); });
    });
  };
})();
