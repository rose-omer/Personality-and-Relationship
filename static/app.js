// Aşamalı geliştirme: JS kapalıysa bütün sayfalar düz form olarak çalışır.
(function () {
  "use strict";

  var root = document.documentElement;

  // --- Tema düğmesi ---------------------------------------------------------
  function systemDark() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function isDark() {
    var theme = root.getAttribute("data-theme");
    return theme ? theme === "dark" : systemDark();
  }

  function syncThemeButton() {
    var dark = isDark();
    root.classList.toggle("is-dark", dark);
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.setAttribute("aria-label", dark ? "Açık temaya geç" : "Koyu temaya geç");
    });
    document.querySelectorAll('meta[name="theme-color"]').forEach(function (m) {
      m.setAttribute("content", dark ? "#181D42" : "#ECEDE9");
    });
  }

  function initTheme() {
    syncThemeButton();
    document.addEventListener("click", function (event) {
      var btn = event.target.closest("[data-theme-toggle]");
      if (!btn) return;
      var next = isDark() ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try {
        localStorage.setItem("tema", next);
      } catch (e) {
        /* Seçim yalnız bu sayfa için geçerli kalır. */
      }
      syncThemeButton();
    });
    if (window.matchMedia) {
      window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", syncThemeButton);
    }
  }

  // --- Soğuk başlangıç notu ------------------------------------------------
  function initColdStart() {
    var note = document.querySelector("[data-cold-start]");
    if (!note || !window.performance || !performance.getEntriesByType) return;
    var nav = performance.getEntriesByType("navigation")[0];
    if (nav && nav.responseStart - nav.requestStart > 3000) note.hidden = false;
  }

  // --- Kopyala ve paylaş ----------------------------------------------------
  function announce(el, text) {
    if (!el) return;
    el.textContent = "";
    window.setTimeout(function () {
      el.textContent = text;
    }, 30);
  }

  function initShare() {
    if (navigator.share) root.classList.add("can-share");

    document.addEventListener("click", function (event) {
      var copyBtn = event.target.closest("[data-copy]");
      if (copyBtn) {
        var status = document.getElementById(copyBtn.getAttribute("data-status"));
        var value = copyBtn.getAttribute("data-copy");
        var fallback = function () {
          var input = document.getElementById(copyBtn.getAttribute("data-input"));
          if (input) {
            input.focus();
            input.select();
          }
          announce(status, "Kopyalanamadı. Bağlantı seçildi; elle kopyala.");
        };
        if (navigator.clipboard && window.isSecureContext) {
          navigator.clipboard.writeText(value).then(function () {
            announce(status, "Bağlantı kopyalandı.");
          }, fallback);
        } else {
          fallback();
        }
        return;
      }

      var shareBtn = event.target.closest("[data-share]");
      if (shareBtn && navigator.share) {
        navigator
          .share({
            title: shareBtn.getAttribute("data-title") || document.title,
            url: shareBtn.getAttribute("data-share"),
          })
          .catch(function () {
            /* Kullanıcı paylaşım penceresini kapattı. */
          });
      }
    });

    document.addEventListener("submit", function (event) {
      var message = event.target.getAttribute("data-confirm");
      if (message && !window.confirm(message)) event.preventDefault();
    });
  }

  // --- Soru akışı: her ekranda bir adım ---------------------------------------
  function initQuiz() {
    var quiz = document.querySelector("[data-quiz]");
    if (!quiz) return;
    var form = quiz.querySelector("form");
    var steps = Array.prototype.slice.call(quiz.querySelectorAll("[data-step]"));
    var progress = quiz.querySelector("progress");
    var count = quiz.querySelector("[data-count]");
    var backBtn = quiz.querySelector("[data-back]");
    var nextBtn = quiz.querySelector("[data-next]");
    var total = steps.length - 1; // İlk adım giriş ekranıdır.
    var reduceMotion =
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    var advanceTimer = null;

    // Sunucu hata döndürdüyse ilk hatalı adımdan başla.
    var current = 0;
    var firstError = quiz.querySelector("[data-step] [data-has-error]");
    if (firstError) current = Math.max(0, steps.indexOf(firstError.closest("[data-step]")));

    quiz.classList.add("is-stepped");

    function stepValid(step) {
      var fields = step.querySelectorAll("input[required]");
      for (var i = 0; i < fields.length; i++) {
        if (!fields[i].checkValidity()) {
          fields[i].reportValidity();
          return false;
        }
      }
      return true;
    }

    function show(index, focus) {
      current = Math.max(0, Math.min(index, steps.length - 1));
      steps.forEach(function (step, i) {
        step.classList.toggle("is-current", i === current);
      });
      updateProgress();
      count.textContent = current === 0 ? "Başlangıç" : current + " / " + total;
      backBtn.hidden = current === 0;
      quiz.classList.toggle("is-last", current === steps.length - 1);
      nextBtn.querySelector("span").textContent = current === 0 ? "Teste başla" : "İleri";
      if (focus) {
        var target = steps[current].querySelector("[data-step-focus]");
        if (target) target.focus({ preventScroll: true });
        window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
      }
    }

    // Çubuk cevaplanan soru sayısını gösterir.
    function updateProgress() {
      progress.max = total;
      progress.value = steps.filter(function (step) {
        return step.querySelector('input[type="radio"]:checked');
      }).length;
    }

    form.addEventListener("change", updateProgress);

    function next() {
      if (!stepValid(steps[current])) return;
      if (current < steps.length - 1) show(current + 1, true);
    }

    nextBtn.addEventListener("click", next);
    backBtn.addEventListener("click", function () {
      window.clearTimeout(advanceTimer);
      show(current - 1, true);
    });

    // Fareyle ya da dokunarak seçince sonraki soruya geç. Klavyede ok tuşları
    // seçimi değiştirir ama ilerletmez (event.detail 0); kullanıcı İleri düğmesine basar.
    form.addEventListener("click", function (event) {
      var input = event.target.closest('.option input[type="radio"]');
      if (!input || event.detail === 0) return;
      if (current >= steps.length - 1) return;
      window.clearTimeout(advanceTimer);
      advanceTimer = window.setTimeout(next, reduceMotion ? 0 : 220);
    });

    // Enter ile örtük gönderimde, son adım değilse yalnız ilerle.
    form.addEventListener("submit", function (event) {
      if (current < steps.length - 1) {
        event.preventDefault();
        next();
        return;
      }
      if (form.dataset.sending === "1") {
        event.preventDefault();
        return;
      }
      form.dataset.sending = "1";
      quiz.querySelectorAll("button[type=submit]").forEach(function (b) {
        b.disabled = true;
      });
      quiz.classList.add("is-analyzing");
      var status = quiz.querySelector("[data-analyzing-focus]");
      if (status) status.focus();
    });

    // Tarayıcı geri tuşuyla sayfayı önbellekten açarsa formu yeniden kullanılabilir yap.
    window.addEventListener("pageshow", function (event) {
      if (!event.persisted) return;
      form.dataset.sending = "";
      quiz.classList.remove("is-analyzing");
      quiz.querySelectorAll("button[type=submit]").forEach(function (b) {
        b.disabled = false;
      });
    });

    show(current, Boolean(firstError));
  }

  // --- Soru görseli inmezse kırık resim yerine boş baskı alanı kalsın -----------
  function initQuestionImages() {
    document.querySelectorAll(".question__image").forEach(function (img) {
      function missing() {
        img.closest(".question__figure").classList.add("is-missing");
      }
      if (img.complete && img.naturalWidth === 0 && img.currentSrc) missing();
      img.addEventListener("error", missing);
    });
  }

  // --- Basit formlar: çift gönderimi engelle ----------------------------------
  function initOnceForms() {
    document.querySelectorAll("form[data-once]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (event.defaultPrevented) return;
        if (form.dataset.sending === "1") {
          event.preventDefault();
          return;
        }
        form.dataset.sending = "1";
        var btn = form.querySelector("button[type=submit]");
        if (!btn) return;
        btn.disabled = true;
        var label = btn.getAttribute("data-busy");
        var span = btn.querySelector("span");
        if (label && span) span.textContent = label;
      });
    });
  }

  // --- Bekleme ekranı: artan aralıkla yokla, 15 dk sonra dur ---------------------
  function initWait() {
    var box = document.querySelector("[data-poll]");
    if (!box) return;
    var url = box.getAttribute("data-poll");
    var status = document.getElementById("wait-status");
    var indicator = document.querySelector(".wait-indicator");
    var retry = document.querySelector("[data-poll-retry]");
    var LIMIT_MS = 15 * 60 * 1000;
    var started = Date.now();
    var delay = 5000;
    var timer = null;

    function stop(message) {
      window.clearTimeout(timer);
      indicator.classList.add("is-stopped");
      status.textContent = message;
      retry.hidden = false;
    }

    function schedule() {
      if (Date.now() - started > LIMIT_MS) {
        stop("15 dakikadır sonuç gelmedi; kontrolü durdurduk. Partnerin bitirince tekrar kontrol et.");
        return;
      }
      timer = window.setTimeout(check, delay);
      delay = Math.min(Math.round(delay * 1.5), 30000);
    }

    function check() {
      fetch(url, { headers: { Accept: "application/json" }, cache: "no-store" })
        .then(function (response) {
          if (response.status === 404) throw new Error("yok");
          if (!response.ok) throw new Error("ag");
          return response.json();
        })
        .then(function (data) {
          if (data.result_url) {
            status.textContent =
              data.status === "hazir" ? "Sonuç hazır, açılıyor." : "Analiz yapılamadı.";
            window.location.assign(data.result_url);
            return;
          }
          if (data.status === "analiz") {
            status.textContent = "İkiniz de bitirdiniz. Analiz hazırlanıyor.";
          }
          schedule();
        })
        .catch(function (error) {
          if (error.message === "yok") {
            stop("Bu oturumun süresi dolmuş ya da oturum silinmiş.");
            return;
          }
          status.textContent = "Bağlantı koptu; yeniden deneniyor.";
          schedule();
        });
    }

    retry.addEventListener("click", function () {
      retry.hidden = true;
      indicator.classList.remove("is-stopped");
      started = Date.now();
      delay = 5000;
      status.textContent = "Kontrol ediliyor.";
      check();
    });

    schedule();
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTheme();
    initColdStart();
    initShare();
    initQuiz();
    initQuestionImages();
    initOnceForms();
    initWait();
  });
})();
