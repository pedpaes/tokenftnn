# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.
O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto usa versionamento semântico.

## [1.1.4] - 2026-11-06

### Corrigido

- Depois de clicar em **JOGAR NOVAMENTE**, o bot espera a tela de matchmaking e
  o início da partida seguinte. Antes, o fallback com **ESC** disparava poucos
  segundos depois do clique e devolvia o jogador ao lobby no meio da fila.
- O fallback com **ESC** só volta a valer se `matchmaking_timeout` estourar sem
  a partida começar.
- A mensagem de parada e a de erro não aparecem mais duplicadas no painel de
  log: o evento da interface não repete o texto já registrado pelo bot.
- O `config.json` de exemplo não limita mais a execução a 30 minutos; o padrão
  passou a ser `0` (sem limite), como já estava documentado.
- A mensagem de limite de tempo agora indica como ajustar
  `max_runtime_minutes`.

### Alterado

- Autoteste ampliado para 84 verificações, cobrindo a espera pela partida após
  **JOGAR NOVAMENTE** e a liberação do fallback quando o matchmaking expira.

## [1.1.3] - 2026-11-05

### Adicionado

- Template `assets/menu_tab.png` e opção `detection.menu_tab_score` para a aba
  de três linhas do painel social.

### Corrigido

- O evento `No teammates available to follow` não agenda mais a saída quando o
  chat ainda lista preenchimentos vivos. Ele só é usado como confirmação depois
  que o rastreamento do esquadrão fica vazio.
- A saída automática agora abre a aba de opções do painel social antes de
  clicar em **Voltar ao Lobby** e não pressiona ESC de novo quando o painel já
  está aberto, evitando fechá-lo por engano.
- O diagnóstico do pós-partida também mostra a confiança da aba de opções.

### Alterado

- Autoteste ampliado para 82 verificações, cobrindo a navegação do painel
  social e o falso sinal de espectador com fills vivos.

## [1.1.2] - 2026-11-05

### Adicionado

- Rastreamento dos preenchimentos pelo canal `BR.Any` do chat do Fortnite.
  O bot identifica quem entrou e quem saiu, ignorando o jogador local.
- Saída automática quando o último preenchimento abandona a partida, com
  cancelamento caso alguém volte e bloqueio quando o token já foi encontrado.
- Detecção dos botões **JOGAR NOVAMENTE**, **RETORNAR AO LOBBY** e **Voltar ao
  Lobby** (menu novo), com templates próprios em `assets/`.
- Fallback **ESC → Voltar ao Lobby** quando o resumo da partida não exibe
  botões, incluindo o caso em que o jogador local morre sem companheiros vivos
  (`No teammates available to follow`).
- Guia de validação supervisionada, mapa da arquitetura, guia de calibragem de
  templates e checklist de release em `docs/`.
- Diagnóstico `tools/check_postmatch.py` para inspecionar o resumo e o menu sem
  clicar no jogo.
- Verificador `tools/check_docs.py` para encontrar links relativos quebrados na
  documentação.

### Alterado

- O pós-partida agora clica visualmente em **JOGAR NOVAMENTE** para reenfileirar
  e em **RETORNAR AO LOBBY** quando o token foi encontrado ou o limite de
  partidas foi atingido. ENTER e ESPAÇO não são mais usados para avançar telas.
- A saída automática usa primeiro o botão **Voltar ao Lobby** do menu novo; a
  seta da interface antiga permanece como fallback.
- Na tela de morte o menu pode já estar aberto; o bot confere antes de pressionar
  ESC, evitando fechar o menu por engano.
- A transição do resumo para a partida seguinte volta a contabilizar a nova
  partida.
- Autoteste ampliado para 75 verificações, cobrindo pós-partida sem ENTER/ESPAÇO,
  menu novo, morte sem companheiros, contagem de partidas, diagnóstico visual e
  links da documentação.
- O workflow de CI agora verifica os links da documentação, salva a saída do
  autoteste e publica os artefatos quando a execução falha.

### Removido

- Opções `postmatch_enter_after`, `postmatch_space_after` e
  `postmatch_safe_click`, substituídas pelo clique visual nos botões do resumo.

## [1.1.1] - 2026-11-05

### Corrigido

- Falso positivo do token causado por personagens e efeitos dourados com muito
  branco no centro. A validação agora limita a proporção máxima de branco do
  disco dourado, além dos limites mínimos já existentes.
- Falso positivo no ícone dourado de "Equipar um Elemental" na tela de resumo
  da partida. O limiar dos templates pequenos subiu de 0,55 para 0,62, faixa
  que ainda aprova todas as capturas reais do token nos testes.
- `config.json` volta a salvar o caminho do log de forma portátil
  (`%LOCALAPPDATA%`), sem gravar o caminho absoluto do usuário.

## [1.1.0] - 2026-11-05

### Adicionado

- Modo **segundo plano**: captura do Fortnite encoberto com `PrintWindow` e
  `PW_RENDERFULLCONTENT`, sem trazer o jogo para a frente.
- **Foco rápido** (~1 s) para cliques e teclas, com restauração da janela em
  primeiro plano e da posição do cursor.
- Botão **Manter PC acordado**, com gerenciamento de motivos (`manual` e
  `bot`) e prevenção de suspensão/desligamento de tela por inatividade.
- Interface em **modo escuro**, barra de título escura no Windows 11,
  diálogos próprios e botão para limpar o registro.
- Identidade visual: logo, banner, social preview e ícone do aplicativo.
- Documentação completa de instalação, uso, configuração e solução de
  problemas.
- Workflow de testes no GitHub Actions.

### Alterado

- Captura em segundo plano é o padrão; o modo primeiro plano continua
  disponível na interface.
- O bot não rouba o foco periodicamente durante a partida no modo segundo
  plano.
- Mensagens de erro de captura são mais claras e incluem janela minimizada.
- Autoteste cobre captura em segundo plano, energia e imagens negativas.

### Corrigido

- Registro do atalho global F8 com a API nativa do Windows.
- Falsos positivos do banner do lobby.
- Barra de título permanecia clara por aplicar o tema antes da janela existir.

## [1.0.0] - 2026-11-05

### Adicionado

- Primeira versão funcional do farm AFK.
- Leitura incremental do `FortniteGame.log` e máquina de estados
  lobby → matchmaking → partida → pós-partida → lobby.
- Detecção visual do token Pirate Shop com OpenCV e validação de cor.
- Clique em JOGAR, CONTINUAR JOGANDO e CLAIM ALL.
- Atalho F8, modo simulação, logs, capturas e arquivo
  `TOKEN_ENCONTRADO.txt`.
