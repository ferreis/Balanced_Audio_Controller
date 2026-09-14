# Balanced Audio Controller v0.10.0-dev

Free and open-source audio controller for Anki Desktop. It keeps Anki's native MPV playback while adding speed, volume, loudness normalization and persistent per-deck audio profiles.

Extensão gratuita e de código aberto para Anki Desktop. Mantém a reprodução nativa pelo MPV e adiciona velocidade, volume, normalização de loudness e perfis persistentes por deck.

---

## English

### Languages

Supported languages:

- English (`en`)
- Brazilian Portuguese (`pt-BR`)

Default configuration:

```json
"language": "auto"
```

`auto` detects the operating-system locale. Portuguese locales use `pt-BR`; unsupported locales fall back to English.

Change it in **Tools → Add-ons → Balanced Audio Controller → Config/Configure** by setting `language` to `auto`, `en`, or `pt-BR`.

### Playback controls

- Speed: **0.25x to 2.0x**, default **1.0x**.
- `−` and `+` change speed by **0.5x**.
- Manual numeric speed input is supported.
- Volume: **0% to 100%**.
- The original Anki play/replay buttons remain native and are not replaced.
- The floating panel is draggable; double-click its title bar to reset its position.

### Real-time normalization

When enabled, the add-on applies FFmpeg `loudnorm` through Anki's MPV player during playback.

- Target loudness: **-50 to -20 LUFS**.
- Default: **-24 LUFS**.
- True peak ceiling: **-1.5 dBTP**.
- LRA target: **7 LU**.
- Optional dual-mono compensation for mono recordings played through stereo output.

This mode does not require a standalone `ffmpeg` executable because it uses the filters available through Anki/MPV.

### Deck profile analysis

The deck profile analyzes each audio file and stores only the calculated gain. Original deck media is never rewritten or re-encoded.

The profile is stored in:

```text
user_files/deck_profiles.json
```

It remains available after Anki or the computer is restarted.

#### Analysis methods

The add-on now supports three modes through `analysis_backend`:

```text
auto
ffmpeg
webaudio
```

**`auto` (recommended)**

- Uses standalone FFmpeg when it is available.
- Automatically falls back to the built-in WebAudio analyzer when FFmpeg is not installed.
- Deck analysis therefore works without requiring the user to install FFmpeg.

**`ffmpeg`**

- Uses FFmpeg `loudnorm` for the most accurate full-file analysis.
- If FFmpeg is missing, the panel can offer an **Install FFmpeg** button when a supported system package manager is available.
- The add-on never silently installs software; installation only starts after an explicit click.

**`webaudio` / Built-in (no FFmpeg)**

- Does not require an external FFmpeg executable.
- Uses Qt WebEngine's WebAudio decoder to decode common deck audio formats such as MP3, OGG and WAV.
- Uses 400 ms blocks with 75% overlap, absolute and relative gating, plus a conservative peak safety margin.
- The measurement is intentionally marked as **approximate** because WebAudio does not expose FFmpeg's full EBU R128/true-peak implementation.
- It is intended to provide useful deck-wide balancing when the user does not want to install FFmpeg.
- Files larger than 8 MB are skipped by the built-in analyzer to avoid excessive memory transfer through the reviewer webview.

### Optional FFmpeg installation

When FFmpeg is missing and automatic installation is supported, the panel displays **Install FFmpeg**.

Supported installers are detected locally:

- Windows: `winget` (`Gyan.FFmpeg`).
- macOS: Homebrew.
- Linux: Homebrew, or `APT`, `DNF`, `Pacman`, or `Zypper` through `pkexec`.

Security rules used by the installer:

- installation only starts after an explicit user click;
- commands are fixed in the source code and never come from card content or add-on configuration;
- external processes use argument arrays with `shell=False`;
- the installer has a timeout;
- failure never blocks normal Anki playback;
- the built-in analyzer remains available if installation is declined or fails.

Some sandboxed Anki packages, including certain Flatpak setups, may not expose a host package manager. In that case automatic installation is unavailable and the built-in analyzer is used instead.

### Analyze deck workflow

1. Open a card from the deck.
2. Choose an analysis method, or leave **Automatic** selected.
3. Click **Analyze deck**.
4. The add-on finds all audio files used by that deck.
5. Each file is measured with FFmpeg or the built-in analyzer.
6. A gain is calculated while respecting the configured target and peak safety.
7. The profile is saved and **Use analyzed profile** is enabled.
8. Study normally; the gain is applied only during playback.

Reanalyze after replacing/adding audio, changing the target LUFS, or changing dual-mono behavior.

### Configuration

```json
{
  "language": "auto",
  "normalize": true,
  "loudness_target": -24,
  "dual_mono": false,
  "speed": 1.0,
  "volume": 1.0,
  "deck_profile_enabled": false,
  "analysis_backend": "auto"
}
```

### Build

```bash
python3 build.py
```

The package is created in `dist/` and contains only runtime add-on files. Tests, local user profiles and caches are excluded.

### Playwright tests

The reviewer UI and built-in loudness measurement have automated Playwright tests:

```bash
python tests/test_audio_controller_playwright.py -v
```

If Chromium is not on PATH, set `BAC_CHROMIUM_EXECUTABLE` or install a Playwright Chromium browser.

---

## Português (Brasil)

### Idiomas

Idiomas suportados:

- English (`en`)
- Português do Brasil (`pt-BR`)

Configuração padrão:

```json
"language": "auto"
```

