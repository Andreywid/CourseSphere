# Relatório Técnico de Segurança e Confiabilidade - CourseSphere

> Autor: Andreywid. Data: 27/10/2026. Ambiente: teste isolado em Docker, com projeto Firebase próprio. Status: concluído. O documento não contém segredos.

## 1. Resumo

O CourseSphere é um assistente web de recomendação de cursos: backend Flask, frontend React, Firebase para login e banco (Realtime Database). Avaliei segurança e confiabilidade no escopo do desafio, em ambiente Docker isolado com um projeto Firebase próprio (detalhes nas seções 2 e 3).

Foram 11 achados. O mais grave, de longe: as regras do Realtime Database estavam em modo de teste, com `.read` e `.write` liberados, então qualquer um sem login lia e escrevia no banco inteiro. Priorizei esse por ser o único que atingia todos os usuários: travei as regras para negar acesso direto de cliente e deixei o backend como único caminho até o banco. No mesmo lote: token fora da URL e dos logs, erros sem detalhe interno, debug desligado e containers não-root.

Dos 11, corrigi 6 (4 na raiz), validados no ambiente de teste; um é injeção de SQL num módulo desligado hoje. Três seguem abertos: senha fraca, uma falha silenciosa no cliente e um endpoint placeholder que o frontend chama. E o limite de requisições, atrás do Nginx, conta pelo IP do proxy, então vale por endpoint e não por cliente. Se eu seguisse, atacava isso e a autenticação opcional do `/users/query`, que aceita token inválido em silêncio.

## 2. Escopo e metodologia

### 2.1 Alvo

CourseSphere é uma aplicação web que ajuda estudantes a encontrar os melhores cursos (*courses*) para se matricular (descrição do `README.md`).

| Camada | Tecnologia | Observações |
|---|---|---|
| Backend (`backend/`) | Python, Flask, Flask-CORS | 7 rotas HTTP em `endpoints.py`. |
| Identidade e dados | Firebase Authentication e Realtime Database (RTDB), via `firebase_admin` | `backend/firebase.py`. Perfil em `users/{uid}/info`; chats em `users/{uid}/chats/{chat_id}`. |
| SQLite | `backend/db.py` e `backend/blueprints/courses.py` | Código presente, mas não exercitado em runtime: o blueprint não está registrado (`endpoints.py:12`, comentado) e não há arquivo SQLite no repositório. |
| OpenAI | Cliente criado no import de `backend/main.py:22` (importado por `endpoints.py:6` por causa de `hashFunction`) | Stub em runtime: nenhuma chamada à API é feita. O `QueryManager` devolve resposta fixa (`query_manager.py:89` e `:104`), e `get_query_details` só roda quando `main.py` é executado como script (`main.py:60-62`). |
| Frontend (`frontend/`) | React 18, Vite 5, TypeScript, MUI 5 | Login pelo SDK do Firebase no cliente (`api.ts:33` e `:58`). Chama o backend em `http://127.0.0.1:5000`, endereço fixo no código. |

### 2.2 Ambiente de teste

O ambiente é isolado em Docker e definido em `docker-compose.yml`.

| Serviço | Base | Execução | Porta no host |
|---|---|---|---|
| `backend` | `python:3.12-slim` | Flask (CLI) em `0.0.0.0:5000` | 5000 |
| `frontend` | `node:20-alpine` | Servidor de desenvolvimento do Vite em `0.0.0.0:3000` | 3000 |

- Os dois serviços ficam na rede bridge dedicada `coursesphere-net`.
- Os segredos `backend/config.json` e `backend/credentials.json` são montados como volumes somente leitura em `/app`. Ficam fora da imagem (`backend/.dockerignore`) e do git (`.gitignore`). O `config.json` do ambiente tem uma chave placeholder, porque a OpenAI não é chamada em runtime.
- O backend sobe pelo CLI do Flask, então o `app.run(debug=True)` de `endpoints.py:108` não é executado e o debug fica desligado no container (ACH-11).
- O frontend usa o servidor de desenvolvimento porque o build de produção (`frontend/Dockerfile`) falha com 15 erros do compilador TypeScript (`tsc -b`) no código original.
- **Firebase.** O candidato usa um projeto Firebase próprio, para poder testar e corrigir o controle de acesso nas fases seguintes. O frontend (`frontend/src/firebaseConfig.ts`), a credencial de serviço do backend e a URL do RTDB do backend apontam para esse projeto.
- **URL do RTDB.** O código original fixava a URL em `backend/firebase.py`, apontando para o projeto Firebase do autor do repositório (commit `68e6a44`), o que causou HTTP 400 nas rotas de perfil na primeira execução do baseline. A URL agora vem da variável de ambiente `FIREBASE_DB_URL`, definida no serviço `backend` do `docker-compose.yml` com o `databaseURL` de `frontend/src/firebaseConfig.ts`. Ver ACH-06 e a seção 4.

### 2.3 Metodologia

- Análise manual guiada pelo OWASP Web Security Testing Guide (WSTG).
- SAST: Semgrep e Bandit.
- SCA: pip-audit (backend) e npm audit (frontend).
- DAST: OWASP ZAP.
- Classificação alinhada ao OWASP Top 10 2021; severidade por CVSS 3.1.

SAST (Semgrep e Bandit) e SCA (pip-audit e npm audit) foram executados em 23/10/2026; as saídas e o mapeamento nos achados estão em [`evidence/tools/README.md`](evidence/tools/README.md). O DAST (OWASP ZAP) ainda não foi executado. Os achados vêm de leitura de código e de observação do ambiente de baseline, e o ACH-11 foi apontado pelo Semgrep e pelo Bandit; os demais candidatos novos das ferramentas ainda não estão na seção 3.

### 2.4 Baseline (Fase 0)

Fase 0 concluída em 23/10/2026. O ambiente sobe com `docker compose up --build`, com o backend (Flask, porta 5000) e o frontend (Vite, porta 3000) na rede `coursesphere-net`, e o fluxo normal foi validado com credenciais reais. A tabela resume o resultado. As linhas de log citadas estão em [`evidence/baseline/backend-baseline.log`](evidence/baseline/backend-baseline.log), com os tokens redigidos.

| Passo | Mecanismo | Resultado |
|---|---|---|
| Ambiente | `docker compose up --build` | Backend e frontend em execução. O log do backend registra o Flask em `0.0.0.0:5000` com debug desligado. |
| Cadastro | `POST /users/create` | HTTP 200. A rota usa só o Firebase Authentication. |
| Login | Firebase Authentication, no cliente | Concluído. O backend aceitou o token do usuário em `GET /users/info` e `POST /users/info` (HTTP 200). |
| Salvar perfil | `POST /users/info`, que grava em `users/{uid}/info` no RTDB | **Validado.** `POST /users/info` e `GET /users/info` retornam HTTP 200 após a correção da URL do RTDB (ACH-06). |
| Query | `POST /users/query` | **Validado.** HTTP 200, mais duas chamadas `POST /hash` (HTTP 200) que a interface usa para gerar os IDs das mensagens (`ChatInterface.tsx:52` e `:61`). A resposta é a string fixa `"Fake implementation"` (`query_manager.py:104`). |

Na primeira execução, antes da correção do ACH-06, `POST /users/info` e `GET /users/info` retornaram HTTP 400. O log dessa execução não foi preservado, porque o container do backend foi recriado ao aplicar a correção.

Comportamentos originais observados (não são regressões da Fase 0; os arquivos envolvidos não foram alterados):

- **"Failed to fetch your chats".** `UserChats.tsx:25` chama `/theactualbackendlink`, rota que não existe no backend. O log registra `OPTIONS /theactualbackendlink` com HTTP 404 e o componente exibe o toast de erro (`UserChats.tsx:41`). Ver ACH-04.
- **Resposta da query sem conteúdo.** O `QueryManager` é um stub e devolve a string `"Fake implementation"`. O frontend lê `result.botResponse` (`api.ts:199`), campo que não existe nessa resposta e fica indefinido.
- **Toast de sucesso sem checar `response.ok`.** `api.ts:168-170` exibe "Successfully saved your information!" qualquer que seja o status HTTP, o que escondeu o HTTP 400 da primeira execução. Ver ACH-07.

