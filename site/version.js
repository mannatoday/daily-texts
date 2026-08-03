// Multi-version watchword renderer + Bible Gateway link sync.
// Priority: ?version= → localStorage → embedded default (RCUV).
(function () {
  "use strict";
  var KEY = "dailyTexts.bibleVersion";
  var GATEWAY = {
    CUV: "CUV",
    RCUV: "RCU17TS",
    CNVT: "CNVT",
    CCBT: "CCBT",
    CSBT: "CSBT"
  };

  var select = document.getElementById("bible-version");
  if (!select) return;

  var hint = document.getElementById("bible-version-hint");
  var dataEl = document.getElementById("day-data");
  var day = null;
  if (dataEl) {
    try {
      day = JSON.parse(dataEl.textContent || "{}");
    } catch (err) {
      day = null;
    }
  }

  var labelsByCode = {};
  Array.prototype.forEach.call(select.options, function (opt) {
    labelsByCode[opt.value] = opt.textContent.trim();
  });
  var validCodes = Object.keys(labelsByCode);
  var defaultVersion =
    (day && day.default_version) || select.value || "RCUV";

  function fromQuery() {
    try {
      var params = new URLSearchParams(window.location.search);
      return params.get("version");
    } catch (err) {
      return null;
    }
  }

  function fromStorage() {
    try {
      return window.localStorage.getItem(KEY);
    } catch (err) {
      return null;
    }
  }

  function resolveVersion() {
    var q = fromQuery();
    if (q && validCodes.indexOf(q) >= 0) return q;
    var s = fromStorage();
    if (s && validCodes.indexOf(s) >= 0) return s;
    if (validCodes.indexOf(defaultVersion) >= 0) return defaultVersion;
    return validCodes[0];
  }

  function gatewayCode(siteCode) {
    return GATEWAY[siteCode] || GATEWAY.RCUV || siteCode;
  }

  function buildUrl(ref, siteCode) {
    return (
      "https://www.biblegateway.com/passage/?search=" +
      encodeURIComponent(ref) +
      "&version=" +
      encodeURIComponent(gatewayCode(siteCode))
    );
  }

  function textFor(block, siteCode) {
    if (!block || !block.translations) return null;
    return (
      block.translations[siteCode] ||
      block.translations[defaultVersion] ||
      null
    );
  }

  function applyVerses(siteCode) {
    if (!day) return;
    var map = { week: day.week_watchword, ot: day.ot, nt: day.nt };
    Object.keys(map).forEach(function (role) {
      var el = document.querySelector('[data-verse="' + role + '"]');
      if (!el) return;
      var text = textFor(map[role], siteCode);
      if (text) el.textContent = text;
    });
  }

  function applyLinks(siteCode) {
    var label = labelsByCode[siteCode] || siteCode;
    var links = document.querySelectorAll("a.reading__open");
    Array.prototype.forEach.call(links, function (link) {
      var ref = link.getAttribute("data-ref");
      if (!ref) return;
      link.href = buildUrl(ref, siteCode);
      link.title = "在 Bible Gateway 閱讀" + label;
      var openLabel = link.querySelector(".reading__open-label");
      var text = "[閱讀 · " + label + "]";
      if (openLabel) openLabel.textContent = text;
      else link.textContent = text;
      link.setAttribute("aria-label", "閱讀（" + label + "）");
    });
  }

  function syncUrl(siteCode) {
    try {
      var url = new URL(window.location.href);
      url.searchParams.set("version", siteCode);
      window.history.replaceState({}, "", url.toString());
    } catch (err) {
      /* file:// or unsupported */
    }
  }

  function apply(siteCode, options) {
    options = options || {};
    select.value = siteCode;
    applyVerses(siteCode);
    applyLinks(siteCode);
    var label = labelsByCode[siteCode] || siteCode;
    if (hint) hint.textContent = "目前顯示：" + label;
    try {
      window.localStorage.setItem(KEY, siteCode);
    } catch (err) {
      /* ignore */
    }
    if (options.updateUrl !== false) syncUrl(siteCode);
  }

  var initial = resolveVersion();
  apply(initial, { updateUrl: true });

  select.addEventListener("change", function () {
    apply(select.value, { updateUrl: true });
  });
})();