`auto` detecta o locale do sistema operacional. Locales em português usam `pt-BR`; idiomas ainda não suportados usam inglês como fallback.

Para alterar, abra **Ferramentas → Extensões/Add-ons → Balanced Audio Controller → Configuração/Config** e defina `language` como `auto`, `en` ou `pt-BR`.

### Controles de reprodução

- Velocidade: **0,25x até 2,0x**, padrão **1,0x**.
- `−` e `+` alteram a velocidade em **0,5x**.
- É possível informar a velocidade manualmente.
- Volume: **0% até 100%**.
- Os botões originais de play/replay do Anki permanecem nativos.
- O painel é arrastável; dois cliques na barra de título restauram a posição padrão.

### Normalização em tempo real

Quando ativada, a extensão aplica o filtro FFmpeg `loudnorm` pelo player MPV do Anki durante a reprodução.

- Loudness alvo: **-50 até -20 LUFS**.
- Padrão: **-24 LUFS**.
- Limite de true peak: **-1,5 dBTP**.
- LRA alvo: **7 LU**.
- Compensação dual-mono opcional para gravações mono reproduzidas em saída estéreo.

Esse modo não exige o executável externo `ffmpeg`, pois utiliza os filtros disponíveis pelo próprio Anki/MPV.

### Perfil de análise do deck

O perfil do deck analisa cada arquivo de áudio e salva somente o ganho calculado. Os arquivos originais do deck nunca são sobrescritos ou recodificados.

O perfil fica em:

```text
user_files/deck_profiles.json
```

Ele continua salvo depois de fechar o Anki ou reiniciar o computador.

#### Métodos de análise

A extensão agora possui três modos em `analysis_backend`:

```text
auto
ffmpeg
webaudio
```

**`auto` (recomendado)**

- Usa o FFmpeg externo quando ele está disponível.
- Caso o FFmpeg não esteja instalado, usa automaticamente o analisador WebAudio interno.
- Portanto, a função **Analisar deck** funciona mesmo sem instalar FFmpeg.

**`ffmpeg`**

- Usa `loudnorm` do FFmpeg para a análise completa mais precisa.
- Se o FFmpeg não existir, o painel pode mostrar **Instalar FFmpeg** quando houver um gerenciador de pacotes compatível.
- A extensão nunca instala programas silenciosamente: a instalação só começa após um clique explícito do usuário.

**`webaudio` / Interno (sem FFmpeg)**

- Não exige um executável FFmpeg externo.
- Usa o decodificador WebAudio do Qt WebEngine para formatos comuns do Anki, como MP3, OGG e WAV.
- Usa blocos de 400 ms com 75% de sobreposição, gate absoluto/relativo e uma margem conservadora de segurança para pico.
- A medição é identificada como **aproximada**, pois o WebAudio não oferece a implementação completa de EBU R128/true peak do FFmpeg.
- É indicado para equilibrar o deck quando o usuário não deseja instalar FFmpeg.
- Arquivos acima de 8 MB são ignorados pelo analisador interno para evitar transferência excessiva de memória pela webview do revisor.

### Instalação opcional do FFmpeg

Quando o FFmpeg não está disponível e o sistema possui um instalador compatível, o painel mostra **Instalar FFmpeg**.

Instaladores detectados:

- Windows: `winget` (`Gyan.FFmpeg`).
- macOS: Homebrew.
- Linux: Homebrew ou `APT`, `DNF`, `Pacman` e `Zypper` através de `pkexec`.

Regras de segurança da instalação:

- só inicia após clique explícito do usuário;
- os comandos são fixos no código e nunca vêm de cartões ou configuração do add-on;
- processos externos usam lista de argumentos e `shell=False`;
- existe timeout para o instalador;
- uma falha nunca impede a reprodução normal do Anki;
- o analisador interno continua disponível se o usuário recusar ou se a instalação falhar.

Algumas instalações em sandbox, como determinados pacotes Flatpak, podem não expor o gerenciador de pacotes do sistema. Nesses casos a instalação automática não é oferecida e o analisador interno continua funcionando.

### Fluxo de Analisar deck

1. Abra um cartão do deck.
2. Escolha o método de análise ou mantenha **Automático**.
3. Clique em **Analisar deck**.
4. A extensão localiza os áudios utilizados pelo deck.
5. Cada arquivo é medido pelo FFmpeg ou pelo mecanismo interno.
6. O ganho é calculado respeitando o alvo e a margem de pico.
7. O perfil é salvo e **Usar perfil analisado** é ativado.
8. Estude normalmente; o ganho é aplicado somente durante a reprodução.

Reanalise depois de adicionar/substituir áudios, alterar o LUFS alvo ou alterar a opção dual-mono.

### Configuração

```json
{
  "language": "auto",
  "normalize": true,
  "loudness_target": -24,
  "dual_mono": false,
  "speed": 1.0,
  "volume": 1.0,
  "deck_profile_enabled": false,
  "analysis_backend": "auto"
}
```

### Build

```bash
python3 build.py
```

O pacote é criado em `dist/` contendo somente os arquivos necessários em runtime. Testes, perfis locais e caches não são incluídos.

### Testes Playwright

A interface do revisor e a medição interna possuem testes automatizados em Playwright:

```bash
python tests/test_audio_controller_playwright.py -v
```

Se o Chromium não estiver no PATH, defina `BAC_CHROMIUM_EXECUTABLE` ou instale um navegador Chromium pelo Playwright.

## License / Licença

MIT License.
