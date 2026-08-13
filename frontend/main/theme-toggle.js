/**
 * VeeraOps Store — Dark/Light theme toggle for the top menu bar, animated
 * with GSAP (circular "wipe" reveal + icon/thumb motion).
 *
 * Self-contained, same pattern as ai-chat-widget.js: one absolute-path
 * <script> include works on every page (main + all category pages) via
 * the existing ingress catch-all to main-service, so this file only needs
 * to live in frontend/main/ and gets reused everywhere.
 *
 * How it works:
 *  - Injects a small pill switch into the page's <header> (tries a few
 *    known "actions" containers first so it sits neatly next to
 *    Login/Orders/Cart on pages that have them; falls back to appending
 *    directly to the header, then to a fixed corner button as a last
 *    resort so it always renders somewhere sensible).
 *  - Persists the choice in localStorage and re-applies it on every page
 *    load (shared across pages since they're same-origin).
 *  - Adds a generic dark-mode override for the CSS custom property names
 *    this project's pages already share (--ink, --muted, --line,
 *    --surface, --bg, --soft, --ink2), so it works without editing every
 *    page's own stylesheet.
 *  - Loads GSAP from cdnjs on demand (no other page needs to add a script
 *    tag for it) and uses it for: the sliding thumb + icon flip, and a
 *    circular reveal animation that wipes from the toggle button across
 *    the viewport when switching themes.
 */
