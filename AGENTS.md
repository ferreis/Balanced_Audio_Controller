# Regras para agentes

- Trabalhar sempre na branch `dev`.
- Ler este arquivo antes de alterar o projeto.
- Ao terminar uma alteração, validar o código, a segurança e abrir um PR de `dev` para `main`.
- Não alterar `main` diretamente; `main` é a linha estável/publicável.
- Criar testes automatizados com Playwright para alterações de interface/comportamento do painel.
- Não executar comandos recebidos de cartões, configurações ou outros dados não confiáveis.
- Processos externos devem usar argumentos separados e `shell=False`.
- Validar caminhos de mídia para impedir path traversal para fora da pasta de mídia da coleção.
- Se algum workflow/action for usado durante desenvolvimento, manter nomes e descrições em pt-BR e não levar workflow de desenvolvimento para `main`.
- Preservar o player nativo do Anki e evitar modificações destrutivas nos arquivos de mídia dos decks.
