# Balanced Audio Controller v0.10.0

Free and open-source audio controller for Anki Desktop. It keeps Anki's native MPV playback while adding speed, volume, loudness normalization, persistent per-deck audio profiles, optional FFmpeg installation, a built-in analyzer that works without FFmpeg, and a minimizable floating panel.

Extensão gratuita e de código aberto para Anki Desktop. Mantém a reprodução nativa pelo MPV e adiciona velocidade, volume, normalização de loudness, perfis persistentes por deck, instalação opcional do FFmpeg, analisador interno que funciona sem FFmpeg e painel flutuante minimizável.

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
- The **−** button in the panel title minimizes the add-on to its title bar. When minimized, the button changes to **+** so the panel can be expanded again.
- The minimized/expanded state is stored locally and restored on later cards.

### Real-time normalization

When enabled, the add-on applies `loudnorm` through Anki's MPV player during playback.

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

The add-on supports three modes through `analysis_backend`:

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
- If FFmpeg is missing and the current platform is supported, the panel offers **Install FFmpeg**.
- The add-on never silently installs software; installation starts only after an explicit click.

**`webaudio` / Built-in (no FFmpeg)**

- Does not require an external FFmpeg executable.
- Uses Qt WebEngine's WebAudio decoder for common audio formats supported by the Anki webview.
- Uses 400 ms analysis blocks, gated RMS measurement and a peak safety calculation.
- The result is intentionally marked as **approximate** because WebAudio does not expose FFmpeg's full EBU R128/true-peak implementation.
- It is intended to provide useful deck-wide balancing when the user does not want to install FFmpeg.
- Files larger than **64 MB** are rejected by the built-in analyzer to avoid excessive memory use.

### Optional FFmpeg installation

When FFmpeg is missing and the platform is supported, the panel displays **Install FFmpeg**.

The add-on downloads a pinned `imageio-ffmpeg` platform package and extracts only its FFmpeg executable into the add-on's persistent `user_files` directory:

```text
user_files/tools/ffmpeg/
```

This does **not** require administrator/root privileges and does not replace the system FFmpeg.

Security rules used by the installer:

- installation only starts after an explicit user click;
- download URLs are fixed in the source code and use HTTPS;
- the expected platform, file size and SHA-256 are pinned;
- redirects to untrusted hosts are rejected;
- only the expected FFmpeg binary is extracted;
- the extracted executable is validated before being used;
- external processes use argument arrays with `shell=False`;
- failure never blocks normal Anki playback;
- the built-in analyzer remains available if installation is declined or fails.

Supported managed-download targets currently include Windows x86-64, Linux x86-64, Linux ARM64, macOS Intel and macOS Apple Silicon.

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

### Tests

Python tests:

```bash
python -m unittest tests.test_analysis_engine -v
```

Playwright reviewer UI tests:

```bash
python tests/test_audio_controller_playwright.py -v
```

The Playwright suite covers analysis controls, FFmpeg state, the built-in loudness measurement, path traversal rejection and panel minimize/expand behavior.

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
- O botão **−** na barra de título minimiza o add-on deixando apenas a barra superior. Minimizado, o botão muda para **+** para expandir novamente.
- O estado minimizado/expandido é salvo localmente e restaurado nos próximos cartões.

### Normalização em tempo real

Quando ativada, a extensão aplica `loudnorm` pelo player MPV do Anki durante a reprodução.

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

A extensão possui três modos em `analysis_backend`:

```text
auto
ffmpeg
webaudio
```

**`auto` (recomendado)**

- Usa o FFmpeg externo quando ele está disponível.
- Caso o FFmpeg não esteja instalado, usa automaticamente o analisador WebAudio interno.
- Portanto, **Analisar deck** funciona mesmo sem instalar FFmpeg.

**`ffmpeg`**

- Usa `loudnorm` do FFmpeg para a análise completa mais precisa.
- Se o FFmpeg não existir e a plataforma for suportada, o painel oferece **Instalar FFmpeg**.
- A extensão nunca instala programas silenciosamente: a instalação só começa após um clique explícito do usuário.

**`webaudio` / Interno (sem FFmpeg)**

