(function () {
  "use strict";

  function isStandalone() {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true
    );
  }

  if (isStandalone()) return;

  var ua = window.navigator.userAgent || "";
  var isIOS =
    /iphone|ipad|ipod/i.test(ua) ||
    (/Macintosh/.test(ua) && "ontouchend" in document); // iPadOS 13+
  var deferredPrompt = null;
  var built = false;

  function buildCta() {
    if (built) return document.querySelector(".install-cta");
    var foot = document.querySelector(".site-foot");
    if (!foot) return null;
    built = true;

    var cta = document.createElement("div");
    cta.className = "install-cta";
    cta.hidden = true;

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "install-btn";
    btn.textContent = "加到主畫面";

    var hint = document.createElement("p");
    hint.className = "install-hint";
    hint.hidden = true;

    cta.appendChild(btn);
    cta.appendChild(hint);
    foot.insertBefore(cta, foot.firstChild);

    btn.addEventListener("click", function () {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(function () {
          deferredPrompt = null;
        });
        return;
      }
      if (hint.hidden) {
        hint.textContent = isIOS
          ? "在 Safari 點最下方的「分享」，再選「加入主畫面」即可。"
          : "在瀏覽器選單選擇「安裝」或「加到主畫面」。";
        hint.hidden = false;
      } else {
        hint.hidden = true;
      }
    });

    return cta;
  }

  function showCta() {
    var cta = buildCta();
    if (cta) cta.hidden = false;
  }

  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferredPrompt = e;
    showCta();
  });

  window.addEventListener("appinstalled", function () {
    deferredPrompt = null;
    var cta = document.querySelector(".install-cta");
    if (cta) cta.remove();
  });

  // iOS has no beforeinstallprompt event; surface the button so users get steps.
  if (isIOS) showCta();
})();
