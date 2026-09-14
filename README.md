# Balanced Audio Controller v0.9.0-dev

Free and open-source audio controller for Anki Desktop.  
Control playback speed and volume, normalize loudness in real time, and analyze an entire deck to keep its audio files at a more consistent perceived loudness.

Extensão gratuita e de código aberto para Anki Desktop.  
Controle velocidade e volume, normalize o loudness em tempo real e analise um deck inteiro para deixar seus arquivos de áudio com uma intensidade percebida mais consistente.

<img width="233" height="349" alt="Balanced Audio Controller" src="https://github.com/user-attachments/assets/77ca8035-09e4-4e7c-bac7-593ddb79139b" />

- [English](#english)
- [Português (Brasil)](#português-brasil)

---

# English

## Features

Balanced Audio Controller keeps Anki's native MPV audio player and adds a movable control panel to the review screen.

### Playback speed

- Range: **0.25x to 2.0x**.
- Default: **1.0x**.
- The `−` and `+` buttons change speed by **0.5x**.
- You can type a custom value directly into the numeric field.
- The add-on changes MPV playback speed without replacing Anki's original play buttons.

### Volume

- Output volume from **0% to 100%**.
- Applied directly to Anki's native MPV player.

### Real-time loudness normalization

When **Real-time normalization** is enabled, the add-on uses FFmpeg's `loudnorm` filter through MPV.

The goal is to reduce large perceived-volume differences between recordings while they are being played.

Configuration:

- **Target loudness:** `-50` to `-20 LUFS`.
- Default target: **-24 LUFS**.
- True peak limit: **-1.5 dBTP**.
- Loudness Range target: **7 LU**.

Values closer to `-20 LUFS` sound louder. Values closer to `-50 LUFS` sound quieter.

### Dual-mono

The **Treat mono as dual-mono** option compensates EBU R128 loudness measurement for mono recordings intended to be heard through stereo output.

This can be useful for language-learning decks and other decks containing mono voice recordings.

### Deck normalization profile

Real-time normalization works while each file is playing. Very short recordings, however, may not give a dynamic filter enough time to measure them as consistently as a full offline analysis.

The **Deck profile** feature solves this by analyzing the deck before playback.

Click **Analyze deck** and the add-on will:

1. Find the audio files used by cards in the current deck.
2. Measure integrated loudness and true peak for each file with FFmpeg `loudnorm`.
3. Calculate an individual gain for every successfully analyzed file.
4. Limit positive gain so that the calculated result respects the `-1.5 dBTP` true-peak ceiling.
5. Save the analysis to `user_files/deck_profiles.json`.
6. Apply the corresponding gain automatically when that file is played.

The original media files are **not modified or re-encoded**.

If **Use analyzed profile** is enabled, the deck profile takes priority for analyzed files. Real-time normalization remains available as a fallback for files that do not have a compatible profile entry.

If you change the target LUFS value or the dual-mono option after analyzing a deck, the profile is marked as outdated and should be analyzed again.

Use **Clear** to remove the saved profile for the current deck.

### Movable panel

- Drag the `Audio` title bar to reposition the panel.
- The position is remembered locally.
- Double-click the title bar to restore the default position.

## Language

The add-on supports:

- **English** (`en`)
- **Português (Brasil)** (`pt-BR`)

The default configuration is:

```json
"language": "auto"
```

In `auto` mode, the add-on detects the computer/system locale:

- Portuguese system locales use **pt-BR**.
- Any unsupported locale falls back to **English**.

You can force a language manually.

### How to change the language

In Anki Desktop:

1. Open **Tools → Add-ons**.
2. Select **Balanced Audio Controller**.
3. Open **Config / Configure**.
4. Change `language` to one of:

```text
auto
en
pt-BR
```

5. Save the configuration.
6. Reopen the reviewer, or move to a newly rendered card, for the interface to use the new language.

## Configuration reference

The main settings are:

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

### `language`

Interface language.

- `auto`: detect system locale.
- `en`: force English.
- `pt-BR`: force Brazilian Portuguese.

### `normalize`

Enables or disables real-time loudness normalization.

### `loudness_target`

Integrated loudness target in LUFS. Accepted range: `-50` to `-20`.

Default: `-24`.

### `dual_mono`

Enables dual-mono compensation for loudness measurement.

### `speed`

Initial playback speed. Accepted range: `0.25` to `2.0`.

Default: `1.0`.

### `volume`

Initial MPV output volume represented from `0.0` to `1.0`.

- `0.0` = 0%
- `0.5` = 50%
- `1.0` = 100%

### `deck_profile_enabled`

Enables use of the analyzed deck profile when a compatible profile exists.

## FFmpeg requirement

Normal Anki playback and the MPV real-time controls do not require you to manually run FFmpeg.

The **Analyze deck** feature needs access to an `ffmpeg` executable so it can perform the offline measurements. The add-on searches the system PATH and common locations near the Anki runtime.

If FFmpeg cannot be found, normal playback continues to work, but deck analysis cannot start.

## Compatibility

Currently tested primarily with:

- Anki Desktop 26.08.1
- Linux

Other desktop systems may work, but should be tested before being listed as officially supported.

Add-ons that also change MPV speed, volume, or audio filters may conflict with Balanced Audio Controller.

## Build

An `.ankiaddon` file is a ZIP archive using the `.ankiaddon` extension. The add-on files must be placed at the root of the archive.

Build the package with:

```bash
python3 build.py
```

The version is read from `manifest.json`. The generated file is written to `dist/`, for example:

```text
dist/Balanced_Audio_Controller-v0.9.0-dev.ankiaddon
```

The build includes:

- `__init__.py`
- `i18n.py`
- `config.json`
- `config.schema.json`
- `manifest.json`
- `README.md`
- `LICENSE`
- `web/`

Runtime/user data such as `user_files/` is not packaged.

## Development branches

- `main`: stable/publishable versions.
- `dev`: development and testing before merging into `main`.

## License

MIT License.

---

# Português (Brasil)

## Funcionalidades

O Balanced Audio Controller mantém o player de áudio MPV nativo do Anki e adiciona um painel móvel à tela de revisão.

### Velocidade de reprodução

- Intervalo: **0,25x até 2,0x**.
- Padrão: **1,0x**.
- Os botões `−` e `+` alteram a velocidade em **0,5x**.
- Também é possível digitar manualmente um valor no campo numérico.
- A extensão altera a velocidade do MPV sem substituir os botões de reprodução originais do Anki.

### Volume

- Volume de saída entre **0% e 100%**.
- Aplicado diretamente ao player MPV nativo do Anki.

### Normalização de loudness em tempo real

Quando **Normalização em tempo real** está ativada, a extensão usa o filtro `loudnorm` do FFmpeg por meio do MPV.

O objetivo é reduzir grandes diferenças de volume percebido entre as gravações durante a reprodução.

Configuração:

- **Loudness alvo:** `-50` até `-20 LUFS`.
- Alvo padrão: **-24 LUFS**.
- Limite de true peak: **-1,5 dBTP**.
- Loudness Range alvo: **7 LU**.

Valores mais próximos de `-20 LUFS` soam mais altos. Valores mais próximos de `-50 LUFS` soam mais baixos.

### Dual-mono

A opção **Tratar mono como dual-mono** compensa a medição EBU R128 para gravações mono que serão ouvidas em uma saída estéreo.

Isso pode ser útil em decks de idiomas e outros decks com gravações de voz mono.

### Perfil de normalização do deck

A normalização em tempo real trabalha enquanto cada arquivo está sendo reproduzido. Porém, gravações muito curtas podem não dar tempo suficiente para um filtro dinâmico realizar uma medição tão consistente quanto uma análise completa feita antes da reprodução.

A função **Perfil do deck** resolve isso analisando o deck antecipadamente.

Clique em **Analisar deck** e a extensão irá:

1. Localizar os arquivos de áudio utilizados pelos cartões do deck atual.
2. Medir o loudness integrado e o true peak de cada arquivo com FFmpeg `loudnorm`.
3. Calcular um ganho individual para cada arquivo analisado com sucesso.
4. Limitar ganho positivo para que o resultado calculado respeite o teto de true peak de `-1,5 dBTP`.
5. Salvar a análise em `user_files/deck_profiles.json`.
6. Aplicar automaticamente o ganho correspondente quando aquele arquivo for reproduzido.

Os arquivos de mídia originais **não são modificados nem recodificados**.

Se **Usar perfil analisado** estiver ativado, o perfil do deck terá prioridade para os arquivos analisados. A normalização em tempo real continua disponível como fallback para arquivos sem uma entrada compatível no perfil.

Se você alterar o LUFS alvo ou a opção dual-mono depois de analisar um deck, o perfil será marcado como desatualizado e deverá ser analisado novamente.

Use **Limpar** para remover o perfil salvo do deck atual.

### Painel móvel

- Arraste a barra de título `Áudio` para mover o painel.
- A posição é salva localmente.
- Clique duas vezes na barra de título para restaurar a posição padrão.

## Idioma

A extensão possui suporte para:

- **English** (`en`)
- **Português (Brasil)** (`pt-BR`)

A configuração padrão é:

```json
"language": "auto"
```

No modo `auto`, a extensão detecta o locale do computador/sistema:

- Sistemas configurados em português usam **pt-BR**.
- Qualquer idioma ainda não suportado usa **English** como fallback.

Também é possível forçar manualmente um idioma.

### Como alterar o idioma

No Anki Desktop:

1. Abra **Ferramentas → Extensões/Add-ons**.
2. Selecione **Balanced Audio Controller**.
3. Abra **Configuração / Config**.
4. Altere `language` para uma das opções:

```text
auto
en
pt-BR
```

5. Salve a configuração.
6. Reabra a tela de revisão ou avance para um cartão renderizado novamente para que a interface use o novo idioma.

## Referência das configurações

As principais configurações são:

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

### `language`

Idioma da interface.

- `auto`: detectar o locale do sistema.
- `en`: forçar inglês.
- `pt-BR`: forçar português do Brasil.

### `normalize`

Ativa ou desativa a normalização de loudness em tempo real.

### `loudness_target`

Loudness integrado alvo em LUFS. Intervalo aceito: `-50` até `-20`.

Padrão: `-24`.

### `dual_mono`

Ativa a compensação dual-mono na medição de loudness.

### `speed`

Velocidade inicial de reprodução. Intervalo aceito: `0,25` até `2,0`.

Padrão: `1,0`.

### `volume`

Volume inicial de saída do MPV representado entre `0.0` e `1.0`.

- `0.0` = 0%
- `0.5` = 50%
- `1.0` = 100%

### `deck_profile_enabled`

Ativa o uso do perfil analisado do deck quando existir um perfil compatível.

## Requisito do FFmpeg

A reprodução normal do Anki e os controles em tempo real do MPV não exigem que você execute manualmente o FFmpeg.

A função **Analisar deck** precisa encontrar um executável `ffmpeg` para realizar as medições offline. A extensão procura no PATH do sistema e em locais comuns próximos ao runtime do Anki.

Se o FFmpeg não for encontrado, a reprodução normal continua funcionando, mas a análise do deck não poderá ser iniciada.

## Compatibilidade

Atualmente testado principalmente com:

- Anki Desktop 26.08.1
- Linux

Outros sistemas desktop podem funcionar, mas devem ser testados antes de serem listados como oficialmente suportados.

Outras extensões que também alterem velocidade, volume ou filtros do MPV podem entrar em conflito com o Balanced Audio Controller.

## Build

Um arquivo `.ankiaddon` é um arquivo ZIP utilizando a extensão `.ankiaddon`. Os arquivos do add-on precisam ficar na raiz do pacote.

Para gerar o pacote:

```bash
python3 build.py
```

A versão é lida do `manifest.json`. O arquivo gerado é colocado em `dist/`, por exemplo:

```text
dist/Balanced_Audio_Controller-v0.9.0-dev.ankiaddon
```

O build inclui:

- `__init__.py`
- `i18n.py`
- `config.json`
- `config.schema.json`
- `manifest.json`
- `README.md`
- `LICENSE`
- `web/`

Dados gerados em execução, como `user_files/`, não são incluídos no pacote.

## Branches de desenvolvimento

- `main`: versões estáveis/publicáveis.
- `dev`: desenvolvimento e testes antes do merge para `main`.

## Licença

MIT License.