- Não exige um executável FFmpeg externo.
- Usa o decodificador WebAudio do Qt WebEngine para os formatos aceitos pela webview do Anki.
- Usa blocos de 400 ms, medição RMS com gate e cálculo de segurança de pico.
- A medição é identificada como **aproximada**, pois o WebAudio não oferece a implementação completa de EBU R128/true peak do FFmpeg.
- É indicado para equilibrar o deck quando o usuário não deseja instalar FFmpeg.
- Arquivos acima de **64 MB** são rejeitados pelo analisador interno para evitar uso excessivo de memória.

### Instalação opcional do FFmpeg

Quando o FFmpeg não está disponível e a plataforma é suportada, o painel mostra **Instalar FFmpeg**.

A extensão baixa um pacote de plataforma fixado do `imageio-ffmpeg` e extrai somente o executável FFmpeg para a pasta persistente do add-on:

```text
user_files/tools/ffmpeg/
```

Isso **não exige administrador/root** e não substitui o FFmpeg instalado no sistema.

Regras de segurança da instalação:

- só inicia após clique explícito do usuário;
- URLs de download são fixas no código e usam HTTPS;
- plataforma, tamanho esperado e SHA-256 são fixados;
- redirecionamentos para hosts não confiáveis são rejeitados;
- somente o binário esperado do FFmpeg é extraído;
- o executável extraído é validado antes de ser usado;
- processos externos usam lista de argumentos e `shell=False`;
- uma falha nunca impede a reprodução normal do Anki;
- o analisador interno continua disponível se o usuário recusar ou se a instalação falhar.

Os downloads gerenciados atualmente suportam Windows x86-64, Linux x86-64, Linux ARM64, macOS Intel e macOS Apple Silicon.

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

### Testes

Testes Python:

```bash
python -m unittest tests.test_analysis_engine -v
```

Testes Playwright da interface do revisor:

```bash
python tests/test_audio_controller_playwright.py -v
```

A suíte Playwright valida controles de análise, estado do FFmpeg, medição interna de loudness, rejeição de path traversal e o comportamento de minimizar/expandir o painel.

## License / Licença

MIT License.

## Compact reviewer panel / Painel compacto no revisor

The reviewer panel intentionally keeps only the controls used while studying: speed, volume, real-time normalization, deck-profile status and **Analyze deck**. Advanced options and maintenance actions are available under **Tools → Balanced Audio Controller → Settings**.

O painel do revisor mantém somente os controles usados durante o estudo: velocidade, volume, normalização em tempo real, status do perfil e **Analisar deck**. As opções avançadas e ações de manutenção ficam em **Ferramentas → Balanced Audio Controller → Configurações**.

## Materialized normalized audio / Áudio normalizado materializado

After a deck has been analyzed, **Create normalized copies / Criar cópias normalizadas** can render a second, already-normalized audio file for each analyzed source. This operation requires FFmpeg because it writes real audio files; the built-in WebAudio analyzer remains available for analysis only.

The original media is never overwritten. Generated files use a deterministic `bac_norm_...` name and are imported through Anki's media manager. The add-on creates a dedicated **BAC Áudio Normalizado** note field (or a numbered alternative if that name is already used by unrelated content), writes native `[sound:...]` references into it, and can automatically add that field to the same template side (front or back) where the original audio field is used. A separate **Create audio field + update card HTML** action prepares the field/template even before physical audio copies are generated.

Depois que o deck for analisado, **Criar cópias normalizadas** pode gerar um segundo arquivo de áudio já normalizado para cada áudio analisado. Essa operação exige FFmpeg porque grava arquivos de áudio reais; o analisador WebAudio interno continua disponível para análise sem FFmpeg.

A mídia original nunca é sobrescrita. Os arquivos gerados usam nomes determinísticos `bac_norm_...` e são importados pelo gerenciador de mídia do Anki. O add-on cria um campo dedicado **BAC Áudio Normalizado** na nota (ou uma alternativa numerada caso esse nome já contenha dados não relacionados), grava referências nativas `[sound:...]` nele e pode inserir automaticamente esse campo na mesma face do template (frente ou verso) em que o áudio original é usado. A ação separada **Criar campo de áudio + atualizar HTML** prepara o campo/template mesmo antes de gerar as cópias físicas.