Alterações em relação ao repositório original:

- `backend/main.py`: a chamada à OpenAI e o `print` do fim do módulo foram para `if __name__ == "__main__":` (linhas 60-62). Assim, `from main import hashFunction` (`endpoints.py:5`) não dispara chamada de rede no import. As funções não foram alteradas.
- `frontend/Dockerfile`: base trocada de `node:16-alpine` para `node:20-alpine`, porque o Vite 5 exige Node 18 ou superior.
- `frontend/src/firebaseConfig.ts`: valores do projeto Firebase do candidato.
- `.gitignore`: inclusão de `credentials.json`.
- `backend/firebase.py` e `docker-compose.yml`: a URL do RTDB passou a vir da variável de ambiente `FIREBASE_DB_URL` (ACH-06). Feita depois da primeira execução do baseline, que expôs o HTTP 400, e antes da validação final.
- Arquivos novos: `docker-compose.yml`, `backend/Dockerfile`, `backend/.dockerignore`, `backend/config.example.json`, `frontend/Dockerfile.dev`.
- Higiene do repositório (23/10/2026): removidos arquivos `.DS_Store`, pastas `.idea/` e um `package-lock.json` vazio na raiz, versionados por engano no original. No `.gitignore`, `*config.json` virou `config.json`, porque o padrão antigo também casava com `frontend/tsconfig.json`, e `__pycache__/` foi incluído. O `README.md` foi reescrito para a avaliação.

## 3. Achados

Formalização entre 24/10/2026 e 25/10/2026. Os achados ACH-01, 03, 08, 09, 10, 11 e 12 trazem CWE, OWASP Top 10 2021, reprodução, impacto de negócio e causa raiz, e CVSS 3.1 quando aplicável (ACH-01 e ACH-09 têm só a severidade). ACH-04, 05, 06 e 07 seguem como rascunho da Fase 0 (ACH-04 e ACH-06 só com classificação preliminar). O ACH-02 foi consolidado no ACH-03. As reproduções descrevem os passos para a banca repetir, sem payload armado. A tabela abaixo está ordenada por prioridade. As evidências de cada achado ficam em `security/evidence/<ID>/` e as saídas das ferramentas em [`evidence/tools/`](evidence/tools/README.md).

| # | ID | Achado | CVSS 3.1 | Severidade | Situação |
|---|---|---|---|---|---|
| 1 | ACH-12 | Regras do Realtime Database abertas (modo de teste) | 9.8 | Crítico | Corrigido e validado |
| 2 | ACH-08 | `id_token` na URL e no log do Flask | 6.5 | Médio | Corrigido e validado |
| 3 | ACH-03 | Vazamento de detalhe de erro ao cliente | 5.3 | Médio | Corrigido e validado |
| 4 | ACH-11 | Modo debug do Flask habilitado | 7.4 | Alto (inerente) | Corrigido (debug off, seção 5.1) |
| 5 | ACH-01 | Container executa como root | Não atribuído | Baixo | Corrigido (não-root, seção 5.4) |
| 6 | ACH-09 | `/users/query`: autenticação opcional quebrada (fail-open) | Não atribuído | Baixo | Rate limiting aplicado; fail-open aberto (5.3) |
| 7 | ACH-10 | SQL montado por f-string (blueprint inativo) | 7.5 | Alto (inerente) | Latente e não funcional |
| - | ACH-04 | Endpoint placeholder `/theactualbackendlink` | A definir | Baixo (preliminar) | Aberto |
| - | ACH-05 | Cadastro aceita senha de 6 caracteres | A definir | A avaliar | A avaliar |
| - | ACH-06 | URL do RTDB fixa no código | A definir | Menor (preliminar) | Corrigido e validado |
| - | ACH-07 | Falha silenciosa no cliente | A definir | A definir | Aberto |
| - | ACH-02 | Consolidado no ACH-03 | - | - | - |

Ordem por risco prático: primeiro o ACH-12, crítico (corrigido e validado em 25/10/2026); depois o que se manifesta no ambiente fornecido (ACH-08 e ACH-03, corrigidos e validados, na ordem por score), o que depende do modo de execução (ACH-11, corrigido na Fase 5), o hardening (ACH-01, corrigido, e ACH-09, endurecido com rate limiting, mas com o fail-open ainda aberto) e, por último, o ACH-10, latente e não funcional (blueprint inativo, e `db.py` impede o retorno dos dados) apesar do score inerente alto. ACH-04 a ACH-07 ainda não têm CVSS e ficam fora do ranking.

Severidade "inerente" é o score do código como escrito, assumindo as condições do achado (ACH-10: blueprint ativado; ACH-11: execução por `python endpoints.py`). O ambiente fornecido não está nessas condições.

### 3.1 ACH-01: Container executa como root

- **Classificação:** Baixo (hardening e defesa em profundidade). CVSS 3.1 não atribuído. Justificativa: o item não é explorável sozinho; amplifica o impacto de qualquer execução de código no container.
- **CWE:** CWE-250 (execução com privilégios desnecessários).
- **OWASP Top 10 2021:** A05:2021 (configuração incorreta de segurança).
- **Descrição:** as imagens do backend e do frontend não definem usuário não-root, então o Flask e o Vite rodam como root dentro do container. O campo `User` das duas imagens construídas está vazio. O `backend/Dockerfile` foi criado na Fase 0; o repositório original não tinha.
- **Localização:** `backend/Dockerfile` (sem `USER`; `CMD` na linha 16), `frontend/Dockerfile.dev` (sem `USER`; `CMD` na linha 12) e `frontend/Dockerfile` (sem `USER`; `CMD` na linha 24). O Semgrep acusa `missing-user` em `backend/Dockerfile:16`.
- **Reprodução:**
  1. Subir o ambiente com `docker compose up --build`.
  2. Executar `docker compose exec backend id` e `docker compose exec frontend id`.
  3. Observar `uid=0(root)` nas duas saídas.
- **Evidência:** [`evidence/tools/semgrep.json`](evidence/tools/semgrep.json) (regra `missing-user`).
- **Impacto de negócio:** um atacante que execute código no container o faz como root, o que piora o escape do container e a movimentação lateral. A ação de hardening fica para a fase seguinte.
- **Causa raiz:** as imagens não criam nem selecionam um usuário não-root.
- **Situação:** Corrigido na Fase 5 (container não-root, seção 5.4).

### 3.2 ACH-02: Consolidado no ACH-03

O comportamento de `POST /hash` sem o header `Authorization` (HTTP 500 com a exceção interna) passou a ser o caso principal do ACH-03. O ID ACH-02 não é mais usado.

### 3.3 ACH-03: Vazamento de detalhe de erro ao cliente (inclui o antigo ACH-02)

- **CVSS 3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N` = **5.3 (Médio)**. Justificativa: detalhe interno de exceção devolvido ao cliente, trivialmente disparável e útil para reconhecimento.
- **CWE:** CWE-209 (mensagem de erro com informação sensível) e CWE-20 (validação de entrada imprópria).
- **OWASP Top 10 2021:** A05:2021 (configuração incorreta de segurança) e A09:2021 (falhas de registro e monitoramento de segurança).
- **Descrição:** até a correção (seção 4.4), as 7 rotas de `endpoints.py` capturavam `Exception` e devolviam o texto da exceção no corpo da resposta (HTTP 400; HTTP 500 em `/hash`). O texto vinha de Python e do `firebase_admin`, que `firebase.py` reencapsula com `str(e)`, e não era filtrado. Havia uma segunda causa, de entrada: as rotas que liam o token do header faziam `request.headers.get('Authorization').split('Bearer ')[1]` sem verificar se o header existia nem se tinha o prefixo `Bearer `. Sem o header, `.split` levantava `AttributeError` (HTTP 500 no `/hash`); com o header sem o prefixo, o índice `[1]` levantava `IndexError`.
- **Localização** (antes da correção, na numeração original): `backend/endpoints.py:28, 53, 63, 72, 83, 94, 104` (`str(e)` nas 7 rotas) e `:58, 77, 88, 99` (extração do token sem validar o header, em `GET /users/info`, `/hash` e nas rotas de chat); `backend/firebase.py:27, 36, 44, 52, 61, 78, 93, 109, 124, 138, 156, 164` (reencapsulamento com `str(e)`, não alterado).
- **Reprodução** (no código anterior à correção):
  1. Com o ambiente no ar, enviar `POST /hash` sem o header `Authorization`: `curl -i -X POST http://localhost:5000/hash`.
  2. Observar HTTP 500 e, no corpo, `{"error":"'NoneType' object has no attribute 'split'"}`.
  3. Repetir com `-H 'Authorization: Basic abc'` (sem o prefixo `Bearer `) e observar HTTP 500 com `list index out of range`.
  4. Nas demais rotas, um `id_token` inválido fazia a resposta HTTP 400 incluir a mensagem interna do `firebase_admin`, com o valor enviado.
  Depois da correção (seção 4.4): `POST /hash` e `GET /users/info` sem header devolvem HTTP 401 genérico, e uma exceção inesperada devolve HTTP 500 `Internal server error`, com o detalhe só no log do servidor.
