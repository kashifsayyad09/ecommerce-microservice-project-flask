/**
 * VeeraOps Store — shared GSAP animation layer for the storefront.
 *
 * Same architecture as theme-toggle.js / ai-chat-widget.js: one file,
 * included via an absolute-path <script> tag, works on every page via the
 * existing ingress catch-all to main-service.
 *
 * Design rules (learned from the theme-toggle build):
 *  - Never block or change existing behavior. Every animation is layered
 *    ON TOP of the site's existing class-toggle logic (.open, cart badge
 *    text, etc.) via MutationObserver -- it never replaces or monkey-patches
 *    any page's inline functions, so it works the same way on every page
 *    even though each category page has its own separate inline script.
 *  - If GSAP hasn't loaded yet (slow/blocked CDN), everything still works
 *    exactly as before (plain CSS classes) -- animation is enhancement
 *    only, never a dependency for functionality.
 *  - Respects prefers-reduced-motion.
 *  - Shares the exact same GSAP CDN URL as theme-toggle.js so the two
 *    scripts never load GSAP twice.
 */
(function () {
  "use strict";

  const GSAP_SRC = "https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js";
  const REDUCED_MOTION = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function loadGsap() {
    return new Promise((resolve) => {
      if (window.gsap) return resolve(window.gsap);
      const existing = document.querySelector(`script[src="${GSAP_SRC}"]`);
      if (existing) {
        if (window.gsap) return resolve(window.gsap);
        existing.addEventListener("load", () => resolve(window.gsap));
        existing.addEventListener("error", () => resolve(null));
        return;
      }
      const script = document.createElement("script");
      script.src = GSAP_SRC;
      script.onload = () => resolve(window.gsap);
      script.onerror = () => resolve(null);
      document.head.appendChild(script);
    });
  }

  // ---------------------------------------------------------------------
  // 1. Header + hero entrance
  // ---------------------------------------------------------------------
  function animateEntrance(gsap) {
    const header = document.querySelector("header");
    const heroCandidates = [".hero", ".hero-banner", ".banner", ".carousel", "#dealsScroll"];
    const hero = heroCandidates.map((s) => document.querySelector(s)).find(Boolean);

    const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
    if (header) {
      tl.from(header, { y: -24, opacity: 0, duration: 0.5 });
    }
    if (hero) {
      tl.from(hero, { opacity: 0, y: 18, duration: 0.5 }, header ? "-=0.25" : 0);
    }
  }

  // ---------------------------------------------------------------------
  // 2. Scroll-reveal + auto-reveal for dynamically rendered cards
  //    (product cards, deal cards, and anything else with these classes
  //    get faded/lifted in the first time they appear in the viewport --
  //    covers both static markup and cards injected later via innerHTML).
  // ---------------------------------------------------------------------
  const CARD_SELECTOR = ".product-card, .deal-card, .cart-item-row";
  const revealed = new WeakSet();

  function revealCard(gsap, el) {
    if (revealed.has(el)) return;
    revealed.add(el);
    gsap.fromTo(
      el,
      { opacity: 0, y: 16, scale: 0.97 },
      { opacity: 1, y: 0, scale: 1, duration: 0.45, ease: "power2.out" }
    );
  }

  function setupScrollReveal(gsap) {
    if (typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            revealCard(gsap, entry.target);
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: "0px 0px -40px 0px" }
    );

    function observeAll(root) {
      root.querySelectorAll(CARD_SELECTOR).forEach((el) => {
        if (!revealed.has(el)) io.observe(el);
      });
    }

    observeAll(document);

    // Product/deal grids are re-rendered via innerHTML on filter/search/
    // cart changes, so watch the whole document for newly added cards.
    const mo = new MutationObserver((mutations) => {
      for (const m of mutations) {
        m.addedNodes.forEach((node) => {
          if (node.nodeType !== 1) return;
          if (node.matches && node.matches(CARD_SELECTOR)) io.observe(node);
          if (node.querySelectorAll) observeAll(node);
        });
      }
    });
    mo.observe(document.body, { childList: true, subtree: true });
  }

  // ---------------------------------------------------------------------
  // 3. Hover micro-interactions on cards and buttons
  // ---------------------------------------------------------------------
  function setupHoverEffects(gsap) {
    const HOVER_LIFT_SELECTOR = ".product-card, .deal-card";
    const HOVER_PRESS_SELECTOR = ".add-btn, .deal-add-btn, .checkout-cta, .topbar-btn";

    document.addEventListener("pointerenter", (e) => {
      const card = e.target.closest && e.target.closest(HOVER_LIFT_SELECTOR);
      if (card) gsap.to(card, { y: -4, boxShadow: "0 12px 28px rgba(0,0,0,0.14)", duration: 0.2, ease: "power2.out" });
    }, true);
    document.addEventListener("pointerleave", (e) => {
      const card = e.target.closest && e.target.closest(HOVER_LIFT_SELECTOR);
      if (card) gsap.to(card, { y: 0, boxShadow: "none", duration: 0.2, ease: "power2.out" });
    }, true);

    document.addEventListener("pointerdown", (e) => {
      const btn = e.target.closest && e.target.closest(HOVER_PRESS_SELECTOR);
      if (btn) gsap.to(btn, { scale: 0.94, duration: 0.1, ease: "power1.out" });
    });
    document.addEventListener("pointerup", (e) => {
      const btn = e.target.closest && e.target.closest(HOVER_PRESS_SELECTOR);
      if (btn) gsap.to(btn, { scale: 1, duration: 0.25, ease: "back.out(3)" });
    });
  }

  // ---------------------------------------------------------------------
  // 4. Modal / overlay open+close animation
  //    Layers on top of the existing .open class toggle used by
  //    openModal()/closeModal() (and equivalents on other pages) via
  //    MutationObserver -- works regardless of each page's own inline JS.
  // ---------------------------------------------------------------------
  function setupOverlayAnimations(gsap) {
    const overlaySelector = ".overlay, .drawer-overlay";
    const animating = new WeakSet();

    function animateOpen(el) {
      const card = el.querySelector(".modal-card") || el.querySelector(".drawer") || el;
      gsap.fromTo(el, { opacity: 0 }, { opacity: 1, duration: 0.2, ease: "power1.out" });
      if (card !== el) {
        gsap.fromTo(
          card,
          { opacity: 0, y: 16, scale: 0.96 },
          { opacity: 1, y: 0, scale: 1, duration: 0.3, delay: 0.03, ease: "back.out(1.6)" }
        );
      }
    }

    function observe(el) {
      if (animating.has(el)) return;
      animating.add(el);
      let wasOpen = el.classList.contains("open");
      const mo = new MutationObserver(() => {
        const isOpen = el.classList.contains("open");
        if (isOpen && !wasOpen) animateOpen(el);
        wasOpen = isOpen;
      });
      mo.observe(el, { attributes: true, attributeFilter: ["class"] });
    }

    document.querySelectorAll(overlaySelector).forEach(observe);
    const domObserver = new MutationObserver((mutations) => {
      for (const m of mutations) {
        m.addedNodes.forEach((node) => {
          if (node.nodeType !== 1) return;
          if (node.matches && node.matches(overlaySelector)) observe(node);
          if (node.querySelectorAll) node.querySelectorAll(overlaySelector).forEach(observe);
        });
      }
    });
    domObserver.observe(document.body, { childList: true, subtree: true });

    // The sliding cart drawer (<aside id="cartDrawer">) isn't itself an
    // ".overlay"/".drawer-overlay" element, so give it a matching bounce.
    const cartDrawer = document.getElementById("cartDrawer");
    const drawerOverlayEl = document.getElementById("drawerOverlay");
    if (cartDrawer && drawerOverlayEl) {
      let wasOpen = drawerOverlayEl.classList.contains("open");
      const mo = new MutationObserver(() => {
        const isOpen = drawerOverlayEl.classList.contains("open");
        if (isOpen && !wasOpen) {
          gsap.fromTo(cartDrawer, { x: 24, opacity: 0.6 }, { x: 0, opacity: 1, duration: 0.35, ease: "power3.out" });
        }
        wasOpen = isOpen;
      });
      mo.observe(drawerOverlayEl, { attributes: true, attributeFilter: ["class"] });
    }
  }

  // ---------------------------------------------------------------------
  // 5. Cart badge "pop" when the item count changes
  // ---------------------------------------------------------------------
  function setupCartBadgeAnimation(gsap) {
    const badge = document.getElementById("cartCountBadge");
    if (!badge) return;
    let lastText = badge.textContent;
    const mo = new MutationObserver(() => {
      if (badge.textContent !== lastText) {
        lastText = badge.textContent;
        gsap.fromTo(badge, { scale: 1.6 }, { scale: 1, duration: 0.4, ease: "elastic.out(1, 0.5)" });
      }
    });
    mo.observe(badge, { childList: true, characterData: true, subtree: true });
  }

  // ---------------------------------------------------------------------
  // 6. Toast notification slide/fade
  // ---------------------------------------------------------------------
  function setupToastAnimation(gsap) {
    const toast = document.getElementById("toast");
    if (!toast) return;
    let wasShown = toast.classList.contains("show");
    const mo = new MutationObserver(() => {
      const isShown = toast.classList.contains("show");
      if (isShown && !wasShown) {
        gsap.fromTo(toast, { y: 16, opacity: 0 }, { y: 0, opacity: 1, duration: 0.3, ease: "back.out(2)" });
      }
      wasShown = isShown;
    });
    mo.observe(toast, { attributes: true, attributeFilter: ["class"] });
  }

  async function init() {
    if (REDUCED_MOTION) return; // respect the user's OS preference, no animation layer at all

    const gsap = await loadGsap();
    if (!gsap) return; // CDN unavailable -- site already works fine without this layer

    const subsystems = [
      animateEntrance,
      setupScrollReveal,
      setupHoverEffects,
      setupOverlayAnimations,
      setupCartBadgeAnimation,
      setupToastAnimation,
    ];
    for (const fn of subsystems) {
      try {
        fn(gsap);
      } catch (err) {
        // One subsystem failing (e.g. missing browser API, unexpected DOM
        // shape on a given page) should never take the others down with it.
        console.warn(`gsap-animations: ${fn.name} failed to initialize`, err);
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
