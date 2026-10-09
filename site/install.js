(function () {
  "use strict";

  function isStandalone() {
    try {
      return (
        window.matchMedia("(display-mode: standalone)").matches ||
        window.navigator.standalone === true
      );
    } catch (err) {
      return false;
    }
  }

  function start() {
    if (isStandalone()) return;

    var ua = window.navigator.userAgent || "";
    var isIOS =
      /iphone|ipad|ipod/i.test(ua) ||
      (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
    var isAndroid = /android/i.test(ua);
    var deferredPrompt = null;

    var host = document.getElementById("install-slot");
    if (!host) host = document.querySelector(".site-foot");
    if (!host) return;

    var cta = document.createElement("div");
    cta.className = "install-cta";

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "install-btn";
    btn.textContent = "加到主畫面";

    var hint = document.createElement("p");
    hint.className = "install-hint";
    hint.hidden = true;

    cta.appendChild(btn);
    cta.appendChild(hint);
    if (host.id === "install-slot") host.appendChild(cta);
    else host.insertBefore(cta, host.firstChild);

    function hintText() {
      if (isIOS) {
        return "請用 Safari 開啟這個網站。點畫面最下方的「分享」，再選「加入主畫面」。";
      }
      if (isAndroid) {
        return "點瀏覽器右上角選單，再選「加到主畫面」或「安裝應用程式」。";
      }
      return "在瀏覽器選單選擇「安裝」或「加到主畫面」。";
    }

    btn.addEventListener("click", function () {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(function () {
          deferredPrompt = null;
        });
        return;
      }
      hint.hidden = !hint.hidden;
      if (!hint.hidden) hint.textContent = hintText();
    });

    window.addEventListener("beforeinstallprompt", function (e) {
      e.preventDefault();
      deferredPrompt = e;
    });

    window.addEventListener("appinstalled", function () {
      deferredPrompt = null;
      cta.remove();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
