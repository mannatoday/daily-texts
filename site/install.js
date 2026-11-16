(function () {
  "use strict";

  if ("serviceWorker" in navigator) {
    var swUrl = "sw.js";
    var manifest = document.querySelector('link[rel="manifest"]');
    if (manifest && manifest.href) {
      try {
        swUrl = new URL("sw.js", manifest.href).href;
      } catch (err) {}
    }
    navigator.serviceWorker.register(swUrl).catch(function () {});
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
    var done = document.getElementById("install-done");
    var note = document.querySelector(".home-screen-note");
    if (isStandalone()) {
      if (done) done.hidden = false;
      if (note) note.hidden = true;
      return;
    }

    var deferredPrompt = null;
    var nowWrap = document.getElementById("install-now-wrap");
    var now = document.getElementById("install-now");

    window.addEventListener("beforeinstallprompt", function (e) {
      e.preventDefault();
      deferredPrompt = e;
      if (nowWrap) nowWrap.hidden = false;
    });

    if (now) {
      now.addEventListener("click", function () {
        if (!deferredPrompt) return;
        var prompt = deferredPrompt;
        deferredPrompt = null;
        prompt.prompt();
        prompt.userChoice.then(function () {
          if (nowWrap) nowWrap.hidden = true;
        });
      });
    }

    window.addEventListener("appinstalled", function () {
      deferredPrompt = null;
      if (nowWrap) nowWrap.hidden = true;
      if (done) done.hidden = false;
      if (note) note.hidden = true;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
