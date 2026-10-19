/* OurBayis — all site JS lives here (CSP: script-src 'self', no inline). */
(function () {
  "use strict";

  // .reveal sections are only hidden once this runs (html.js), so a failed script never blanks the page
  document.documentElement.classList.add("js");

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
    // remember the couple's own order so "Suggested order" can put it back after a price sort
    if (grid) grid.querySelectorAll(".gift-card[data-cat]").forEach(function (card, i) { card.setAttribute("data-order", i); });
    function applyRegistryView() {
      if (!grid) return;
      var cards = Array.prototype.slice.call(grid.querySelectorAll(".gift-card[data-cat]"));
      var shown = 0;
      cards.forEach(function (card) {
        var ok = (catFilter === "all" || card.getAttribute("data-cat") === catFilter) &&
                 (!onlyAvail || !onlyAvail.checked || card.getAttribute("data-available") === "1");
        card.style.display = ok ? "" : "none";
        if (ok) shown++;
      });
      if (regSort) {
        var dir = regSort.value === "price_desc" ? -1 : 1;
        var key = regSort.value ? "data-price" : "data-order";
        cards.slice().sort(function (a, b) {
          return dir * ((+a.getAttribute(key) || 0) - (+b.getAttribute(key) || 0)) ||
                 (+a.getAttribute("data-order") - +b.getAttribute("data-order"));
        }).forEach(function (card) {
          var dlg = card.nextElementSibling && card.nextElementSibling.tagName === "DIALOG" ? card.nextElementSibling : null;
          grid.appendChild(card);
          if (dlg) grid.appendChild(dlg);
        });
      }
      if (regCount) {
        var label = (shown === 1 && regCount.getAttribute("data-label-one")) || regCount.getAttribute("data-label") || "";
        regCount.textContent = label.replace("{n}", shown) || (shown + " / " + cards.length);
      }
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
    // browsers restore the checkbox/select after Back or reload; make the list match them
    // (they're restored after DOMContentLoaded, so check again on pageshow)
    window.addEventListener("pageshow", function () {
      if (grid && ((onlyAvail && onlyAvail.checked) || (regSort && regSort.value))) applyRegistryView();
    });

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

  // Messages render at the top of the page, but many actions send you back to a spot lower down
  // (#item-12, #mine, #claim-3) — so the "done" / "that didn't work" line would be off-screen.
  // When the page opens at a #fragment, show the messages as a toast pinned to the bottom instead.
  document.addEventListener("DOMContentLoaded", function () {
    var stack = document.querySelector(".flash-stack");
    if (!stack || !location.hash) return;
    stack.classList.add("flash-toast");
    var x = document.createElement("button");
    x.type = "button";
    x.className = "flash-x";
    x.textContent = "✕";
    x.setAttribute("aria-label", stack.getAttribute("data-close-label") || "Close");
    x.addEventListener("click", function () { stack.remove(); });
    stack.appendChild(x);
    // a success note fades on its own; an error waits until it's closed
    if (!stack.querySelector(".flash-err")) setTimeout(function () { stack.remove(); }, 7000);
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
    // click on the backdrop closes — but only when the pointer is really outside the box:
    // a click on the dialog's own scrollbar also targets <dialog> and must not lose the form
    if (e.target.tagName === "DIALOG" && e.detail > 0) {
      var r = e.target.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) {
        e.target.close();
      }
    }

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
    if (b) setTimeout(function () { b.disabled = true; b.setAttribute("data-auto-disabled", ""); }, 0);
  });

  // starter-pack picker: live "N gifts selected · ₪total" beside the sticky submit, and a
  // "Select all" / "Clear" toggle per group (the form works the same without any of this)
  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("starter-form");
    var tally = document.getElementById("starter-tally");
    if (!form || !tally) return;
    function boxes(scope) {
      return Array.prototype.slice.call(scope.querySelectorAll("input[type=checkbox][data-price]:not(:disabled)"));
    }
    function update() {
      var n = 0, total = 0;
      boxes(form).forEach(function (cb) {
        if (!cb.checked) return;
        var qtyInput = form.querySelector("input[name='qty_" + cb.name.slice(4) + "']");
        var qty = Math.max(1, Math.min(99, parseInt(qtyInput && qtyInput.value, 10) || 1));
        n += 1;
        total += (parseInt(cb.getAttribute("data-price"), 10) || 0) * qty;
      });
      var tpl = n === 0 ? tally.getAttribute("data-none") : tally.getAttribute(n === 1 ? "data-one" : "data-many");
      tally.textContent = tpl.replace("{n}", n).replace("{total}", "₪" + total.toLocaleString("en-US"));
      form.querySelectorAll("[data-starter-all]").forEach(function (btn) {
        var group = boxes(btn.closest(".starter-group"));
        var all = group.length > 0 && group.every(function (cb) { return cb.checked; });
        btn.textContent = btn.getAttribute(all ? "data-label-none" : "data-label-all");
        btn.hidden = group.length === 0;
      });
    }
    form.addEventListener("change", update);
    form.addEventListener("input", function (e) { if (e.target.type === "number") update(); });
    form.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-starter-all]");
      if (!btn) return;
      var group = boxes(btn.closest(".starter-group"));
      var all = group.every(function (cb) { return cb.checked; });
      group.forEach(function (cb) { cb.checked = !all; });
      update();
    });
    update();
    // the browser may restore checked boxes when coming Back to the page
    window.addEventListener("pageshow", update);
  });

  // coming Back to a page from the back/forward cache would otherwise leave its buttons dead
  window.addEventListener("pageshow", function (e) {
    if (!e.persisted) return;
    document.querySelectorAll("[data-auto-disabled]").forEach(function (b) {
      b.disabled = false;
      b.removeAttribute("data-auto-disabled");
    });
  });
})();
