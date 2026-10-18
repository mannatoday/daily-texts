(function () {
  "use strict";

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(function () {});
  }

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

    var triggers = document.querySelectorAll(".install-trigger");
    if (!triggers.length) return;

    var hint = document.getElementById("install-hint");
    var ua = window.navigator.userAgent || "";
    var isIOS =
      /iphone|ipad|ipod/i.test(ua) ||
      (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
    var isAndroid = /android/i.test(ua);
    var deferredPrompt = null;

    for (var i = 0; i < triggers.length; i++) {
      triggers[i].hidden = false;
    }

    function hintText() {
      if (isIOS) {
        return "請用 Safari 開啟這個網站。點畫面最下方的「分享」，再選「加入主畫面」。";
      }
      if (isAndroid) {
        return "請先刪掉主畫面上舊的捷徑。再到 Chrome 選單選「安裝應用程式」。裝好後圖示不會再有 Chrome 小標。";
      }
      return "在瀏覽器選單選擇「安裝」或「加到主畫面」。";
    }

    function onClick() {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(function () {
          deferredPrompt = null;
        });
        return;
      }
      if (!hint) return;
      hint.hidden = !hint.hidden;
      if (!hint.hidden) hint.textContent = hintText();
    }

    for (var j = 0; j < triggers.length; j++) {
      triggers[j].addEventListener("click", onClick);
    }

    window.addEventListener("beforeinstallprompt", function (e) {
      e.preventDefault();
      deferredPrompt = e;
    });

    window.addEventListener("appinstalled", function () {
      deferredPrompt = null;
      for (var k = 0; k < triggers.length; k++) {
        triggers[k].hidden = true;
      }
      if (hint) hint.hidden = true;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
