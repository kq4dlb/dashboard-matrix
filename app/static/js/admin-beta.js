"use strict";

(() => {
  const el = (id) => document.getElementById(id);
  let importDocument = null;
  let screenshotDataUrl = null;

  async function responseJson(response) {
    const text = await response.text();
    if (!response.ok) {
      try {
        const parsed = JSON.parse(text);
        throw new Error(parsed.detail || text || `HTTP ${response.status}`);
      } catch (error) {
        if (error instanceof SyntaxError) throw new Error(text || `HTTP ${response.status}`);
        throw error;
      }
    }
    return text ? JSON.parse(text) : {};
  }

  function pretty(value) {
    return JSON.stringify(value, null, 2);
  }

  function dashboardOptionsForScreenshot() {
    const select = el("layout-screenshot-dashboard");
    if (!select || typeof dashboards === "undefined") return;
    const current = select.value;
    select.replaceChildren();
    for (const dashboard of dashboards) {
      const option = new Option(dashboard.name, dashboard.slug);
      select.add(option);
    }
    if ([...select.options].some((option) => option.value === current)) {
      select.value = current;
    }
  }

  const originalRenderDashboards = typeof renderDashboards === "function" ? renderDashboards : null;
  if (originalRenderDashboards) {
    renderDashboards = function renderDashboardsWithBetaControls() {
      originalRenderDashboards();
      dashboardOptionsForScreenshot();
    };
  }

  async function readImportFile() {
    const file = el("layout-import-file")?.files?.[0];
    if (!file) throw new Error("Choose a Dashboard Matrix layout JSON file first.");
    let document;
    try {
      document = JSON.parse(await file.text());
    } catch {
      throw new Error("The selected file does not contain valid JSON.");
    }
    importDocument = document;
    return { file, document };
  }

  el("layout-analyze")?.addEventListener("click", async () => {
    const output = el("layout-analysis");
    const button = el("layout-import");
    output.textContent = "Analyzing…";
    button.disabled = true;
    try {
      const { document } = await readImportFile();
      const result = await responseJson(await fetch("/api/layout-imports/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document }),
      }));
      output.textContent = pretty(result);
      button.disabled = false;
    } catch (error) {
      output.textContent = `Analysis failed: ${error.message}`;
    }
  });

  el("layout-import")?.addEventListener("click", async () => {
    const output = el("layout-analysis");
    try {
      const { file, document } = importDocument
        ? { file: el("layout-import-file").files[0], document: importDocument }
        : await readImportFile();
      output.textContent = "Importing…";
      const result = await responseJson(await fetch("/api/layout-imports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document,
          conflict_strategy: el("layout-conflict-strategy").value,
          include_station: el("layout-import-station").checked,
          source_name: file?.name || "uploaded-layout.json",
        }),
      }));
      output.textContent = pretty(result);
      await loadDashboards();
    } catch (error) {
      output.textContent = `Import failed: ${error.message}`;
    }
  });

  el("layout-import-file")?.addEventListener("change", () => {
    importDocument = null;
    el("layout-import").disabled = true;
    el("layout-analysis").textContent = "Select Analyze before importing.";
  });

  function exportMetadata() {
    return {
      title: el("layout-export-title").value.trim(),
      description: el("layout-export-description").value.trim(),
      tags: el("layout-export-tags").value
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean)
        .slice(0, 20),
    };
  }

  async function buildExportDocument() {
    const includeStation = el("layout-export-station").checked;
    const document = await responseJson(await fetch(
      `/api/layout-exports/current?include_station=${includeStation ? "true" : "false"}`,
      { cache: "no-store" },
    ));
    document.metadata = exportMetadata();
    return document;
  }

  function exportFilename(document) {
    const raw = document.metadata?.title || "dashboard-matrix-layout";
    const slug = raw.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "dashboard-matrix-layout";
    const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
    return `${stamp}-${slug}.json`;
  }

  function downloadExportDocument(document) {
    const blob = new Blob([pretty(document)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = documentCreate("a");
    anchor.href = url;
    anchor.download = exportFilename(document);
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function downloadExport() {
    const document = await buildExportDocument();
    downloadExportDocument(document);
    return document;
  }

  function documentCreate(tag) {
    return window.document.createElement(tag);
  }

  el("layout-download")?.addEventListener("click", async () => {
    const message = el("layout-publish-message");
    try {
      await downloadExport();
      message.textContent = "Layout JSON downloaded.";
    } catch (error) {
      message.textContent = `Export failed: ${error.message}`;
    }
  });

  function blobToDataUrl(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error || new Error("Unable to read screenshot"));
      reader.readAsDataURL(blob);
    });
  }

  el("layout-preview")?.addEventListener("click", async () => {
    const message = el("layout-screenshot-message");
    const preview = el("layout-screenshot-preview");
    const slug = el("layout-screenshot-dashboard").value;
    if (!slug) {
      message.textContent = "Choose a dashboard first.";
      return;
    }
    message.textContent = "Capturing screenshot…";
    preview.hidden = true;
    try {
      const response = await fetch(`/api/screenshots/${encodeURIComponent(slug)}.png`, { cache: "no-store" });
      if (!response.ok) throw new Error((await response.text()) || `HTTP ${response.status}`);
      const blob = await response.blob();
      screenshotDataUrl = await blobToDataUrl(blob);
      preview.src = screenshotDataUrl;
      preview.hidden = false;
      message.textContent = `Screenshot ready (${Math.round(blob.size / 1024)} KB).`;
    } catch (error) {
      screenshotDataUrl = null;
      message.textContent = `Screenshot failed: ${error.message}`;
    }
  });

  async function loadPublishSettings() {
    try {
      const settings = await responseJson(await fetch("/api/layout-exports/publish-settings", { cache: "no-store" }));
      el("layout-publish-repository").value = settings.repository;
      el("layout-publish-branch").value = settings.branch;
      el("layout-publish-folder").value = settings.folder;
      el("layout-auto-publish").checked = Boolean(settings.auto_publish);
    } catch (error) {
      el("layout-publish-message").textContent = `Unable to load publishing settings: ${error.message}`;
    }
  }

  function publishDestination() {
    return {
      repository: el("layout-publish-repository").value.trim(),
      branch: el("layout-publish-branch").value.trim() || "main",
      folder: el("layout-publish-folder").value.trim() || "layouts",
      auto_publish: el("layout-auto-publish").checked,
    };
  }

  el("layout-save-publish")?.addEventListener("click", async () => {
    const message = el("layout-publish-message");
    try {
      await responseJson(await fetch("/api/layout-exports/publish-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(publishDestination()),
      }));
      message.textContent = "Exchange destination saved. GitHub token was not stored.";
    } catch (error) {
      message.textContent = `Save failed: ${error.message}`;
    }
  });

  async function publishExport(document = null) {
    const message = el("layout-publish-message");
    message.textContent = "Publishing to GitHub Exchange…";
    const payload = {
      ...publishDestination(),
      token: el("layout-publish-token").value || null,
      include_station: el("layout-export-station").checked,
      metadata: exportMetadata(),
      screenshot_data_url: screenshotDataUrl,
      document,
    };
    const result = await responseJson(await fetch("/api/layout-exports/publish", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }));
    el("layout-publish-token").value = "";
    const links = [result.json_url, result.screenshot_url].filter(Boolean);
    message.textContent = `Published ${result.json_path}${result.screenshot_path ? ` and ${result.screenshot_path}` : ""}.`;
    if (links.length) {
      message.append(" ");
      links.forEach((href, index) => {
        const anchor = documentCreate("a");
        anchor.href = href;
        anchor.target = "_blank";
        anchor.rel = "noopener";
        anchor.textContent = index === 0 ? "Open layout" : "Open screenshot";
        if (index) message.append(" · ");
        message.append(anchor);
      });
    }
    return result;
  }

  el("layout-export-action")?.addEventListener("click", async () => {
    const message = el("layout-publish-message");
    try {
      const document = await buildExportDocument();
      downloadExportDocument(document);
      if (el("layout-auto-publish").checked) {
        await publishExport(document);
      } else {
        message.textContent = "Layout downloaded. Enable automatic publishing to push the same export to GitHub.";
      }
    } catch (error) {
      message.textContent = `Export failed: ${error.message}`;
    }
  });

  async function loadUpdateSettings() {
    const output = el("update-result");
    try {
      const settings = await responseJson(await fetch("/api/updates/settings", { cache: "no-store" }));
      el("update-repository").value = settings.repository;
      el("update-channel").value = settings.channel;
      el("update-automatic").checked = settings.automatic_checks;
      output.textContent = settings.last_check ? pretty(settings.last_check) : "No update check has been run.";
    } catch (error) {
      output.textContent = `Unable to load update settings: ${error.message}`;
    }
  }

  el("update-save")?.addEventListener("click", async () => {
    const output = el("update-result");
    try {
      const result = await responseJson(await fetch("/api/updates/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repository: el("update-repository").value.trim(),
          channel: el("update-channel").value,
          automatic_checks: el("update-automatic").checked,
        }),
      }));
      output.textContent = `Saved update settings.\n${pretty(result)}`;
    } catch (error) {
      output.textContent = `Save failed: ${error.message}`;
    }
  });

  el("update-check")?.addEventListener("click", async () => {
    const output = el("update-result");
    output.textContent = "Checking GitHub…";
    try {
      output.textContent = pretty(await responseJson(await fetch("/api/updates/check", { method: "POST" })));
    } catch (error) {
      output.textContent = `Update check failed: ${error.message}`;
    }
  });

  async function loadThemes() {
    const list = el("theme-package-list");
    try {
      const themes = await responseJson(await fetch("/api/themes", { cache: "no-store" }));
      list.replaceChildren();
      for (const theme of themes) {
        const card = documentCreate("article");
        card.className = "catalog-card";
        card.innerHTML = `<div><span class="catalog-category">${escHtml(theme.color_scheme || "theme")}</span><h3>${escHtml(theme.name)}</h3><p>${escHtml(theme.description || "")}</p><small>${escHtml(theme.author || "Unknown")} · ${escHtml(theme.version || "0.0.0")}</small></div>`;
        const actions = documentCreate("div");
        actions.className = "catalog-card-actions";
        const preview = documentCreate("button");
        preview.type = "button";
        preview.textContent = "Preview";
        preview.onclick = () => {
          el("theme-package").href = theme.stylesheet_url;
          localStorage.setItem("dashboardMatrix.themePreview", theme.id);
        };
        actions.append(preview);
        card.append(actions);
        list.append(card);
      }
    } catch (error) {
      list.textContent = `Unable to load themes: ${error.message}`;
    }
  }

  async function testProxy(sourceId) {
    const output = el("proxy-diagnostic-result");
    output.textContent = `Testing ${sourceId}…`;
    try {
      output.textContent = pretty(await responseJson(await fetch(
        `/api/proxy-sources/${encodeURIComponent(sourceId)}/test`,
        { method: "POST" },
      )));
    } catch (error) {
      output.textContent = `Proxy test failed: ${error.message}`;
    }
  }

  const originalRenderProxySources = typeof renderProxySources === "function" ? renderProxySources : null;
  if (originalRenderProxySources) {
    renderProxySources = function renderProxySourcesWithDiagnostics() {
      originalRenderProxySources();
      const items = [...el("proxy-list").querySelectorAll(".tile-list-item")];
      items.forEach((item, index) => {
        const source = proxySources[index];
        const actions = item.querySelector(".tile-list-actions");
        if (!source || !actions) return;
        const button = documentCreate("button");
        button.type = "button";
        button.textContent = "Test";
        button.onclick = () => testProxy(source.source_id);
        actions.prepend(button);
      });
    };
  }

  function permissionLabel(permission) {
    return {
      network: "Public network access",
      "local-network": "Local network access",
      filesystem: "Filesystem access",
      device: "Serial or hardware-device access",
      subprocess: "Start subprocesses",
      secrets: "Use mapped secrets",
    }[permission] || permission;
  }

  renderPlugins = function renderPluginsWithPermissions() {
    const list = el("plugin-list");
    if (!list) return;
    list.replaceChildren();
    for (const plugin of installedPlugins) {
      const card = documentCreate("article");
      card.className = `catalog-card${plugin.enabled ? "" : " disabled-card"}`;
      const body = documentCreate("div");
      const required = plugin.permissions || [];
      const secrets = plugin.secrets || [];
      body.innerHTML = `
        <span class="catalog-category">Plugin ${escHtml(plugin.version)}</span>
        <h3>${escHtml(plugin.name)}</h3>
        <p>${escHtml(plugin.description || "")}</p>
        <small>${escHtml(plugin.author || "Unknown")} · ${plugin.widgets.length} widget(s)</small>
        <label class="inline"><input class="plugin-enabled" type="checkbox" ${plugin.enabled ? "checked" : ""}> Enabled</label>
        <label>Shared settings JSON<textarea class="plugin-settings" rows="3">${escHtml(JSON.stringify(plugin.settings || {}, null, 2))}</textarea></label>
        <fieldset class="plugin-permissions"><legend>Declared permissions</legend>
          ${required.length ? required.map((permission) => `<label class="inline"><input class="plugin-permission" data-permission="${escHtml(permission)}" type="checkbox" ${(plugin.approvals || []).includes(permission) ? "checked" : ""}> ${escHtml(permissionLabel(permission))}</label>`).join("") : '<p class="help">This plugin declares no elevated permissions.</p>'}
        </fieldset>
        <fieldset class="plugin-secrets"><legend>Secret mappings</legend>
          ${secrets.length ? secrets.map((secret) => `<label>${escHtml(secret.name)}${secret.required ? " (required)" : ""}<input class="plugin-secret-ref" data-secret="${escHtml(secret.name)}" value="${escHtml((plugin.secret_refs || {})[secret.name] || "")}" placeholder="Environment variable name"><small>${escHtml(secret.description || "")}${plugin.secret_status?.[secret.name] ? " · configured" : " · not available"}</small></label>`).join("") : '<p class="help">This plugin declares no secrets.</p>'}
        </fieldset>
        <p class="help">${plugin.runtime_ready ? "Permissions and required secrets are ready." : "Approve every declared permission and configure required secret environment variables before the plugin can run."}</p>
      `;
      const actions = documentCreate("div");
      actions.className = "catalog-card-actions";
      const save = documentCreate("button");
      save.textContent = "Save plugin";
      save.onclick = () => savePlugin(plugin.id, card);
      actions.append(save);
      for (const widget of plugin.widgets) {
        const button = documentCreate("button");
        button.textContent = `Add ${widget.name}`;
        button.disabled = !plugin.enabled || !plugin.runtime_ready;
        button.onclick = () => addPluginWidget(plugin.id, widget.id, button);
        actions.append(button);
      }
      card.append(body, actions);
      list.append(card);
    }
  };

  savePlugin = async function savePluginWithPermissions(id, card) {
    const message = el("plugin-message");
    let settings = {};
    try {
      settings = JSON.parse(card.querySelector(".plugin-settings").value || "{}");
    } catch {
      message.textContent = "Invalid plugin settings JSON.";
      return;
    }
    const approvals = [...card.querySelectorAll(".plugin-permission:checked")]
      .map((input) => input.dataset.permission);
    const secretRefs = {};
    for (const input of card.querySelectorAll(".plugin-secret-ref")) {
      const value = input.value.trim();
      if (value) secretRefs[input.dataset.secret] = value;
    }
    const response = await fetch(`/api/plugins/${encodeURIComponent(id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        enabled: card.querySelector(".plugin-enabled").checked,
        settings,
        approvals,
        secret_refs: secretRefs,
      }),
    });
    message.textContent = response.ok ? "Plugin saved." : `Save failed: ${await response.text()}`;
    if (response.ok) await loadPlugins();
  };

  window.addEventListener("DOMContentLoaded", () => {
    dashboardOptionsForScreenshot();
    loadPublishSettings();
    loadUpdateSettings();
    loadThemes();
    const previewTheme = localStorage.getItem("dashboardMatrix.themePreview");
    if (previewTheme) el("theme-package").href = `/themes/${encodeURIComponent(previewTheme)}.css`;
    if (typeof loadProxySources === "function") loadProxySources();
    if (typeof loadPlugins === "function") loadPlugins();
  });
})();
