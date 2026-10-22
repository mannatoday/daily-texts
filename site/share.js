(function () {
  "use strict";

  function dayData() {
    var el = document.getElementById("day-data");
    if (!el) return null;
    try {
      return JSON.parse(el.textContent || "{}");
    } catch (err) {
      return null;
    }
  }

  function isEnglish() {
    return document.documentElement.getAttribute("data-lang") === "en";
  }

  function verseText(role) {
    var el = document.querySelector('[data-verse="' + role + '"]');
    if (!el) return "";
    return (el.textContent || "").replace(/\s+/g, " ").trim();
  }

  function refFor(block, english) {
    if (!block) return "";
    if (english) return block.reference || block.reference_zh || "";
    return block.reference_zh || block.reference || "";
  }

  function pageUrl(day) {
    try {
      var path = window.location.pathname || "";
      var base = path.replace(/[^/]+$/, "");
      var file = (day && day.date ? day.date : "today") + ".html";
      return window.location.origin + base + file + window.location.search;
    } catch (err) {
      return window.location.href;
    }
  }

  function shareTitle(day, english) {
    if (!day) return english ? "Moravian Daily Texts" : "摩拉維亞每日箴言";
    if (english) {
      return (day.date_title_en || day.date || "") + " · Moravian Daily Texts";
    }
    return (day.date_title_zh || day.date || "") + " · 摩拉維亞每日箴言";
  }

  function shareText(day, english) {
    var lines = [];
    var ot = day && day.ot;
    var nt = day && day.nt;
    var otRef = refFor(ot, english);
    var ntRef = refFor(nt, english);
    var otText = verseText("ot");
    var ntText = verseText("nt");

    if (english) {
      if (otText) {
        lines.push("Old Testament" + (otRef ? " (" + otRef + ")" : ""));
        lines.push(otText);
      }
      if (ntText) {
        if (lines.length) lines.push("");
        lines.push("New Testament" + (ntRef ? " (" + ntRef + ")" : ""));
        lines.push(ntText);
      }
    } else {
      if (otText) {
        lines.push("舊約" + (otRef ? "（" + otRef + "）" : ""));
        lines.push(otText);
      }
      if (ntText) {
        if (lines.length) lines.push("");
        lines.push("新約" + (ntRef ? "（" + ntRef + "）" : ""));
        lines.push(ntText);
      }
      var prayer = ((day && day.prayer) || "").trim();
      if (prayer) {
        if (lines.length) lines.push("");
        lines.push("今日禱文");
        lines.push(prayer);
        var source = document.querySelector(".prayer-source");
        var cite = source && (source.textContent || "").trim();
        if (cite) lines.push(cite);
      }
    }
    return lines.join("\n");
  }

  function showStatus(message) {
    var status = document.getElementById("share-status");
    if (!status) return;
    status.hidden = false;
    status.textContent = message;
    window.setTimeout(function () {
      status.hidden = true;
      status.textContent = "";
    }, 2200);
  }

  function copyFallback(text, english) {
    var done = english ? "Copied" : "已複製";
    var fail = english ? "Could not copy" : "無法複製";
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () { showStatus(done); },
        function () { showStatus(fail); }
      );
      return;
    }
    try {
      var area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.left = "-9999px";
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      document.body.removeChild(area);
      showStatus(done);
    } catch (err) {
      showStatus(fail);
    }
  }

  function start() {
    var btn = document.getElementById("share-day");
    if (!btn) return;

    btn.addEventListener("click", function () {
      var day = dayData();
      var english = isEnglish();
      var url = pageUrl(day);
      var title = shareTitle(day, english);
      var body = shareText(day, english);
      var text = body ? body + "\n\n" + url : url;
      var payload = { title: title, text: body, url: url };

      if (typeof navigator.share === "function") {
        navigator.share(payload).catch(function (err) {
          if (err && err.name === "AbortError") return;
          copyFallback(text, english);
        });
        return;
      }
      copyFallback(text, english);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
