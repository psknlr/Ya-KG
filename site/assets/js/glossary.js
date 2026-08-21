/* Ya-KG · bilingual glossary table */
(function () {
  'use strict';
  var KG = window.KG, $ = KG.$, $$ = KG.$$, esc = KG.esc;
  var T = [], TZH = {}, rows = [], api = null;
  var q = '', chF = '', tF = new Set(), letter = '';

  fetch(KG.base + 'data/glossary.json', { cache: 'force-cache' })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      T = d.T; TZH = d.TZH; KG.T = T; KG.TZH = TZH;
      rows = d.G.map(function (r) { return { i: r[0], name: r[1], en: r[2], t: r[3], ch: r[4], pg: r[5] }; });
      T.forEach(function (_, i) { tF.add(i); });
      buildChips(d.CH);
      api = KG.table({
        mount: '#gl', data: rows, cols: 4, sortKey: 'name', dir: 'asc', page: 250,
        value: function (r, k) { return k === 'en' ? (r.en || '').toLowerCase() : k === 'type' ? (TZH[T[r.t]] || '') : r.name; },
        filter: function (r) {
          if (!tF.has(r.t)) return false;
          if (chF && r.ch.indexOf(+chF) < 0) return false;
          if (letter && (r.en || '').toUpperCase().charAt(0) !== letter) return false;
          if (!q) return true;
          return r.name.toLowerCase().indexOf(q) >= 0 || (r.en || '').toLowerCase().indexOf(q) >= 0;
        },
        row: function (r) {
          return '<tr><td><a href="' + KG.conceptUrl(r.i) + '">' + esc(r.name) + '</a></td>' +
            '<td style="font-style:italic;color:var(--ink-2)">' + esc(r.en) + '</td>' +
            '<td>' + KG.chip(T[r.t]) + '</td>' +
            '<td class="tiny dim nowrap">第' + r.ch.join('/') + '章 · p' + r.pg.slice(0, 3).join(', ') + '</td></tr>';
        },
        onPaint: function (view, shown) {
          $('#glCount').textContent = view.length.toLocaleString('zh-CN');
          $('#glMore').hidden = shown >= view.length;
          $('#glMore').textContent = '再显示 ' + Math.min(250, view.length - shown) + ' 条（共 ' + view.length + '）';
        }
      });
      $('#glState').remove();
      wire();
    })
    .catch(function (e) { $('#glState').innerHTML = '<span style="color:var(--bad)">术语表加载失败：' + esc(e.message) + '</span>'; });

  function buildChips(CH) {
    $('#glTypes').innerHTML = T.map(function (t, i) {
      return '<button class="tag-toggle" aria-pressed="true" data-t="' + i + '">' +
        '<span class="dot" style="background:' + KG.typeColor(t) + '"></span>' + esc(TZH[t] || t) + '</button>';
    }).join('');
    $('#glCh').innerHTML = '<option value="">全部章节</option>' + Object.keys(CH).map(function (k) {
      return '<option value="' + k + '">第' + k + '章 · ' + esc(CH[k]) + '</option>';
    }).join('');
    var L = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
    $('#glAlpha').innerHTML = '<button class="tag-toggle" aria-pressed="true" data-l="">全部</button>' +
      L.map(function (x) { return '<button class="tag-toggle" aria-pressed="false" data-l="' + x + '">' + x + '</button>'; }).join('');
  }

  function wire() {
    $('#glQ').addEventListener('input', function (e) { q = e.target.value.trim().toLowerCase(); api.refresh(); });
    $('#glCh').addEventListener('change', function (e) { chF = e.target.value; api.refresh(); });
    $('#glTypes').addEventListener('click', function (e) {
      var b = e.target.closest('.tag-toggle'); if (!b) return;
      var i = +b.dataset.t;
      if (tF.has(i) && tF.size === T.length) { tF = new Set([i]); }
      else if (tF.has(i)) { tF.delete(i); if (!tF.size) T.forEach(function (_, j) { tF.add(j); }); }
      else tF.add(i);
      $$('#glTypes .tag-toggle').forEach(function (x) { x.setAttribute('aria-pressed', tF.has(+x.dataset.t)); });
      api.refresh();
    });
    $('#glAlpha').addEventListener('click', function (e) {
      var b = e.target.closest('.tag-toggle'); if (!b) return;
      letter = b.dataset.l;
      $$('#glAlpha .tag-toggle').forEach(function (x) { x.setAttribute('aria-pressed', x === b); });
      api.refresh();
    });
    $('#glMore').addEventListener('click', function () { api.more(); });
    $('#glCsv').addEventListener('click', function () {
      KG.csv('ya-kg-glossary.csv', [['中文', 'English', '类型', '章节', '页码', '链接']].concat(
        api.view.map(function (r) {
          return [r.name, r.en, TZH[T[r.t]] || T[r.t], r.ch.join('/'), r.pg.join(' '),
            location.origin + KG.conceptUrl(r.i)];
        })));
    });
  }
})();
