(() => {
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
        },
        "pt-BR": {
          title: "Modo de reprodução",
          profile: "Perfil analisado",
          realtime: "Em tempo real",
          created: "Áudios criados",
          hint_profile: "Usa o ganho medido para cada arquivo no perfil analisado do deck.",
          hint_realtime: "Normaliza o áudio original enquanto ele toca.",
          hint_created: "Usa a cópia normalizada gerada e evita aplicar normalização duas vezes.",
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
        #ferreis-audio-controller .fac-playback-mode-hint {
          color: var(--fac-muted);
          font-size: 11px;
          line-height: 1.35;
        }
      `;
      document.head.appendChild(style);
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
      this.installModeSelector();
      this.syncMode();
    },

    updateState(state) {
      this.state = { ...this.state, ...(state || {}) };
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
