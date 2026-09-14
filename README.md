# Balanced Audio Controller v0.7.0

Add-on experimental para Anki Desktop que mantém o player nativo do Anki/MPV e adiciona um painel flutuante arrastável para controlar:

- velocidade de reprodução (0.25x a 2x);
- volume de saída (0 a 100%);
- normalização de loudness em tempo real;
- loudness integrado alvo (-50 a -20 LUFS, padrão -24 LUFS);
- compensação opcional para áudio mono reproduzido em estéreo (dual-mono).

## Normalização

A v0.4 troca o nivelamento dinâmico anterior pelo filtro `loudnorm` do FFmpeg dentro do MPV. O filtro segue o modelo EBU R128 e busca aproximar cada áudio do loudness integrado configurado. O limite de true peak é fixado em -1.5 dBTP para deixar margem contra clipping.

A normalização é aplicada durante a reprodução e não modifica os arquivos de mídia do deck.

## Interface

Todo o controle agora fica no mesmo componente lateral arrastável. Duplo clique na barra `Áudio` restaura a posição padrão.

Os botões originais de replay do cartão continuam sendo controlados pelo próprio Anki; o add-on não intercepta o play.

## v0.5.0

- Velocidade agora usa campo numérico em vez de select.
- Botões −/+ alteram a velocidade em 0,5x por clique.
- Campo aceita valores manuais entre 0,25x e 2,0x.
- Botões e campo de velocidade receberam visual mais compacto e consistente.

## v0.6.0

- Controle de velocidade redesenhado como um único componente segmentado.
- Campo central continua sendo um `input` numérico.
- Botões −/+ alteram a velocidade em 0,5x por clique.
- Velocidade padrão definida explicitamente como 1.0x.
- Mantidos os limites de 0,25x a 2,0x.

## v0.6.1

- Corrigido o alinhamento horizontal do valor de velocidade.
- O valor numérico agora permanece centralizado conforme a largura do componente.
- O sufixo `x` fica ancorado à direita sem deslocar o valor central.

## v0.7.0

- Componente de velocidade reconstruído do zero.
- Botões − e + possuem largura fixa e simétrica.
- Valor e sufixo `x` formam um grupo único centralizado no espaço disponível.
- O campo numérico ajusta sua largura ao conteúdo para manter `1 x`, `0.5 x`, `1.25 x` etc. visualmente centralizados.
- Mantido incremento/decremento de 0,5x e velocidade padrão de 1.0x.
