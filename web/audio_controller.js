(() => {
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const SPEED_BUTTON_STEP = 0.5;
  const PANEL_STORAGE_KEY = "ferreisAudioSidePanelPositionV4";

  const controller = window.FerreisAnkiAudio || {
    root: null,
    config: null,

    mount() {
      const root = document.getElementById("ferreis-audio-controller");
      if (!root || root.dataset.mounted === "1") return;

      this.root = root;
      root.dataset.mounted = "1";

      try {
        this.config = JSON.parse(root.dataset.config || "{}");
      } catch (error) {
        console.error("[Balanced Audio Controller] invalid config", error);
        return;
      }

      this.render();
      window.BACV010?.attach?.(root);
      requestAnimationFrame(() => this.restoreSidePanelPosition());
    },

    t(key, values = {}) {
      const dictionary = this.config?.i18n || {};
      const template = dictionary[key] || key;
      return String(template).replace(/\{(\w+)\}/g, (_match, name) =>
        Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : `{${name}}`
      );
    },

    isPreviewSurface() {
      return ["previewer", "card_layout"].includes(String(this.config?.surface || ""));
    },

    previewSideLabel() {
      return this.t(this.config?.side === "answer" ? "preview_back" : "preview_front");
    },

    render() {
      if (!this.root) return;
      const t = (key, values) => this.t(key, values);

      this.root.innerHTML = `
        <aside class="fac-side-panel" aria-label="${t("audio_control_aria")}">
          <div class="fac-side-handle" title="${t("drag_hint")}">
            <span class="fac-drag-dots">⠿</span>
            <span>${t("audio")}</span>
          </div>

          <div class="fac-side-body">
            ${this.isPreviewSurface() ? `
            <section class="fac-block fac-preview-tools">
              <div class="fac-row fac-row-label">
                <span>${t("preview_mode")}</span>
                <span class="fac-preview-side-badge">${this.previewSideLabel()}</span>
              </div>
              <div class="fac-preview-audio-count">${t("preview_audio_count", { count: Number(this.config.side_audio_count || 0) })}</div>
              <button class="fac-action fac-open-settings" type="button">${t("preview_open_settings")}</button>
            </section>
            ` : ""}

            <section class="fac-block">
              <div class="fac-row fac-row-label">
                <span>${t("speed")}</span>
              </div>
              <div class="fac-speed-control">
                <button class="fac-speed-step fac-speed-down" type="button" title="${t("decrease_speed")}" aria-label="${t("decrease_speed")}">−</button>
                <label class="fac-speed-center" aria-label="${t("playback_speed")}">
                  <span class="fac-speed-value-group">
                    <input class="fac-speed" type="number" min="0.25" max="2" step="0.05" inputmode="decimal" title="${t("playback_speed")}">
                    <span class="fac-speed-unit">x</span>
                  </span>
                </label>
                <button class="fac-speed-step fac-speed-up" type="button" title="${t("increase_speed")}" aria-label="${t("increase_speed")}">+</button>
              </div>
            </section>

            <section class="fac-block">
              <div class="fac-row fac-row-label">
                <span>${t("volume")}</span>
                <span class="fac-volume-value"></span>
              </div>
              <input class="fac-volume" type="range" min="0" max="100" step="1" title="${t("output_volume")}">
            </section>

            <section class="fac-block fac-normalization-block">
              <label class="fac-check-row" title="${t("realtime_normalization_hint")}">
                <input class="fac-normalize" type="checkbox">
                <span>${t("realtime_normalization")}</span>
              </label>
            </section>

            <section class="fac-block fac-deck-profile-block">
              <div class="fac-row fac-row-label fac-deck-title-row">
                <span>${t("deck_profile")}</span>
                <span class="fac-deck-badge">${t("not_analyzed")}</span>
              </div>

              <div class="fac-deck-name" title=""></div>

              <div class="fac-deck-actions">
                <button class="fac-action fac-analyze-deck" type="button">${t("analyze_deck")}</button>
              </div>

              <div class="fac-deck-progress" hidden>
                <div class="fac-deck-progress-track">
                  <div class="fac-deck-progress-bar"></div>
                </div>
                <span class="fac-deck-progress-text"></span>
              </div>

              <div class="fac-deck-summary"></div>
            </section>

            <span class="fac-status">${t("native_player")}</span>
          </div>
        </aside>
      `;

      const speed = this.root.querySelector(".fac-speed");
      const requestedSpeed = clamp(Number(this.config.speed || 1), 0.25, 2);
      speed.value = this.formatSpeed(requestedSpeed);
      this.syncSpeedInputWidth(speed);

      const volume = this.root.querySelector(".fac-volume");
      volume.value = String(Math.round(clamp(Number(this.config.volume ?? 1), 0, 1) * 100));
      this.root.querySelector(".fac-volume-value").textContent = `${volume.value}%`;

      const normalize = this.root.querySelector(".fac-normalize");
      normalize.checked = Boolean(this.config.normalize);


      this.root.querySelector(".fac-speed-down").addEventListener("click", () => this.stepSpeed(-1));
      this.root.querySelector(".fac-speed-up").addEventListener("click", () => this.stepSpeed(1));

      const commitSpeedInput = () => {
        const parsed = Number(String(speed.value).replace(",", "."));
        if (!Number.isFinite(parsed)) {
          speed.value = this.formatSpeed(this.config.speed || 1);
          this.syncSpeedInputWidth(speed);
          return;
        }
        this.setSpeed(parsed);
      };
      speed.addEventListener("input", () => this.syncSpeedInputWidth(speed));
      speed.addEventListener("change", commitSpeedInput);
      speed.addEventListener("blur", commitSpeedInput);
      speed.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
          commitSpeedInput();
          speed.blur();
        }
      });

      volume.addEventListener("input", () => {
        const value = clamp(Number(volume.value) / 100, 0, 1);
        this.config.volume = value;
        this.root.querySelector(".fac-volume-value").textContent = `${volume.value}%`;
        pycmd(`ferreis_audio:set:volume:${value}`);
      });

      normalize.addEventListener("change", (event) => {
        this.config.normalize = Boolean(event.target.checked);
        pycmd(`ferreis_audio:set:normalize:${this.config.normalize ? 1 : 0}`);
      });


      const settingsButton = this.root.querySelector(".fac-open-settings");
      if (settingsButton) {
        settingsButton.addEventListener("click", () => {
          pycmd("ferreis_audio:v010:settings");
        });
      }

      this.root.querySelector(".fac-analyze-deck").addEventListener("click", () => {
        this.updateDeckProfile({
          ...(this.config.deck_profile || {}),
          analyzing: true,
          progress: 0,
          message: this.t("preparing_analysis"),
        });
        pycmd("ferreis_audio:deck:analyze");
      });


      this.updateDeckProfile(this.config.deck_profile || {});
      this.enableSidePanelDrag();
    },

    setStatus(text) {
      const status = this.root?.querySelector(".fac-status");
      if (status) {
        status.textContent = text || this.t("native_player");
        status.title = status.textContent;
      }
    },

    formatSpeed(value) {
      const rounded = Math.round(Number(value) * 100) / 100;
      return rounded.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
    },

    syncSpeedInputWidth(input) {
      if (!input) return;
      const text = String(input.value || "1");
      const width = Math.max(1.4, Math.min(4.2, text.length + 0.35));
      input.style.width = `${width}ch`;
    },


    updateDeckProfile(state) {
      if (!this.root) return;
      this.config.deck_profile = { ...(this.config.deck_profile || {}), ...(state || {}) };
      const profile = this.config.deck_profile;

      const name = this.root.querySelector(".fac-deck-name");
      const badge = this.root.querySelector(".fac-deck-badge");
      const analyze = this.root.querySelector(".fac-analyze-deck");
      const summary = this.root.querySelector(".fac-deck-summary");
      const progressWrap = this.root.querySelector(".fac-deck-progress");
      const progressBar = this.root.querySelector(".fac-deck-progress-bar");
      const progressText = this.root.querySelector(".fac-deck-progress-text");

      if (name) {
        name.textContent = profile.deck_name || this.t("current_deck");
        name.title = name.textContent;
      }
      if (analyze) analyze.disabled = Boolean(profile.analyzing);

      if (badge) {
        badge.classList.remove("fac-badge-ok", "fac-badge-warn", "fac-badge-busy");
        if (profile.analyzing) {
          badge.textContent = this.t("analyzing");
          badge.classList.add("fac-badge-busy");
        } else if (profile.exists && profile.stale) {
          badge.textContent = this.t("reanalyze");
          badge.classList.add("fac-badge-warn");
        } else if (profile.exists) {
          badge.textContent = this.t("ready");
          badge.classList.add("fac-badge-ok");
        } else {
          badge.textContent = this.t("not_analyzed");
        }
      }

      const progress = clamp(Number(profile.progress || 0), 0, 100);
      if (progressWrap) progressWrap.hidden = !profile.analyzing;
      if (progressBar) progressBar.style.width = `${progress}%`;
      if (progressText) progressText.textContent = profile.message || `${profile.processed || 0}/${profile.total || 0}`;

      if (summary) {
        if (profile.error) {
          summary.textContent = profile.error;
          summary.className = "fac-deck-summary fac-deck-error";
        } else if (profile.exists) {
          const parts = [this.t("audio_count", { count: profile.file_count || 0 })];
          if (Number.isFinite(Number(profile.min_lufs)) && Number.isFinite(Number(profile.max_lufs))) {
            parts.push(this.t("loudness_range", {
              min: Number(profile.min_lufs).toFixed(1),
              max: Number(profile.max_lufs).toFixed(1),
            }));
          }
          if (profile.failed_count) parts.push(this.t("failure_count", { count: profile.failed_count }));
          if (profile.stale) parts.push(this.t("target_changed"));
          summary.textContent = profile.message || parts.join(" · ");
          summary.className = "fac-deck-summary";
        } else {
          summary.textContent = profile.message || this.t("deck_summary_empty");
          summary.className = "fac-deck-summary";
        }
      }
    },

    setSpeed(value) {
      value = clamp(Number(value), 0.25, 2);
      value = Math.round(value * 100) / 100;
      this.config.speed = value;
      const speed = this.root?.querySelector(".fac-speed");
      if (speed) {
        speed.value = this.formatSpeed(value);
        this.syncSpeedInputWidth(speed);
      }
      pycmd(`ferreis_audio:set:speed:${value}`);
    },

    stepSpeed(direction) {
      const current = Number(this.config.speed || 1);
      this.setSpeed(current + (direction * SPEED_BUTTON_STEP));
    },

    restoreSidePanelPosition() {
      if (!this.root) return;
      const panel = this.root.querySelector(".fac-side-panel");
      if (!panel) return;

      let saved = null;
      try {
        saved = JSON.parse(localStorage.getItem(PANEL_STORAGE_KEY) || "null");
      } catch (_) {}

      if (saved && Number.isFinite(saved.left) && Number.isFinite(saved.top)) {
        const rect = panel.getBoundingClientRect();
        panel.style.right = "auto";
        panel.style.left = `${clamp(saved.left, 4, Math.max(4, window.innerWidth - rect.width - 4))}px`;
        panel.style.top = `${clamp(saved.top, 4, Math.max(4, window.innerHeight - rect.height - 4))}px`;
      }
    },

    resetSidePanelPosition() {
      if (!this.root) return;
      const panel = this.root.querySelector(".fac-side-panel");
      if (!panel) return;
      localStorage.removeItem(PANEL_STORAGE_KEY);
      panel.style.left = "auto";
      panel.style.right = "14px";
      panel.style.top = "12%";
    },

    enableSidePanelDrag() {
      const panel = this.root?.querySelector(".fac-side-panel");
      const handle = this.root?.querySelector(".fac-side-handle");
      if (!panel || !handle) return;

      let dragging = false;
      let offsetX = 0;
      let offsetY = 0;

      const move = (event) => {
        if (!dragging) return;
        const rect = panel.getBoundingClientRect();
        const left = clamp(event.clientX - offsetX, 4, Math.max(4, window.innerWidth - rect.width - 4));
        const top = clamp(event.clientY - offsetY, 4, Math.max(4, window.innerHeight - rect.height - 4));
        panel.style.right = "auto";
        panel.style.left = `${left}px`;
        panel.style.top = `${top}px`;
      };

      const end = () => {
        if (!dragging) return;
        dragging = false;
        panel.classList.remove("fac-dragging");
        const rect = panel.getBoundingClientRect();
        localStorage.setItem(PANEL_STORAGE_KEY, JSON.stringify({ left: rect.left, top: rect.top }));
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", end);
        window.removeEventListener("pointercancel", end);
      };

      handle.addEventListener("pointerdown", (event) => {
        if (event.button !== 0) return;
        const rect = panel.getBoundingClientRect();
        dragging = true;
        offsetX = event.clientX - rect.left;
        offsetY = event.clientY - rect.top;
        panel.classList.add("fac-dragging");
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", end);
        window.addEventListener("pointercancel", end);
        event.preventDefault();
      });

      handle.addEventListener("dblclick", () => this.resetSidePanelPosition());
    },
  };

  window.FerreisAnkiAudio = controller;
})();
