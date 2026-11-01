"use strict";

(() => {
  const storageKey = "starlight-theme";
  const parse = (value) => value === "light" || value === "dark" ? value : "auto";
  const system = window.matchMedia("(prefers-color-scheme: dark)");
  let preference = "auto";
  try {
    preference = parse(localStorage.getItem(storageKey));
  } catch {
    // Theme selection still works when storage is unavailable.
  }

  function apply(value, persist = false) {
    preference = parse(value);
    const resolved = preference === "auto" ? (system.matches ? "dark" : "light") : preference;
    document.documentElement.dataset.theme = resolved;
    document.querySelector("meta[name=\"theme-color\"]").content = resolved === "dark" ? "#1b211d" : "#faf9f6";
    const picker = document.getElementById("theme");
    if (picker) picker.value = preference;
    if (persist) {
      try {
        localStorage.setItem(storageKey, preference === "auto" ? "" : preference);
      } catch {}
    }
  }

  apply(preference);
  system.addEventListener("change", () => apply(preference));
  window.addEventListener("storage", (event) => {
    if (event.key === storageKey || event.key === null) apply(event.newValue);
  });
  document.addEventListener("DOMContentLoaded", () => {
    const picker = document.getElementById("theme");
    picker.value = preference;
    picker.addEventListener("change", () => apply(picker.value, true));
    picker.disabled = false;
  });
})();
