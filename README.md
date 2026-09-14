# Balanced Audio Controller v0.9.0

Free and open-source audio controller for Anki Desktop. Adds playback speed, volume, real-time loudness normalization and per-deck audio analysis while keeping Anki's native MPV player.

Extensão gratuita e de código aberto para Anki Desktop. Adiciona controle de velocidade, volume, normalização de loudness em tempo real e análise por deck mantendo o player MPV nativo do Anki.

## English

### Features

- Playback speed from **0.25x to 2.0x**, default **1.0x**.
- `−` / `+` change speed by **0.5x**.
- Manual numeric speed input.
- Output volume from **0% to 100%**.
- Real-time FFmpeg `loudnorm` normalization through MPV.
- Target loudness from **-50 to -20 LUFS**, default **-24 LUFS**.
- True peak ceiling of **-1.5 dBTP** and LRA target of **7 LU**.
- Optional dual-mono compensation.
- Movable panel with saved position; double-click the title bar to reset it.
- Deck normalization profile: analyzes every audio file in the current deck, calculates an individual gain, stores it in `user_files/deck_profiles.json`, and applies it on playback without modifying the original media files.

### Language

Supported languages: English (`en`) and Brazilian Portuguese (`pt-BR`).

Default:

```json
"language": "auto"
```

`auto` detects the system locale. Portuguese locales use `pt-BR`; unsupported locales fall back to English.

To change it: **Tools → Add-ons → Balanced Audio Controller → Config/Configure**, then set `language` to `auto`, `en`, or `pt-BR`.

### Configuration

```json
{
  "language": "auto",
  "normalize": true,
  "loudness_target": -24,
  "dual_mono": false,
  "speed": 1.0,
  "volume": 1.0,
  "deck_profile_enabled": false
}
```

`normalize` enables real-time normalization. `loudness_target` selects the target LUFS. `dual_mono` compensates mono material intended for stereo playback. `speed` sets initial speed. `volume` uses a `0.0` to `1.0` scale. `deck_profile_enabled` enables the analyzed deck profile when compatible data exists.

### Deck analysis and FFmpeg

Click **Analyze deck** to measure integrated loudness and true peak for each audio file. The profile has priority over real-time normalization for analyzed files. Changing target LUFS or dual-mono marks the profile as outdated and it should be analyzed again.

Deck analysis requires an `ffmpeg` executable available on the system. Normal Anki playback continues to work if FFmpeg is unavailable.

### Build

```bash
python3 build.py
```

Output:

```text
dist/Balanced_Audio_Controller-v0.9.0.ankiaddon
```

`main` contains stable/publishable versions. `dev` contains development and testing changes.

---

## Português (Brasil)

### Funcionalidades

- Velocidade de **0,25x até 2,0x**, padrão **1,0x**.
- `−` / `+` alteram a velocidade em **0,5x**.
- Campo numérico para definir a velocidade manualmente.
- Volume de saída entre **0% e 100%**.
- Normalização em tempo real com FFmpeg `loudnorm` pelo MPV.
- Loudness alvo de **-50 até -20 LUFS**, padrão **-24 LUFS**.
- Limite de true peak em **-1,5 dBTP** e LRA alvo de **7 LU**.
- Compensação dual-mono opcional.
- Painel móvel com posição salva; clique duas vezes no título para restaurar a posição padrão.
- Perfil de normalização do deck: analisa todos os arquivos de áudio do deck atual, calcula um ganho individual, salva em `user_files/deck_profiles.json` e aplica durante a reprodução sem modificar os arquivos originais.

### Idioma

Idiomas suportados: English (`en`) e Português do Brasil (`pt-BR`).

Padrão:

```json
"language": "auto"
```

`auto` detecta o locale do sistema. Locales em português usam `pt-BR`; idiomas não suportados usam inglês como fallback.

Para alterar: **Ferramentas → Extensões/Add-ons → Balanced Audio Controller → Configuração/Config**, depois defina `language` como `auto`, `en` ou `pt-BR`.

### Configuração

```json
{
  "language": "auto",
  "normalize": true,
  "loudness_target": -24,
  "dual_mono": false,
  "speed": 1.0,
  "volume": 1.0,
  "deck_profile_enabled": false
}
```

`normalize` ativa a normalização em tempo real. `loudness_target` define o LUFS alvo. `dual_mono` compensa material mono destinado a saída estéreo. `speed` define a velocidade inicial. `volume` usa uma escala de `0.0` a `1.0`. `deck_profile_enabled` ativa o perfil analisado quando houver dados compatíveis.

### Análise do deck e FFmpeg

Clique em **Analisar deck** para medir loudness integrado e true peak de cada áudio. O perfil tem prioridade sobre a normalização em tempo real para arquivos analisados. Se o LUFS alvo ou dual-mono forem alterados, o perfil fica desatualizado e deve ser analisado novamente.

A análise do deck precisa encontrar um executável `ffmpeg`. A reprodução normal do Anki continua funcionando se o FFmpeg não estiver disponível.

### Build

```bash
python3 build.py
```

Saída:

```text
dist/Balanced_Audio_Controller-v0.9.0.ankiaddon
```

`main` contém versões estáveis/publicáveis. `dev` contém alterações em desenvolvimento e testes.

## License / Licença

MIT License.
