/* OurBayis — all site JS lives here (CSP: script-src 'self', no inline). */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    // hamburger nav toggle
    var burger = document.getElementById("hamburger"), nav = document.getElementById("main-nav");
    if (burger) burger.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      burger.setAttribute("aria-expanded", open);
    });

    // registry browsing: category chips + "available only" + price sort, all client-side
    // (the whole list is already on the page; nothing here changes server state)
    var chips = document.getElementById("cat-chips");
    var onlyAvail = document.getElementById("only-available");
    var regSort = document.getElementById("reg-sort");
    var regCount = document.getElementById("reg-count");
    var grid = document.querySelector(".gift-grid");
    var catFilter = "all";
    function applyRegistryView() {
      if (!grid) return;
      var cards = Array.prototype.slice.call(grid.querySelectorAll(".gift-card[data-cat]"));
      var shown = 0;
      cards.forEach(function (card) {
        var ok = (catFilter === "all" || card.getAttribute("data-cat") === catFilter) &&
                 (!onlyAvail || !onlyAvail.checked || card.getAttribute("data-available") === "1");
        card.style.display = ok ? "" : "none";
        var dlg = card.nextElementSibling;
        if (ok) shown++;
      });
      if (regSort && regSort.value) {
        var dir = regSort.value === "price_desc" ? -1 : 1;
        cards.slice().sort(function (a, b) {
          return dir * ((+a.getAttribute("data-price") || 0) - (+b.getAttribute("data-price") || 0));
        }).forEach(function (card) {
          var dlg = card.nextElementSibling && card.nextElementSibling.tagName === "DIALOG" ? card.nextElementSibling : null;
          grid.appendChild(card);
          if (dlg) grid.appendChild(dlg);
        });
      }
      if (regCount) regCount.textContent = (regCount.getAttribute("data-label") || "").replace("{n}", shown) || (shown + " / " + cards.length);
    }
    if (chips) chips.addEventListener("click", function (e) {
      var chip = e.target.closest(".chip");
      if (!chip) return;
      chips.querySelectorAll(".chip").forEach(function (c) {
        c.classList.remove("active");
        c.setAttribute("aria-pressed", "false");
      });
      chip.classList.add("active");
      chip.setAttribute("aria-pressed", "true");
      catFilter = chip.getAttribute("data-filter");
      applyRegistryView();
    });
    if (onlyAvail) onlyAvail.addEventListener("change", applyRegistryView);
    if (regSort) regSort.addEventListener("change", applyRegistryView);

    // shana bundle-picker: clicking a bundle's CTA pre-selects it in the form
    var bundleSelect = document.getElementById("bundle-select");
    if (bundleSelect) document.addEventListener("click", function (e) {
      var a = e.target.closest("[data-bundle]");
      if (!a) return;
      bundleSelect.value = a.getAttribute("data-bundle");
      // keep the chosen package visible: the select sits at the top of the form
      setTimeout(function () { bundleSelect.focus({ preventScroll: true }); }, 0);
    });
  });

  // v3 phase 2: reveal-on-scroll for elements marked .reveal
  document.addEventListener("DOMContentLoaded", function () {
    var reveals = document.querySelectorAll(".reveal");
    if (!reveals.length) return;
    if (!("IntersectionObserver" in window) ||
        window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      reveals.forEach(function (el) { el.classList.add("in"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.05, rootMargin: "0px 0px -5% 0px" });
    reveals.forEach(function (el) { io.observe(el); });
  });

  // v3 phase 2: swap a broken/missing product photo for its category illustration
  document.addEventListener(
    "error",
    function (e) {
      var img = e.target;
      if (img.tagName === "IMG" && img.classList.contains("gift-img-img")) {
        var box = img.closest(".gift-img");
        if (box) { box.classList.add("ill-box"); }
        img.style.display = "none";
      }
    },
    true
  );

  // one shared modal opener/closer: any [data-modal] button opens the dialog with that id
  var lastOpener = null;
  document.addEventListener("click", function (e) {
    var opener = e.target.closest("[data-modal]");
    if (opener) {
      var dlg = document.getElementById(opener.getAttribute("data-modal"));
      if (dlg && dlg.showModal) {
        lastOpener = opener;
        dlg.showModal();
        e.preventDefault();
        var first = dlg.querySelector("input:not([type=hidden]):not(.hp), select, textarea");
        if (first) first.focus();
      }
    }
    var closer = e.target.closest("[data-close]");
    if (closer) { var d = closer.closest("dialog"); if (d) d.close(); }
    if (e.target.tagName === "DIALOG") e.target.close(); // click on backdrop

    // data-print: print the page
    var printBtn = e.target.closest("[data-print]");
    if (printBtn) window.print();

    // data-confirm on a button (not the whole form): only that submitter needs
    // confirmation, e.g. a "delete" button next to a harmless "save" button
    var confirmBtn = e.target.closest("[data-confirm]");
    if (confirmBtn && !window.confirm(confirmBtn.getAttribute("data-confirm"))) {
      e.preventDefault();
    }
  });

  // focus return to the element that opened a dialog, once it closes
  document.addEventListener(
    "close",
    function (e) {
      if (e.target.tagName === "DIALOG" && lastOpener && document.contains(lastOpener)) {
        lastOpener.focus();
        lastOpener = null;
      }
    },
    true
  );

  // share beacon: copy-link / WhatsApp buttons on the dashboard tell the server
  // the registry was shared (checklist step); CSRF token comes from <meta>.
  document.addEventListener("click", function (e) {
    var el = e.target.closest("[data-share-beacon]");
    if (!el || !window.fetch) return;
    var meta = document.querySelector('meta[name="csrf-token"]');
    var fd = new FormData();
    fd.append("csrf_token", meta ? meta.getAttribute("content") : "");
    fetch(el.getAttribute("data-share-beacon"), { method: "POST", body: fd, credentials: "same-origin", keepalive: true }).catch(function () {});
  });

  // copy-link buttons, with a select+prompt fallback when the Clipboard API fails
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-copy]");
    if (!btn) return;
    var text = btn.getAttribute("data-copy");
    var flash = function () {
      var old = btn.textContent;
      btn.textContent = btn.getAttribute("data-copied-label") || "Copied!";
      setTimeout(function () { btn.textContent = old; }, 1600);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(flash, function () { window.prompt("Copy:", text); });
    } else {
      window.prompt("Copy:", text);
    }
  });

  // data-autosubmit: change on a select/input submits its form
  document.addEventListener("change", function (e) {
    var el = e.target.closest("[data-autosubmit]");
    if (el && el.form) el.form.submit();
  });

  // data-confirm on the <form> itself (whole-form actions like /logout forms
  // don't need this, but a single-button "release this gift" form can use it)
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (form.hasAttribute("data-confirm") && !window.confirm(form.getAttribute("data-confirm"))) {
      e.preventDefault();
      return;
    }
    // prevent double submits
    var b = form.querySelector("button[type=submit]");
    if (b) setTimeout(function () { b.disabled = true; }, 0);
  });
})();
