/* Ya-KG · dataset statistics dashboard */
(function () {
  'use strict';
  var KG = window.KG, $ = KG.$, esc = KG.esc;

  fetch(KG.base + 'data/stats.json', { cache: 'force-cache' })
    .then(function (r) { return r.json(); })
    .then(render)
    .catch(function (e) { $('#stWrap').innerHTML = '<div class="empty" style="color:var(--bad)">统计数据加载失败：' + esc(e.message) + '</div>'; });

  function bars(rows, color, link) {
    var mx = Math.max.apply(null, rows.map(function (r) { return r[1]; })) || 1;
    return rows.map(function (r) {
      var label = link && r[2] != null
        ? '<a href="' + KG.conceptUrl(r[2]) + '">' + esc(r[0]) + '</a>' : esc(r[0]);
      var c = typeof color === 'function' ? color(r) : color;
      return '<div class="srow"><span class="k" title="' + esc(r[0]) + '">' + label + '</span>' +
        '<span class="bar" style="width:' + Math.max(2, r[1] / mx * 100) + '%;max-width:190px;background:' + c + '"></span>' +
        '<span class="v">' + r[1].toLocaleString('zh-CN') + '</span></div>';
    }).join('');
  }
  function card(title, body, sub) {
    return '<div class="card pad"><h4 style="margin-bottom:' + (sub ? '3px' : '12px') + '">' + title + '</h4>' +
      (sub ? '<p class="tiny dimmer mb2">' + sub + '</p>' : '') + body + '</div>';
  }

  function render(d) {
    KG.T = d.T; KG.TZH = d.TZH;
    var tc = d.types.map(function (r) { return [d.TZH[r[0]] || r[0], r[1], null, r[0]]; });
    var html = '';

    html += card('按类型的实体分布', bars(tc, function (r) { return KG.typeColor(r[3]); }),
      '14 个实体类型，共 ' + d.meta.n.toLocaleString('zh-CN') + ' 个概念');
    html += card('按谓词的关系分布', bars(d.rels.map(function (r) { return [d.RZH[r[0]] || r[0], r[1]]; }), 'var(--acc)'),
      '28 种关系谓词，共 ' + d.meta.e.toLocaleString('zh-CN') + ' 条三元组');
    html += card('各章概念数', bars(d.chapters, 'var(--t-Procedure)'), '概念可跨章出现，故合计大于实体总数');
    html += card('各章知识点数', bars(d.chapterFacts, 'var(--t-Prosthesis)'), '教材中抽取的结构化知识点');
    html += card('核心枢纽概念', bars(d.hubs, 'var(--t-Disease)', true), '按连接度（出向 + 入向关系数）排序');
    html += card('参数最密集的概念', bars(d.paramTop, 'var(--warm)', true), '带定量临床标准最多的概念');
    html += card('知识点属性分布', bars(d.attrs, 'var(--t-Classification)'), '知识点按属性名归类');
    html += card('参数单位分布', bars(d.units.map(function (u) { return [u[0] || '（无单位）', u[1]]; }), 'var(--t-Parameter)'),
      '定量参数所用的量纲');

    var evPct = (d.meta.ext / d.meta.e * 100).toFixed(1);
    html += card('数据质量', 
      '<div class="stack" style="gap:12px">' +
      qbar('有原文依据句的关系', d.meta.ext, d.meta.e, 'var(--ok)') +
      qbar('由共现推断的关系', d.meta.inf, d.meta.e, 'var(--warn)') +
      qbar('具备英文译名的实体', d.meta.g, d.meta.n, 'var(--acc)') +
      qbar('带同义词的实体', d.quality.aliased, d.meta.n, 'var(--t-Classification)') +
      qbar('带定义的实体', d.quality.defined, d.meta.n, 'var(--t-Prosthesis)') +
      '</div>', evPct + '% 的关系可回溯到教材原文');

    html += card('图结构', '<div class="stack" style="gap:2px">' +
      kv('实体（节点）', d.meta.n) + kv('关系（边）', d.meta.e) +
      kv('平均度', (2 * d.meta.e / d.meta.n).toFixed(2)) +
      kv('最大度', d.graph.maxDeg) +
      kv('孤立节点', d.graph.isolated) +
      kv('最大连通分量', d.graph.lcc + ' （' + (d.graph.lcc / d.meta.n * 100).toFixed(1) + '%）') +
      kv('连通分量数', d.graph.components) +
      kv('覆盖页码', d.graph.pages + ' 页（' + d.meta.pages + '）') +
      '</div>', '基于无向化后的连通性计算');

    $('#stWrap').innerHTML = html;
  }
  function kv(k, v) {
    return '<div class="aside-kv" style="display:flex;justify-content:space-between;font-size:13px;padding:5px 0;border-bottom:1px solid var(--line-soft)">' +
      '<span class="dim">' + k + '</span><b>' + (typeof v === 'number' ? v.toLocaleString('zh-CN') : v) + '</b></div>';
  }
  function qbar(label, v, total, color) {
    var pct = v / total * 100;
    return '<div><div class="spread tiny" style="margin-bottom:3px"><span>' + label + '</span>' +
      '<b>' + v.toLocaleString('zh-CN') + ' · ' + pct.toFixed(1) + '%</b></div>' +
      '<div class="progress" style="margin-top:0"><i style="width:' + pct + '%;background:' + color + '"></i></div></div>';
  }
})();
