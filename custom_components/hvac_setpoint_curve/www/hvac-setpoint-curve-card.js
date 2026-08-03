class HvacSetpointCurveCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) {
      throw new Error("entity is required");
    }
    this.config = config;
    this.mode = null;
    this.points = [];
    this.dirty = false;
    this.dragIndex = null;
    this.attachShadow({ mode: "open" });
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
      this.shadowRoot.innerHTML = `<ha-card><div class="wrap">Entity not found: ${this.config.entity}</div></ha-card>`;
      return;
    }

    const attrs = state.attributes || {};
    const entryId = attrs.config_entry_id;
    const isDutch = String(this._hass.language || "").toLowerCase().startsWith("nl");
    const ui = isDutch
      ? {
          heating: "Verwarmen",
          cooling: "Koelen",
          outdoorCurve: "Afzonderlijke stook- en koellijnen op basis van buitentemperatuur",
          customPreset: "Eigen preset",
          help: "Voeg minimaal 3 losse setpoints toe. Wijzigingen verschijnen direct in de curve.",
          outdoor: "Buiten °C",
          setpoint: "Doel °C",
          remove: "Verwijder",
          add: "Punt toevoegen",
          saveCurve: "Gekozen curve opslaan",
          outdoorNow: "Buiten nu",
          outdoorAverage: "Buiten gemiddeld",
          coolingIndoor: "Binnen koelen",
          heatingIndoor: "Binnen verwarmen",
          targetNow: "Doel nu",
          coolingStabilizing: "Koeling stabiliseert — modus blijft beschikbaar voor restwarmte",
          heatingStabilizing: "Verwarming stabiliseert — modus blijft beschikbaar voor restkou",
          demandHelp: "Buiten gemiddeld bepaalt of een cyclus mag starten. Tijdens stabilisatie zet restwarmte de teller terug; duidelijke afkoeling voorbij het doel schakelt direct uit.",
        }
      : {
          heating: "Heating",
          cooling: "Cooling",
          outdoorCurve: "Separate heating and cooling curves based on outdoor temperature",
          customPreset: "Custom preset",
          help: "Add at least 3 individual setpoints. Changes appear in the curve immediately.",
          outdoor: "Outdoor °C",
          setpoint: "Target °C",
          remove: "Remove",
          add: "Add point",
          saveCurve: "Save selected curve",
          outdoorNow: "Outdoor now",
          outdoorAverage: "Outdoor average",
          coolingIndoor: "Cooling indoor",
          heatingIndoor: "Heating indoor",
          targetNow: "Target now",
          coolingStabilizing: "Cooling is stabilizing — mode remains available for residual heat",
          heatingStabilizing: "Heating is stabilizing — mode remains available for residual cold",
          demandHelp: "The outdoor average permits a cycle to start. Residual drift resets stabilization; clear cooling or heating past target switches the mode off immediately.",
        };

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

    const availableModes = [
      attrs.cooling_enabled ? "cooling" : null,
      attrs.heating_enabled ? "heating" : null,
    ].filter(Boolean);
    if (!availableModes.includes(this.mode)) {
      this.mode = availableModes[0] || "cooling";
      this.dirty = false;
    }
    if (!this.dirty) {
      const selectedCurve =
        this.mode === "heating" ? attrs.heating_curve_points : attrs.cooling_curve_points;
      this.points = structuredClone(selectedCurve || attrs.curve_points || []);
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
          aspect-ratio: 16 / 9;
          border: 1px solid var(--divider-color, #d8d8d8);
          border-radius: 6px;
          background: var(--card-background-color, #fff);
          touch-action: none;
        }
        .editor {
          display: grid;
          grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
          gap: 16px;
          align-items: start;
        }
        .editor-side {
          min-width: 0;
        }
        .editor-title {
          margin: 0 0 4px;
          font-size: 15px;
          font-weight: 600;
        }
        .rows {
          display: grid;
          gap: 8px;
          margin-top: 10px;
        }
        .row {
          display: grid;
          grid-template-columns: 1fr 1fr auto;
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
        @media (max-width: 760px) {
          .editor { grid-template-columns: 1fr; }
        }
      </style>
      <ha-card>
        <div class="wrap">
          <div class="top">
            <div>
              <h2>${this.config.title || "HVAC Setpoint Curve"}</h2>
              <div class="muted">${ui.outdoorCurve}</div>
            </div>
            ${
              availableModes.length > 1
                ? `<div class="tabs">
                    <button data-mode="cooling" class="${this.mode === "cooling" ? "active" : ""}">${ui.cooling}</button>
                    <button data-mode="heating" class="${this.mode === "heating" ? "active" : ""}">${ui.heating}</button>
                  </div>`
                : ""
            }
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
                    <label>${ui.setpoint}
                      <input data-index="${index}" data-key="setpoint" type="number" step="0.1" value="${point.setpoint}">
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
            </div>
            <canvas width="1100" height="620" aria-label="${ui.outdoorCurve}"></canvas>
          </div>
        </div>
      </ha-card>
    `;

    this.bindEvents(entryId);
    this.draw();
  }

  bindEvents(entryId) {
    this.shadowRoot.querySelectorAll("[data-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        this.mode = button.dataset.mode;
        this.dirty = false;
        this.render();
      });
    });

    this.shadowRoot.querySelectorAll("input").forEach((input) => {
      input.addEventListener("input", () => {
        const index = Number(input.dataset.index);
        this.points[index][input.dataset.key] = Number(input.value);
        this.normalize(false);
        this.dirty = true;
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
      const last = this.points[this.points.length - 1] || { outdoor_temp: 20, setpoint: 21 };
      this.points.push({ outdoor_temp: Number(last.outdoor_temp) + 5, setpoint: Number(last.setpoint) });
      this.normalize(true);
      this.dirty = true;
      this.render();
    });

    this.shadowRoot.querySelector("[data-save]")?.addEventListener("click", () => {
      this.normalize(true);
      if (this.points.length < 3) return;
      this._hass.callService("hvac_setpoint_curve", "set_curve", {
        entry_id: entryId,
        mode: this.mode,
        points: this.points,
      });
      this.dirty = false;
    });

    const canvas = this.shadowRoot.querySelector("canvas");
    canvas.addEventListener("pointerdown", (event) => this.startDrag(event));
    canvas.addEventListener("pointermove", (event) => this.drag(event));
    canvas.addEventListener("pointerup", () => this.endDrag());
    canvas.addEventListener("pointerleave", () => this.endDrag());
  }

  normalize(sort) {
    this.points = this.points
      .map((point) => ({
        outdoor_temp: Math.round(Number(point.outdoor_temp) * 10) / 10,
        setpoint: Math.round(Number(point.setpoint) * 10) / 10,
      }))
      .filter((point) => Number.isFinite(point.outdoor_temp) && Number.isFinite(point.setpoint))
      .slice(0, 6);
    if (sort) this.points.sort((a, b) => a.outdoor_temp - b.outdoor_temp);
  }

  bounds() {
    return {
      minX: Number(this.config.min_outdoor ?? -40),
      maxX: Number(this.config.max_outdoor ?? 40),
      minY: Number(this.config.min_setpoint ?? 15),
      maxY: Number(this.config.max_setpoint ?? 31),
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

  pointFromEvent(event) {
    const canvas = this.shadowRoot.querySelector("canvas");
    const rect = canvas.getBoundingClientRect();
    const b = this.bounds();
    const x = ((event.clientX - rect.left) / rect.width) * canvas.width;
    const y = ((event.clientY - rect.top) / rect.height) * canvas.height;
    return {
      outdoor_temp: Math.round((b.minX + ((x - b.pad) / (canvas.width - b.pad * 2)) * (b.maxX - b.minX)) * 10) / 10,
      setpoint: Math.round((b.minY + ((canvas.height - b.pad - y) / (canvas.height - b.pad * 2)) * (b.maxY - b.minY)) * 10) / 10,
    };
  }

  startDrag(event) {
    const canvas = this.shadowRoot.querySelector("canvas");
    const rect = canvas.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * canvas.width;
    const y = ((event.clientY - rect.top) / rect.height) * canvas.height;
    let best = null;
    let bestDistance = 28;
    this.points.forEach((point, index) => {
      const pos = this.xy(point, canvas);
      const distance = Math.hypot(pos.x - x, pos.y - y);
      if (distance < bestDistance) {
        best = index;
        bestDistance = distance;
      }
    });
    this.dragIndex = best;
  }

  drag(event) {
    if (this.dragIndex === null) return;
    const b = this.bounds();
    const point = this.pointFromEvent(event);
    this.points[this.dragIndex] = {
      outdoor_temp: Math.min(b.maxX, Math.max(b.minX, point.outdoor_temp)),
      setpoint: Math.min(b.maxY, Math.max(b.minY, point.setpoint)),
    };
    this.dirty = true;
    this.draw();
  }

  endDrag() {
    if (this.dragIndex === null) return;
    this.dragIndex = null;
    this.normalize(true);
    this.render();
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

    const lineColor = "#0f766e";
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 5;
    ctx.beginPath();
    [...this.points].sort((a, b) => a.outdoor_temp - b.outdoor_temp).forEach((point, index) => {
      const pos = this.xy(point, canvas);
      if (index === 0) ctx.moveTo(pos.x, pos.y);
      else ctx.lineTo(pos.x, pos.y);
    });
    ctx.stroke();

    this.points.forEach((point, index) => {
      const pos = this.xy(point, canvas);
      ctx.fillStyle = index === this.dragIndex ? "#dc2626" : lineColor;
      ctx.fillRect(pos.x - 9, pos.y - 9, 18, 18);
      ctx.fillStyle = "#111827";
      ctx.fillText(`P${index + 1}`, pos.x + 12, pos.y - 12);
    });
  }
}

customElements.define("hvac-setpoint-curve-card", HvacSetpointCurveCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "hvac-setpoint-curve-card",
  name: "HVAC Setpoint Curve Editor",
  description: "Visual editor for one shared HVAC heating/cooling setpoint curve.",
});
