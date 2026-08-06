class HvacSetpointCurveCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) {
      throw new Error("entity is required");
    }
    this.config = config;
    this.mode = null;
    this.points = [];
    this.dirty = false;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() {
    return 5;
  }

  render() {
    if (!this.shadowRoot || !this._hass) return;
    const state = this._hass.states[this.config.entity];
    if (!state) {
      this.shadowRoot.innerHTML = `<ha-card><div class="wrap">Entity not found: ${this.escapeHtml(this.config.entity)}</div></ha-card>`;
      return;
    }

    const attrs = state.attributes || {};
    const entryId = attrs.config_entry_id;
    const isDutch = String(this._hass.language || "").toLowerCase().startsWith("nl");
    const ui = isDutch
      ? {
          heating: "Verwarmen",
          cooling: "Koelen",
          outdoorCurve: "Eén gebouwprofiel voor verwarmen, neutraal en koelen",
          customPreset: "Aangepaste comfortband",
          help: "Kies minimaal 3 buitentemperaturen. Verwarmen blijft altijd onder koelen.",
          graphTitle: "Visuele stook-/koellijn",
          graphHelp: "Pas de eenvoudige waarden onder de grafiek aan; de lijnen veranderen direct mee.",
          heatingTarget: "Verwarmen tot",
          coolingTarget: "Koelen vanaf",
          neutralZone: "Daartussen blijft het systeem neutraal.",
          outdoor: "Buiten °C",
          setpoint: "Doel °C",
          remove: "Verwijder",
          add: "Punt toevoegen",
          saveCurve: "Gebouwprofiel opslaan",
          saving: "Opslaan…",
          saved: "Curve opgeslagen",
          saveError: "Opslaan mislukt. Controleer de Home Assistant-logboeken.",
          unsaved: "Niet-opgeslagen wijzigingen",
          discard: "Niet-opgeslagen wijzigingen verwerpen?",
          outdoorNow: "Buiten nu",
          outdoorAverage: "Buiten gemiddeld",
          coolingIndoor: "Binnen koelen",
          heatingIndoor: "Binnen verwarmen",
          targetNow: "Doel nu",
          coolingStabilizing: "Koeling stabiliseert — modus blijft beschikbaar voor restwarmte",
          heatingStabilizing: "Verwarming stabiliseert — modus blijft beschikbaar voor restkou",
          demandHelp: "Buiten gemiddeld bepaalt of een curvesessie mag starten. De eigen thermostaat bewaakt daarna het doel; deze integratie schakelt de klimaatmodus nooit uit.",
        }
      : {
          heating: "Heating",
          cooling: "Cooling",
          outdoorCurve: "One building profile for heating, neutral and cooling",
          customPreset: "Custom comfort band",
          help: "Choose at least 3 outdoor temperatures. Heating must always remain below cooling.",
          graphTitle: "Visual heating/cooling curve",
          graphHelp: "Edit the simple values below; both lines update immediately.",
          heatingTarget: "Heat up to",
          coolingTarget: "Cool from",
          neutralZone: "Between these limits the system remains neutral.",
          outdoor: "Outdoor °C",
          setpoint: "Target °C",
          remove: "Remove",
          add: "Add point",
          saveCurve: "Save building profile",
          saving: "Saving…",
          saved: "Curve saved",
          saveError: "Save failed. Check the Home Assistant logs.",
          unsaved: "Unsaved changes",
          discard: "Discard unsaved changes?",
          outdoorNow: "Outdoor now",
          outdoorAverage: "Outdoor average",
          coolingIndoor: "Cooling indoor",
          heatingIndoor: "Heating indoor",
          targetNow: "Target now",
          coolingStabilizing: "Cooling is stabilizing — mode remains available for residual heat",
          heatingStabilizing: "Heating is stabilizing — mode remains available for residual cold",
          demandHelp: "The outdoor average permits a curve session to start. The device thermostat then maintains the target; this integration never switches the climate mode off.",
        };
    this.ui = ui;

    const formatTemperature = (value) => {
      const number = Number(value);
      return Number.isFinite(number) ? `${number.toFixed(1)} °C` : null;
    };
    const statusItems = [
      [ui.outdoorNow, attrs.outdoor_temperature_used],
      [ui.outdoorAverage, attrs.outdoor_temperature_average],
      [ui.coolingIndoor, attrs.cooling_indoor_temperature_used],
      [ui.heatingIndoor, attrs.heating_indoor_temperature_used],
      [ui.targetNow, state.state],
    ].filter(([, value]) => formatTemperature(value));
    const stabilizationMessages = [
      attrs.cooling_stabilizing ? ui.coolingStabilizing : null,
      attrs.heating_stabilizing ? ui.heatingStabilizing : null,
    ].filter(Boolean);

    if (!this.dirty) {
      const heating = attrs.heating_curve_points || [];
      const cooling = attrs.cooling_curve_points || [];
      const count = Math.min(heating.length, cooling.length);
      this.points = Array.from({ length: count }, (_, index) => ({
        outdoor_temp: Number(heating[index].outdoor_temp),
        heating_setpoint: Number(heating[index].setpoint),
        cooling_setpoint: Number(cooling[index].setpoint),
      }));
    }

    this.shadowRoot.innerHTML = `
      <style>
        ha-card { overflow: hidden; }
        .wrap { padding: 16px; }
        .top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 12px;
        }
        h2 {
          margin: 0;
          font-size: 18px;
          font-weight: 600;
        }
        .tabs {
          display: flex;
          gap: 6px;
        }
        button {
          border: 1px solid var(--divider-color, #d8d8d8);
          border-radius: 6px;
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color, #111);
          min-height: 34px;
          padding: 7px 10px;
          cursor: pointer;
          font: inherit;
        }
        button.active {
          border-color: var(--primary-color, #03a9f4);
          background: var(--primary-color, #03a9f4);
          color: var(--text-primary-color, #fff);
        }
        button.save {
          background: var(--accent-color, #ff9800);
          border-color: var(--accent-color, #ff9800);
          color: var(--text-primary-color, #fff);
        }
        canvas {
          width: 100%;
          aspect-ratio: 16 / 8;
          min-height: 240px;
          max-height: 440px;
          border: 1px solid var(--divider-color, #d8d8d8);
          border-radius: 6px;
          background: var(--card-background-color, #fff);
          touch-action: none;
        }
        .editor {
          display: grid;
          grid-template-columns: minmax(0, 1fr);
          gap: 10px;
        }
        .editor-side {
          min-width: 0;
        }
        .editor-title {
          margin: 0 0 4px;
          font-size: 15px;
          font-weight: 600;
        }
        .graph-heading {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 4px 12px;
        }
        .rows {
          display: grid;
          gap: 8px;
          margin-top: 10px;
        }
        .row {
          display: grid;
          grid-template-columns: 1fr 1fr 1fr auto;
          gap: 8px;
          align-items: end;
        }
        label {
          display: grid;
          gap: 4px;
          color: var(--secondary-text-color, #666);
          font-size: 12px;
        }
        input {
          width: 100%;
          box-sizing: border-box;
          border: 1px solid var(--divider-color, #d8d8d8);
          border-radius: 6px;
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color, #111);
          min-height: 34px;
          padding: 6px 8px;
          font: inherit;
        }
        .actions {
          display: flex;
          justify-content: space-between;
          gap: 8px;
          margin-top: 12px;
        }
        .muted {
          color: var(--secondary-text-color, #666);
          font-size: 12px;
        }
        .status {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
          gap: 8px;
          margin: 0 0 8px;
        }
        .metric {
          padding: 8px 10px;
          border: 1px solid var(--divider-color, #d8d8d8);
          border-radius: 6px;
        }
        .metric span, .metric strong { display: block; }
        .metric span { color: var(--secondary-text-color, #666); font-size: 11px; }
        .metric strong { margin-top: 2px; font-size: 14px; }
        .demand-help { margin: 0 0 14px; }
        .stabilizing {
          margin: 0 0 10px;
          padding: 8px 10px;
          border-radius: 6px;
          background: color-mix(in srgb, var(--primary-color, #03a9f4) 12%, transparent);
          color: var(--primary-text-color, #111);
          font-size: 12px;
        }
        @media (max-width: 520px) {
          canvas { min-height: 200px; }
          .row { grid-template-columns: 1fr 1fr; }
          .row button { grid-column: 1 / -1; }
        }
      </style>
      <ha-card>
        <div class="wrap">
          <div class="top">
            <div>
              <h2>${this.escapeHtml(this.config.title || "HVAC Setpoint Curve")}</h2>
              <div class="muted">${ui.outdoorCurve}</div>
            </div>
          </div>
          <div class="status">
            ${statusItems
              .map(
                ([label, value]) => `
              <div class="metric">
                <span>${label}</span>
                <strong>${formatTemperature(value)}</strong>
              </div>`
              )
              .join("")}
          </div>
          ${stabilizationMessages.map((message) => `<div class="stabilizing">${message}</div>`).join("")}
          <div class="muted demand-help">${ui.demandHelp}</div>
          <div class="editor">
            <div class="graph-heading">
              <p class="editor-title">${ui.graphTitle}</p>
              <div class="muted">${ui.graphHelp}</div>
            </div>
            <canvas width="1100" height="550" aria-label="${ui.outdoorCurve}"></canvas>
            <div class="editor-side">
              <p class="editor-title">${ui.customPreset}</p>
              <div class="muted">${ui.help}</div>
              <div class="rows">
                ${this.points
                  .map(
                    (point, index) => `
                  <div class="row">
                    <label>${ui.outdoor}
                      <input data-index="${index}" data-key="outdoor_temp" type="number" step="0.1" value="${point.outdoor_temp}">
                    </label>
                    <label>${ui.heatingTarget}
                      <input data-index="${index}" data-key="heating_setpoint" type="number" step="0.1" value="${point.heating_setpoint}">
                    </label>
                    <label>${ui.coolingTarget}
                      <input data-index="${index}" data-key="cooling_setpoint" type="number" step="0.1" value="${point.cooling_setpoint}">
                    </label>
                    <button data-remove="${index}" ${this.points.length <= 3 ? "disabled" : ""}>${ui.remove}</button>
                  </div>`
                  )
                  .join("")}
              </div>
              <div class="actions">
                <button data-add ${this.points.length >= 6 ? "disabled" : ""}>${ui.add}</button>
                <button class="save" data-save ${!entryId || this.points.length < 3 ? "disabled" : ""}>${ui.saveCurve}</button>
              </div>
              <div class="muted save-status" role="status">${this.dirty ? ui.unsaved : ""}</div>
            </div>
          </div>
        </div>
      </ha-card>
    `;

    this.bindEvents(entryId, ui);
    this.draw();
  }

  bindEvents(entryId, ui) {
    this.shadowRoot.querySelectorAll("[data-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        if (this.dirty && !window.confirm(ui.discard)) return;
        this.mode = button.dataset.mode;
        this.dirty = false;
        this.render();
      });
    });

    this.shadowRoot.querySelectorAll("input[data-index]").forEach((input) => {
      input.addEventListener("input", () => {
        const index = Number(input.dataset.index);
        this.points[index][input.dataset.key] = Number(input.value);
        this.normalize(false);
        this.dirty = true;
        this.setSaveStatus(ui.unsaved);
        this.draw();
      });
    });

    this.shadowRoot.querySelectorAll("[data-remove]").forEach((button) => {
      button.addEventListener("click", () => {
        this.points.splice(Number(button.dataset.remove), 1);
        this.normalize(true);
        this.dirty = true;
        this.render();
      });
    });

    this.shadowRoot.querySelector("[data-add]")?.addEventListener("click", () => {
      const last = this.points[this.points.length - 1] || {
        outdoor_temp: 20,
        heating_setpoint: 20,
        cooling_setpoint: 24,
      };
      this.points.push({
        outdoor_temp: Number(last.outdoor_temp) + 5,
        heating_setpoint: Number(last.heating_setpoint),
        cooling_setpoint: Number(last.cooling_setpoint),
      });
      this.normalize(true);
      this.dirty = true;
      this.render();
    });

    this.shadowRoot.querySelector("[data-save]")?.addEventListener("click", async (event) => {
      this.normalize(true);
      if (this.points.length < 3) return;
      const button = event.currentTarget;
      button.disabled = true;
      this.setSaveStatus(ui.saving);
      try {
        await this._hass.callService("hvac_setpoint_curve", "set_profile", {
          entry_id: entryId,
          heating_points: this.points.map((point) => ({
            outdoor_temp: point.outdoor_temp,
            setpoint: point.heating_setpoint,
          })),
          cooling_points: this.points.map((point) => ({
            outdoor_temp: point.outdoor_temp,
            setpoint: point.cooling_setpoint,
          })),
        });
        this.dirty = false;
        this.setSaveStatus(ui.saved);
      } catch (error) {
        this.dirty = true;
        this.setSaveStatus(ui.saveError);
        console.error("Failed to save HVAC setpoint curve", error);
      } finally {
        button.disabled = false;
      }
    });

  }

  normalize(sort) {
    this.points = this.points
      .map((point) => ({
        outdoor_temp: Math.round(Number(point.outdoor_temp) * 10) / 10,
        heating_setpoint: Math.round(Number(point.heating_setpoint) * 10) / 10,
        cooling_setpoint: Math.round(Number(point.cooling_setpoint) * 10) / 10,
      }))
      .filter(
        (point) =>
          Number.isFinite(point.outdoor_temp) &&
          Number.isFinite(point.heating_setpoint) &&
          Number.isFinite(point.cooling_setpoint) &&
          point.heating_setpoint < point.cooling_setpoint
      )
      .slice(0, 6);
    if (sort) this.points.sort((a, b) => a.outdoor_temp - b.outdoor_temp);
  }

  setSaveStatus(message) {
    const status = this.shadowRoot?.querySelector(".save-status");
    if (status) status.textContent = message;
  }

  escapeHtml(value) {
    const element = document.createElement("span");
    element.textContent = String(value ?? "");
    return element.innerHTML;
  }

  bounds() {
    const minX = Number(this.config.min_outdoor ?? -40);
    const maxX = Number(this.config.max_outdoor ?? 40);
    const minY = Number(this.config.min_setpoint ?? 15);
    const maxY = Number(this.config.max_setpoint ?? 31);
    return {
      minX: Number.isFinite(minX) && Number.isFinite(maxX) && minX < maxX ? minX : -40,
      maxX: Number.isFinite(minX) && Number.isFinite(maxX) && minX < maxX ? maxX : 40,
      minY: Number.isFinite(minY) && Number.isFinite(maxY) && minY < maxY ? minY : 15,
      maxY: Number.isFinite(minY) && Number.isFinite(maxY) && minY < maxY ? maxY : 31,
      pad: 54,
    };
  }

  xy(point, canvas) {
    const b = this.bounds();
    return {
      x: b.pad + ((point.outdoor_temp - b.minX) / (b.maxX - b.minX)) * (canvas.width - b.pad * 2),
      y: canvas.height - b.pad - ((point.setpoint - b.minY) / (b.maxY - b.minY)) * (canvas.height - b.pad * 2),
    };
  }

  draw() {
    const canvas = this.shadowRoot.querySelector("canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const b = this.bounds();
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = getComputedStyle(this).getPropertyValue("--card-background-color") || "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = "#c6cbd1";
    ctx.lineWidth = 1;
    ctx.fillStyle = "#6b7280";
    ctx.font = "20px sans-serif";
    for (let temp = b.minX; temp <= b.maxX; temp += 5) {
      const x = this.xy({ outdoor_temp: temp, setpoint: b.minY }, canvas).x;
      ctx.beginPath();
      ctx.moveTo(x, b.pad);
      ctx.lineTo(x, canvas.height - b.pad);
      ctx.stroke();
      if (temp % 10 === 0) ctx.fillText(String(temp), x - 12, canvas.height - 18);
    }
    for (let setpoint = b.minY; setpoint <= b.maxY; setpoint += 1) {
      const y = this.xy({ outdoor_temp: b.minX, setpoint }, canvas).y;
      ctx.beginPath();
      ctx.moveTo(b.pad, y);
      ctx.lineTo(canvas.width - b.pad, y);
      ctx.stroke();
      ctx.fillText(String(setpoint), 16, y + 7);
    }

    const sorted = [...this.points].sort((a, b) => a.outdoor_temp - b.outdoor_temp);
    if (sorted.length > 1) {
      ctx.fillStyle = "rgba(16, 185, 129, 0.14)";
      ctx.beginPath();
      sorted.forEach((point, index) => {
        const pos = this.xy({ outdoor_temp: point.outdoor_temp, setpoint: point.cooling_setpoint }, canvas);
        if (index === 0) ctx.moveTo(pos.x, pos.y);
        else ctx.lineTo(pos.x, pos.y);
      });
      [...sorted].reverse().forEach((point) => {
        const pos = this.xy({ outdoor_temp: point.outdoor_temp, setpoint: point.heating_setpoint }, canvas);
        ctx.lineTo(pos.x, pos.y);
      });
      ctx.closePath();
      ctx.fill();
    }
    const drawCurve = (key, color) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 5;
      ctx.beginPath();
      sorted.forEach((point, index) => {
        const pos = this.xy({ outdoor_temp: point.outdoor_temp, setpoint: point[key] }, canvas);
        if (index === 0) ctx.moveTo(pos.x, pos.y);
        else ctx.lineTo(pos.x, pos.y);
      });
      ctx.stroke();
      sorted.forEach((point) => {
        const pos = this.xy({ outdoor_temp: point.outdoor_temp, setpoint: point[key] }, canvas);
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, 8, 0, Math.PI * 2);
        ctx.fill();
      });
    };
    drawCurve("heating_setpoint", "#dc2626");
    drawCurve("cooling_setpoint", "#0284c7");

    ctx.font = "bold 20px sans-serif";
    ctx.fillStyle = "#dc2626";
    ctx.fillText(this.ui?.heating || "Heating", b.pad + 12, b.pad + 28);
    ctx.fillStyle = "#0284c7";
    ctx.fillText(this.ui?.cooling || "Cooling", b.pad + 150, b.pad + 28);
  }
}

if (!customElements.get("hvac-setpoint-curve-card")) {
  customElements.define("hvac-setpoint-curve-card", HvacSetpointCurveCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "hvac-setpoint-curve-card",
  name: "HVAC Building Profile",
  description: "Visual editor for automatic heating, the neutral comfort zone and cooling.",
});
