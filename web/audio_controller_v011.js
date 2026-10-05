(() => {
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  const ext = window.BACV011 || {
    root: null,
    state: {},
    mountedRoot: null,

    language() {
      return window.FerreisAnkiAudio?.config?.language === "pt-BR" ? "pt-BR" : "en";
    },

    text(key) {
      const dictionary = {
        en: {
          title: "Playback mode",
          profile: "Analyzed profile",
          realtime: "Real time",
          created: "Created audio",
          hint_profile: "Uses the gain measured for each audio file in the analyzed deck profile.",
          hint_realtime: "Normalizes the original audio while it plays.",
          hint_created: "Uses the generated normalized copy and avoids applying normalization twice.",
          overvolume: "OverVolume",
          overvolume_gain: "Extra gain",
          overvolume_hint: "Use when audio is still too quiet at 100%. Adds playback-only gain after normalization and uses a limiter to reduce clipping.",
        },
        "pt-BR": {
          title: "Modo de reprodução",
          profile: "Perfil analisado",
          realtime: "Em tempo real",
          created: "Áudios criados",
          hint_profile: "Usa o ganho medido para cada arquivo no perfil analisado do deck.",
          hint_realtime: "Normaliza o áudio original enquanto ele toca.",
          hint_created: "Usa a cópia normalizada gerada e evita aplicar normalização duas vezes.",
          overvolume: "OverVolume",
          overvolume_gain: "Ganho extra",
          overvolume_hint: "Use quando o áudio continuar baixo mesmo em 100%. Adiciona ganho somente na reprodução depois da normalização e usa um limitador para reduzir clipping.",
        },
      };
      return dictionary[this.language()][key] || key;
    },

    inferMode() {
      const configured = String(this.state.playback_mode || "");
      if (["profile", "realtime", "created"].includes(configured)) return configured;
      const base = window.FerreisAnkiAudio;
      if (base?.config?.deck_profile?.enabled) return "profile";
      if (base?.config?.normalize !== false) return "realtime";
      return "created";
    },

    installStyles() {
      if (document.getElementById("fac-v011-styles")) return;
      const style = document.createElement("style");
      style.id = "fac-v011-styles";
      style.textContent = `
        #ferreis-audio-controller .fac-playback-mode-select {
          box-sizing: border-box;
          width: 100%;
          min-height: 32px;
          padding: 5px 7px;
          border: 1px solid var(--fac-border);
          border-radius: 6px;
          background: var(--fac-bg-soft);
          color: var(--fac-text);
          font: inherit;
        }
        #ferreis-audio-controller .fac-playback-mode-hint,
        #ferreis-audio-controller .fac-overvolume-hint {
          color: var(--fac-muted);
          font-size: 11px;
          line-height: 1.35;
        }
        #ferreis-audio-controller .fac-overvolume-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
        }
        #ferreis-audio-controller .fac-overvolume-value {
          color: var(--fac-text);
          font-variant-numeric: tabular-nums;
          white-space: nowrap;
        }
        #ferreis-audio-controller .fac-overvolume-gain:disabled {
          opacity: 0.4;
        }
      `;
      document.head.appendChild(style);
    },

    installOverVolume() {
      if (!this.root || this.root.querySelector(".fac-overvolume-block")) return;
      const volume = this.root.querySelector(".fac-volume");
      const anchor = volume?.closest(".fac-block");
      if (!anchor || !anchor.parentNode) return;

      const section = document.createElement("section");
      section.className = "fac-block fac-overvolume-block";
      section.innerHTML = `
        <div class="fac-overvolume-head">
          <label class="fac-check-row" title="${this.text("overvolume_hint")}">
            <input class="fac-overvolume-enabled" type="checkbox">
            <span>${this.text("overvolume")}</span>
          </label>
          <span class="fac-overvolume-value">+6.0 dB</span>
        </div>
        <div class="fac-row fac-row-label"><span>${this.text("overvolume_gain")}</span></div>
        <input class="fac-overvolume-gain" type="range" min="0" max="12" step="0.5" value="6" aria-label="${this.text("overvolume_gain")}">
        <div class="fac-overvolume-hint">${this.text("overvolume_hint")}</div>
      `;
      anchor.insertAdjacentElement("afterend", section);

      const enabled = section.querySelector(".fac-overvolume-enabled");
      const gain = section.querySelector(".fac-overvolume-gain");

      enabled.addEventListener("change", () => {
        this.state.overvolume_enabled = Boolean(enabled.checked);
        this.syncOverVolume();
        pycmd(`ferreis_audio:v011:overvolume:enabled:${enabled.checked ? 1 : 0}`);
      });

      gain.addEventListener("input", () => {
        const value = clamp(Number(gain.value || 0), 0, 12);
        this.state.overvolume_gain_db = value;
        this.syncOverVolume();
        pycmd(`ferreis_audio:v011:overvolume:gain:${value}`);
      });
    },

    syncOverVolume() {
      if (!this.root) return;
      const base = window.FerreisAnkiAudio;
      const hasEnabled = Object.prototype.hasOwnProperty.call(this.state, "overvolume_enabled");
      const hasGain = Object.prototype.hasOwnProperty.call(this.state, "overvolume_gain_db");
      const enabled = hasEnabled
        ? Boolean(this.state.overvolume_enabled)
        : Boolean(base?.config?.overvolume_enabled ?? false);
      const rawGain = hasGain
        ? Number(this.state.overvolume_gain_db)
        : Number(base?.config?.overvolume_gain_db ?? 6);
      const gainDb = clamp(Number.isFinite(rawGain) ? rawGain : 6, 0, 12);

      this.state.overvolume_enabled = enabled;
      this.state.overvolume_gain_db = gainDb;

      const checkbox = this.root.querySelector(".fac-overvolume-enabled");
      const slider = this.root.querySelector(".fac-overvolume-gain");
      const value = this.root.querySelector(".fac-overvolume-value");
      if (checkbox) checkbox.checked = enabled;
      if (slider) {
        slider.value = String(gainDb);
        slider.disabled = !enabled;
      }
      if (value) value.textContent = `+${gainDb.toFixed(1)} dB`;

      if (base?.config) {
        base.config.overvolume_enabled = enabled;
        base.config.overvolume_gain_db = gainDb;
      }
    },

    installModeSelector() {
      if (!this.root || this.root.querySelector(".fac-playback-mode-block")) return;
      const anchor = this.root.querySelector(".fac-normalization-block");
      if (!anchor) return;

      const section = document.createElement("section");
      section.className = "fac-block fac-playback-mode-block";
      section.innerHTML = `
        <div class="fac-row fac-row-label"><span>${this.text("title")}</span></div>
        <select class="fac-playback-mode-select" aria-label="${this.text("title")}">
          <option value="profile">${this.text("profile")}</option>
          <option value="realtime">${this.text("realtime")}</option>
          <option value="created">${this.text("created")}</option>
        </select>
        <div class="fac-playback-mode-hint"></div>
      `;
      anchor.parentNode.insertBefore(section, anchor);

      section.querySelector(".fac-playback-mode-select").addEventListener("change", (event) => {
        const mode = String(event.target.value || "realtime");
        if (!["profile", "realtime", "created"].includes(mode)) return;
        this.state.playback_mode = mode;
        this.syncMode();
        pycmd(`ferreis_audio:v011:mode:${mode}`);
      });
    },

    syncMode() {
      if (!this.root) return;
      const mode = this.inferMode();
      const select = this.root.querySelector(".fac-playback-mode-select");
      if (select && select.value !== mode) select.value = mode;
      const hint = this.root.querySelector(".fac-playback-mode-hint");
      if (hint) hint.textContent = this.text(`hint_${mode}`);

      const normalize = this.root.querySelector(".fac-normalize");
      if (normalize) normalize.checked = mode === "realtime";
      const base = window.FerreisAnkiAudio;
      if (base?.config) {
        base.config.playback_mode = mode;
        base.config.normalize = mode === "realtime";
        if (base.config.deck_profile) base.config.deck_profile.enabled = mode === "profile";
      }
    },

    attach(root) {
      if (!root) return;
      this.root = root;
      this.mountedRoot = root;
      this.installStyles();
      this.installOverVolume();
      this.installModeSelector();
      this.syncOverVolume();
      this.syncMode();
    },

    updateState(state) {
      this.state = { ...this.state, ...(state || {}) };
      this.syncOverVolume();
      this.syncMode();
    },

    patchV010() {
      const v010 = window.BACV010;
      if (!v010 || v010.__bacV011Patched) return;

      const originalAttach = v010.attach.bind(v010);
      v010.attach = (root) => {
        originalAttach(root);
        window.BACV011?.attach(root);
      };

      const originalUpdateState = v010.updateState.bind(v010);
      v010.updateState = (state) => {
        originalUpdateState(state);
        window.BACV011?.updateState(state);
      };
      v010.__bacV011Patched = true;
    },

    async boot() {
      for (let attempt = 0; attempt < 100; attempt++) {
        const root = document.getElementById("ferreis-audio-controller");
        if (root && window.FerreisAnkiAudio && window.BACV010) {
          this.patchV010();
          this.state = { ...(window.BACV010.state || {}) };
          this.attach(root);
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 50));
      }
    },
  };

  window.BACV011 = ext;
  ext.boot();
})();
