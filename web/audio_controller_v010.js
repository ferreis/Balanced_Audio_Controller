(() => {
  const MAX_AUDIO_BYTES = 64 * 1024 * 1024;
  const PANEL_MINIMIZED_KEY = "ferreisAudioSidePanelMinimizedV1";
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const t = (key, values = {}) => {
    const base = window.FerreisAnkiAudio;
    return base?.t ? base.t(key, values) : key;
  };

  const ext = window.BACV010 || {
    root: null,
    state: {},
    mounted: false,

    async boot() {
      for (let i = 0; i < 100; i++) {
        const root = document.getElementById("ferreis-audio-controller");
        const base = window.FerreisAnkiAudio;
        if (root && base && root.dataset.mounted === "1") {
          this.root = root;
          this.augment();
          return;
        }
        await sleep(50);
      }
    },

    augment() {
      if (this.mounted || !this.root) return;
      const block = this.root.querySelector(".fac-deck-profile-block");
      const actions = this.root.querySelector(".fac-deck-actions");
      const handle = this.root.querySelector(".fac-side-handle");
      if (!block || !actions || !handle) return;
      this.mounted = true;

      this.installMinimizeStyles();
      this.installMinimizeControl(handle);

      const engine = document.createElement("div");
      engine.className = "fac-analysis-engine";
      engine.innerHTML = `
        <div class="fac-row fac-row-label">
          <span>${t("analysis_method")}</span>
          <span class="fac-engine-status"></span>
        </div>
        <select class="fac-analysis-backend" aria-label="${t("analysis_method")}">
          <option value="auto">${t("analysis_auto")}</option>
          <option value="ffmpeg">${t("analysis_ffmpeg")}</option>
          <option value="webaudio">${t("analysis_webaudio")}</option>
        </select>
        <button class="fac-action fac-install-ffmpeg" type="button" hidden>${t("install_ffmpeg")}</button>
        <div class="fac-engine-note"></div>
      `;
      block.insertBefore(engine, actions);

      const oldAnalyze = this.root.querySelector(".fac-analyze-deck");
      if (oldAnalyze) {
        const fresh = oldAnalyze.cloneNode(true);
        oldAnalyze.replaceWith(fresh);
        fresh.addEventListener("click", () => {
          const base = window.FerreisAnkiAudio;
          base?.updateDeckProfile?.({ ...(base.config?.deck_profile || {}), analyzing: true, progress: 0, message: t("preparing_analysis") });
          pycmd("ferreis_audio:v010:analyze");
        });
      }

      const select = this.root.querySelector(".fac-analysis-backend");
      select.addEventListener("change", () => {
        this.state.analysis_backend = select.value;
        pycmd(`ferreis_audio:v010:backend:${select.value}`);
      });
      this.root.querySelector(".fac-install-ffmpeg").addEventListener("click", () => {
        pycmd("ferreis_audio:v010:ffmpeg:install");
      });

      const base = window.FerreisAnkiAudio;
      this.state = {
        ...(base?.config?.deck_profile || {}),
        analysis_backend: base?.config?.analysis_backend || base?.config?.deck_profile?.analysis_backend || "auto",
      };
      this.updateState(this.state);
      if (base?.updateDeckProfile && !base.__bacV010Patched) {
        const original = base.updateDeckProfile.bind(base);
        base.updateDeckProfile = (state) => {
          original(state);
          this.updateState(state || {});
        };
        base.__bacV010Patched = true;
      }
      pycmd("ferreis_audio:v010:state");
    },

    panelLabel(minimized) {
      const language = window.FerreisAnkiAudio?.config?.language || "en";
      if (language === "pt-BR") return minimized ? "Expandir painel" : "Minimizar painel";
      return minimized ? "Expand panel" : "Minimize panel";
    },

    readMinimizedState() {
      try {
        return localStorage.getItem(PANEL_MINIMIZED_KEY) === "1";
      } catch (_) {
        return false;
      }
    },

    installMinimizeStyles() {
      if (document.getElementById("fac-minimize-styles")) return;
      const style = document.createElement("style");
      style.id = "fac-minimize-styles";
      style.textContent = `
        #ferreis-audio-controller .fac-panel-toggle {
          flex: 0 0 24px;
          display: grid;
          place-items: center;
          width: 24px;
          height: 22px;
          margin: 0 0 0 auto;
          padding: 0;
          border-radius: 5px;
          font-size: 16px;
          line-height: 1;
        }
        #ferreis-audio-controller .fac-side-panel.fac-minimized {
          width: 152px;
        }
        #ferreis-audio-controller .fac-side-panel.fac-minimized .fac-side-body {
          display: none;
        }
        #ferreis-audio-controller .fac-side-panel.fac-minimized .fac-side-handle {
          border-bottom: 0;
        }
      `;
      document.head.appendChild(style);
    },

    installMinimizeControl(handle) {
      let button = handle.querySelector(".fac-panel-toggle");
      if (!button) {
        button = document.createElement("button");
        button.className = "fac-panel-toggle";
        button.type = "button";
        handle.appendChild(button);
      }

      button.addEventListener("pointerdown", (event) => event.stopPropagation());
      button.addEventListener("dblclick", (event) => event.stopPropagation());
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        const panel = this.root?.querySelector(".fac-side-panel");
        if (!panel) return;
        this.setMinimized(!panel.classList.contains("fac-minimized"));
      });

      this.setMinimized(this.readMinimizedState(), false);
    },

    setMinimized(minimized, persist = true) {
      const panel = this.root?.querySelector(".fac-side-panel");
      const button = this.root?.querySelector(".fac-panel-toggle");
      if (!panel || !button) return;

      const collapsed = Boolean(minimized);
      panel.classList.toggle("fac-minimized", collapsed);
      button.textContent = collapsed ? "+" : "−";
      button.title = this.panelLabel(collapsed);
      button.setAttribute("aria-label", button.title);
      button.setAttribute("aria-expanded", collapsed ? "false" : "true");

      if (persist) {
        try {
          localStorage.setItem(PANEL_MINIMIZED_KEY, collapsed ? "1" : "0");
        } catch (_) {}
      }

      if (!collapsed) {
        requestAnimationFrame(() => window.FerreisAnkiAudio?.restoreSidePanelPosition?.());
      }
    },

    resolvedBackend() {
      const chosen = this.state.analysis_backend || "auto";
      if (chosen === "ffmpeg" || chosen === "webaudio") return chosen;
      return this.state.ffmpeg?.available ? "ffmpeg" : "webaudio";
    },

    updateState(state) {
      if (!this.root) return;
      this.state = { ...this.state, ...(state || {}) };
      const select = this.root.querySelector(".fac-analysis-backend");
      const status = this.root.querySelector(".fac-engine-status");
      const install = this.root.querySelector(".fac-install-ffmpeg");
      const note = this.root.querySelector(".fac-engine-note");
      if (!select || !status || !install || !note) return;

      select.value = this.state.analysis_backend || "auto";
      select.disabled = Boolean(this.state.analyzing || this.state.ffmpeg?.installing);
      const ff = this.state.ffmpeg || {};
      const resolved = this.resolvedBackend();
      if (ff.installing) {
        status.textContent = t("ffmpeg_installing_ui");
      } else if (resolved === "ffmpeg" && ff.available) {
        status.textContent = t("ffmpeg_ready");
      } else if (resolved === "ffmpeg") {
        status.textContent = t("ffmpeg_missing");
      } else {
        status.textContent = t("analysis_webaudio_short");
      }
      install.hidden = Boolean(ff.available) || !Boolean(ff.installer_available);
      install.disabled = Boolean(ff.installing || this.state.analyzing);
      install.textContent = ff.installing ? t("ffmpeg_installing_ui") : t("install_ffmpeg");
      note.textContent = resolved === "webaudio" ? t("webaudio_hint") : t("ffmpeg_installer_hint");
    },

    mediaUrl(filename) {
      const raw = String(filename || "").replace(/\\/g, "/");
      const parts = raw.split("/");
      if (!raw || parts.some((part) => !part || part === "." || part === "..")) return null;
      return `./${parts.map((part) => encodeURIComponent(part)).join("/")}`;
    },

    measureAudioBuffer(audioBuffer, dualMono) {
      const channels = Number(audioBuffer.numberOfChannels || 0);
      const length = Number(audioBuffer.length || 0);
      const sampleRate = Number(audioBuffer.sampleRate || 0);
      if (!channels || !length || !sampleRate) throw new Error("invalid audio buffer");

      const block = Math.max(1, Math.round(sampleRate * 0.4));
      const hop = Math.max(1, Math.round(sampleRate * 0.1));
      const maxFrames = 1_200_000;
      const stride = Math.max(1, Math.ceil(length / maxFrames));
      const energies = [];
      let peak = 0;

      for (let start = 0; start < length; start += hop) {
        const end = Math.min(length, start + block);
        let sum = 0;
        let count = 0;
        for (let c = 0; c < channels; c++) {
          const data = audioBuffer.getChannelData(c);
          for (let i = start; i < end; i += stride) {
            const sample = Number(data[i] || 0);
            sum += sample * sample;
            peak = Math.max(peak, Math.abs(sample));
            count++;
          }
        }
        if (count) energies.push(sum / count);
        if (end >= length) break;
      }
      if (!energies.length) throw new Error("empty measurement");

      const toDb = (energy) => -0.691 + 10 * Math.log10(Math.max(energy, 1e-12));
      const absolute = energies.filter((energy) => toDb(energy) > -70);
      const base = absolute.length ? absolute : energies;
      const preliminaryEnergy = base.reduce((a, b) => a + b, 0) / base.length;
      const relativeGate = toDb(preliminaryEnergy) - 10;
      const gated = base.filter((energy) => toDb(energy) > relativeGate);
      const finalEnergy = (gated.length ? gated : base).reduce((a, b) => a + b, 0) / (gated.length ? gated.length : base.length);
      let inputI = toDb(finalEnergy);
      if (dualMono && channels === 1) inputI += 10 * Math.log10(2);
      const inputTp = 20 * Math.log10(Math.max(peak, 1e-9));
      return { input_i: inputI, input_tp: inputTp };
    },

    async startWebAudioAnalysis(payload) {
      const session = String(payload?.session || "");
      const files = Array.isArray(payload?.files) ? payload.files : [];
      if (!session || !files.length) return;
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) {
        pycmd(`ferreis_audio:v010:webaudio:done:${session}`);
        return;
      }
      const context = new AudioCtx();
      try {
        for (const filename of files) {
          let result = { filename, ok: false };
          try {
            const url = this.mediaUrl(filename);
            if (!url) throw new Error("unsafe media path");
            const response = await fetch(url, { credentials: "same-origin", redirect: "error", cache: "force-cache" });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const size = Number(response.headers.get("content-length") || 0);
            if (size > MAX_AUDIO_BYTES) throw new Error("audio too large");
            const bytes = await response.arrayBuffer();
            if (bytes.byteLength > MAX_AUDIO_BYTES) throw new Error("audio too large");
            const audio = await context.decodeAudioData(bytes.slice(0));
            result = { filename, ok: true, ...this.measureAudioBuffer(audio, Boolean(payload.dual_mono)) };
          } catch (error) {
            result.error = String(error?.message || error).slice(0, 200);
          }
          pycmd(`ferreis_audio:v010:webaudio:item:${session}:${encodeURIComponent(JSON.stringify(result))}`);
          await sleep(0);
        }
      } finally {
        try { await context.close(); } catch (_) {}
        pycmd(`ferreis_audio:v010:webaudio:done:${session}`);
      }
    },
  };

  window.BACV010 = ext;
  ext.boot();
})();
