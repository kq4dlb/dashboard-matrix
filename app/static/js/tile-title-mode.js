"use strict";

(() => {
  const grid = document.getElementById("dashboard-grid");
  if (!grid) return;

  let settingsById = new Map();
  let refreshPromise = null;

  async function loadTileSettings() {
    if (refreshPromise) return refreshPromise;

    refreshPromise = fetch("/api/tiles", { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((tiles) => {
        settingsById = new Map(
          tiles.map((tile) => [String(tile.id), tile.settings || {}])
        );
      })
      .catch((error) => {
        console.warn("Unable to load tile title settings:", error);
      })
      .finally(() => {
        refreshPromise = null;
      });

    return refreshPromise;
  }

  function applyTitleMode(tileElement) {
    const id = String(tileElement.dataset.tileId || "");
    const height = Number(tileElement.dataset.h || 1);
    const settings = settingsById.get(id) || {};
    const setting = settings.show_title;

    // Auto: hide only when the tile is one grid row tall.
    const hidden = setting === false || (setting !== true && height === 1);

    tileElement.classList.toggle("title-hidden", hidden);
    tileElement.dataset.titleMode =
      setting === true ? "show" : setting === false ? "hide" : "auto";
  }

  function applyAll() {
    grid.querySelectorAll(".tile").forEach(applyTitleMode);
  }

  async function refresh() {
    await loadTileSettings();
    applyAll();
  }

  const observer = new MutationObserver((mutations) => {
    let needsApply = false;

    for (const mutation of mutations) {
      if (mutation.type === "childList" && mutation.addedNodes.length) {
        needsApply = true;
        break;
      }

      if (
        mutation.type === "attributes" &&
        ["data-h", "data-tile-id"].includes(mutation.attributeName)
      ) {
        needsApply = true;
        break;
      }
    }

    if (needsApply) {
      queueMicrotask(applyAll);
    }
  });

  observer.observe(grid, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["data-h", "data-tile-id"],
  });

  // Configuration changes can arrive through Dashboard Matrix's WebSocket and rebuild
  // the grid. Periodically refresh the small tile settings map as a fallback.
  refresh();
  setInterval(refresh, 60_000);

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refresh();
  });
})();
