"use strict";

(() => {
  const form = document.getElementById("tile-form");
  const settingsField = document.getElementById("settings");
  const tileIdField = document.getElementById("tile-id");

  if (!form || !settingsField || !tileIdField) return;

  const label = document.createElement("label");
  label.className = "tile-title-mode-field";
  label.innerHTML = `
    Title display
    <select id="show-title">
      <option value="auto">Auto — hide on one-row tiles</option>
      <option value="show">Always show</option>
      <option value="hide">Always hide</option>
    </select>
    <small class="help">
      In Auto mode, titles are hidden only when the tile is one grid row tall.
      Hidden titles remain available as drag handles in Layout mode.
    </small>
  `;

  const titleSelector = label.querySelector("#show-title");
  const settingsLabel = settingsField.closest("label");

  if (settingsLabel) {
    settingsLabel.parentNode.insertBefore(label, settingsLabel);
  } else {
    form.append(label);
  }

  function parseSettings() {
    try {
      return settingsField.value.trim()
        ? JSON.parse(settingsField.value)
        : {};
    } catch {
      return null;
    }
  }

  function syncSelectorFromSettings() {
    const settings = parseSettings();
    if (!settings) return;

    titleSelector.value =
      settings.show_title === true
        ? "show"
        : settings.show_title === false
          ? "hide"
          : "auto";
  }

  function writeSelectorToSettings() {
    const settings = parseSettings();
    if (!settings) return;

    if (titleSelector.value === "show") {
      settings.show_title = true;
    } else if (titleSelector.value === "hide") {
      settings.show_title = false;
    } else {
      delete settings.show_title;
    }

    settingsField.value = JSON.stringify(settings, null, 2);
  }

  // Capture phase runs before the existing tileForm.onsubmit handler creates
  // its API payload.
  form.addEventListener(
    "submit",
    () => {
      writeSelectorToSettings();
    },
    true
  );

  titleSelector.addEventListener("change", writeSelectorToSettings);
  settingsField.addEventListener("input", syncSelectorFromSettings);
  settingsField.addEventListener("change", syncSelectorFromSettings);

  // Existing admin.js changes field values programmatically when Edit/Clear is
  // selected, which does not emit input events. Watch the values cheaply and
  // update only when they actually change.
  let previousTileId = tileIdField.value;
  let previousSettings = settingsField.value;

  setInterval(() => {
    if (
      tileIdField.value !== previousTileId ||
      settingsField.value !== previousSettings
    ) {
      previousTileId = tileIdField.value;
      previousSettings = settingsField.value;
      syncSelectorFromSettings();
    }
  }, 200);

  syncSelectorFromSettings();
})();
