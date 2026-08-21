/* Ya-KG · study / flashcard mode with lightweight spaced repetition */
(function () {
  'use strict';
  var KG = window.KG, $ = KG.$, $$ = KG.$$, esc = KG.esc;
  var T = [], TZH = {}, pool = [], deck = [], pos = 0, revealed = false;
  var mode = 'def', chF = '', loaded = {}, stats = { seen: 0, ok: 0, no: 0 };
  var LS = 'kg-srs';

  function srs() { try { return JSON.parse(localStorage.getItem(LS) || '{}'); } catch (e) { return {}; } }
  function setSrs(o) { try { localStorage.setItem(LS, JSON.stringify(o)); } catch (e) {} }

  function load(ch) {
    if (loaded[ch]) return Promise.resolve(loaded[ch]);
    return fetch(KG.base + 'data/cards/ch' + ch + '.json', { cache: 'force-cache' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        T = d.T; TZH = d.TZH; KG.T = T; KG.TZH = TZH;
        loaded[ch] = d.C.map(function (r) {
          return { i: r[0], name: r[1], en: r[2], t: r[3], def: r[4], f: r[5] || [], p: r[6] || [], ch: ch };
        });
        return loaded[ch];
      });
  }

  function chapters() { return chF ? [chF] : Object.keys(window.KG_CH); }

  function build() {
    $('#cardBox').innerHTML = '<div class="empty">正在准备卡片…</div>';
    Promise.all(chapters().map(load)).then(function (parts) {
      pool = [].concat.apply([], parts);
      if (mode === 'en') pool = pool.filter(function (c) { return c.en; });
      else if (mode === 'param') pool = pool.filter(function (c) { return c.p.length; });
      else pool = pool.filter(function (c) { return c.def || c.f.length; });
      var s = srs(), now = Date.now();
      // due-first ordering: unseen > due > future, then shuffle within band
      deck = pool.slice().map(function (c) {
        var r = s[c.i];
        var band = !r ? 0 : (r.due <= now ? 1 : 2);
        return { c: c, band: band, k: Math.random() };
      }).sort(function (a, b) { return a.band - b.band || a.k - b.k; }).map(function (x) { return x.c; });
      pos = 0; revealed = false; stats = { seen: 0, ok: 0, no: 0 };
      render();
    }).catch(function (e) {
      $('#cardBox').innerHTML = '<div class="empty" style="color:var(--bad)">卡片加载失败：' + esc(e.message) + '</div>';
    });
  }

  function render() {
    var box = $('#cardBox');
    if (!deck.length) { box.innerHTML = '<div class="empty">当前筛选条件下没有可用卡片<br><span class="tiny">试试切换章节或题型</span></div>'; bar(); return; }
    if (pos >= deck.length) {
      box.innerHTML = '<div class="flash" style="cursor:default"><div class="q">本轮完成 🎉</div>' +
        '<div class="a" style="text-align:center">共练习 <b>' + stats.seen + '</b> 张 · 掌握 <b style="color:var(--ok)">' +
        stats.ok + '</b> · 待复习 <b style="color:var(--warn)">' + stats.no + '</b></div>' +
        '<div class="hint">按 <kbd>R</kbd> 重新开始</div></div>';
      bar(); return;
    }
    var c = deck[pos], q, qen = '', a = '';
    if (mode === 'def') {
      q = c.name; qen = c.en || '';
      a = (c.def ? '<p style="margin-bottom:10px">' + esc(c.def) + '</p>' : '') + factList(c);
    } else if (mode === 'rev') {
      q = c.def || (c.f[0] ? c.f[0][1] : c.name);
      a = '<div style="font-size:20px;font-weight:660;margin-bottom:6px">' + esc(c.name) + '</div>' +
        (c.en ? '<div class="dim" style="font-style:italic;margin-bottom:10px">' + esc(c.en) + '</div>' : '') + factList(c);
    } else if (mode === 'en') {
      q = c.name;
      a = '<div style="font-size:22px;font-weight:660;font-style:italic;text-align:center">' + esc(c.en) + '</div>' +
        (c.def ? '<p class="dim small mt2">' + esc(c.def) + '</p>' : '');
    } else {
      var p = c.p[Math.floor(Math.random() * c.p.length)];
      q = c.name; qen = p[0] + ' = ?';
      a = '<div style="text-align:center"><span class="prm-v" style="font-size:22px">' + esc(p[1]) + '</span></div>' +
        (p[2] ? '<p class="dim small mt2" style="text-align:center">' + esc(p[2]) + '</p>' : '') +
        (c.p.length > 1 ? '<div class="sec-title">该概念的其他参数</div>' + c.p.map(function (x) {
          return '<div class="prm"><span class="pn">' + esc(x[0]) + '</span><span class="pv">' + esc(x[1]) + '</span>' +
            (x[2] ? '<span class="pc">' + esc(x[2]) + '</span>' : '') + '</div>'; }).join('') : '');
    }
    box.innerHTML = '<div class="flash" id="flash" tabindex="0" role="button" aria-label="点击翻面">' +
      '<div class="q">' + esc(q) + '</div>' +
      (qen ? '<div class="qen">' + esc(qen) + '</div>' : '') +
      (revealed ? '<div class="a">' + a + '</div>' +
        '<div class="hint"><a href="' + KG.conceptUrl(c.i) + '">查看完整词条 ↗</a></div>'
        : '<div class="hint">点击卡片或按 <kbd>空格</kbd> 显示答案</div>') +
      '</div>';
    $('#flash').addEventListener('click', flip);
    bar();
  }
  function factList(c) {
    if (!c.f.length) return '';
    var g = {};
    c.f.forEach(function (x) { (g[x[0]] = g[x[0]] || []).push(x[1]); });
    return Object.keys(g).map(function (k) {
      return '<div class="sec-title" style="margin:12px 0 5px">' + esc(k) + '</div><ul class="facts">' +
        g[k].map(function (v) { return '<li>' + esc(v) + '</li>'; }).join('') + '</ul>';
    }).join('');
  }
  function bar() {
    var pct = deck.length ? Math.min(100, pos / deck.length * 100) : 0;
    $('#prog').style.width = pct + '%';
    $('#cardMeta').textContent = deck.length ? (Math.min(pos + 1, deck.length) + ' / ' + deck.length +
      '　掌握 ' + stats.ok + ' · 待复习 ' + stats.no) : '0 / 0';
    $('#gradeRow').hidden = !revealed || pos >= deck.length;
  }
  function flip() { if (pos < deck.length) { revealed = !revealed; render(); } }
  function grade(ok) {
    if (pos >= deck.length) return;
    var c = deck[pos], s = srs(), r = s[c.i] || { n: 0 };
    r.n = ok ? r.n + 1 : 0;
    var days = [0.007, 1, 3, 7, 16, 35, 70][Math.min(r.n, 6)];
    r.due = Date.now() + days * 864e5;
    s[c.i] = r; setSrs(s);
    stats.seen++; ok ? stats.ok++ : stats.no++;
    pos++; revealed = false; render();
  }

  /* wiring */
  $('#cmMode').addEventListener('change', function (e) { mode = e.target.value; build(); });
  $('#cmCh').addEventListener('change', function (e) { chF = e.target.value; build(); });
  $('#cmRestart').addEventListener('click', build);
  $('#cmReset').addEventListener('click', function () {
    if (confirm('确定清除本机保存的复习进度？')) { setSrs({}); KG.toast('复习进度已清除'); build(); }
  });
  $('#gradeNo').addEventListener('click', function () { grade(false); });
  $('#gradeOk').addEventListener('click', function () { grade(true); });
  document.addEventListener('keydown', function (e) {
    if (/^(input|select|textarea)$/i.test(e.target.tagName)) return;
    if (e.key === ' ') { e.preventDefault(); flip(); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); if (pos < deck.length) { pos++; revealed = false; render(); } }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); if (pos > 0) { pos--; revealed = false; render(); } }
    else if (revealed && (e.key === '1' || e.key === 'j')) grade(false);
    else if (revealed && (e.key === '2' || e.key === 'k')) grade(true);
    else if (e.key === 'r' || e.key === 'R') build();
  });

  $('#cmCh').innerHTML = '<option value="">全部章节</option>' + Object.keys(window.KG_CH).map(function (k) {
    return '<option value="' + k + '">第' + k + '章 · ' + esc(window.KG_CH[k]) + '</option>';
  }).join('');
  build();
})();
