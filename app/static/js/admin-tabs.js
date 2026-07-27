"use strict";

(() => {
  const tabs = Array.from(document.querySelectorAll("[data-admin-tab]"));
  const panels = Array.from(document.querySelectorAll("[data-admin-panel]"));
  if (!tabs.length || !panels.length) return;

  const storageKey = "dashboard-matrix.admin.active-tab";
  const validTabs = new Set(tabs.map((tab) => tab.dataset.adminTab));

  function storedTab() {
    try {
      return window.localStorage.getItem(storageKey) || "";
    } catch (_error) {
      return "";
    }
  }

  function rememberTab(name) {
    try {
      window.localStorage.setItem(storageKey, name);
    } catch (_error) {
      // The Admin UI still works when browser storage is disabled.
    }
  }

  function hashTab() {
    const match = window.location.hash.match(/^#admin-([a-z-]+)$/);
    return match && validTabs.has(match[1]) ? match[1] : "";
  }

  function activate(name, options = {}) {
    const { focus = false, updateHash = true } = options;
    if (!validTabs.has(name)) name = tabs[0].dataset.adminTab;

    tabs.forEach((tab) => {
      const active = tab.dataset.adminTab === name;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active && focus) tab.focus();
    });

    panels.forEach((panel) => {
      const active = panel.dataset.adminPanel === name;
      panel.hidden = !active;
      panel.classList.toggle("is-active", active);
    });

    rememberTab(name);
    if (updateHash) {
      const nextHash = `#admin-${name}`;
      if (window.location.hash !== nextHash) {
        window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${nextHash}`);
      }
    }
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activate(tab.dataset.adminTab));
    tab.addEventListener("keydown", (event) => {
      let nextIndex = index;
      if (event.key === "ArrowRight" || event.key === "ArrowDown") nextIndex = (index + 1) % tabs.length;
      else if (event.key === "ArrowLeft" || event.key === "ArrowUp") nextIndex = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === "Home") nextIndex = 0;
      else if (event.key === "End") nextIndex = tabs.length - 1;
      else return;

      event.preventDefault();
      activate(tabs[nextIndex].dataset.adminTab, { focus: true });
    });
  });

  window.addEventListener("hashchange", () => {
    const name = hashTab();
    if (name) activate(name, { updateHash: false });
  });

  document.body.classList.add("admin-tabs-ready");
  activate(hashTab() || storedTab() || tabs[0].dataset.adminTab, { updateHash: true });

  window.dashboardMatrixAdminTabs = Object.freeze({ activate });
})();
