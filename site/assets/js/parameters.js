/* Ya-KG · quantitative clinical parameters table */
(function () {
  'use strict';
  var KG = window.KG, $ = KG.$, $$ = KG.$$, esc = KG.esc;
  var T = [], TZH = {}, rows = [], api = null, q = '', chF = '', uF = '';

  fetch(KG.base + 'data/parameters.json', { cache: 'force-cache' })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      T = d.T; TZH = d.TZH; KG.T = T; KG.TZH = TZH;
      rows = d.P.map(function (r) {
        return { i: r[0], ent: r[1], t: r[2], n: r[3], v: r[4], u: r[5], c: r[6], pg: r[7], ch: r[8] };
      });
      buildFilters(d.CH, d.units);
      api = KG.table({
        mount: '#pt', data: rows, cols: 5, sortKey: 'ent', dir: 'asc', page: 250,
        value: function (r, k) { return k === 'pg' ? r.pg : k === 'n' ? r.n : k === 'v' ? r.v : r.ent; },
        filter: function (r) {
          if (chF && r.ch.indexOf(+chF) < 0) return false;
          if (uF && r.u !== uF) return false;
          if (!q) return true;
          return r.ent.toLowerCase().indexOf(q) >= 0 || (r.n || '').toLowerCase().indexOf(q) >= 0 ||
            (r.v || '').toLowerCase().indexOf(q) >= 0 || (r.c || '').toLowerCase().indexOf(q) >= 0;
        },
        row: function (r) {
          return '<tr><td><a href="' + KG.conceptUrl(r.i) + '">' + esc(r.ent) + '</a> ' + KG.chip(T[r.t]) + '</td>' +
            '<td>' + esc(r.n) + '</td>' +
            '<td class="nowrap"><span class="prm-v">' + esc(r.v) + esc(r.u) + '</span></td>' +
            '<td class="small dim">' + esc(r.c) + '</td>' +
            '<td class="tiny dimmer nowrap">p' + r.pg + '</td></tr>';
        },
        onPaint: function (view, shown) {
          $('#ptCount').textContent = view.length.toLocaleString('zh-CN');
          $('#ptMore').hidden = shown >= view.length;
          $('#ptMore').textContent = '再显示 ' + Math.min(250, view.length - shown) + ' 条（共 ' + view.length + '）';
        }
      });
      $('#ptState').remove();
      wire();
    })
    .catch(function (e) { $('#ptState').innerHTML = '<span style="color:var(--bad)">参数表加载失败：' + esc(e.message) + '</span>'; });

  function buildFilters(CH, units) {
    $('#ptCh').innerHTML = '<option value="">全部章节</option>' + Object.keys(CH).map(function (k) {
      return '<option value="' + k + '">第' + k + '章 · ' + esc(CH[k]) + '</option>';
    }).join('');
    $('#ptUnit').innerHTML = '<option value="">全部单位</option>' + units.map(function (u) {
      return '<option value="' + esc(u[0]) + '">' + (u[0] ? esc(u[0]) : '（无单位）') + ' · ' + u[1] + '</option>';
    }).join('');
  }
  function wire() {
    $('#ptQ').addEventListener('input', function (e) { q = e.target.value.trim().toLowerCase(); api.refresh(); });
    $('#ptCh').addEventListener('change', function (e) { chF = e.target.value; api.refresh(); });
    $('#ptUnit').addEventListener('change', function (e) { uF = e.target.value; api.refresh(); });
    $('#ptMore').addEventListener('click', function () { api.more(); });
    $('#ptCsv').addEventListener('click', function () {
      KG.csv('ya-kg-parameters.csv', [['概念', '类型', '参数', '数值', '单位', '适用条件', '页码', '链接']].concat(
        api.view.map(function (r) {
          return [r.ent, TZH[T[r.t]] || T[r.t], r.n, r.v, r.u, r.c, r.pg, location.origin + KG.conceptUrl(r.i)];
        })));
    });
  }
})();