- **Evidência:** antes: [`evidence/ACH-03/hash-no-auth-500.txt`](evidence/ACH-03/hash-no-auth-500.txt) (HTTP 500 com a exceção interna, 25/10/2026). Depois: [`evidence/ACH-03/hash-no-auth-401.txt`](evidence/ACH-03/hash-no-auth-401.txt) e [`evidence/ACH-03/users-info-no-auth-401.txt`](evidence/ACH-03/users-info-no-auth-401.txt) (HTTP 401 genérico, 26/10/2026).
- **Impacto de negócio:** expõe internals (bibliotecas, estrutura do código) a um cliente não autenticado, o que facilita um ataque dirigido.
- **Causa raiz:** exceções capturadas de forma genérica, com `str(e)` devolvido ao cliente, e entrada não validada nas rotas que leem o header.
- **Situação:** Corrigido e validado em 26/10/2026 (seção 4.4).

### 3.4 ACH-04: Endpoint placeholder `/theactualbackendlink` chamado pelo frontend

- **Localização:** `frontend/src/components/UserChats/UserChats.tsx:25` (chamada), `:33-35` (erro quando a resposta não é OK) e `:41` (toast "Failed to fetch your chats"). O componente é renderizado em `frontend/src/pages/home/Home.tsx:9`, na rota `/` (`App.tsx:43`).
- **Descrição:** `UserChats` faz `GET http://127.0.0.1:5000/theactualbackendlink` assim que há usuário autenticado. A rota não existe em `backend/endpoints.py` (rotas nas linhas 23 a 126) nem em `backend/blueprints/`, e a string não aparece em nenhum outro arquivo do repositório.
- **Observado:** o log do backend registra `OPTIONS /theactualbackendlink` com HTTP 404 e nenhum `GET` correspondente; o frontend mostra o toast de erro. Um `GET` direto à rota também retorna 404.
- **Evidência:** [`evidence/baseline/backend-baseline.log`](evidence/baseline/backend-baseline.log) (linhas `OPTIONS /theactualbackendlink` com HTTP 404, sem `GET` correspondente).
- **Classificação preliminar:** qualidade de código / baixo.

### 3.5 ACH-05: Cadastro aceita senha de 6 caracteres (fraco, a avaliar)

- **Localização:** `backend/endpoints.py:28-31` (única validação: e-mail e senha não vazios) e `frontend/src/pages/signup/SignUp.tsx:16` (o botão só exige campos não vazios).
- **Descrição:** no baseline, o cadastro aceitou uma senha numérica sequencial de 6 caracteres. Nem backend nem frontend aplicam política de senha além de "não vazia". O único limite efetivo vem do `firebase_admin`, que exige no mínimo 6 caracteres (`firebase_admin._auth_utils.validate_password`, verificado na versão instalada na imagem do backend).
- **Observação:** 6 caracteres é o mínimo padrão do Firebase Authentication. O item só vira achado se houver política esperada acima disso. A política de senha configurável no projeto Firebase não foi verificada.
- **Severidade:** a definir na Fase 2.

### 3.6 ACH-06: URL do RTDB fixa no código, acoplada ao projeto do autor do repositório (corrigido)

- **Localização:** `backend/firebase.py:5` no código original (commit `68e6a44`): `database_url` com a URL do RTDB do projeto do autor, passada a `initialize_app` na linha seguinte. Era a única ocorrência da URL no repositório.
- **Descrição:** a URL não era configurável e apontava para um projeto Firebase diferente do projeto das credenciais usadas no ambiente de teste. Na primeira execução do baseline, as rotas que dependem do RTDB (`POST` e `GET /users/info`) retornaram HTTP 400, enquanto as que só usam o Authentication (`POST /users/create`, `POST /hash`) retornaram 200. O log dessa execução não foi preservado.
- **Correção:** a URL passou a ser lida de `FIREBASE_DB_URL`, sem valor padrão (seção 4.1).
- **Status:** corrigido e validado em 23/10/2026: com credenciais reais, `POST /users/info` e `GET /users/info` retornam HTTP 200.
- **Evidência:** [`evidence/baseline/backend-baseline.log`](evidence/baseline/backend-baseline.log) (linhas `POST /users/info` e `GET /users/info` com HTTP 200).
- **Classificação preliminar:** configuração / menor.

### 3.7 ACH-07: Falha silenciosa no cliente: a interface exibe sucesso com HTTP 400

- **Localização:** `frontend/src/api.ts:168-170` (`saveProfileChanges`: o `.then` exibe "Successfully saved your information!" sem verificar `response.ok`).
- **Descrição:** `fetch` só rejeita a promessa em falha de rede; respostas HTTP 4xx e 5xx resolvem normalmente. Como o `.then` não examina o status, o toast de sucesso aparece mesmo quando o backend rejeita a gravação, e o `.catch` (linhas 171-173) só trata falha de rede. O erro do backend fica mascarado para o usuário.
- **Mesmo padrão em outros fluxos** (sem verificação de `response.ok`): cadastro, em que `createUser` devolve o corpo da resposta (`api.ts:13-24`) e `performSignup` segue para o login (`:31-37`); leitura do perfil, em que `setProfileInfoIfLoggedIn` trata o corpo de erro como dados do perfil e não preenche nenhum campo, sem aviso (`:91-99`); e a query, em que `fetchCourseSphereResponse` exibe "Successfully retrieved bot response!" (`:195-197`). Os fluxos de chat e `/hash` verificam `response.ok` (`:248`, `:274`, `:293`, `:314`).
- **Observado:** na primeira execução do baseline, antes da correção do ACH-06, `POST /users/info` retornou HTTP 400 e a interface exibiu o toast de sucesso. O log dessa execução não foi preservado.
- **Severidade:** a definir na Fase 2.

### 3.8 ACH-08: `id_token` na URL de `GET /users/info` e registrado no log do Flask

- **CVSS 3.1:** `CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:L/A:N` = **6.5 (Médio)**. Justificativa: credencial bearer exposta em query string e registrada em log; a exploração depende de alcançar o canal de vazamento dentro da janela de validade do token.
- **CWE:** CWE-598 (uso de GET com dado sensível na query string) e CWE-532 (informação sensível em arquivo de log).
- **OWASP Top 10 2021:** A02:2021 (falhas criptográficas).
- **Descrição:** até a correção (seção 4.3), o frontend enviava o ID token do Firebase na query string de um `GET`. O backend lia o token de `request.args`, e o log de acesso padrão do Flask grava a linha de requisição inteira, então o token ficava em texto claro no log do backend. As demais rotas autenticadas recebem o token no header `Authorization` (`/hash` e `/chats/...`) ou no corpo da requisição (`POST /users/info`, `api.ts:158`).
- **Localização** (antes da correção): `frontend/src/api.ts:91` montava a URL com `?id_token=${idToken}`, e `backend/endpoints.py:58`, em `get_user_info`, lia `request.args.get("id_token")`; o token é verificado em `:59` (`Firebase.verify_id_token`). O backend não tem configuração de log própria; vale o log de acesso padrão.
- **Reprodução:**
  1. Subir o ambiente, fazer login e abrir o Dashboard (`/dashboard`), que dispara `GET /users/info?id_token=<token>`.
  2. Executar `docker compose logs backend` e procurar as linhas `GET /users/info?id_token=...`.
  3. Observar o token inteiro na URL registrada no log.
  4. Os passos 1 a 3 valem para o código anterior à correção. Depois dela (seção 4.3), o log registra só `GET /users/info`, sem o token.
