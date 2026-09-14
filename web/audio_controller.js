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
      requestAnimationFrame(() => this.restoreSidePanelPosition());
    },

    render() {
      if (!this.root) return;
      this.root.innerHTML = `
        <aside class="fac-side-panel" aria-label="Controle de áudio">
          <div class="fac-side-handle" title="Arraste para mover. Clique duas vezes para restaurar a posição.">
            <span class="fac-drag-dots">⠿</span>
            <span>Áudio</span>
          </div>

          <div class="fac-side-body">
            <section class="fac-block">
              <div class="fac-row fac-row-label">
                <span>Velocidade</span>
              </div>
              <div class="fac-speed-control">
                <button class="fac-speed-step fac-speed-down" type="button" title="Diminuir 0,5x" aria-label="Diminuir velocidade em 0,5x">−</button>
                <label class="fac-speed-center" aria-label="Velocidade de reprodução">
                  <span class="fac-speed-value-group">
                    <input class="fac-speed" type="number" min="0.25" max="2" step="0.05" inputmode="decimal" title="Velocidade de reprodução">
                    <span class="fac-speed-unit">x</span>
                  </span>
                </label>
                <button class="fac-speed-step fac-speed-up" type="button" title="Aumentar 0,5x" aria-label="Aumentar velocidade em 0,5x">+</button>
              </div>
            </section>

            <section class="fac-block">
              <div class="fac-row fac-row-label">
                <span>Volume</span>
                <span class="fac-volume-value"></span>
              </div>
              <input class="fac-volume" type="range" min="0" max="100" step="1" title="Volume de saída">
            </section>

            <section class="fac-block fac-normalization-block">
              <label class="fac-check-row" title="Normalizar o loudness percebido em tempo real usando FFmpeg loudnorm / EBU R128">
                <input class="fac-normalize" type="checkbox">
                <span>Normalização em tempo real</span>
              </label>

              <div class="fac-normalization-settings">
                <div class="fac-row fac-row-label">
                  <span>Loudness alvo</span>
                  <span class="fac-loudness-value"></span>
                </div>
                <input class="fac-loudness" type="range" min="-50" max="-20" step="1" title="Loudness integrado alvo em LUFS">
                <div class="fac-range-hint"><span>-50</span><span>-20 LUFS</span></div>

                <label class="fac-check-row fac-dual-mono-wrap" title="Compensa a medição de arquivos mono quando serão ouvidos em saída estéreo">
                  <input class="fac-dual-mono" type="checkbox">
                  <span>Tratar mono como dual-mono</span>
                </label>
              </div>
            </section>

            <section class="fac-block fac-deck-profile-block">
              <div class="fac-row fac-row-label fac-deck-title-row">
                <span>Perfil do deck</span>
                <span class="fac-deck-badge">Não analisado</span>
              </div>

              <div class="fac-deck-name" title=""></div>

              <label class="fac-check-row fac-deck-enable-wrap" title="Usa o ganho medido para cada arquivo do deck. O perfil tem prioridade sobre a normalização em tempo real.">
                <input class="fac-deck-enable" type="checkbox">
                <span>Usar perfil analisado</span>
              </label>

              <div class="fac-deck-actions">
                <button class="fac-action fac-analyze-deck" type="button">Analisar deck</button>
                <button class="fac-action fac-action-secondary fac-clear-deck" type="button">Limpar</button>
              </div>

              <div class="fac-deck-progress" hidden>
                <div class="fac-deck-progress-track">
                  <div class="fac-deck-progress-bar"></div>
                </div>
                <span class="fac-deck-progress-text"></span>
              </div>

              <div class="fac-deck-summary"></div>
            </section>

            <span class="fac-status">Player nativo do Anki</span>
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

      const loudness = this.root.querySelector(".fac-loudness");
      loudness.value = String(Math.round(clamp(Number(this.config.loudness_target ?? -24), -50, -20)));
      this.updateLoudnessValue(Number(loudness.value));

      const dualMono = this.root.querySelector(".fac-dual-mono");
      dualMono.checked = Boolean(this.config.dual_mono);
      this.updateNormalizationEnabledState();

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
        this.updateNormalizationEnabledState();
        pycmd(`ferreis_audio:set:normalize:${this.config.normalize ? 1 : 0}`);
      });

      loudness.addEventListener("input", () => {
        const value = clamp(Number(loudness.value), -50, -20);
        this.config.loudness_target = value;
        this.updateLoudnessValue(value);
        pycmd(`ferreis_audio:set:loudness_target:${value}`);
      });

      dualMono.addEventListener("change", (event) => {
        this.config.dual_mono = Boolean(event.target.checked);
        pycmd(`ferreis_audio:set:dual_mono:${this.config.dual_mono ? 1 : 0}`);
      });

      this.root.querySelector(".fac-deck-enable").addEventListener("change", (event) => {
        const enabled = Boolean(event.target.checked);
        if (!this.config.deck_profile) this.config.deck_profile = {};
        this.config.deck_profile.enabled = enabled;
        pycmd(`ferreis_audio:deck:enable:${enabled ? 1 : 0}`);
      });

      this.root.querySelector(".fac-analyze-deck").addEventListener("click", () => {
        this.updateDeckProfile({ ...(this.config.deck_profile || {}), analyzing: true, progress: 0, message: "Preparando análise..." });
        pycmd("ferreis_audio:deck:analyze");
      });

      this.root.querySelector(".fac-clear-deck").addEventListener("click", () => {
        pycmd("ferreis_audio:deck:clear");
      });

      this.updateDeckProfile(this.config.deck_profile || {});
      this.enableSidePanelDrag();
    },

    setStatus(text) {
      const status = this.root?.querySelector(".fac-status");
      if (status) {
        status.textContent = text || "Player nativo do Anki";
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

    updateLoudnessValue(value) {
      const output = this.root?.querySelector(".fac-loudness-value");
      if (output) output.textContent = `${Math.round(Number(value))} LUFS`;
    },

    updateNormalizationEnabledState() {
      const enabled = Boolean(this.config.normalize);
      const settings = this.root?.querySelector(".fac-normalization-settings");
      if (settings) settings.classList.toggle("fac-disabled", !enabled);
      for (const element of this.root?.querySelectorAll(".fac-normalization-settings input") || []) {
        element.disabled = !enabled;
      }
    },

    updateDeckProfile(state) {
      if (!this.root) return;
      this.config.deck_profile = { ...(this.config.deck_profile || {}), ...(state || {}) };
      const profile = this.config.deck_profile;

      const name = this.root.querySelector(".fac-deck-name");
      const badge = this.root.querySelector(".fac-deck-badge");
      const enable = this.root.querySelector(".fac-deck-enable");
      const analyze = this.root.querySelector(".fac-analyze-deck");
      const clear = this.root.querySelector(".fac-clear-deck");
      const summary = this.root.querySelector(".fac-deck-summary");
      const progressWrap = this.root.querySelector(".fac-deck-progress");
      const progressBar = this.root.querySelector(".fac-deck-progress-bar");
      const progressText = this.root.querySelector(".fac-deck-progress-text");

      if (name) {
        name.textContent = profile.deck_name || "Deck atual";
        name.title = name.textContent;
      }
      if (enable) {
        enable.checked = Boolean(profile.enabled);
        enable.disabled = !profile.exists || Boolean(profile.analyzing);
      }
      if (analyze) analyze.disabled = Boolean(profile.analyzing);
      if (clear) clear.disabled = !profile.exists || Boolean(profile.analyzing);

      if (badge) {
        badge.classList.remove("fac-badge-ok", "fac-badge-warn", "fac-badge-busy");
        if (profile.analyzing) {
          badge.textContent = "Analisando";
          badge.classList.add("fac-badge-busy");
        } else if (profile.exists && profile.stale) {
          badge.textContent = "Reanalisar";
          badge.classList.add("fac-badge-warn");
        } else if (profile.exists) {
          badge.textContent = "Pronto";
          badge.classList.add("fac-badge-ok");
        } else {
          badge.textContent = "Não analisado";
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
          const parts = [`${profile.file_count || 0} áudio(s)`];
          if (Number.isFinite(Number(profile.min_lufs)) && Number.isFinite(Number(profile.max_lufs))) {
            parts.push(`${Number(profile.min_lufs).toFixed(1)} a ${Number(profile.max_lufs).toFixed(1)} LUFS`);
          }
          if (profile.failed_count) parts.push(`${profile.failed_count} falha(s)`);
          if (profile.stale) parts.push("alvo mudou");
          summary.textContent = profile.message || parts.join(" · ");
          summary.className = "fac-deck-summary";
        } else {
          summary.textContent = profile.message || "Analise o deck para calcular um ganho específico para cada áudio.";
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
