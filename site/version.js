// Multi-version watchword renderer.
// Priority: ?version= → localStorage → embedded default (RCUV).
(function () {
  "use strict";
  var KEY = "dailyTexts.bibleVersion";

  var select = document.getElementById("bible-version");
  if (!select) return;

  var dataEl = document.getElementById("day-data");
  var day = null;
  if (dataEl) {
    try {
      day = JSON.parse(dataEl.textContent || "{}");
    } catch (err) {
      day = null;
    }
  }

  var validCodes = Array.prototype.map.call(select.options, function (opt) {
    return opt.value;
  });
  var defaultVersion =
    (day && day.default_version) || select.value || "RCUV";

  function fromQuery() {
    try {
      return new URLSearchParams(window.location.search).get("version");
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

  function syncUrl(siteCode) {
    try {
      var url = new URL(window.location.href);
      url.searchParams.set("version", siteCode);
      window.history.replaceState({}, "", url.toString());
    } catch (err) {
      /* file:// or unsupported */
    }
  }

  function apply(siteCode) {
    select.value = siteCode;
    applyVerses(siteCode);
    try {
      window.localStorage.setItem(KEY, siteCode);
    } catch (err) {
      /* ignore */
    }
    syncUrl(siteCode);
  }

  apply(resolveVersion());

  select.addEventListener("change", function () {
    apply(select.value);
  });
})();