- **Evidência:** [`evidence/baseline/backend-baseline.log`](evidence/baseline/backend-baseline.log), com o valor do token redigido antes de salvar (o valor original tinha 932 caracteres e prefixo de JWT). Ao repetir a reprodução, redigir o token antes de salvar qualquer log (ver [`evidence/README.md`](evidence/README.md)). Depois da correção: [`evidence/ACH-08/after-fix-no-token.log`](evidence/ACH-08/after-fix-no-token.log), com `GET /users/info` e `POST /users/info` em HTTP 200 e nenhuma URL com `?id_token=`.
- **Impacto de negócio:** um token roubado (log, histórico do navegador, `Referer`) permite impersonar o usuário durante a janela de validade, lendo e alterando os dados dele.
- **Causa raiz:** credencial na query string de uma requisição `GET`.
- **Situação:** Corrigido e validado: corrigido no código em 25/10/2026 (seção 4.3) e validado com login real em 26/10/2026 ([`evidence/ACH-08/after-fix-no-token.log`](evidence/ACH-08/after-fix-no-token.log)).

### 3.9 ACH-09: Autenticação opcional quebrada em `/users/query` (fail-open e sem limite de taxa)

- **Classificação:** Baixo, latente. CVSS 3.1 não atribuído. Justificativa: o endpoint é público por desenho e hoje devolve só um stub; os defeitos são de hardening e ganham peso quando a lógica for concluída. O item foi reenquadrado: antes era tratado como ausência de autenticação (CWE-306, 5.3).
- **CWE:** CWE-636 (falha aberta, em vez de falhar de forma segura).
- **OWASP Top 10 2021:** A07:2021 (falhas de identificação e autenticação).
- **Descrição:** `/users/query` é público por desenho: `fetchCourseSphereResponse` não chama `ensureUserLoggedIn`, ao contrário das demais chamadas autenticadas do `api.ts` (`:87, :144, :225, :258, :280, :300`); o `QueryManager` prevê consulta sem usuário (`query_manager.py:101`); e a leitura do usuário é opcional (`Firebase.try_get_user_info`). O problema real é que a autenticação opcional não funciona: (1) o frontend envia `idToken` como Promise não aguardada e com nome diferente do que o backend lê (`id_token`), então nem um usuário logado é reconhecido; (2) um token inválido ou ausente é rebaixado em silêncio para anônimo, porque `try_get_user_info` devolve `None` em qualquer falha e a rota responde 200 (fail-open); (3) o endpoint público não tem limite de taxa, o que é latente porque o handler é um stub. O teste `hasUserData = (self.user_data is not None)` (`query_manager.py:101`) nunca é falso, porque `:47` sempre cria o objeto de usuário, mesmo com usuário ausente: o ramo anônimo previsto no código não é detectado.
- **Localização:** `backend/endpoints.py:77-85` (rota; `:81` lê `id_token`); `backend/firebase.py:64-68` (`try_get_user_info` devolve `None` em qualquer falha); `backend/query_manager.py:47` e `:101`; `frontend/src/api.ts:183-186` (função sem `ensureUserLoggedIn`, `idToken` sem `await` e com nome divergente) e `:191` (header `Authorization`).
- **Reprodução:**
  1. Com o ambiente no ar, enviar `POST /users/query` com um `id_token` inválido no corpo: `curl -i -X POST http://localhost:5000/users/query -H 'Content-Type: application/json' -d '{"query":"test","id_token":"invalido"}'`.
  2. Observar HTTP 200 com a resposta fixa `"Fake implementation"`: o token inválido não é rejeitado (fail-open). O mesmo ocorre sem token e com um header `Authorization` inválido.
  3. No navegador, na aba Rede, observar a chamada feita pelo frontend logado: o corpo traz `idToken: {}` (a Promise serializada) e nenhum `id_token`, e o header vai como `Bearer [object Promise]`. A serialização foi verificada isoladamente em Node 20.
- **Evidência:** [`evidence/ACH-09/users-query-no-auth.txt`](evidence/ACH-09/users-query-no-auth.txt), capturada em 25/10/2026 (sem token e sem `Authorization`, HTTP 200). Ela continua válida: mostra que o endpoint responde a anônimos, o comportamento público esperado. O fail-open com token inválido foi verificado em teste local isolado e não tem arquivo de evidência.
- **Impacto de negócio:** usuários logados são tratados como anônimos e um token inválido não gera erro. Quando a lógica passar a usar dados do usuário, a personalização não funcionará e as falhas de autenticação ficarão invisíveis; sem limite de taxa, um endpoint público fica exposto a abuso quando o handler passar a executar trabalho caro.
- **Causa raiz:** o contrato de autenticação opcional não está implementado de ponta a ponta: o cliente envia o token de forma errada e o servidor trata qualquer falha como anônimo.
- **Situação:** Parcialmente endurecido na Fase 5: rate limiting aplicado (seção 5.3); o fail-open da autenticação opcional (token como Promise, rebaixamento silencioso) segue aberto.

### 3.10 ACH-10: SQL montado por f-string em `blueprints/courses.py` (blueprint inativo)

- **CVSS 3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N` = **7.5 (Alto, inerente)**. Justificativa: concatenar entrada em SQL permite ler o banco; o `execute` do `sqlite3` roda uma única instrução, então não há escrita. O score vale para o código como escrito: hoje o blueprint é inalcançável (ver pré-condições) e os dados são de cursos, públicos.
- **CWE:** CWE-89 (injeção de SQL).
- **OWASP Top 10 2021:** A03:2021 (injeção).
- **Descrição:** os valores vindos da URL são interpolados por f-string no texto SQL e executados por `cursor.execute(query)`, sem parametrização. Nas rotas com parâmetro `string` (`semester`, `department` e `instructor`) o valor fica entre aspas simples. As rotas `<int:...>` usam o mesmo padrão, mas o conversor do Flask limita o valor a dígitos. Confirmado por Semgrep (`tainted-sql-string`, 6 hits) e Bandit (B608, 6 hits). As três rotas `string` compartilham a mesma regra de URL, e na prática só `semester` é alcançada ([`recon.md`](recon.md), seção 2).
- **Localização:** `backend/blueprints/courses.py:80, 96, 112` (rotas `string`) e `:30, 47, 64` (rotas `int`); `backend/db.py:9` (`cursor.execute(query)`).
- **Pré-condições de ativação (hoje nenhuma é atendida):**
  1. O blueprint ser importado e registrado em `endpoints.py`, onde hoje só existe o comentário `#app.register_blueprint(courses_bp)` (linha 12).
  2. Os imports `backend.db` e `backend.endpoints` (`courses.py:3-4`) resolverem: no container a aplicação roda de `/app` e não existe o pacote `backend`.
  3. Existir o banco SQLite no caminho de `db.py:4` (`cournell-course-sphere-data/roster_reviews.sqlite.db`): o repositório não traz arquivo SQLite, e o nome da pasta está grafado diferente da pasta de dados (`cornell-course-sphere-data`).
- **Reprodução (condicional):**
  1. Atender as três pré-condições.
  2. Chamar `GET /courses/<valor>` com um valor que contenha uma aspa simples.
  3. Observar que a aspa fecha o literal da string SQL e altera a consulta: o SQLite a rejeita com `unrecognized token`, registrado no log do backend.
- **Observação:** mesmo com as três pré-condições, `db.execute_query` fecha a conexão antes de devolver o cursor (`db.py:11-12`), e o `.fetchall()` das rotas falha com `Cannot operate on a closed database` (verificado em teste local com os arquivos reais, banco temporário). Hoje o resultado da consulta não chega ao cliente: o padrão de injeção continua presente e ganha efeito prático se esse defeito for corrigido.
- **Evidência:** Semgrep e Bandit em [`evidence/tools/`](evidence/tools/README.md).
- **Impacto de negócio:** se ativado, leitura não autorizada do banco.
- **Causa raiz:** consulta montada por f-string, sem parametrização.
- **Situação:** Latente e não funcional: o blueprint está inativo e, mesmo ativado, `db.py:11-12` impede que o resultado das consultas chegue ao cliente.

