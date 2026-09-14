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

    // registry gift chip filter
    var chips = document.getElementById("cat-chips");
    if (chips) chips.addEventListener("click", function (e) {
      var chip = e.target.closest(".chip");
      if (!chip) return;
      chips.querySelectorAll(".chip").forEach(function (c) { c.classList.remove("active"); });
      chip.classList.add("active");
      var f = chip.getAttribute("data-filter");
      document.querySelectorAll(".gift-card").forEach(function (card) {
        card.style.display = (f === "all" || card.getAttribute("data-cat") === f) ? "" : "none";
      });
    });

    // shana bundle-picker: clicking a bundle's CTA pre-selects it in the form
    var bundleSelect = document.getElementById("bundle-select");
    if (bundleSelect) document.addEventListener("click", function (e) {
      var a = e.target.closest("[data-bundle]");
      if (!a) return;
      bundleSelect.value = a.getAttribute("data-bundle");
    });
  });

  // one shared modal opener/closer: any [data-modal] button opens the dialog with that id
  document.addEventListener("click", function (e) {
    var opener = e.target.closest("[data-modal]");
    if (opener) {
      var dlg = document.getElementById(opener.getAttribute("data-modal"));
      if (dlg && dlg.showModal) { dlg.showModal(); e.preventDefault(); }
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

  // copy-link buttons
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-copy]");
    if (!btn) return;
    navigator.clipboard.writeText(btn.getAttribute("data-copy")).then(function () {
      var old = btn.textContent;
      btn.textContent = btn.getAttribute("data-copied-label") || "Copied!";
      setTimeout(function () { btn.textContent = old; }, 1600);
    });
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
