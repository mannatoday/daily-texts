// Language toggle plus multi-version watchword renderer.
// Language: ?lang= → version hint → localStorage → Chinese.
// Version: ?version= (if it belongs to that language) → per-language localStorage → default.
(function () {
  "use strict";
  var LANG_KEY = "dailyTexts.lang";
  var VERSION_KEY = "dailyTexts.bibleVersion";
  var ENGLISH = [
    { code: "NIV", label: "NIV" },
    { code: "NLT", label: "NLT" },
    { code: "NIRV", label: "NIrV" },
    { code: "KJV", label: "KJV" }
  ];
  var CHINESE = ["CUV", "RCUV", "CNVT", "CSBT", "WCB"];
  var DEFAULTS = { zh: "RCUV", en: "NIV" };

  var select = document.getElementById("bible-version");
  var dataEl = document.getElementById("day-data");
  var day = null;
  if (dataEl) {
    try {
      day = JSON.parse(dataEl.textContent || "{}");
    } catch (err) {
      day = null;
    }
  }

  function queryParam(name) {
    try {
      return new URLSearchParams(window.location.search).get(name);
    } catch (err) {
      return null;
    }
  }

  function stored(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (err) {
      return null;
    }
  }

  function remember(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (err) {
      /* ignore */
    }
  }

  function listFor(lang) {
    var fallback = lang === "en"
      ? ENGLISH
      : CHINESE.map(function (code) { return { code: code, label: code }; });
    var fromDay = day && (lang === "en" ? day.english_versions : day.versions);
    if (!fromDay || !fromDay.length) return fallback;
    if (lang !== "en") return fromDay;
    var allowed = {};
    ENGLISH.forEach(function (item) { allowed[item.code] = true; });
    var merged = fromDay.filter(function (item) { return allowed[item.code]; });
    var seen = {};
    merged.forEach(function (item) { seen[item.code] = true; });
    fallback.forEach(function (item) {
      if (!seen[item.code]) merged.push(item);
    });
    return merged;
  }

  function codesFor(lang) {
    return listFor(lang).map(function (item) {
      return item.code;
    });
  }

  function resolveLang() {
    var q = queryParam("lang");
    if (q === "en" || q === "zh") return q;
    var version = queryParam("version");
    if (version && ENGLISH.some(function (item) { return item.code === version; })) return "en";
    if (version && CHINESE.indexOf(version) >= 0) return "zh";
    var saved = stored(LANG_KEY);
    if (saved === "en" || saved === "zh") return saved;
    if (document.documentElement.getAttribute("data-lang") === "en") return "en";
    return "zh";
  }

  function storedVersion(lang, codes) {
    var saved = stored(VERSION_KEY + "." + lang);
    if (saved && codes.indexOf(saved) >= 0) return saved;
    if (lang === "zh") {
      var legacy = stored(VERSION_KEY);
      if (legacy && codes.indexOf(legacy) >= 0) return legacy;
    }
    var fallback = (day && (lang === "en" ? day.default_english_version : day.default_version)) || DEFAULTS[lang];
    if (codes.indexOf(fallback) >= 0) return fallback;
    return codes[0];
  }

  function resolveVersion(lang, codes) {
    var q = queryParam("version");
    if (q && codes.indexOf(q) >= 0) return q;
    return storedVersion(lang, codes);
  }

  function gatewayMap() {
    var map = {
      CUV: "CUV",
      RCUV: "RCU17TS",
      CNVT: "CNVT",
      CSBT: "CSBT",
      KJV: "KJV",
      NIV: "NIV",
      NLT: "NLT",
      NIRV: "NIRV"
    };
    var extra = (day && day.gateway) || {};
    Object.keys(extra).forEach(function (key) { map[key] = extra[key]; });
    return map;
  }

  function gatewayCode(siteCode) {
    var map = gatewayMap();
    return Object.prototype.hasOwnProperty.call(map, siteCode) ? map[siteCode] : null;
  }

  function gatewayUrl(ref, siteCode) {
    var code = gatewayCode(siteCode);
    if (!code || !ref) return "";
    return (
      "https://www.biblegateway.com/passage/?search=" +
      encodeURIComponent(ref) +
      "&version=" +
      encodeURIComponent(code)
    );
  }

  function setLangChrome(lang) {
    var root = document.documentElement;
    if (lang === "en") {
      root.setAttribute("data-lang", "en");
      root.lang = "en";
    } else {
      root.removeAttribute("data-lang");
      root.lang = "zh-Hant";
    }
    var title = document.querySelector("title");
    if (title) {
      var next = title.getAttribute(lang === "en" ? "data-en" : "data-zh");
      if (next) title.textContent = next;
    }
    var buttons = document.querySelectorAll("[data-set-lang]");
    Array.prototype.forEach.call(buttons, function (btn) {
      btn.setAttribute(
        "aria-pressed",
        btn.getAttribute("data-set-lang") === lang ? "true" : "false"
      );
    });
  }

  function fillSelect(lang, version) {
    if (!select) return;
    var list = listFor(lang);
    select.innerHTML = "";
    list.forEach(function (item) {
      var opt = document.createElement("option");
      opt.value = item.code;
      opt.textContent = item.label;
      if (item.code === version) opt.selected = true;
      select.appendChild(opt);
    });
    select.value = version;
  }

  function textFor(block, siteCode) {
    if (!block || !block.translations) return "";
    var direct = block.translations[siteCode];
    if (direct && String(direct).trim()) return direct;
    var english = ENGLISH.some(function (item) { return item.code === siteCode; });
    if (!english) return "";
    for (var i = 0; i < ENGLISH.length; i++) {
      var alt = block.translations[ENGLISH[i].code];
      if (alt && String(alt).trim()) return alt;
    }
    return "";
  }

  function applyVerses(siteCode, lang) {
    if (!day) return;
    var map = { week: day.week_watchword, ot: day.ot, nt: day.nt };
    Object.keys(map).forEach(function (role) {
      var el = document.querySelector('[data-verse="' + role + '"]');
      var block = map[role];
      if (!el || !block) return;
      var text = textFor(block, siteCode);
      el.textContent = "";
      if (text) {
        el.textContent = text;
        reportFums(block, siteCode);
        return;
      }
      var href = gatewayUrl(block.reference, siteCode);
      if (!href) return;
      var link = document.createElement("a");
      link.className = "verse__fallback";
      link.href = href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = lang === "en" ? "Read on Bible Gateway" : "在 Bible Gateway 閱讀";
      el.appendChild(link);
    });
  }

  function applyReadingLinks(siteCode, lang) {
    var links = document.querySelectorAll("a.reading__open");
    Array.prototype.forEach.call(links, function (link) {
      var ref = link.getAttribute("data-ref");
      if (!ref) return;
      var href = gatewayUrl(ref, siteCode);
      if (!href) {
        link.hidden = true;
        return;
      }
      link.hidden = false;
      link.href = href;
      var zh = link.getAttribute("data-label-zh") || ref;
      if (lang === "en") {
        link.title = "Read on Bible Gateway";
        link.setAttribute("aria-label", "Read " + ref);
      } else {
        link.title = "在 Bible Gateway 閱讀";
        link.setAttribute("aria-label", "閱讀 " + zh);
      }
    });
  }

  var EXTRA_NOTICES = {
    NIV: "Scripture quotations taken from The Holy Bible, New International Version®, NIV®. Copyright © 1973, 1978, 1984, 2011 by Biblica, Inc.™ Used by permission. All rights reserved worldwide.",
    NLT: "Scripture quotations are taken from the Holy Bible, New Living Translation, copyright © 1996, 2004, 2015 by Tyndale House Foundation. Used by permission of Tyndale House Publishers, Carol Stream, Illinois 60188. All rights reserved.",
    NIRV: "Scripture quotations are taken from the Holy Bible, New International Reader’s Version®, NIrV®. Copyright © 1995, 1996, 1998, 2014 by Biblica, Inc.™ Used by permission. All rights reserved worldwide."
  };

  function reportFums(block, siteCode) {
    var raw = block && block.fums && block.fums[siteCode];
    if (!raw) return;
    raw.split(/\s+/).forEach(function (token) {
      if (!token || reportFums.seen[token]) return;
      reportFums.seen[token] = true;
      var ping = new Image();
      ping.referrerPolicy = "no-referrer";
      ping.src = "https://fums.api.bible/fums/?t=" + encodeURIComponent(token);
    });
  }
  reportFums.seen = {};

  function applyNotice(siteCode) {
    var note = document.getElementById("version-notice");
    if (!note) return;
    var notices = (day && day.notices) || {};
    var text = notices[siteCode] || EXTRA_NOTICES[siteCode] || "";
    note.hidden = !text;
    if (text) note.textContent = text;
  }

  function syncUrl(lang, version) {
    try {
      var url = new URL(window.location.href);
      url.searchParams.set("lang", lang);
      if (select) url.searchParams.set("version", version);
      window.history.replaceState({}, "", url.toString());
    } catch (err) {
      /* file:// or unsupported */
    }
  }

  function apply(lang, version) {
    setLangChrome(lang);
    fillSelect(lang, version);
    applyVerses(version, lang);
    applyReadingLinks(version, lang);
    applyNotice(version);
    remember(LANG_KEY, lang);
    remember(VERSION_KEY + "." + lang, version);
    syncUrl(lang, version);
  }

  var lang = resolveLang();
  var version = resolveVersion(lang, codesFor(lang));
  apply(lang, version);

  if (select) {
    select.addEventListener("change", function () {
      version = select.value;
      apply(lang, version);
    });
  }

  var buttons = document.querySelectorAll("[data-set-lang]");
  Array.prototype.forEach.call(buttons, function (btn) {
    btn.addEventListener("click", function () {
      var next = btn.getAttribute("data-set-lang");
      if (next !== "en" && next !== "zh") return;
      if (next === lang) return;
      lang = next;
      version = storedVersion(lang, codesFor(lang));
      apply(lang, version);
    });
  });
})();
