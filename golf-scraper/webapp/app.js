/* Renders the deal dashboard from window.GOLF_DATA (see data.js). */
(function () {
  "use strict";

  var DATA = window.GOLF_DATA || { meta: {}, listings: [] };
  var meta = DATA.meta || {};
  var listings = DATA.listings || [];

  var money = new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: meta.currency || "CAD",
    maximumFractionDigits: 0,
  });

  var els = {
    metaLine: document.getElementById("meta-line"),
    stats: document.getElementById("stats"),
    list: document.getElementById("list"),
    search: document.getElementById("search"),
    dealsOnly: document.getElementById("deals-only"),
    sort: document.getElementById("sort"),
    generated: document.getElementById("generated"),
  };

  function isDeal(l) {
    return l.estimated_profit != null && l.estimated_profit > 0 &&
           l.margin_pct != null && l.margin_pct >= (meta.min_margin || 0.4);
  }

  function renderMeta() {
    var loc = meta.location ? cap(meta.location) : "Ottawa";
    els.metaLine.textContent =
      loc + ", ON · “" + (meta.query || "golf clubs") + "” · " +
      listings.length + " listings";
    if (meta.generated) {
      els.generated.textContent = "Updated " + meta.generated;
    }
  }

  function renderStats() {
    var deals = listings.filter(isDeal);
    var bestProfit = listings.reduce(function (m, l) {
      return Math.max(m, l.estimated_profit || 0);
    }, 0);
    var totalProfit = deals.reduce(function (s, l) {
      return s + (l.estimated_profit || 0);
    }, 0);
    var cards = [
      { num: listings.length, label: "Listings" },
      { num: deals.length, label: "Deals", good: true },
      { num: money.format(bestProfit), label: "Best profit", good: true },
      { num: money.format(totalProfit), label: "Total upside", good: true },
    ];
    els.stats.innerHTML = cards.map(function (c) {
      return '<div class="stat' + (c.good ? " good" : "") + '">' +
        '<div class="num">' + c.num + "</div>" +
        '<div class="label">' + c.label + "</div></div>";
    }).join("");
  }

  function cardHTML(l) {
    var dealCls = isDeal(l) ? " is-deal" : "";
    var thumb = l.image_url
      ? '<img class="thumb" src="' + esc(l.image_url) + '" alt="" loading="lazy" ' +
        'onerror="this.outerHTML=\'<div class=&quot;thumb-fallback&quot;>⛳</div>\'">'
      : '<div class="thumb-fallback">⛳</div>';

    var badges = [];
    if (l.model) badges.push('<span class="badge">' + esc(l.model) + "</span>");
    else if (l.brand) badges.push('<span class="badge">' + esc(l.brand) + "</span>");
    if (l.location) badges.push('<span class="badge loc">' + esc(l.location) + "</span>");

    var price = l.price != null ? money.format(l.price) : "—";
    var resale = l.estimated_resale != null
      ? "est. resale " + money.format(l.estimated_resale) : "no price guide";

    var profitHTML;
    if (l.estimated_profit != null) {
      var pos = l.estimated_profit >= 0;
      var mar = l.margin_pct != null ? Math.round(l.margin_pct * 100) + "%" : "";
      profitHTML =
        '<div class="amt ' + (pos ? "pos" : "neg") + '">' +
        (pos ? "+" : "") + money.format(l.estimated_profit) + "</div>" +
        '<div class="mar">' + mar + " margin</div>";
    } else {
      profitHTML = '<div class="unknown">unknown<br>model</div>';
    }

    return '<a class="card' + dealCls + '" href="' + esc(l.url || "#") +
      '" target="_blank" rel="noopener">' +
      thumb +
      '<div class="card-body">' +
        '<p class="card-title">' + esc(l.title || "Untitled") + "</p>" +
        '<div class="badge-row">' + badges.join("") + "</div>" +
        '<div class="price-row">' +
          '<span class="price">' + price + "</span>" +
          '<span class="resale">' + resale + "</span>" +
          '<span class="profit">' + profitHTML + "</span>" +
        "</div>" +
      "</div></a>";
  }

  function currentView() {
    var q = (els.search.value || "").trim().toLowerCase();
    var dealsOnly = els.dealsOnly.checked;
    var key = els.sort.value;

    var rows = listings.filter(function (l) {
      if (dealsOnly && !isDeal(l)) return false;
      if (!q) return true;
      return (l.title + " " + l.brand + " " + l.model).toLowerCase().indexOf(q) !== -1;
    });

    rows.sort(function (a, b) {
      if (key === "price") return (a.price || 1e9) - (b.price || 1e9);
      return (b[key] || -1e9) - (a[key] || -1e9);
    });
    return rows;
  }

  function renderList() {
    var rows = currentView();
    if (!rows.length) {
      els.list.innerHTML = '<div class="empty">No listings match.</div>';
      return;
    }
    els.list.innerHTML = rows.map(cardHTML).join("");
  }

  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  els.search.addEventListener("input", renderList);
  els.dealsOnly.addEventListener("change", renderList);
  els.sort.addEventListener("change", renderList);

  renderMeta();
  renderStats();
  renderList();
})();
