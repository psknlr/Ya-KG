/* Ya-KG · concept page — neighbourhood minimap */
(function () {
  'use strict';
  var KG = window.KG, $ = KG.$, esc = KG.esc;
  var el = $('#nbrdata');
  if (!el) return;
  var D;
  try { D = JSON.parse(el.textContent); } catch (e) { return; }
  var cv = $('#minimap');
  if (!cv || !D.n.length) { if (cv) cv.remove(); var h = $('#minimapBox'); if (h && !D.n.length) h.remove(); return; }

  var cx = cv.getContext('2d'), W = 0, H = 0, pts = [], hov = null;

  function layout() {
    var r = cv.getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
    W = Math.max(1, r.width); H = Math.max(1, r.height);
    cv.width = W * dpr; cv.height = H * dpr;
    cx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var outs = D.n.filter(function (x) { return x[3] === 1; });
    var ins = D.n.filter(function (x) { return x[3] === 0; });
    var cxp = W / 2, cyp = H / 2, rad = Math.min(W, H) / 2 - 26;
    pts = [];
    function place(list, a0, a1) {
      list.forEach(function (x, i) {
        var a = list.length === 1 ? (a0 + a1) / 2 : a0 + (a1 - a0) * (i / (list.length - 1));
        var jitter = (i % 2) * 12;
        pts.push({ d: x, x: cxp + Math.cos(a) * (rad - jitter), y: cyp + Math.sin(a) * (rad - jitter) });
      });
    }
    place(outs, -Math.PI * 0.44, Math.PI * 0.44);
    place(ins, Math.PI * 0.56, Math.PI * 1.44);
    paint();
  }
  function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
  function paint() {
    var dark = KG.currentTheme() === 'dark';
    var halo = css('--canvas-halo'), ink = css('--canvas-ink');
    var cxp = W / 2, cyp = H / 2;
    cx.clearRect(0, 0, W, H);
    pts.forEach(function (p) {
      cx.strokeStyle = hov === p ? (dark ? 'rgba(103,205,216,.75)' : 'rgba(13,110,122,.6)')
                                 : (dark ? 'rgba(140,158,170,.28)' : 'rgba(120,136,152,.3)');
      cx.lineWidth = hov === p ? 1.6 : 1;
      cx.beginPath(); cx.moveTo(cxp, cyp); cx.lineTo(p.x, p.y); cx.stroke();
    });
    pts.forEach(function (p) {
      cx.beginPath(); cx.arc(p.x, p.y, hov === p ? 6 : 4.6, 0, 6.2832);
      cx.fillStyle = KG.typeColor(p.d[2]); cx.fill();
      cx.lineWidth = 1.2; cx.strokeStyle = halo; cx.stroke();
    });
    cx.beginPath(); cx.arc(cxp, cyp, 9, 0, 6.2832);
    cx.fillStyle = KG.typeColor(D.c[1]); cx.fill();
    cx.lineWidth = 2.2; cx.strokeStyle = ink; cx.stroke();
    if (hov) {
      var t = hov.d[1], f = 11.5;
      cx.font = f + 'px "PingFang SC","Microsoft YaHei",sans-serif';
      var w = cx.measureText(t).width + 12;
      var bx = Math.max(2, Math.min(W - w - 2, hov.x - w / 2)), by = hov.y > H / 2 ? hov.y - 26 : hov.y + 12;
      cx.fillStyle = css('--tip-bg');
      cx.beginPath(); cx.roundRect(bx, by, w, 19, 4); cx.fill();
      cx.fillStyle = css('--tip-ink');
      cx.textAlign = 'left'; cx.fillText(t, bx + 6, by + 13.5);
    }
  }
  function hit(e) {
    var r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top, best = null, bd = 14;
    pts.forEach(function (p) { var d = Math.hypot(p.x - mx, p.y - my); if (d < bd) { bd = d; best = p; } });
    return best;
  }
  cv.addEventListener('mousemove', function (e) {
    var h = hit(e);
    if (h !== hov) { hov = h; cv.style.cursor = h ? 'pointer' : 'default'; paint(); }
  });
  cv.addEventListener('mouseleave', function () { hov = null; paint(); });
  cv.addEventListener('click', function (e) { var h = hit(e); if (h) location.href = KG.conceptUrl(h.d[0]); });
  addEventListener('resize', layout);
  document.addEventListener('kg:theme', paint);
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', paint);
  if (!CanvasRenderingContext2D.prototype.roundRect) {
    CanvasRenderingContext2D.prototype.roundRect = function (x, y, w, h, r) {
      this.moveTo(x + r, y); this.arcTo(x + w, y, x + w, y + h, r); this.arcTo(x + w, y + h, x, y + h, r);
      this.arcTo(x, y + h, x, y, r); this.arcTo(x, y, x + w, y, r); this.closePath(); return this;
    };
  }
  layout();
})();