### 3.11 ACH-11: Modo debug do Flask habilitado no ponto de entrada

- **CVSS 3.1:** `CVSS:3.1/AV:L/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H` = **7.4 (Alto, inerente)**. Justificativa: `app.run(debug=True)` expõe o debugger interativo do Werkzeug (execução de código potencial, protegida por PIN, daí `AC:H`) e stack traces. No modo padrão (`python endpoints.py`) o servidor escuta só em `127.0.0.1`, porque `app.run` não recebe `host`, então o vetor é local. Se o processo for exposto (bind em `0.0.0.0` ou proxy), o vetor sobe para `AV:N` e o score para 8.1. O container do projeto roda pelo CLI do Flask com debug desligado; o score reflete o modo padrão do app.
- **CWE:** CWE-489 (código de depuração ativo) e CWE-215 (informação sensível em código de depuração).
- **OWASP Top 10 2021:** A05:2021 (configuração incorreta de segurança).
- **Descrição:** `endpoints.py` termina com `app.run(debug=True)` dentro de `if __name__ == '__main__'`. Executado assim, o Flask liga o debugger do Werkzeug: uma exceção não tratada devolve a página com o stack trace completo, e o console interativo fica protegido por PIN (o log mostra `Debugger PIN`). Confirmado por Semgrep (`debug-enabled`) e Bandit (B201, HIGH).
- **Localização:** `backend/endpoints.py:138` (dentro do bloco `__main__` de `:137-138`).
- **Reprodução:**
  1. A partir de `backend/`, com as dependências, `config.json`, `credentials.json` e `FIREBASE_DB_URL` presentes, executar `python endpoints.py` (modo padrão do app). O log mostra `Debug mode: on` e `Debugger is active!`.
  2. Provocar uma exceção não tratada: enviar `POST /users/create` com o corpo JSON `null` (a leitura do JSON fica fora do `try`, `endpoints.py:25-27`).
  3. Antes da correção do ACH-03, a resposta era a página do debugger do Werkzeug com o stack trace completo. Depois dela, o errorhandler global devolve o 500 genérico, mas o debugger continua ativo: o console interativo é servido em `/console`, protegido por PIN (verificado em teste local).
  4. Repetir o mesmo pedido no container fornecido (CLI do Flask, `Debug mode: off`) e observar apenas `Internal Server Error`.
- **Evidência:** Semgrep e Bandit em [`evidence/tools/`](evidence/tools/README.md); o log do container fornecido mostra `Debug mode: off` ([`evidence/baseline/backend-baseline.log`](evidence/baseline/backend-baseline.log)).
- **Impacto de negócio:** exposição de internals e, no pior caso, execução de código no servidor.
- **Causa raiz:** debug ligado no código, sem controle por configuração.
- **Situação:** Corrigido na Fase 5 (debug desligado por padrão, seção 5.1): com `python endpoints.py`, `Debug mode: off` e `GET /console` → 404. A correção do ACH-03 (errorhandler global) já suprimia a página de stack trace; o debug desligado fecha também o `/console`.

### 3.12 ACH-12: Regras do Realtime Database abertas (modo de teste)

