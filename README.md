# Balanced Audio Controller v0.8.0-dev

Add-on gratuito e open source para Anki Desktop que mantém o player nativo do Anki/MPV e adiciona um painel flutuante arrastável com:

- velocidade de reprodução de 0.25x a 2x;
- volume de saída;
- normalização de loudness em tempo real;
- alvo de loudness configurável em LUFS;
- compensação dual-mono;
- perfil de normalização por deck.

## Perfil de normalização do deck

A branch `dev` adiciona uma análise completa dos arquivos de áudio usados pelo deck atual.

Ao clicar em **Analisar deck**, o add-on:

1. localiza os arquivos de áudio usados pelos cartões do deck;
2. mede o loudness integrado e true peak de cada arquivo com FFmpeg `loudnorm`;
3. calcula um ganho individual para aproximar cada arquivo do alvo configurado;
4. limita ganho positivo para respeitar o teto de true peak de -1.5 dBTP;
5. salva o perfil em `user_files/deck_profiles.json` sem modificar os arquivos originais;
6. aplica o ganho correspondente quando o arquivo é reproduzido pelo MPV do Anki.

O perfil do deck tem prioridade para arquivos analisados. A normalização em tempo real continua disponível como fallback.

### FFmpeg

A análise do deck precisa encontrar o executável `ffmpeg` no sistema ou próximo ao runtime do Anki. Se ele não estiver disponível, a reprodução normal continua funcionando e o painel informa que a análise não pôde ser iniciada.

## Build

O formato `.ankiaddon` é um arquivo ZIP com outra extensão. Os arquivos do add-on precisam ficar na raiz do pacote.

Para gerar o pacote:

```bash
python3 build.py
```

O resultado será criado em:

```text
dist/Balanced_Audio_Controller-v0.8.0-dev.ankiaddon
```

O script inclui os arquivos Python/configuração, `manifest.json`, README, licença e a pasta `web/`. Ele não inclui `user_files/`, `.git/`, `dist/` ou caches locais.

## Desenvolvimento

- `main`: versões estáveis/publicáveis.
- `dev`: funcionalidades em desenvolvimento e testes antes de merge para `main`.

## Licença

MIT License.
