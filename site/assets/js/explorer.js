/* Ya-KG · interactive graph explorer */
(function () {
  'use strict';
  var KG = window.KG, $ = KG.$, $$ = KG.$$, esc = KG.esc;
  var root = document.documentElement;

  var D, T, R, CH, RZH, TZH, N, E, F, P;
  var out = [], inn = [], fct = [], prm = [], deg = [];
  var sel = null, onT = null, q = '', chF = '', hideInf = false, hops = 1;
  var VN = [], VE = [], view = { x: 0, y: 0, k: 1 }, drag = null, hov = null, anim = 0, W = 1, H = 1;
  var cv = $('#cv'), cx = cv.getContext('2d');
  var shell = $('#explorer');

  /* ================= boot ================= */
  $('#exState').textContent = '正在载入知识图谱数据…';
  fetch(KG.base + 'data/kg.json', { cache: 'force-cache' })
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(boot)
    .catch(function (err) {
      $('#exState').innerHTML = '<span style="color:var(--bad)">数据加载失败：' + esc(err.message) +
        '</span><br><span class="tiny">请检查网络后刷新页面</span>';
    });

  function boot(d) {
    D = d; T = d.T; R = d.R; CH = d.CH;
    TZH = (d.TZH || {}); RZH = (d.RZH || {});
    KG.T = T; KG.TZH = TZH;
    N = d.N.map(function (r, i) { return { i: i, name: r[0], en: r[1], t: r[2], def: r[3], al: r[4], ch: r[5], pg: r[6], mt: r[7] }; });
    E = d.E.map(function (r) { return { s: r[0], o: r[1], p: r[2], ev: r[3], inf: !!r[4] }; });
    F = d.F.map(function (r) { return { e: r[0], a: r[1], v: r[2], pg: r[3] }; });
    P = (d.P || []).map(function (r) { return { e: r[0], n: r[1], v: r[2], u: r[3], c: r[4], pg: r[5] }; });

    N.forEach(function () { out.push([]); inn.push([]); fct.push([]); prm.push([]); });
    E.forEach(function (e, k) { out[e.s].push(k); inn[e.o].push(k); });
    F.forEach(function (f, k) { fct[f.e].push(k); });
    P.forEach(function (p, k) { prm[p.e].push(k); });
    deg = N.map(function (n, i) { return out[i].length + inn[i].length; });
    onT = new Set(T.map(function (_, i) { return i; }));

    buildFilters();
    wire();
    $('#exState').remove();

    var start = null;
    var m = /[?&]n=(\d+)/.exec(location.search) || /^#(\d+)$/.exec(location.hash);
    if (m) start = +m[1];
    if (start == null || !N[start]) start = N.reduce(function (b, n) { return deg[n.i] > deg[b.i] ? n : b; }, N[0]).i;
    drawList();
    pick(start, true);
    resize();
  }

  /* ================= filters / sidebar ================= */
  function buildFilters() {
    $('#tchips').innerHTML = T.map(function (t, i) {
      return '<button class="tag-toggle" aria-pressed="true" data-t="' + i + '" title="' + esc(t) + '">' +
        '<span class="dot" style="background:' + KG.typeColor(t) + '"></span>' + esc(TZH[t] || t) + '</button>';
    }).join('');
    $('#ch').innerHTML = '<option value="">全部章节</option>' + Object.keys(CH).map(function (k) {
      return '<option value="' + k + '">第' + k + '章 · ' + esc(CH[k]) + '</option>';
    }).join('');
    $('#legend').innerHTML = T.map(function (t) {
      return '<span class="l"><span class="dot" style="background:' + KG.typeColor(t) + '"></span>' + esc(TZH[t] || t) + '</span>';
    }).join('');
  }

  function match() {
    var s = q.trim().toLowerCase();
    var a = N.filter(function (n) { return onT.has(n.t); });
    if (chF) a = a.filter(function (n) { return n.ch.indexOf(+chF) >= 0; });
    if (s) a = a.filter(function (n) {
      return n.name.toLowerCase().indexOf(s) >= 0 || (n.en || '').toLowerCase().indexOf(s) >= 0 ||
        n.al.some(function (x) { return x.toLowerCase().indexOf(s) >= 0; }) ||
        (n.def || '').toLowerCase().indexOf(s) >= 0;
    });
    return a.sort(function (x, y) { return (deg[y.i] + y.mt) - (deg[x.i] + x.mt); });
  }

  function drawList() {
    var a = match(), cap = 400;
    $('#cnt').textContent = a.length.toLocaleString('zh-CN') + ' 个概念';
    $('#hits').innerHTML = a.slice(0, cap).map(function (n) {
      return '<div class="hit" role="option" aria-selected="' + (sel === n.i) + '" data-i="' + n.i + '">' +
        '<div class="nm">' + esc(n.name) + KG.chip(T[n.t]) + '</div>' +
        (n.en ? '<div class="en">' + esc(n.en) + '</div>' : '') +
        '<div class="mt">' + deg[n.i] + ' 关系 · ' + fct[n.i].length + ' 知识点' +
        (prm[n.i].length ? ' · <b>' + prm[n.i].length + ' 参数</b>' : '') + ' · 第' + n.ch.join('/') + '章</div></div>';
    }).join('') + (a.length > cap ? '<div class="hit" style="cursor:default;color:var(--ink-4)">…… 另有 ' +
      (a.length - cap) + ' 个结果，请缩小筛选范围</div>' : '');
  }

  /* ================= detail panel ================= */
  var ORD = ['定义', '分类', '适应证', '禁忌证', '步骤', '操作要点', '要求', '注意事项',
             '优点', '缺点', '材料性能', '数值标准', '并发症', '失败原因', '原因', '处理', '特点'];

  function drawDet() {
    var d = $('#det');
    if (sel == null) { d.innerHTML = '<div class="empty">从左侧列表选择一个概念<br>或点击图中的节点</div>'; return; }
    var n = N[sel];
    var fs = {};
    fct[sel].forEach(function (k) { var f = F[k]; (fs[f.a || '要点'] = fs[f.a || '要点'] || []).push(f); });
    var keys = ORD.filter(function (k) { return fs[k]; })
      .concat(Object.keys(fs).filter(function (k) { return ORD.indexOf(k) < 0; }));

    var h = '<div class="chead"><h1 style="font-size:21px">' + esc(n.name) + ' ' + KG.chip(T[n.t]) + '</h1>' +
      (n.en ? '<div class="en">' + esc(n.en) + '</div>' : '') +
      '<div class="m">第' + n.ch.join('、') + '章<span class="sep">·</span>p' + n.pg.slice(0, 8).join(', ') +
      '<span class="sep">·</span>' + deg[sel] + ' 关系<span class="sep">·</span>' + fct[sel].length + ' 知识点' +
      (prm[sel].length ? '<span class="sep">·</span>' + prm[sel].length + ' 参数' : '') + '</div>' +
      '<div class="row tight mt1">' +
        '<a class="btn sm" href="' + KG.conceptUrl(sel) + '">独立页面 ↗</a>' +
        '<button class="btn sm ghost" data-act="copylink">复制链接</button>' +
        '<button class="btn sm ghost" data-act="json">导出 JSON</button>' +
      '</div></div>';

    if (n.def) h += '<div class="def-box" style="font-size:14px;margin:14px 0 0">' + esc(n.def) + '</div>';
    if (n.al.length) h += '<div class="alias-row">' + n.al.map(function (a) {
      return '<span class="pill">' + esc(a) + '</span>'; }).join('') + '</div>';

    if (prm[sel].length) {
      h += '<div class="sec-title">定量参数<span class="n">' + prm[sel].length + '</span></div>';
      h += prm[sel].map(function (k) {
        var p = P[k];
        return '<div class="prm"><span class="pn">' + esc(p.n) + '</span>' +
          '<span class="pv">' + esc(p.v) + esc(p.u) + '</span>' +
          (p.c ? '<span class="pc">' + esc(p.c) + '</span>' : '') + '<span class="pg">p' + p.pg + '</span></div>';
      }).join('');
    }
    keys.forEach(function (k) {
      h += '<div class="sec-title">' + esc(k) + '<span class="n">' + fs[k].length + '</span></div><ul class="facts">' +
        fs[k].map(function (f) { return '<li>' + esc(f.v) + '<span class="pg">p' + f.pg + '</span></li>'; }).join('') + '</ul>';
    });

    h += relBlock(out[sel], 'out') + relBlock(inn[sel], 'in');
    d.innerHTML = h;
    d.scrollTop = 0;
  }

  function relBlock(keys, dir) {
    if (!keys.length) return '';
    var ks = hideInf ? keys.filter(function (k) { return !E[k].inf; }) : keys;
    if (!ks.length) return '';
    var g = {};
    ks.forEach(function (k) { var e = E[k]; (g[e.p] = g[e.p] || []).push(e); });
    var h = '<div class="sec-title">' + (dir === 'out' ? '出向关系' : '入向关系') +
      '<span class="n">' + ks.length + '</span></div>';
    h += Object.keys(g).sort(function (a, b) { return g[b].length - g[a].length; }).map(function (p) {
      var rows = g[p], pn = R[p];
      return '<div class="rel-grp"><div class="gh"><span class="pred">' + esc(RZH[pn] || pn) +
        '</span><code>' + esc(pn) + '</code><span class="n">' + rows.length + '</span></div>' +
        rows.map(function (e) {
          var oid = dir === 'out' ? e.o : e.s;
          return '<div class="rel"><div class="hd"><a href="#" data-go="' + oid + '">' + esc(N[oid].name) + '</a>' +
            KG.chip(T[N[oid].t]) + (e.inf ? '<span class="badge-inf" title="由同段落共现推断，无原文依据句">推断</span>' : '') +
            '</div>' + (e.ev ? '<div class="ev">' + esc(e.ev) + '</div>' : '') + '</div>';
        }).join('') + '</div>';
    }).join('');
    return h;
  }

  function nodeJSON(i) {
    var n = N[i];
    return JSON.stringify({
      id: i, name: n.name, en: n.en, type: T[n.t], definition: n.def, aliases: n.al,
      chapters: n.ch, pages: n.pg, mentions: n.mt,
      facts: fct[i].map(function (k) { return { attr: F[k].a, value: F[k].v, page: F[k].pg }; }),
      parameters: prm[i].map(function (k) { return { name: P[k].n, value: P[k].v, unit: P[k].u, condition: P[k].c, page: P[k].pg }; }),
      out: out[i].map(function (k) { return { predicate: R[E[k].p], target: N[E[k].o].name, evidence: E[k].ev, inferred: E[k].inf }; }),
      in: inn[i].map(function (k) { return { predicate: R[E[k].p], source: N[E[k].s].name, evidence: E[k].ev, inferred: E[k].inf }; })
    }, null, 2);
  }

  /* ================= selection ================= */
  function pick(i, silent) {
    sel = i;
    drawList(); drawDet(); buildLocal(i, hops);
    var el = $('#hits .hit[data-i="' + i + '"]');
    if (el) el.scrollIntoView({ block: 'nearest' });
    document.title = N[i].name + ' · 知识图谱浏览器 · Ya-KG';
    var u = KG.base.replace(/[^/]*$/, '') ;
    try {
      history[silent ? 'replaceState' : 'pushState']({ n: i }, '', '?n=' + i);
    } catch (e) {}
    if (innerWidth <= 1000 && !silent) shell.dataset.pane = 'graph';
  }
  addEventListener('popstate', function (e) {
    var m = /[?&]n=(\d+)/.exec(location.search);
    var i = m ? +m[1] : null;
    if (i != null && N && N[i] && i !== sel) { sel = i; drawList(); drawDet(); buildLocal(i, hops); }
  });

  /* ================= graph ================= */
  function resize() {
    var p = cv.parentElement, r = p.getBoundingClientRect();
    var dpr = Math.min(devicePixelRatio || 1, 2);
    W = Math.max(1, Math.round(r.width || p.offsetWidth || 640));
    H = Math.max(1, Math.round(r.height || p.offsetHeight || 480));
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    cx.setTransform(dpr, 0, 0, dpr, 0, 0);
    paint();
  }

  function buildLocal(rootId, h) {
    var dist = new Map([[rootId, 0]]), fr = [rootId], CAP = 160;
    for (var lvl = 0; lvl < h; lvl++) {
      var nx = [];
      for (var a = 0; a < fr.length; a++) {
        var u = fr[a], nb = [];
        out[u].forEach(function (k) { if (!hideInf || !E[k].inf) nb.push(E[k].o); });
        inn[u].forEach(function (k) { if (!hideInf || !E[k].inf) nb.push(E[k].s); });
        for (var b = 0; b < nb.length; b++) {
          var v = nb[b];
          if (!dist.has(v) && onT.has(N[v].t) && dist.size < CAP) { dist.set(v, lvl + 1); nx.push(v); }
        }
      }
      if (!nx.length) break;
      fr = nx;
    }
    var ids = Array.from(dist.keys()), pos = new Map();
    VN = ids.map(function (id, j) {
      var dd = dist.get(id), ang = j * 2.399963, rr = dd === 0 ? 0 : 76 + dd * 98;
      var o = { id: id, d: dd, x: Math.cos(ang) * rr + (Math.random() - .5) * 24,
                y: Math.sin(ang) * rr + (Math.random() - .5) * 24, vx: 0, vy: 0 };
      pos.set(id, o); return o;
    });
    VE = [];
    E.forEach(function (e) {
      if (hideInf && e.inf) return;
      if (pos.has(e.s) && pos.has(e.o)) VE.push({ a: pos.get(e.s), b: pos.get(e.o), p: e.p, inf: e.inf });
    });
    view = { x: 0, y: 0, k: 1 };
    $('#gmeta').textContent = VN.length + ' 节点 · ' + VE.length + ' 关系';
    run(240, true);
  }

  function step() {
    // dense neighbourhoods need more room, or hub nodes collapse into a blob
    var crowd = Math.min(2.4, Math.max(1, VN.length / 70));
    var rep = 2500 * crowd, K = 0.023, i, j;
    for (i = 0; i < VN.length; i++) {
      var a = VN[i];
      for (j = i + 1; j < VN.length; j++) {
        var b = VN[j], dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy;
        if (d2 < 0.01) { dx = Math.random() - .5; dy = Math.random() - .5; d2 = 0.01; }
        var dd = Math.sqrt(d2), f = rep / Math.max(d2, 130), fx = dx / dd * f, fy = dy / dd * f;
        a.vx -= fx; a.vy -= fy; b.vx += fx; b.vy += fy;
      }
    }
    for (i = 0; i < VE.length; i++) {
      var e = VE[i], ex = e.b.x - e.a.x, ey = e.b.y - e.a.y, el = Math.hypot(ex, ey) || .01;
      var ff = (el - 118 * crowd) * K, ffx = ex / el * ff, ffy = ey / el * ff;
      e.a.vx += ffx; e.a.vy += ffy; e.b.vx -= ffx; e.b.vy -= ffy;
    }
    for (i = 0; i < VN.length; i++) {
      var n = VN[i];
      if (n.d === 0) { n.x = n.y = 0; n.vx = n.vy = 0; continue; }
      var g = 0.010 + 0.006 * n.d;
      n.vx -= n.x * g; n.vy -= n.y * g;
      n.vx *= .80; n.vy *= .80;
      n.x += n.vx; n.y += n.vy;
    }
  }
  function fitView() {
    if (!VN.length) return;
    var x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    VN.forEach(function (n) { x0 = Math.min(x0, n.x); x1 = Math.max(x1, n.x); y0 = Math.min(y0, n.y); y1 = Math.max(y1, n.y); });
    var pad = 70, bw = Math.max(x1 - x0, 1), bh = Math.max(y1 - y0, 1);
    view.k = Math.max(.24, Math.min(2.2, Math.min((W - pad * 2) / bw, (H - pad * 2) / bh)));
    view.x = -((x0 + x1) / 2) * view.k; view.y = -((y0 + y1) / 2) * view.k;
  }
  function run(t, fit) {
    // batch several physics steps per frame: one step per frame took ~4s to settle
    cancelAnimationFrame(anim);
    var c = 0;
    (function loop() {
      var batch = c < t * 0.6 ? 4 : 2;
      for (var b = 0; b < batch && c < t; b++) { step(); c++; }
      if (fit) fitView();          // stay framed the whole way, not just at the end
      paint();
      if (c < t) anim = requestAnimationFrame(loop);
    })();
  }
  function css(v) { return getComputedStyle(root).getPropertyValue(v).trim(); }
  function paint() {
    var dark = KG.currentTheme() === 'dark';
    var edgeDim = dark ? 'rgba(140,158,170,.20)' : 'rgba(120,136,152,.22)';
    var edgeHot = dark ? 'rgba(103,205,216,.55)' : 'rgba(13,110,122,.45)';
    var halo = css('--canvas-halo'), label = css('--canvas-ink');
    cx.clearRect(0, 0, W, H);
    cx.save();
    cx.translate(W / 2 + view.x, H / 2 + view.y); cx.scale(view.k, view.k);
    cx.lineWidth = 1 / view.k;
    for (var i = 0; i < VE.length; i++) {
      var e = VE[i];
      var hot = (hov && (e.a === hov || e.b === hov)) || e.a.d === 0 || e.b.d === 0;
      cx.strokeStyle = hot ? edgeHot : edgeDim;
      if (e.inf) { cx.setLineDash([3 / view.k, 3 / view.k]); } else { cx.setLineDash([]); }
      cx.beginPath(); cx.moveTo(e.a.x, e.a.y); cx.lineTo(e.b.x, e.b.y); cx.stroke();
    }
    cx.setLineDash([]);
    for (i = 0; i < VN.length; i++) {
      var n = VN[i], nd = N[n.id];
      var r = n.d === 0 ? 13.5 : Math.max(4.5, Math.min(10.5, 3.6 + Math.sqrt(deg[n.id]) * 1.15));
      cx.beginPath(); cx.arc(n.x, n.y, r, 0, 6.2832);
      cx.fillStyle = KG.typeColor(T[nd.t]);
      cx.globalAlpha = n.d === 0 ? 1 : (hov === n ? 1 : .88); cx.fill(); cx.globalAlpha = 1;
      cx.lineWidth = (n.d === 0 ? 2.6 : hov === n ? 2 : 1.1) / view.k;
      cx.strokeStyle = (n.d === 0 || hov === n) ? label : halo;
      cx.stroke();
      if (n.d === 0 || hov === n || (view.k > 1.1 && n.d <= 1 && deg[n.id] > 6)) {
        cx.font = (n.d === 0 ? 640 : 400) + ' ' + ((n.d === 0 ? 13.5 : 11.5) / view.k) + 'px ' +
          '"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif';
        cx.textAlign = 'center';
        cx.lineWidth = 3.4 / view.k; cx.strokeStyle = halo;
        var ly = n.y - r - 5 / view.k;
        cx.strokeText(nd.name, n.x, ly);
        cx.fillStyle = label; cx.fillText(nd.name, n.x, ly);
      }
    }
    cx.restore();
  }

  function at(mx, my) {
    var x = (mx - W / 2 - view.x) / view.k, y = (my - H / 2 - view.y) / view.k, best = null, bd = 1e9;
    for (var i = 0; i < VN.length; i++) {
      var n = VN[i], d = Math.hypot(n.x - x, n.y - y);
      if (d < bd && d < 16) { bd = d; best = n; }
    }
    return best;
  }
  function local(e) {
    var r = cv.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  /* ================= wiring ================= */
  function wire() {
    $('#q').addEventListener('input', function (e) { q = e.target.value; drawList(); });
    $('#ch').addEventListener('change', function (e) { chF = e.target.value; drawList(); });
    $('#hops').addEventListener('change', function (e) { hops = +e.target.value; if (sel != null) buildLocal(sel, hops); });
    $('#refit').addEventListener('click', function () { if (VN.length) { fitView(); paint(); } });
    $('#relayout').addEventListener('click', function () { if (sel != null) buildLocal(sel, hops); });
    $('#png').addEventListener('click', exportPNG);
    $('#infTgl').addEventListener('change', function (e) {
      hideInf = e.target.checked; drawDet(); if (sel != null) buildLocal(sel, hops);
    });
    $('#tchips').addEventListener('click', function (e) {
      var b = e.target.closest('.tag-toggle'); if (!b) return;
      var i = +b.dataset.t;
      if (onT.has(i) && onT.size === T.length) onT = new Set([i]);
      else if (onT.has(i)) { onT.delete(i); if (!onT.size) onT = new Set(T.map(function (_, j) { return j; })); }
      else onT.add(i);
      $$('#tchips .tag-toggle').forEach(function (x) { x.setAttribute('aria-pressed', onT.has(+x.dataset.t)); });
      drawList(); if (sel != null) buildLocal(sel, hops);
    });
    $('#tall').addEventListener('click', function () {
      onT = new Set(T.map(function (_, j) { return j; }));
      $$('#tchips .tag-toggle').forEach(function (x) { x.setAttribute('aria-pressed', 'true'); });
      drawList(); if (sel != null) buildLocal(sel, hops);
    });
    $('#hits').addEventListener('click', function (e) {
      var el = e.target.closest('.hit[data-i]'); if (el) pick(+el.dataset.i);
    });
    $('#det').addEventListener('click', function (e) {
      var a = e.target.closest('a[data-go]');
      if (a) { e.preventDefault(); pick(+a.dataset.go); return; }
      var b = e.target.closest('[data-act]'); if (!b) return;
      if (b.dataset.act === 'copylink') KG.copy(location.origin + location.pathname + '?n=' + sel, '链接已复制');
      if (b.dataset.act === 'json') KG.download('ya-kg-' + KG.safeName(N[sel].en, 'c' + sel) + '.json', nodeJSON(sel), 'application/json');
    });
    $$('.ex-tabs button').forEach(function (b) {
      b.addEventListener('click', function () {
        shell.dataset.pane = b.dataset.pane;
        $$('.ex-tabs button').forEach(function (x) { x.setAttribute('aria-selected', x === b); });
        if (b.dataset.pane === 'graph') setTimeout(function () { resize(); fitView(); paint(); }, 0);
      });
    });

    /* pointer */
    cv.addEventListener('pointerdown', function (e) {
      cv.setPointerCapture(e.pointerId);
      var l = local(e), n = at(l.x, l.y);
      drag = n ? { n: n, mode: 'node' } : { mode: 'pan', x: l.x - view.x, y: l.y - view.y, moved: false };
    });
    cv.addEventListener('pointermove', function (e) {
      var l = local(e);
      if (drag && drag.mode === 'pan') { drag.moved = true; view.x = l.x - drag.x; view.y = l.y - drag.y; paint(); return; }
      if (drag && drag.mode === 'node') {
        var n = drag.n;
        n.x = (l.x - W / 2 - view.x) / view.k; n.y = (l.y - H / 2 - view.y) / view.k;
        n.vx = n.vy = 0; run(20); return;
      }
      var h = at(l.x, l.y);
      if (h !== hov) {
        hov = h; paint();
        var t = $('#tip');
        if (h) {
          var nd = N[h.id];
          t.innerHTML = '<b>' + esc(nd.name) + '</b>' + (nd.en ? ' · ' + esc(nd.en) : '') + '<br>' +
            esc(TZH[T[nd.t]] || T[nd.t]) + ' · ' + deg[h.id] + ' 关系 · 第' + nd.ch.join('/') + '章';
          t.style.opacity = 1;
          t.style.left = Math.min(l.x + 14, W - 280) + 'px';
          t.style.top = (l.y + 14) + 'px';
        } else t.style.opacity = 0;
      }
    });
    cv.addEventListener('pointerup', function (e) {
      var wasDrag = drag;
      if (drag && drag.mode === 'node') run(50);
      drag = null;
      if (wasDrag && wasDrag.mode === 'pan' && !wasDrag.moved) {
        var l = local(e), n = at(l.x, l.y);
        if (n && n.id !== sel) pick(n.id);
      }
    });
    cv.addEventListener('pointerleave', function () { drag = null; hov = null; $('#tip').style.opacity = 0; paint(); });
    cv.addEventListener('wheel', function (e) {
      e.preventDefault();
      var l = local(e), f = e.deltaY < 0 ? 1.13 : 1 / 1.13;
      var nk = Math.max(.2, Math.min(4.5, view.k * f));
      var wx = (l.x - W / 2 - view.x) / view.k, wy = (l.y - H / 2 - view.y) / view.k;
      view.k = nk; view.x = l.x - W / 2 - wx * nk; view.y = l.y - H / 2 - wy * nk;
      paint();
    }, { passive: false });

    /* pinch */
    var pts = new Map(), pd = 0;
    cv.addEventListener('pointerdown', function (e) { pts.set(e.pointerId, e); });
    cv.addEventListener('pointermove', function (e) {
      if (!pts.has(e.pointerId)) return;
      pts.set(e.pointerId, e);
      if (pts.size === 2) {
        drag = null;
        var a = Array.from(pts.values()), d = Math.hypot(a[0].clientX - a[1].clientX, a[0].clientY - a[1].clientY);
        if (pd) { view.k = Math.max(.2, Math.min(4.5, view.k * (d / pd))); paint(); }
        pd = d;
      }
    });
    ['pointerup', 'pointercancel', 'pointerleave'].forEach(function (ev) {
      cv.addEventListener(ev, function (e) { pts.delete(e.pointerId); if (pts.size < 2) pd = 0; });
    });

    addEventListener('resize', resize);
    document.addEventListener('kg:theme', function () { paint(); });
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () { paint(); });
    document.addEventListener('keydown', function (e) {
      if (/^(input|select|textarea)$/i.test(e.target.tagName)) return;
      if (e.key === 'f' && sel != null) { fitView(); paint(); }
      if (e.key === 'r' && sel != null) buildLocal(sel, hops);
    });
    requestAnimationFrame(resize);
    setTimeout(resize, 280);
  }

  function exportPNG() {
    if (!VN.length) return;
    var scale = 2, pad = 60;
    var x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    VN.forEach(function (n) { x0 = Math.min(x0, n.x); x1 = Math.max(x1, n.x); y0 = Math.min(y0, n.y); y1 = Math.max(y1, n.y); });
    var ow = (x1 - x0 + pad * 2), oh = (y1 - y0 + pad * 2);
    var c2 = document.createElement('canvas');
    c2.width = ow * scale; c2.height = oh * scale;
    var g = c2.getContext('2d');
    g.fillStyle = css('--bg') || '#fff'; g.fillRect(0, 0, c2.width, c2.height);
    g.setTransform(scale, 0, 0, scale, 0, 0);
    g.translate(-x0 + pad, -y0 + pad);
    var dark = KG.currentTheme() === 'dark';
    var halo = css('--canvas-halo'), label = css('--canvas-ink');
    VE.forEach(function (e) {
      g.strokeStyle = dark ? 'rgba(140,158,170,.3)' : 'rgba(120,136,152,.3)';
      g.lineWidth = 1; g.setLineDash(e.inf ? [3, 3] : []);
      g.beginPath(); g.moveTo(e.a.x, e.a.y); g.lineTo(e.b.x, e.b.y); g.stroke();
    });
    g.setLineDash([]);
    VN.forEach(function (n) {
      var nd = N[n.id], r = n.d === 0 ? 13.5 : Math.max(4.5, Math.min(10.5, 3.6 + Math.sqrt(deg[n.id]) * 1.15));
      g.beginPath(); g.arc(n.x, n.y, r, 0, 6.2832);
      g.fillStyle = KG.typeColor(T[nd.t]); g.fill();
      g.lineWidth = n.d === 0 ? 2.4 : 1; g.strokeStyle = halo; g.stroke();
      if (n.d === 0 || deg[n.id] > 5) {
        g.font = (n.d === 0 ? 640 : 400) + ' ' + (n.d === 0 ? 14 : 11.5) + 'px "PingFang SC","Microsoft YaHei",sans-serif';
        g.textAlign = 'center'; g.lineWidth = 3.2;
        g.strokeStyle = halo;
        g.strokeText(nd.name, n.x, n.y - r - 5);
        g.fillStyle = label; g.fillText(nd.name, n.x, n.y - r - 5);
      }
    });
    c2.toBlob(function (blob) {
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'ya-kg-' + KG.safeName(N[sel].en, 'c' + sel) + '-' + hops + 'hop.png';
      a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); }, 500);
      KG.toast('子图已导出为 PNG');
    });
  }
})();
