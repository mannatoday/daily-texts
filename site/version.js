// Bible version picker: rewrites Bible Gateway reading links and remembers
// the choice in localStorage. Visible labels update so the change is obvious.
(function () {
  "use strict";
  var KEY = "dailyTexts.bibleVersion";
  var DEFAULT_VERSION = "CUV";

  var select = document.getElementById("bible-version");
  if (!select) return;

  var hint = document.getElementById("bible-version-hint");
  var labelsByCode = {};
  Array.prototype.forEach.call(select.options, function (opt) {
    labelsByCode[opt.value] = opt.textContent.trim();
  });
  var validCodes = Object.keys(labelsByCode);

  var saved = null;
  try {
    saved = window.localStorage.getItem(KEY);
  } catch (err) {
    /* private mode or storage disabled */
  }
  var version = validCodes.indexOf(saved) >= 0 ? saved : DEFAULT_VERSION;

  function buildUrl(ref, code) {
    return (
      "https://www.biblegateway.com/passage/?search=" +
      encodeURIComponent(ref) +
      "&version=" +
      encodeURIComponent(code)
    );
  }

  function apply(code) {
    var label = labelsByCode[code] || code;
    var links = document.querySelectorAll("a.reading__open");
    Array.prototype.forEach.call(links, function (link) {
      var ref = link.getAttribute("data-ref");
      if (!ref) {
        try {
          var current = new URL(link.href);
          ref = current.searchParams.get("search") || "";
          if (ref) link.setAttribute("data-ref", ref);
        } catch (err) {
          return;
        }
      }
      if (!ref) return;
      link.href = buildUrl(ref, code);
      link.title = "在 Bible Gateway 閱讀" + label;
      var openLabel = link.querySelector(".reading__open-label");
      var text = "[閱讀 · " + label + "]";
      if (openLabel) {
        openLabel.textContent = text;
      } else {
        link.textContent = text;
      }
      var ariaBase = link.getAttribute("aria-label") || "";
      var base = ariaBase.replace(/（[^）]*）\s*$/, "").replace(/\s*·.*$/, "");
      if (!base) base = "閱讀";
      link.setAttribute("aria-label", base + "（" + label + "）");
    });
    if (hint) {
      hint.textContent = "［閱讀］目前使用：" + label;
    }
    select.setAttribute("aria-description", "目前譯本：" + label);
  }

  select.value = version;
  apply(version);

  select.addEventListener("change", function () {
    var code = select.value;
    try {
      window.localStorage.setItem(KEY, code);
    } catch (err) {
      /* ignore */
    }
    apply(code);
  });
})();