(function () {
  "use strict";

  const THEME_KEY = "googleStoreTheme"; // "light" | "dark"
  const GSAP_SRC = "https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js";

  const DARK_VARS = {
    "--ink": "#e5e7eb",
    "--ink2": "#cbd5e1",
    "--muted": "#94a3b8",
    "--line": "#2a3342",
    "--surface": "#161b26",
    "--bg": "#0d1117",
    "--soft": "#1c2330",
    "--shadow": "0 2px 20px rgba(0,0,0,0.55)",
  };

  function injectDarkModeStyles() {
    const rules = Object.entries(DARK_VARS)
      .map(([k, v]) => `${k}: ${v};`)
      .join(" ");
    const style = document.createElement("style");
    style.id = "veeraops-theme-vars";
    style.textContent = `
      html[data-theme="dark"] { ${rules} color-scheme: dark; }
      html[data-theme="dark"] body { background: var(--bg); color: var(--ink); }
      html { transition: color-scheme .2s; }
      html[data-theme="dark"] img { filter: brightness(.92) contrast(1.03); }
      .theme-toggle-switch {
        position: relative; width: 50px; height: 27px; border-radius: 999px;
        border: none; cursor: pointer; padding: 0; flex-shrink: 0;
        background: linear-gradient(90deg, #495066, #2b3245);
        display: inline-flex; align-items: center; margin: 0 2px;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08);
      }
      html[data-theme="dark"] .theme-toggle-switch {
        background: linear-gradient(90deg, #1e293b, #0f172a);
      }
      .theme-toggle-thumb {
        position: absolute; top: 3px; left: 3px; width: 21px; height: 21px;
        border-radius: 50%; background: #fff; display: flex; align-items: center;
        justify-content: center; font-size: 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.35);
        will-change: transform;
      }
      .theme-toggle-fixed {
        position: fixed; left: 18px; bottom: 18px; z-index: 9998;
      }
      .veeraops-theme-reveal {
        position: fixed; inset: 0; z-index: 99999; pointer-events: none;
        clip-path: circle(0px at 0px 0px);
      }
    `;
    document.head.appendChild(style);
  }

  function getStoredTheme() {
    try {
      return localStorage.getItem(THEME_KEY);
    } catch {
      return null;
    }
  }

  function setStoredTheme(theme) {
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* ignore */
    }
  }

  function prefersDark() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function applyThemeAttribute(theme) {
    document.documentElement.setAttribute("data-theme", theme);
  }

  function loadGsap() {
    return new Promise((resolve) => {
      if (window.gsap) return resolve(window.gsap);
      const existing = document.querySelector(`script[src="${GSAP_SRC}"]`);
      if (existing) {
        existing.addEventListener("load", () => resolve(window.gsap));
        return;
      }
      const script = document.createElement("script");
      script.src = GSAP_SRC;
      script.onload = () => resolve(window.gsap);
      script.onerror = () => resolve(null); // degrade gracefully, no GSAP
      document.head.appendChild(script);
    });
  }

  function findMountPoint() {
    const candidateSelectors = [
      ".topbar-actions",
      ".header-actions",
      ".nav-actions",
      ".site-header-actions",
    ];
    for (const sel of candidateSelectors) {
      const node = document.querySelector(sel);
      if (node) return { node, mode: "prepend" };
    }
    const header = document.querySelector("header");
    if (header) return { node: header, mode: "append" };
    return null;
  }

  function buildToggle() {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "theme-toggle-switch";
    btn.setAttribute("aria-label", "Toggle dark mode");
    btn.setAttribute("role", "switch");

    const thumb = document.createElement("span");
    thumb.className = "theme-toggle-thumb";
    thumb.textContent = "☀️";
    btn.appendChild(thumb);

    return { btn, thumb };
  }

  function positionThumb(gsap, thumb, theme, animate) {
    const x = theme === "dark" ? 23 : 0;
    const label = theme === "dark" ? "🌙" : "☀️";
    if (gsap && animate) {
      gsap.to(thumb, {
        x,
        rotation: theme === "dark" ? 180 : 0,
        duration: 0.35,
        ease: "back.out(2)",
        onStart: () => {
          gsap.to(thumb, { scale: 0, duration: 0.12, onComplete: () => (thumb.textContent = label) });
        },
        onComplete: () => gsap.to(thumb, { scale: 1, duration: 0.18 }),
      });
    } else {
      thumb.style.transform = `translateX(${x}px)`;
      thumb.textContent = label;
    }
  }

  function runRevealAnimation(gsap, originEl, prevBg, nextTheme) {
    // The theme switch itself has already happened by the time this runs
    // (see the click handler) -- this is purely the visual flourish: wipe
    // an overlay showing the *previous* theme's background away from the
    // button's position, revealing the new theme underneath. A cheap,
    // reliable way to animate a full page recolor without tweening dozens
    // of individual elements.
    if (!gsap || !originEl) return;

    const rect = originEl.getBoundingClientRect();
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    const maxRadius = Math.hypot(
      Math.max(x, window.innerWidth - x),
      Math.max(y, window.innerHeight - y)
    );

    const overlay = document.createElement("div");
    overlay.className = "veeraops-theme-reveal";
    overlay.style.background = prevBg || (nextTheme === "dark" ? "#f0f4fb" : "#0d1117");
    document.body.appendChild(overlay);

    const state = { r: maxRadius };
    gsap.to(state, {
      r: 0,
      duration: 0.65,
      ease: "power2.inOut",
      onUpdate: () => {
        overlay.style.clipPath = `circle(${state.r}px at ${x}px ${y}px)`;
      },
      onComplete: () => overlay.remove(),
    });
  }

  async function init() {
    injectDarkModeStyles();

    const initialTheme = getStoredTheme() || (prefersDark() ? "dark" : "light");
    applyThemeAttribute(initialTheme);

    const mount = findMountPoint();
    const { btn, thumb } = buildToggle();
    if (mount) {
      if (mount.mode === "prepend") mount.node.insertBefore(btn, mount.node.firstChild);
      else mount.node.appendChild(btn);
    } else {
      btn.classList.add("theme-toggle-fixed");
      document.body.appendChild(btn);
    }

    positionThumb(null, thumb, initialTheme, false);

    // GSAP loads in the background. The toggle is fully functional the
    // instant it's mounted, whether or not GSAP has finished loading yet
    // -- GSAP only ever adds a visual flourish on top of an already-correct
    // theme switch, never gates it.
    let gsapReady = null;
    loadGsap().then((g) => {
      gsapReady = g;
      positionThumb(gsapReady, thumb, currentTheme(), false);
    });

    btn.addEventListener("click", () => {
      const next = currentTheme() === "dark" ? "light" : "dark";
      const prevBg =
        getComputedStyle(document.documentElement).getPropertyValue("--bg").trim() ||
        getComputedStyle(document.body).backgroundColor;

      setStoredTheme(next);
      applyThemeAttribute(next);
      positionThumb(gsapReady, thumb, next, true);
      runRevealAnimation(gsapReady, btn, prevBg, next);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
