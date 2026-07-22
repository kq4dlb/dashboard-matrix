"use strict";

(() => {
  function initializeMapProfileAdmin() {
    if (document.getElementById("map-profile-form")) return;

    // Anchor to the Station Settings form itself. This is stable regardless
    // of how the Admin tabs or their wrapper attributes are structured.
    const stationForm = document.getElementById("station-form");
    if (!stationForm) {
      console.warn("Dashboard Matrix Map Profile: #station-form was not found.");
      return;
    }

    const stationSection =
      stationForm.closest("section") ||
      stationForm.closest(".admin-section") ||
      stationForm.parentElement;

    if (!stationSection || !stationSection.parentElement) {
      console.warn("Dashboard Matrix Map Profile: Station Settings container was not found.");
      return;
    }

    const section = document.createElement("section");
    section.className = "admin-section map-profile-section";
    section.innerHTML = `
      <h2>Map View Profile</h2>
      <p>
        Set a shared viewport for map-based tiles. Providers can use the global
        profile or override it per tile.
      </p>

      <form id="map-profile-form">
        <div class="form-grid">
          <label>
            View profile
            <select id="map-profile"></select>
          </label>

          <label>
            Default zoom
            <input id="map-zoom"
                   type="number"
                   min="1"
                   max="18"
                   step="0.1">
          </label>

          <label>
            Distance radius
            <select id="map-radius">
              <option value="25">25 miles</option>
              <option value="50">50 miles</option>
              <option value="100">100 miles</option>
              <option value="250">250 miles</option>
              <option value="500">500 miles</option>
              <option value="1000">1,000 miles</option>
              <option value="2000">2,000 miles</option>
            </select>
          </label>

          <label>
            Custom latitude
            <input id="map-custom-lat"
                   type="number"
                   min="-90"
                   max="90"
                   step="0.000001">
          </label>

          <label>
            Custom longitude
            <input id="map-custom-lon"
                   type="number"
                   min="-180"
                   max="180"
                   step="0.000001">
          </label>
        </div>

        <div class="button-row">
          <button type="submit">Save map profile</button>

          <button id="install-dx-map" type="button">
            Add adapted DX map to catalog
          </button>

          <a class="button secondary"
             href="/maps/dxcluster"
             target="_blank"
             rel="noopener">
            Preview DX map
          </a>
        </div>

        <p id="map-profile-status" class="form-message"></p>

        <p class="help">
          Local follows the station grid square. Custom uses the coordinates
          above. Regional profiles use fixed centers and bounds.
        </p>
      </form>
    `;

    stationSection.insertAdjacentElement("afterend", section);

    const form = section.querySelector("#map-profile-form");
    const profileField = section.querySelector("#map-profile");
    const zoomField = section.querySelector("#map-zoom");
    const radiusField = section.querySelector("#map-radius");
    const customLatField = section.querySelector("#map-custom-lat");
    const customLonField = section.querySelector("#map-custom-lon");
    const statusField = section.querySelector("#map-profile-status");
    const installButton = section.querySelector("#install-dx-map");

    function setStatus(message, isError = false) {
      statusField.textContent = message;
      statusField.classList.toggle("error", isError);
    }

    async function loadProfile() {
      const response = await fetch("/api/settings/map-profile", {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`Unable to load map profile: HTTP ${response.status}`);
      }

      const data = await response.json();

      profileField.replaceChildren(
        ...data.presets.map((preset) => {
          const option = document.createElement("option");
          option.value = preset.id;
          option.textContent = preset.name;
          return option;
        })
      );

      profileField.value = data.profile;
      zoomField.value = data.zoom;
      radiusField.value = String(data.radius_miles);
      customLatField.value = data.center_lat;
      customLonField.value = data.center_lon;

      setStatus(
        `Current center: ${data.center_lat}, ${data.center_lon} · ${data.name}`
      );
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      setStatus("Saving…");

      const response = await fetch("/api/settings/map-profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile: profileField.value,
          zoom: Number(zoomField.value),
          radius_miles: Number(radiusField.value),
          custom_latitude: Number(customLatField.value),
          custom_longitude: Number(customLonField.value),
        }),
      });

      if (!response.ok) {
        setStatus(`Save failed: ${await response.text()}`, true);
        return;
      }

      const data = await response.json();
      setStatus(
        `Saved: ${data.name} centered at ${data.center_lat}, ${data.center_lon}`
      );
    });

    installButton.addEventListener("click", async () => {
      installButton.disabled = true;
      setStatus("Adding catalog entry…");

      try {
        const response = await fetch(
          "/api/map-providers/dxcluster/install-catalog",
          { method: "POST" }
        );

        if (!response.ok) throw new Error(await response.text());

        setStatus(
          "DX Cluster Map — Dashboard Matrix View was added or updated in the catalog."
        );
      } catch (error) {
        setStatus(`Catalog update failed: ${error}`, true);
      } finally {
        installButton.disabled = false;
      }
    });

    loadProfile().catch((error) => {
      console.error("Dashboard Matrix Map Profile load failed:", error);
      setStatus(String(error), true);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeMapProfileAdmin, {
      once: true,
    });
  } else {
    initializeMapProfileAdmin();
  }
})();
