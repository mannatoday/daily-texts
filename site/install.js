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
    var done = document.getElementById("install-done");
    if (isStandalone()) {
      if (done) done.hidden = false;
      return;
    }

    var triggers = document.querySelectorAll(".install-trigger");
    for (var i = 0; i < triggers.length; i++) {
      triggers[i].hidden = false;
      if (triggers[i].tagName === "BUTTON") {
        triggers[i].addEventListener("click", function () {
          window.location.href = "install.html";
        });
      }
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
      for (var k = 0; k < triggers.length; k++) {
        triggers[k].hidden = true;
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
