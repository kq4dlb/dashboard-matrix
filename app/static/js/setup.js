"use strict";

const $ = (id) => document.getElementById(id);
let selectedTemplate = "blank";

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

async function loadTemplates() {
  const response = await fetch("/api/setup/status", { cache: "no-store" });
  const data = await response.json();
  const container = $("setup-templates");
  container.replaceChildren();
  for (const template of data.templates) {
    const label = document.createElement("label");
    label.className = "template-choice";
    label.innerHTML = `
      <input type="radio" name="starter-template" value="${escapeHtml(template.id)}" ${template.id === selectedTemplate ? "checked" : ""}>
      <strong>${escapeHtml(template.name)}</strong>
      <span>${escapeHtml(template.description)}</span>
    `;
    label.querySelector("input").addEventListener("change", () => {
      selectedTemplate = template.id;
    });
    container.append(label);
  }
}

$("setup-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = $("setup-message");
  const password = $("setup-password").value;
  if (password !== $("setup-password-confirm").value) {
    message.textContent = "The passwords do not match.";
    return;
  }
  message.textContent = "Creating dashboards…";
  const response = await fetch("/api/setup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      display_name: $("setup-display-name").value.trim(),
      callsign: $("setup-callsign").value.trim(),
      grid_square: $("setup-grid").value.trim(),
      template: selectedTemplate,
      password,
      theme: $("setup-theme").value,
      release_channel: $("setup-channel").value,
    }),
  });
  if (!response.ok) {
    message.textContent = `Setup failed: ${await response.text()}`;
    return;
  }
  const result = await response.json();
  location.href = result.redirect || "/admin";
});

loadTemplates().catch((error) => {
  $("setup-message").textContent = error.message;
});
