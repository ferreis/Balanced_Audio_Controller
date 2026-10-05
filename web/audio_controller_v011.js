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
          group_playback: "Playback",
          group_processing: "Normalization",
          group_deck: "Deck",
          title: "Playback mode",
          profile: "Analyzed profile",
          realtime: "Real time",
          created: "Created audio",
          hint_profile: "Uses the gain measured for each audio file. Run Analyze deck again after changing the target loudness.",
          hint_realtime: "Normalizes the original audio while it plays. No deck analysis is required.",
          hint_created: "Keeps the original player and adds a second native player for the permanent bac_norm_* copy. Both remain on the card even if the add-on is disabled.",
          state_ready: "Ready",
          state_instant: "Immediate",
          state_needs_analysis: "Needs analysis",
          state_needs_copies: "Needs copies",
          overvolume: "OverVolume",
          overvolume_gain: "Extra gain",
          overvolume_hint: "Optional playback boost after the selected mode. Use it only when 100% volume is still too quiet.",
        },
        "pt-BR": {
          group_playback: "Reprodução",
          group_processing: "Normalização",
          group_deck: "Deck",
          title: "Modo de reprodução",
          profile: "Perfil analisado",
          realtime: "Em tempo real",
          created: "Áudios criados",
          hint_profile: "Usa o ganho medido para cada arquivo. Reanalise o deck depois de alterar o loudness alvo.",
          hint_realtime: "Normaliza o áudio original enquanto ele toca. Não exige análise prévia do deck.",
          hint_created: "Mantém o player do áudio original e adiciona um segundo player nativo para a cópia permanente bac_norm_*. Os dois ficam no card mesmo com o add-on desativado.",
          state_ready: "Pronto",
          state_instant: "Imediato",
          state_needs_analysis: "Precisa analisar",
          state_needs_copies: "Precisa gerar",
          overvolume: "OverVolume",
          overvolume_gain: "Ganho extra",
          overvolume_hint: "Boost opcional aplicado depois do modo escolhido. Use apenas quando 100% de volume ainda estiver baixo.",
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
        #ferreis-audio-controller .fac-side-panel {
          width: 246px;
        }
        #ferreis-audio-controller .fac-side-body {
          gap: 8px;
          padding: 9px;
        }
        #ferreis-audio-controller .fac-ui-group {
          overflow: hidden;
          border: 1px solid var(--fac-divider);
          border-radius: 9px;
          background: rgba(255, 255, 255, 0.025);
        }
        #ferreis-audio-controller .fac-ui-group-title {
          padding: 7px 9px;
          border-bottom: 1px solid var(--fac-divider);
          background: rgba(255, 255, 255, 0.035);
          color: var(--fac-muted);
          font-size: 10px;
          font-weight: 600;
          letter-spacing: 0.04em;
          text-transform: uppercase;
        }
        #ferreis-audio-controller .fac-ui-group > .fac-block {
          padding: 9px;
          border-bottom: 1px solid var(--fac-divider);
        }
        #ferreis-audio-controller .fac-ui-group > .fac-block:last-child {
          border-bottom: 0;
        }
        #ferreis-audio-controller .fac-playback-mode-head,
        #ferreis-audio-controller .fac-overvolume-head {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
        }
        #ferreis-audio-controller .fac-playback-mode-select {
          box-sizing: border-box;
          width: 100%;
          min-height: 34px;
          padding: 5px 8px;
          border: 1px solid var(--fac-border);
          border-radius: 7px;
          background-color: rgb(31, 34, 40);
          color: var(--fac-text, #e8e9ec);
          -webkit-text-fill-color: var(--fac-text, #e8e9ec);
          color-scheme: dark;
          font: inherit;
        }
        #ferreis-audio-controller .fac-playback-mode-select option {
          background-color: rgb(31, 34, 40);
          color: #e8e9ec;
          -webkit-text-fill-color: #e8e9ec;
        }
        #ferreis-audio-controller .fac-mode-state {
          max-width: 92px;
          padding: 2px 6px;
          overflow: hidden;
          border: 1px solid var(--fac-border);
          border-radius: 999px;
          color: var(--fac-muted);
          font-size: 9px;
          line-height: 1.2;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        #ferreis-audio-controller .fac-mode-state.fac-state-ok {
          border-color: rgba(115, 201, 145, 0.45);
          color: var(--fac-success);
        }
        #ferreis-audio-controller .fac-mode-state.fac-state-warn {
          border-color: rgba(229, 192, 123, 0.45);
          color: var(--fac-warning);
        }
        #ferreis-audio-controller .fac-playback-mode-hint,
        #ferreis-audio-controller .fac-overvolume-hint {
          color: var(--fac-muted);
          font-size: 10px;
          line-height: 1.4;
        }
        #ferreis-audio-controller .fac-overvolume-value {
          color: var(--fac-text);
          font-variant-numeric: tabular-nums;
          white-space: nowrap;
        }
        #ferreis-audio-controller .fac-overvolume-gain:disabled {
          opacity: 0.4;
        }
        #ferreis-audio-controller .fac-normalization-block[hidden] {
          display: none !important;
        }
        #ferreis-audio-controller .fac-status {
          display: block;
          margin: 1px 2px 0;
          padding: 6px 7px;
          overflow: hidden;
          border-radius: 6px;
          background: rgba(0, 0, 0, 0.10);
          color: var(--fac-muted);
          font-size: 9px;
          line-height: 1.3;
          text-overflow: ellipsis;
          white-space: nowrap;
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
        <div class="fac-playback-mode-head">
          <div class="fac-row fac-row-label"><span>${this.text("title")}</span></div>
          <span class="fac-mode-state"></span>
        </div>
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

    modeReadiness(mode) {
      if (mode === "realtime") {
        return { text: this.text("state_instant"), className: "fac-state-ok" };
      }
      if (mode === "profile") {
        const ready = Boolean(this.state.exists) && !Boolean(this.state.stale);
        return {
          text: this.text(ready ? "state_ready" : "state_needs_analysis"),
          className: ready ? "fac-state-ok" : "fac-state-warn",
        };
      }
      const ready = Boolean(this.state.created_ready);
      return {
        text: this.text(ready ? "state_ready" : "state_needs_copies"),
        className: ready ? "fac-state-ok" : "fac-state-warn",
      };
    },

    syncMode() {
      if (!this.root) return;
      const mode = this.inferMode();
      const select = this.root.querySelector(".fac-playback-mode-select");
      if (select && select.value !== mode) select.value = mode;
      const hint = this.root.querySelector(".fac-playback-mode-hint");
      if (hint) hint.textContent = this.text(`hint_${mode}`);

      const stateBadge = this.root.querySelector(".fac-mode-state");
      if (stateBadge) {
        const readiness = this.modeReadiness(mode);
        stateBadge.classList.remove("fac-state-ok", "fac-state-warn");
        stateBadge.classList.add(readiness.className);
        stateBadge.textContent = readiness.text;
        stateBadge.title = readiness.text;
      }

      const normalize = this.root.querySelector(".fac-normalize");
      if (normalize) normalize.checked = mode === "realtime";
      const base = window.FerreisAnkiAudio;
      if (base?.config) {
        base.config.playback_mode = mode;
        base.config.normalize = mode === "realtime";
        if (base.config.deck_profile) base.config.deck_profile.enabled = mode === "profile";
      }
    },

    makeGroup(className, title, blocks, anchor) {
      if (!this.root || !anchor?.parentNode || this.root.querySelector(`.${className}`)) return;
      const group = document.createElement("div");
      group.className = `fac-ui-group ${className}`;
      const heading = document.createElement("div");
      heading.className = "fac-ui-group-title";
      heading.textContent = title;
      group.appendChild(heading);
      anchor.parentNode.insertBefore(group, anchor);
      for (const block of blocks) {
        if (block) group.appendChild(block);
      }
    },

    organizePanel() {
      if (!this.root) return;
      const speed = this.root.querySelector(".fac-speed")?.closest(".fac-block");
      const volume = this.root.querySelector(".fac-volume")?.closest(".fac-block");
      const mode = this.root.querySelector(".fac-playback-mode-block");
      const overvolume = this.root.querySelector(".fac-overvolume-block");
      const deck = this.root.querySelector(".fac-deck-profile-block");
      const legacyNormalize = this.root.querySelector(".fac-normalization-block");

      if (legacyNormalize) {
        legacyNormalize.hidden = true;
        legacyNormalize.setAttribute("aria-hidden", "true");
      }

      if (speed && volume) {
        this.makeGroup("fac-playback-group", this.text("group_playback"), [speed, volume], speed);
      }
      if (mode) {
        this.makeGroup(
          "fac-processing-group",
          this.text("group_processing"),
          [mode, overvolume],
          mode
        );
      }
      if (deck) {
        this.makeGroup("fac-deck-group", this.text("group_deck"), [deck], deck);
      }
    },

    syncBusyState() {
      if (!this.root) return;
      const analyze = this.root.querySelector(".fac-analyze-deck");
      if (analyze) {
        analyze.disabled = Boolean(this.state.analyzing || this.state.materializing);
      }
    },

    attach(root) {
      if (!root) return;
      this.root = root;
      this.mountedRoot = root;
      this.installStyles();
      this.installOverVolume();
      this.installModeSelector();
      this.organizePanel();
      this.syncOverVolume();
      this.syncMode();
      this.syncBusyState();
    },

    updateState(state) {
      this.state = { ...this.state, ...(state || {}) };
      this.syncOverVolume();
      this.syncMode();
      this.syncBusyState();
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
