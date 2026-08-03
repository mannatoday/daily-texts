// Bible version picker: rewrites Bible Gateway reading links and remembers
// the choice in localStorage.
(function () {
  "use strict";
  var KEY = "dailyTexts.bibleVersion";
  var DEFAULT_VERSION = "CUV";

  var select = document.getElementById("bible-version");
  if (!select) return;

  var validCodes = Array.prototype.map.call(select.options, function (opt) {
    return opt.value;
  });

  var saved = null;
  try {
    saved = window.localStorage.getItem(KEY);
  } catch (err) {
    /* private mode or storage disabled */
  }
  var version = validCodes.indexOf(saved) >= 0 ? saved : DEFAULT_VERSION;

  function apply(code) {
    var links = document.querySelectorAll("a.reading__open");
    Array.prototype.forEach.call(links, function (link) {
      try {
        var url = new URL(link.href);
        url.searchParams.set("version", code);
        link.href = url.toString();
      } catch (err) {
        /* leave link unchanged */
      }
    });
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