- **CVSS 3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` = **9.8 (Crítico)**. Justificativa: qualquer cliente sem credenciais lê, altera e apaga os dados do banco pela API REST, sem interação do usuário e sem privilégio algum.
- **CWE:** CWE-284 (controle de acesso impróprio) e CWE-862 (autorização ausente).
- **OWASP Top 10 2021:** A01:2021 (quebra de controle de acesso).
- **Descrição:** as regras do Realtime Database estão no modo de teste padrão: `.read` e `.write` condicionados apenas a uma data (`now < 1795230000000`, 21/11/2026), sem checar autenticação. Até essa data qualquer pessoa pode ler e escrever no banco. O `databaseURL` é público (`frontend/src/firebaseConfig.ts:4`, entregue ao navegador), então um cliente não autenticado acessa o banco pela API REST, contornando o backend e toda a verificação de token. As regras não estavam no repositório; ficavam só no console do Firebase.
- **Localização:** regras do RTDB do projeto Firebase, exportadas em [`evidence/ACH-12/database-rules.json`](evidence/ACH-12/database-rules.json); `databaseURL` em `frontend/src/firebaseConfig.ts:4`. Não é um defeito do código do backend: o Admin SDK (`backend/firebase.py`) ignora as regras.
- **Reprodução (nível de relatório, sem dump):**
  1. Ler o `databaseURL` em `frontend/src/firebaseConfig.ts`, que é público.
  2. Enviar ao endpoint REST do banco uma requisição de leitura sem credenciais, limitada às chaves de primeiro nível (parâmetro `shallow=true`), sem baixar dados.
  3. Observar que a requisição é aceita, em vez de negada com `Permission denied`. Com as regras originais essa requisição não foi executada; a evidência primária é o export das regras. Depois da correção, a mesma leitura sem credenciais recebe HTTP 401 (`Permission denied`).
- **Evidência:** [`evidence/ACH-12/database-rules.json`](evidence/ACH-12/database-rules.json), obtido em 25/10/2026 por leitura das regras do projeto com a conta de serviço (somente leitura, sem acesso a dados). Está no formato do console, com comentários, e não menciona `auth`. Depois da correção: [`evidence/ACH-12/unauth-denied-after-lock.txt`](evidence/ACH-12/unauth-denied-after-lock.txt) (leitura sem credenciais negada, HTTP 401) e [`evidence/ACH-12/baseline-after-lock.txt`](evidence/ACH-12/baseline-after-lock.txt) (fluxo do baseline mantido).
- **Impacto de negócio:** leitura, alteração e exclusão de todos os dados de todos os usuários, sem login.
- **Causa raiz:** regras não escopadas por usuário e não versionadas.
- **Correção:** versionada em `database.rules.json` e `firebase.json` e publicada no projeto em 25/10/2026; ver a seção 4.2.
- **Situação:** Corrigido e validado em 25/10/2026: as regras publicadas negam todo acesso de cliente, a leitura sem credenciais recebe HTTP 401 e o fluxo do baseline continua funcionando.

## 4. Correções

Correções aplicadas até agora. As demais entram aqui conforme forem feitas.

### 4.1 ACH-06: URL do RTDB externalizada

- **Alteração:** `backend/firebase.py` (linhas 6-11) lê a URL de `FIREBASE_DB_URL`, sem valor padrão, e levanta `RuntimeError` com mensagem explícita se a variável estiver ausente ou vazia. O `docker-compose.yml` define a variável no serviço `backend` com o `databaseURL` de `frontend/src/firebaseConfig.ts`, que é a fonte única do valor.
- **Verificação local** (container sem rede, com credencial de teste descartável): sem a variável, ou com ela vazia, o backend não sobe e exibe a mensagem de erro; com a variável, sobe e o `firebase_admin` usa exatamente o valor informado. O valor do `docker-compose.yml` é igual ao `databaseURL` de `frontend/src/firebaseConfig.ts`.
- **Validação:** em 23/10/2026, com credenciais reais, `POST /users/info` e `GET /users/info` retornaram HTTP 200 ([`evidence/baseline/backend-baseline.log`](evidence/baseline/backend-baseline.log)).

### 4.2 ACH-12: Regras do Realtime Database restritas

- **Alteração:** dois arquivos novos na raiz do repositório. `database.rules.json` define `.read` e `.write` como `false`, e `firebase.json` aponta para ele (`database.rules`). As regras passam a ser versionadas.
- **Por que `false` e não regras por usuário:** o frontend não lê nem escreve no RTDB. Ele importa `getDatabase` (`api.ts:4`, `Nav.tsx:20`, `UserChats.tsx:4`) e cria a variável `database` (`api.ts:9`, `Nav.tsx:24`, `UserChats.tsx:10`), mas nunca a usa: não há chamada a `ref`, `get`, `set` nem `onValue` em `frontend/src`. Todo acesso ao RTDB passa pelo backend (`firebase.py`), que usa o Admin SDK e ignora as regras (comportamento documentado do Firebase). Regras por `auth.uid === $uid` em `users/$uid` só seriam necessárias se o frontend passasse a acessar o banco direto.
- **Aplicação:** publicada no projeto Firebase em 25/10/2026; as regras lidas do projeto com a conta de serviço são exatamente `.read: false` e `.write: false`. Para reaplicar: `firebase deploy --only database --project <id-do-projeto>` com o Firebase CLI autenticado, ou colando o conteúdo de `database.rules.json` no console (Realtime Database, aba Regras).
- **Verificação pós-aplicação:** (1) a leitura sem credenciais é negada com HTTP 401 (`Permission denied`), em [`evidence/ACH-12/unauth-denied-after-lock.txt`](evidence/ACH-12/unauth-denied-after-lock.txt); (2) o fluxo do baseline continua funcionando, com `GET /users/info` e `POST /users/info` retornando HTTP 200, em [`evidence/ACH-12/baseline-after-lock.txt`](evidence/ACH-12/baseline-after-lock.txt). Um teste de unidade das regras (emulador do Firebase) previne regressão: ver seção 7.9.
- **Validação local:** os dois arquivos são JSON válido e `firebase.json` aponta para um arquivo existente.

### 4.3 ACH-08: Token no header `Authorization`

- **Causa raiz:** credencial na query string de um `GET`, que o log de acesso do Flask registra junto com a URL.
- **Alteração:**
  - `backend/endpoints.py`, em `get_user_info`: passou a ler o token de `request.headers.get("Authorization").split("Bearer ")[1]`, como as rotas `/hash` e `/chats/*` (a extração foi depois centralizada em `get_bearer_token`, seção 4.4). A função não tem chamador interno, então a assinatura ficou `def get_user_info():`, sem o parâmetro `id_token=None` e sem o comentário sobre outro contexto. O tratamento de erro (`str(e)`) não mudou, porque é o ACH-03.
  - `frontend/src/api.ts:91-95`: `setProfileInfoIfLoggedIn` chama `http://127.0.0.1:5000/users/info`, sem `?id_token=`, e envia `Authorization: Bearer ${idToken}`.
  - O `POST /users/info` não mudou: o token vai no corpo, o que não é o ACH-08.
- **Solução:** o token vai no header, que não aparece na URL nem no log de acesso.
- **Verificação local** (stack recriado com `docker compose up -d --build`, sem token real):
  - `GET /users/info` com `Authorization: Bearer invalido` chega à verificação do Firebase e retorna HTTP 400 com `Error verifying ID token`, o que prova que o header é lido.
  - `GET /users/info?id_token=invalido`, no formato antigo, é ignorado: a resposta é a de requisição sem header.
  - O preflight de CORS vindo de `http://localhost:3000` aceita o header `authorization`.
  - O log de acesso registra `GET /users/info HTTP/1.1`, sem token.
  - O frontend continua com os mesmos 15 erros de TypeScript herdados, nenhum novo, e o Vite serve o `api.ts` com o header.
- **Efeito colateral:** sem o header, `GET /users/info` passa a responder como `/hash` e `/chats/*` (exceção interna no corpo, HTTP 400). Isso entra no ACH-03.
- **Validação com login real** (26/10/2026): abrindo o Dashboard e salvando o perfil, o log registra `GET /users/info` (duas vezes) e `POST /users/info` com HTTP 200, e nenhuma URL com `?id_token=`; o preflight passou a ser `OPTIONS /users/info`, sem query string. Evidência: [`evidence/ACH-08/after-fix-no-token.log`](evidence/ACH-08/after-fix-no-token.log).

### 4.4 ACH-03: Erro genérico ao cliente e validação do header

- **Causa raiz (dupla):** (1) cada rota capturava `Exception` e devolvia `str(e)` ao cliente; (2) as rotas que liam o token do header faziam `.split("Bearer ")[1]` sem validar a presença do header, o que estourava a exceção e, no `/hash`, virava HTTP 500.
- **Alteração** (`backend/endpoints.py`):
  - Helper `get_bearer_token()` (linhas 17-21): lê o header `Authorization`, exige o prefixo `Bearer ` e devolve o token ou `None`.
  - As quatro rotas que usam o header (`GET /users/info`, `/hash`, `POST /chats/<id>/messages`, `DELETE /chats/<id>`) chamam `get_bearer_token()` no início e, sem token, devolvem HTTP 401 com `"Missing or invalid Authorization header"`, antes do `try`.
  - Nenhum `except` devolve mais `str(e)`: cada um registra o detalhe no servidor com `app.logger.exception(...)` e devolve mensagem genérica, mantendo o código de status. `/hash` e `save_chat`, que usavam `jsonify` cru, passaram a usar `error_response`.
  - Rede de segurança global: `@app.errorhandler(Exception)` (linhas 129-134) loga qualquer exceção não tratada e devolve `"Internal server error"` (500); `HTTPException` (404, 405...) mantém o próprio status.
- **Solução:** o detalhe da exceção fica só no log do servidor e o cliente recebe mensagem genérica, o que resolve o HTTP 500 vazado do `/hash` e do `GET /users/info` sem header (causa raiz dupla).
- **Não alterado:** verificação de token, Firebase e `hashFunction`; só o tratamento de erro e a leitura do header mudaram.
- **Verificação local** (stack recriado com `docker compose up --build`, sem token real):
  - `POST /hash` e `GET /users/info` sem header → HTTP 401 genérico (antes: HTTP 500 com a exceção). Evidência: [`evidence/ACH-03/hash-no-auth-401.txt`](evidence/ACH-03/hash-no-auth-401.txt) e [`evidence/ACH-03/users-info-no-auth-401.txt`](evidence/ACH-03/users-info-no-auth-401.txt).
  - `POST /hash` com `Authorization: Basic abc` (sem `Bearer `) → HTTP 401, não mais `list index out of range`.
  - `GET /users/info` com `Bearer invalido` → HTTP 400 `Could not get user info`; o detalhe (`InvalidIdTokenError`) aparece só no log do servidor.
  - Exceção inesperada (`POST /users/create` com corpo `null`) → HTTP 500 `Internal server error`, sem stack trace no corpo; `GET /rota-inexistente` continua 404.
  - As rotas de chat sem header → HTTP 401; `POST /users/query` sem token segue HTTP 200 (ACH-09, não tocado).
- **Baseline:** validado com login real em 26/10/2026, com um `Bearer <token>` válido, `GET /users/info` (várias vezes) e `POST /users/info` retornaram HTTP 200, e nenhuma URL traz o token. Evidência: [`evidence/ACH-03/baseline-after-fix-200.log`](evidence/ACH-03/baseline-after-fix-200.log).
- **Efeito no ACH-11:** o errorhandler global já suprime a página de stack trace nas exceções de rota em modo debug, mas o debugger continua habilitado e o `/console` exposto; o ACH-11 segue aberto.

## 5. Hardening de segurança (Fase 5)

Melhorias aplicadas além das três correções de causa raiz da seção 4. Cada uma fecha ou endurece um ponto, e o baseline (login, salvar e carregar perfil em HTTP 200, app carregando, query respondendo) foi verificado depois de cada mudança. Todas em 26/10/2026.

### 5.1 Debug desligado (fecha o ACH-11)

- **O quê:** em `backend/endpoints.py`, `app.run(debug=True)` virou `app.run(debug=os.environ.get("FLASK_DEBUG") == "1")`, com debug desligado por padrão.
- **Por quê:** o modo debug servia o debugger do Werkzeug (console interativo em `/console`, RCE via PIN) e stack traces completos.
- **Verificação:** rodando `python endpoints.py` sem `FLASK_DEBUG`, o log mostra `Debug mode: off`, `GET /console` → 404 e uma exceção não exibe a página do debugger. No container (CLI do Flask) `/console` também → 404.
- **Fecha:** ACH-11.

### 5.2 CORS por allowlist

- **O quê:** `CORS(app)` virou `CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_headers=["Content-Type", "Authorization"])`.
- **Por quê:** o `CORS(app)` original refletia qualquer `Origin` (observação do recon). A allowlist restringe à origem do frontend e mantém o header `Authorization` permitido, sem o qual o fluxo do ACH-08 quebraria.
- **Verificação:** o preflight de `http://localhost:3000` retorna HTTP 200 com `Access-Control-Allow-Origin: http://localhost:3000` e `Access-Control-Allow-Headers: authorization, content-type`; a origem `http://other.example` não recebe `Access-Control-Allow-Origin`; o preflight de `POST /users/info` continua 200.

### 5.3 Rate limiting (endurece o ACH-09)

- **O quê:** `flask-limiter` (adicionado ao `requirements.txt`) com limites por IP nos endpoints que o backend expõe: `/users/create` 5/min, `/users/query` 30/min, `/hash` 60/min. O preflight `OPTIONS` é isento, para não quebrar o navegador.
- **Por quê:** o ACH-09 apontou um endpoint público sem limite de taxa.
- **Observação:** o login é feito pelo Firebase Auth no cliente e não passa pelo backend, então o backend limita apenas o que ele expõe; o Firebase tem proteção própria contra abuso de login. O rate limiting **não** corrige o fail-open da autenticação opcional do ACH-09 (token como Promise, rebaixamento silencioso), que segue aberto.
- **Verificação:** `/users/create` bloqueia na 6ª requisição em um minuto (HTTP 429); uma query e o salvar perfil não são bloqueados; `OPTIONS` não consome o limite.

### 5.4 Container não-root (fecha o ACH-01)

- **O quê:** instrução `USER` não-root nos três Dockerfiles: `appuser` (uid 10001) no `backend/Dockerfile`; usuário interno `node` (uid 1000) no `frontend/Dockerfile.dev` e no `frontend/Dockerfile`.
- **Por quê:** rodar como root amplifica o impacto de qualquer execução de código no container (ACH-01).
- **Segredos montados:** `config.json` e `credentials.json` são world-readable (0644), então o `appuser` os lê sem mudar o dono do volume.
- **Verificação:** `docker compose exec backend id` → `uid=10001(appuser)` e `frontend` → `uid=1000(node)`; os dois sobem, o backend lê os segredos e o baseline fica em 200. O `frontend/Dockerfile` (produção) recebeu `USER node`, mas não foi construído, porque o build de produção ainda falha nos erros de TypeScript herdados (seção 2.2); a mudança nele é só por consistência.
- **Fecha:** ACH-01.

### 5.5 Não feito agora: headers de segurança

CSP, HSTS, `X-Frame-Options` e `X-Content-Type-Options` protegem o frontend no navegador e ficam para a camada do Nginx (Fase 7), que é o lugar certo. Anotado aqui para não se perder.

## 6. Observabilidade e confiabilidade (SRE)

### 6.1 Instrumentação (Fase 6)

Adicionado ao `backend/endpoints.py`:

- **Logs estruturados em JSON (stdout)** com `python-json-logger`: uma linha JSON por requisição (`after_request`) com `request_id` (UUID por requisição), `method`, `path`, `route`, `status`, `latency_ms` e `asctime`. O log de acesso em texto do Werkzeug foi silenciado; a linha JSON é o registro da requisição. O `path` nunca inclui a query string, então nenhum token vaza.
- **Eventos de autenticação:** o helper `verify_uid` loga `auth` com `result: success` (e o `uid`, nunca o token) ou `result: failure` (motivo genérico `invalid_or_expired_token`, sem o token nem a mensagem do provedor, que pode ecoar o token). O `app.logger.exception` do ACH-03 também sai em JSON; para falha de autenticação o traceback é limpo (`raise AuthError() from None` tira a mensagem do Firebase da pilha).
- **`/health` (liveness):** `GET /health` → HTTP 200 `{"status": "ok"}`, sem autenticação e sem rate limit.
- **`/metrics` (Prometheus):** `prometheus-flask-exporter`, sem autenticação e sem rate limit, com contagem e latência de requisição por rota e status. **Em produção, `/metrics` deve ficar em rede interna, não exposto publicamente.**
- **Verificado (26/10/2026):** nenhum token nos logs (inclusive um token malformado enviado de propósito), `/health` e `/metrics` em 200, e o baseline intacto.

**Stack de observabilidade funcional (diferencial, ambiente de teste):** o `docker-compose.yml` sobe Prometheus (raspa `/metrics` de `backend1` e `backend2` direto, a cada 15s), Grafana (dashboard provisionado, seção 6.3) e Redis (store compartilhado do rate limiter, seção 6.4). Em produção seriam serviços gerenciados ou internos, não publicados.

### 6.2 SLIs e SLOs

Um SLI é a razão de eventos bons sobre o total de eventos válidos:

$$\text{SLI} = \frac{\text{eventos bons}}{\text{eventos válidos}}$$

**SLI 1, disponibilidade de `/users/info`:** proporção de requisições a `/users/info` com status menor que 500.

$$\text{SLI}_{\text{disp}} = \frac{\#\{\text{req a /users/info com status} < 500\}}{\#\{\text{req a /users/info}\}}$$

- **SLO:** 99,5% em 30 dias.
- **PromQL** (usa o `_count` do histograma, que tem o label `path`; o counter `flask_http_request_total` só tem `method` e `status`):

```promql
sum(rate(flask_http_request_duration_seconds_count{path="/users/info", status!~"5.."}[30d]))
/
sum(rate(flask_http_request_duration_seconds_count{path="/users/info"}[30d]))
```

**SLI 2, latência:** proporção de requisições servidas em menos de 300 ms.

$$\text{SLI}_{\text{lat}} = \frac{\#\{\text{req com duração} < 300\,\text{ms}\}}{\#\{\text{req}\}}$$

- **SLO:** 95% em 28 dias.
- **PromQL:**

```promql
sum(rate(flask_http_request_duration_seconds_bucket{le="0.3"}[28d]))
/
sum(rate(flask_http_request_duration_seconds_count[28d]))
```

- **Nota:** o `prometheus-flask-exporter` foi configurado com um bucket `0.3` no histograma (diferencial, Fase 7 parte 2), então a query casa exatamente com o SLO de 300 ms.

### 6.3 Dashboard (Grafana)

Painéis:

- **Taxa de requisição** por rota: `sum by (path) (rate(flask_http_request_duration_seconds_count[5m]))`.
- **Taxa de erro 5xx:** `(sum(rate(flask_http_request_duration_seconds_count{status=~"5.."}[5m])) or vector(0)) / sum(rate(flask_http_request_duration_seconds_count[5m]))` (o `or vector(0)` mostra 0 quando não há erro).
- **Latência p50/p95/p99:** `histogram_quantile(0.5, sum by (le) (rate(flask_http_request_duration_seconds_bucket[5m])))` (e idem para 0.95 e 0.99).
- **Os 2 SLIs vs SLO:** as razões de 6.2, com linhas de meta em 99,5% e 95%.

O dashboard é **provisionado e funcional** (diferencial, Fase 7 parte 2): datasource Prometheus e os painéis vêm de arquivos em `observability/grafana/provisioning/` e `observability/grafana/dashboards/coursesphere.json`, sem clique manual. O dashboard `CourseSphere SRE` (uid `coursesphere-sre`) aparece no Grafana em `localhost:3001`. Alertas ligados aos SLOs ficam para uma próxima parte.

### 6.4 Riscos de disponibilidade e resiliência

- **Backend como ponto único.** Um só container Flask, sem balanceador nem réplica, servido pelo servidor de desenvolvimento do Flask: se ele cai, a API cai. **Resiliência:** rodar sob um WSGI de produção (gunicorn) com múltiplos workers atrás do Nginx, usar `/health` como liveness/readiness e, depois, mais de uma réplica.
- **Rate limiter (Redis, diferencial).** O `flask-limiter` passou a usar o Redis como store compartilhado (`RATELIMIT_STORAGE_URI`), então o limite é **global** entre `backend1` e `backend2` (verificado: 5 requisições somadas passam e a 6ª dá HTTP 429, mesmo caindo na outra instância). **Ressalva honesta:** atrás do Nginx, `get_remote_address` enxerga o IP do proxy, então o limite hoje é global por endpoint para todos os clientes, não por cliente real; o limite por cliente exige confiar no `X-Forwarded-For` (ex.: `ProxyFix`). O Redis do ambiente de teste não tem persistência; em produção seria um Redis gerenciado.
- **Dependência do Firebase.** Auth e RTDB são externos; indisponibilidade ou latência do Firebase degrada login, perfil e chat. **Resiliência:** definir timeouts nas chamadas, manter o tratamento de erro genérico (ACH-03) e monitorar a taxa de erro e a latência das rotas que chamam o Firebase, com alerta ligado aos SLOs.

## 7. Infraestrutura e escalabilidade (Fase 7)

Parte 1: Nginx balanceando duas instâncias do backend, backend sob gunicorn e headers de segurança no Nginx. Tudo em 26/10/2026.

### 7.1 Desenho

```
navegador (localhost:3000, frontend Vite)
        │  chamadas de API para http://localhost:5000  (agora o Nginx)
        ▼
   Nginx  (publica 5000, round-robin, headers de segurança)
        ├──────────────► backend1:5000  (gunicorn, 1 worker)
        └──────────────► backend2:5000  (gunicorn, 1 worker)
```

- O frontend continua chamando `http://localhost:5000`, que agora é o Nginx, não o backend direto.
- `backend1` e `backend2` compartilham a mesma imagem e os mesmos volumes de segredo (somente leitura) e **não** publicam a 5000 no host; só o Nginx publica. No compose, os dois serviços saem de uma âncora YAML (`x-backend`) e diferem só pela variável `INSTANCE_NAME`.

### 7.2 Backend sob gunicorn

- O `CMD` do `backend/Dockerfile` trocou o servidor de desenvolvimento do Flask por `gunicorn --bind 0.0.0.0:5000 --workers 1 endpoints:app` (`gunicorn` adicionado ao `requirements.txt`). `WORKDIR` e os caminhos relativos não mudaram.
- **Um worker por instância**, para manter o `/metrics` simples (um processo por instância, sem modo multiprocess do Prometheus). A escala é horizontal, por mais instâncias atrás do Nginx. gunicorn roda como o usuário não-root `appuser` (Fase 5) e escuta na 5000 (porta alta, sem privilégio).

### 7.3 Nginx

- `upstream` com `backend1:5000` e `backend2:5000`, round-robin (padrão), em `nginx/nginx.conf`. O Nginx (`nginx:1.27-alpine`) escuta na 5000 publicada.
- Repassa `Host`, `Origin` e `Authorization` ao backend.
- **Não** adiciona headers de CORS: o backend já cuida do CORS (flask-cors, Fase 5), e um header duplicado quebraria o navegador. Verificado: a resposta tem exatamente um `Access-Control-Allow-Origin`.

### 7.4 Headers de segurança (os adiados da Fase 5)

Adicionados no Nginx (`add_header ... always`), apropriados para uma API JSON:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Content-Security-Policy: default-src 'none'`

O **HSTS** (`Strict-Transport-Security`) entra junto com a terminação TLS, que ainda não existe nesta parte.

### 7.5 Como provar a distribuição

Cada instância se identifica: o backend adiciona o header de resposta `X-Backend-Instance` (valor de `INSTANCE_NAME`) e inclui o campo `instance` em cada linha de log JSON. Então:

```bash
for i in $(seq 1 20); do curl -s -i localhost:5000/health | grep -i ^X-Backend-Instance; done
```

alterna `backend1` e `backend2`. Evidências em [`evidence/infra/`](evidence/README.md): `load-balancing.txt` (20 requisições, 10/10), `backend-instances.log` (logs JSON das duas instâncias) e `security-headers.txt` (headers via Nginx). O header `X-Backend-Instance` serve para demonstrar o balanceamento; em produção pode ser removido para não expor a topologia.

### 7.6 Verificações (26/10/2026)

- A stack sobe (`backend1`, `backend2`, `nginx`, `frontend`).
- `curl localhost:5000/health` → HTTP 200 `{"status":"ok"}` com os quatro headers de segurança e um só `Access-Control-Allow-Origin`.
- 20 requisições a `/health` → 10 em `backend1` e 10 em `backend2` (round-robin).
- Via Nginx: `POST /users/query` → 200, `GET /users/info` sem token → 401, com `Bearer` inválido → 400; `frontend` em `localhost:3000` → 200.
- Preflight de `localhost:3000` → 200 com um único `Access-Control-Allow-Origin`.
- Nenhum token nas evidências nem nos logs das instâncias.
- **Pendente:** o fluxo completo de login no navegador (login + salvar perfil + query) deve ser reconfirmado pelo usuário, já que o endpoint `localhost:5000` passou a ser o Nginx.

### 7.7 A fazer na Fase 7 (próximas partes)

Parte 2 (diferencial) concluída: Prometheus + Grafana provisionado + Redis para o rate limiter + bucket de 0,3 s (ver seção 6). Falta: terminação TLS + HSTS, alertas ligados aos SLOs, rate limit por cliente real (`X-Forwarded-For`/`ProxyFix`) e build de produção do frontend (hoje falha nos erros de TypeScript herdados).

### 7.8 CI de segurança (GitHub Actions, diferencial)

`.github/workflows/security.yml` roda SAST e SCA a cada `push` e `pull_request`, automatizando o que foi feito manual na Fase 2. Jobs:

- **Semgrep (SAST)** em `backend/` e `frontend/src`, com os pacotes `p/python`, `p/flask` e `p/javascript`; publica o SARIF na aba Security e como artefato.
- **Bandit (SAST)** no backend.
- **pip-audit (SCA)** nas dependências do backend (`backend/requirements.txt`).
- **npm audit (SCA)** no frontend, com `--audit-level=high`.

**Modo report:** os jobs usam `continue-on-error`, então não bloqueiam o merge. A escolha é deliberada: o projeto tem achados herdados já rastreados (ACH-xx) e vulnerabilidades transitivas no frontend; bloquear deixaria a CI sempre vermelha. Para virar um gate bloqueante, basta remover o `continue-on-error` (ou usar `--error` no Semgrep). Nenhum job usa segredos, sobe a aplicação ou toca o Firebase: só instalam as ferramentas e analisam os arquivos do repositório.

**Dependabot:** `.github/dependabot.yml` abre PRs semanais de atualização para `pip` (backend), `npm` (frontend), `github-actions` e `docker` (imagem base do backend).

Validado localmente, em containers, que cada comando roda: Semgrep gera SARIF válido, pip-audit não achou vulnerabilidade nas bibliotecas do backend, Bandit lista os achados conhecidos e o npm audit sinaliza as dependências `high` do frontend. A CI em si só executa depois do push no GitHub.

### 7.9 Teste de autorização das regras do RTDB (diferencial)

`security/rules-tests/` tem um teste automatizado das regras do Realtime Database, com o **Firebase Local Emulator Suite** e o `@firebase/rules-unit-testing`. Se as regras voltarem ao modo de teste aberto, o teste quebra. Ele carrega o `database.rules.json` no emulador e afirma que o acesso de cliente é **negado** (leitura e escrita, não autenticado e autenticado), já que as regras são deny-all e todo acesso legítimo passa pelo backend via Admin SDK.

- **Como rodar:** `cd security/rules-tests && npm install && npm run emulate` (que é `firebase emulators:exec --project demo-coursesphere --only database "npm test"`).
- **Offline e sem segredos:** roda só no emulador, com um projeto `demo-*`; não toca o projeto real, não usa `credentials.json` e precisa apenas de Node e Java (o emulador). Dá para pôr na CI.
- **É um teste de unidade das regras**, diferente da verificação por REST do ACH-12 (seção 4.2), que checa a regra já publicada no projeto. Se as regras passarem a ser por usuário (`auth.uid === $uid`), o teste já tem o esqueleto para afirmar que um usuário acessa só o próprio nó. Rodado em 27/10/2026, os 4 testes passam: [`evidence/ACH-12/rules-test-pass.txt`](evidence/ACH-12/rules-test-pass.txt).

## 8. Recomendações priorizadas

_A preencher._
