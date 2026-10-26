# Relatório Técnico de Segurança e Confiabilidade - CourseSphere

> **Status:** rascunho preenchido de forma incremental. Fase 0 (ambiente isolado e baseline) concluída em 23/10/2026; na Fase 2, os achados ACH-01, 03, 08, 09, 10 e 11 foram formalizados em 24/10/2026 e o ACH-12 em 25/10/2026, quando também foram evidenciadas as reproduções do ACH-03 e do ACH-09. Na Fase 4, o ACH-12 foi corrigido e validado em 25/10/2026, e o ACH-08 foi corrigido em 25/10/2026 e validado em 26/10/2026. As seções 1, 5 e 6 são placeholders, e a seção 4 lista as correções.
> O documento não contém segredos. Prints e logs ficam em [`evidence/`](evidence/README.md). O inventário de rotas que abre a Fase 1 está em [`recon.md`](recon.md).

## 1. Sumário executivo

_A preencher ao final do trabalho._

## 2. Escopo e metodologia

### 2.1 Alvo

CourseSphere é uma aplicação web que ajuda estudantes a encontrar os melhores cursos (*courses*) para se matricular (descrição do `README.md`).

| Camada | Tecnologia | Observações |
|---|---|---|
| Backend (`backend/`) | Python, Flask, Flask-CORS | 7 rotas HTTP em `endpoints.py`. |
| Identidade e dados | Firebase Authentication e Realtime Database (RTDB), via `firebase_admin` | `backend/firebase.py`. Perfil em `users/{uid}/info`; chats em `users/{uid}/chats/{chat_id}`. |
| SQLite | `backend/db.py` e `backend/blueprints/courses.py` | Código presente, mas não exercitado em runtime: o blueprint não está registrado (`endpoints.py:11`, comentado) e não há arquivo SQLite no repositório. |
| OpenAI | Cliente criado no import de `backend/main.py:22` (importado por `endpoints.py:5` por causa de `hashFunction`) | Stub em runtime: nenhuma chamada à API é feita. O `QueryManager` devolve resposta fixa (`query_manager.py:89` e `:104`), e `get_query_details` só roda quando `main.py` é executado como script (`main.py:60-62`). |
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
| 3 | ACH-03 | Vazamento de detalhe de erro ao cliente | 5.3 | Médio | Aberto |
| 4 | ACH-11 | Modo debug do Flask habilitado | 7.4 | Alto (inerente) | Aberto, latente no container; quick win |
| 5 | ACH-01 | Container executa como root | Não atribuído | Baixo | Aberto |
| 6 | ACH-09 | `/users/query`: autenticação opcional quebrada (fail-open) | Não atribuído | Baixo | Latente; hardening |
| 7 | ACH-10 | SQL montado por f-string (blueprint inativo) | 7.5 | Alto (inerente) | Latente e não funcional |
| — | ACH-04 | Endpoint placeholder `/theactualbackendlink` | A definir | Baixo (preliminar) | Aberto |
| — | ACH-05 | Cadastro aceita senha de 6 caracteres | A definir | A avaliar | A avaliar |
| — | ACH-06 | URL do RTDB fixa no código | A definir | Menor (preliminar) | Corrigido e validado |
| — | ACH-07 | Falha silenciosa no cliente | A definir | A definir | Aberto |
| — | ACH-02 | Consolidado no ACH-03 | — | — | — |

Ordem por risco prático: primeiro o ACH-12, crítico (corrigido e validado em 25/10/2026); depois o que se manifesta no ambiente fornecido (ACH-08, corrigido e validado, e ACH-03, por score), o que depende do modo de execução (ACH-11, quick win), o hardening (ACH-01 e ACH-09, ambos de severidade Baixa, sendo o ACH-09 latente) e, por último, o ACH-10, latente e não funcional (blueprint inativo, e `db.py` impede o retorno dos dados) apesar do score inerente alto. ACH-04 a ACH-07 ainda não têm CVSS e ficam fora do ranking.

Severidade "inerente" é o score do código como escrito, assumindo as condições do achado (ACH-10: blueprint ativado; ACH-11: execução por `python endpoints.py`). O ambiente fornecido não está nessas condições.

### 3.1 ACH-01 — Container executa como root

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
- **Situação:** Aberto.

### 3.2 ACH-02 — Consolidado no ACH-03

O comportamento de `POST /hash` sem o header `Authorization` (HTTP 500 com a exceção interna) passou a ser o caso principal do ACH-03. O ID ACH-02 não é mais usado.

### 3.3 ACH-03 — Vazamento de detalhe de erro ao cliente (inclui o antigo ACH-02)

- **CVSS 3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N` = **5.3 (Médio)**. Justificativa: detalhe interno de exceção devolvido ao cliente, trivialmente disparável e útil para reconhecimento.
- **CWE:** CWE-209 (mensagem de erro com informação sensível) e CWE-20 (validação de entrada imprópria).
- **OWASP Top 10 2021:** A05:2021 (configuração incorreta de segurança) e A09:2021 (falhas de registro e monitoramento de segurança).
- **Descrição:** as 7 rotas de `endpoints.py` capturam `Exception` e devolvem o texto da exceção no corpo da resposta (HTTP 400; HTTP 500 em `/hash`). O texto vem de Python e do `firebase_admin`, que `firebase.py` reencapsula com `str(e)`, e não é filtrado. O caso mais claro é `POST /hash`: a rota faz `request.headers.get('Authorization').split('Bearer ')[1]` sem verificar se o header existe nem se tem o prefixo `Bearer `. Sem o header, `.split` levanta `AttributeError`; com o header sem o prefixo, o índice `[1]` levanta `IndexError`. O `except Exception` devolve HTTP 500 com `{"error": str(e)}`. O mesmo trecho existe em `POST /chats/<chat_id>/messages`, em `DELETE /chats/<chat_id>` e, desde a correção do ACH-08, em `GET /users/info`; nessas rotas a resposta é HTTP 400.
- **Localização:** `backend/endpoints.py:28, 53, 63, 72, 83, 94, 104` (`str(e)` nas 7 rotas); `backend/endpoints.py:77` (extração do token em `/hash`, tratada em `:82-83`) e `:58`, `:88`, `:99` (mesmo trecho em `GET /users/info` e nas rotas de chat); `backend/firebase.py:27, 36, 44, 52, 61, 78, 93, 109, 124, 138, 156, 164` (reencapsulamento com `str(e)`).
- **Reprodução:**
  1. Com o ambiente no ar, enviar `POST /hash` sem o header `Authorization`: `curl -i -X POST http://localhost:5000/hash`.
  2. Observar HTTP 500 e, no corpo, `{"error":"'NoneType' object has no attribute 'split'"}`.
  3. Repetir com `-H 'Authorization: Basic abc'` (sem o prefixo `Bearer `) e observar HTTP 500 com `list index out of range`.
  4. Nas demais rotas, `GET /users/info?id_token=x` retorna HTTP 400 com `Error getting user info: Error verifying ID token: Wrong number of segments in token: b'x'`, que inclui o valor enviado.
- **Evidência:** [`evidence/ACH-03/hash-no-auth-500.txt`](evidence/ACH-03/hash-no-auth-500.txt), capturada em 25/10/2026 (passos 1 e 2: HTTP 500 com a exceção interna). Os passos 3 e 4 não foram capturados.
- **Impacto de negócio:** expõe internals (bibliotecas, estrutura do código) a um cliente não autenticado, o que facilita um ataque dirigido.
- **Causa raiz:** exceções capturadas de forma genérica, com `str(e)` devolvido ao cliente, e entrada não validada no `/hash`.
- **Situação:** Aberto.

### 3.4 ACH-04 — Endpoint placeholder `/theactualbackendlink` chamado pelo frontend

- **Localização:** `frontend/src/components/UserChats/UserChats.tsx:25` (chamada), `:33-35` (erro quando a resposta não é OK) e `:41` (toast "Failed to fetch your chats"). O componente é renderizado em `frontend/src/pages/home/Home.tsx:9`, na rota `/` (`App.tsx:43`).
- **Descrição:** `UserChats` faz `GET http://127.0.0.1:5000/theactualbackendlink` assim que há usuário autenticado. A rota não existe em `backend/endpoints.py` (rotas nas linhas 16 a 97) nem em `backend/blueprints/`, e a string não aparece em nenhum outro arquivo do repositório.
- **Observado:** o log do backend registra `OPTIONS /theactualbackendlink` com HTTP 404 e nenhum `GET` correspondente; o frontend mostra o toast de erro. Um `GET` direto à rota também retorna 404.
- **Evidência:** [`evidence/baseline/backend-baseline.log`](evidence/baseline/backend-baseline.log) (linhas `OPTIONS /theactualbackendlink` com HTTP 404, sem `GET` correspondente).
- **Classificação preliminar:** qualidade de código / baixo.

### 3.5 ACH-05 — Cadastro aceita senha de 6 caracteres (fraco, a avaliar)

- **Localização:** `backend/endpoints.py:21-24` (única validação: e-mail e senha não vazios) e `frontend/src/pages/signup/SignUp.tsx:16` (o botão só exige campos não vazios).
- **Descrição:** no baseline, o cadastro aceitou uma senha numérica sequencial de 6 caracteres. Nem backend nem frontend aplicam política de senha além de "não vazia". O único limite efetivo vem do `firebase_admin`, que exige no mínimo 6 caracteres (`firebase_admin._auth_utils.validate_password`, verificado na versão instalada na imagem do backend).
- **Observação:** 6 caracteres é o mínimo padrão do Firebase Authentication. O item só vira achado se houver política esperada acima disso. A política de senha configurável no projeto Firebase não foi verificada.
- **Severidade:** a definir na Fase 2.

### 3.6 ACH-06 — URL do RTDB fixa no código, acoplada ao projeto do autor do repositório (corrigido)

- **Localização:** `backend/firebase.py:5` no código original (commit `68e6a44`): `database_url` com a URL do RTDB do projeto do autor, passada a `initialize_app` na linha seguinte. Era a única ocorrência da URL no repositório.
- **Descrição:** a URL não era configurável e apontava para um projeto Firebase diferente do projeto das credenciais usadas no ambiente de teste. Na primeira execução do baseline, as rotas que dependem do RTDB (`POST` e `GET /users/info`) retornaram HTTP 400, enquanto as que só usam o Authentication (`POST /users/create`, `POST /hash`) retornaram 200. O log dessa execução não foi preservado.
- **Correção:** a URL passou a ser lida de `FIREBASE_DB_URL`, sem valor padrão (seção 4.1).
- **Status:** corrigido e validado em 23/10/2026: com credenciais reais, `POST /users/info` e `GET /users/info` retornam HTTP 200.
- **Evidência:** [`evidence/baseline/backend-baseline.log`](evidence/baseline/backend-baseline.log) (linhas `POST /users/info` e `GET /users/info` com HTTP 200).
- **Classificação preliminar:** configuração / menor.

### 3.7 ACH-07 — Falha silenciosa no cliente: a interface exibe sucesso com HTTP 400

- **Localização:** `frontend/src/api.ts:168-170` (`saveProfileChanges`: o `.then` exibe "Successfully saved your information!" sem verificar `response.ok`).
- **Descrição:** `fetch` só rejeita a promessa em falha de rede; respostas HTTP 4xx e 5xx resolvem normalmente. Como o `.then` não examina o status, o toast de sucesso aparece mesmo quando o backend rejeita a gravação, e o `.catch` (linhas 171-173) só trata falha de rede. O erro do backend fica mascarado para o usuário.
- **Mesmo padrão em outros fluxos** (sem verificação de `response.ok`): cadastro, em que `createUser` devolve o corpo da resposta (`api.ts:13-24`) e `performSignup` segue para o login (`:31-37`); leitura do perfil, em que `setProfileInfoIfLoggedIn` trata o corpo de erro como dados do perfil e não preenche nenhum campo, sem aviso (`:91-99`); e a query, em que `fetchCourseSphereResponse` exibe "Successfully retrieved bot response!" (`:195-197`). Os fluxos de chat e `/hash` verificam `response.ok` (`:248`, `:274`, `:293`, `:314`).
- **Observado:** na primeira execução do baseline, antes da correção do ACH-06, `POST /users/info` retornou HTTP 400 e a interface exibiu o toast de sucesso. O log dessa execução não foi preservado.
- **Severidade:** a definir na Fase 2.

### 3.8 ACH-08 — `id_token` na URL de `GET /users/info` e registrado no log do Flask

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

### 3.9 ACH-09 — Autenticação opcional quebrada em `/users/query` (fail-open e sem limite de taxa)

- **Classificação:** Baixo, latente. CVSS 3.1 não atribuído. Justificativa: o endpoint é público por desenho e hoje devolve só um stub; os defeitos são de hardening e ganham peso quando a lógica for concluída. O item foi reenquadrado: antes era tratado como ausência de autenticação (CWE-306, 5.3).
- **CWE:** CWE-636 (falha aberta, em vez de falhar de forma segura).
- **OWASP Top 10 2021:** A07:2021 (falhas de identificação e autenticação).
- **Descrição:** `/users/query` é público por desenho: `fetchCourseSphereResponse` não chama `ensureUserLoggedIn`, ao contrário das demais chamadas autenticadas do `api.ts` (`:87, :144, :225, :258, :280, :300`); o `QueryManager` prevê consulta sem usuário (`query_manager.py:101`); e a leitura do usuário é opcional (`Firebase.try_get_user_info`). O problema real é que a autenticação opcional não funciona: (1) o frontend envia `idToken` como Promise não aguardada e com nome diferente do que o backend lê (`id_token`), então nem um usuário logado é reconhecido; (2) um token inválido ou ausente é rebaixado em silêncio para anônimo, porque `try_get_user_info` devolve `None` em qualquer falha e a rota responde 200 (fail-open); (3) o endpoint público não tem limite de taxa, o que é latente porque o handler é um stub. O teste `hasUserData = (self.user_data is not None)` (`query_manager.py:101`) nunca é falso, porque `:47` sempre cria o objeto de usuário, mesmo com usuário ausente: o ramo anônimo previsto no código não é detectado.
- **Localização:** `backend/endpoints.py:65-72` (rota; `:69` lê `id_token`); `backend/firebase.py:64-68` (`try_get_user_info` devolve `None` em qualquer falha); `backend/query_manager.py:47` e `:101`; `frontend/src/api.ts:183-186` (função sem `ensureUserLoggedIn`, `idToken` sem `await` e com nome divergente) e `:191` (header `Authorization`).
- **Reprodução:**
  1. Com o ambiente no ar, enviar `POST /users/query` com um `id_token` inválido no corpo: `curl -i -X POST http://localhost:5000/users/query -H 'Content-Type: application/json' -d '{"query":"test","id_token":"invalido"}'`.
  2. Observar HTTP 200 com a resposta fixa `"Fake implementation"`: o token inválido não é rejeitado (fail-open). O mesmo ocorre sem token e com um header `Authorization` inválido.
  3. No navegador, na aba Rede, observar a chamada feita pelo frontend logado: o corpo traz `idToken: {}` (a Promise serializada) e nenhum `id_token`, e o header vai como `Bearer [object Promise]`. A serialização foi verificada isoladamente em Node 20.
- **Evidência:** [`evidence/ACH-09/users-query-no-auth.txt`](evidence/ACH-09/users-query-no-auth.txt), capturada em 25/10/2026 (sem token e sem `Authorization`, HTTP 200). Ela continua válida: mostra que o endpoint responde a anônimos, o comportamento público esperado. O fail-open com token inválido foi verificado em teste local isolado e não tem arquivo de evidência.
- **Impacto de negócio:** usuários logados são tratados como anônimos e um token inválido não gera erro. Quando a lógica passar a usar dados do usuário, a personalização não funcionará e as falhas de autenticação ficarão invisíveis; sem limite de taxa, um endpoint público fica exposto a abuso quando o handler passar a executar trabalho caro.
- **Causa raiz:** o contrato de autenticação opcional não está implementado de ponta a ponta: o cliente envia o token de forma errada e o servidor trata qualquer falha como anônimo.
- **Situação:** Latente. Hardening, fora do conjunto de correções prioritárias.

### 3.10 ACH-10 — SQL montado por f-string em `blueprints/courses.py` (blueprint inativo)

- **CVSS 3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N` = **7.5 (Alto, inerente)**. Justificativa: concatenar entrada em SQL permite ler o banco; o `execute` do `sqlite3` roda uma única instrução, então não há escrita. O score vale para o código como escrito: hoje o blueprint é inalcançável (ver pré-condições) e os dados são de cursos, públicos.
- **CWE:** CWE-89 (injeção de SQL).
- **OWASP Top 10 2021:** A03:2021 (injeção).
- **Descrição:** os valores vindos da URL são interpolados por f-string no texto SQL e executados por `cursor.execute(query)`, sem parametrização. Nas rotas com parâmetro `string` (`semester`, `department` e `instructor`) o valor fica entre aspas simples. As rotas `<int:...>` usam o mesmo padrão, mas o conversor do Flask limita o valor a dígitos. Confirmado por Semgrep (`tainted-sql-string`, 6 hits) e Bandit (B608, 6 hits). As três rotas `string` compartilham a mesma regra de URL, e na prática só `semester` é alcançada ([`recon.md`](recon.md), seção 2).
- **Localização:** `backend/blueprints/courses.py:80, 96, 112` (rotas `string`) e `:30, 47, 64` (rotas `int`); `backend/db.py:9` (`cursor.execute(query)`).
- **Pré-condições de ativação (hoje nenhuma é atendida):**
  1. O blueprint ser importado e registrado em `endpoints.py`, onde hoje só existe o comentário `#app.register_blueprint(courses_bp)` (linha 11).
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

### 3.11 ACH-11 — Modo debug do Flask habilitado no ponto de entrada

- **CVSS 3.1:** `CVSS:3.1/AV:L/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H` = **7.4 (Alto, inerente)**. Justificativa: `app.run(debug=True)` expõe o debugger interativo do Werkzeug (execução de código potencial, protegida por PIN, daí `AC:H`) e stack traces. No modo padrão (`python endpoints.py`) o servidor escuta só em `127.0.0.1`, porque `app.run` não recebe `host`, então o vetor é local. Se o processo for exposto (bind em `0.0.0.0` ou proxy), o vetor sobe para `AV:N` e o score para 8.1. O container do projeto roda pelo CLI do Flask com debug desligado; o score reflete o modo padrão do app.
- **CWE:** CWE-489 (código de depuração ativo) e CWE-215 (informação sensível em código de depuração).
- **OWASP Top 10 2021:** A05:2021 (configuração incorreta de segurança).
- **Descrição:** `endpoints.py` termina com `app.run(debug=True)` dentro de `if __name__ == '__main__'`. Executado assim, o Flask liga o debugger do Werkzeug: uma exceção não tratada devolve a página com o stack trace completo, e o console interativo fica protegido por PIN (o log mostra `Debugger PIN`). Confirmado por Semgrep (`debug-enabled`) e Bandit (B201, HIGH).
- **Localização:** `backend/endpoints.py:108` (dentro do bloco `__main__` de `:107-108`).
- **Reprodução:**
  1. A partir de `backend/`, com as dependências, `config.json`, `credentials.json` e `FIREBASE_DB_URL` presentes, executar `python endpoints.py` (modo padrão do app). O log mostra `Debug mode: on` e `Debugger is active!`.
  2. Provocar uma exceção não tratada: enviar `POST /users/create` com o corpo JSON `null` (a leitura do JSON fica fora do `try`, `endpoints.py:18-20`).
  3. Observar a página do debugger do Werkzeug, com o stack trace completo (HTTP 500).
  4. Repetir o mesmo pedido no container fornecido (CLI do Flask, `Debug mode: off`) e observar apenas `Internal Server Error`.
- **Evidência:** Semgrep e Bandit em [`evidence/tools/`](evidence/tools/README.md); o log do container fornecido mostra `Debug mode: off` ([`evidence/baseline/backend-baseline.log`](evidence/baseline/backend-baseline.log)).
- **Impacto de negócio:** exposição de internals e, no pior caso, execução de código no servidor.
- **Causa raiz:** debug ligado no código, sem controle por configuração.
- **Situação:** Aberto, latente: o container fornecido não é afetado. Quick win: o ajuste é pontual, na linha 108 de `endpoints.py`.

### 3.12 ACH-12 — Regras do Realtime Database abertas (modo de teste)

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

### 4.1 ACH-06 — URL do RTDB externalizada

- **Alteração:** `backend/firebase.py` (linhas 6-11) lê a URL de `FIREBASE_DB_URL`, sem valor padrão, e levanta `RuntimeError` com mensagem explícita se a variável estiver ausente ou vazia. O `docker-compose.yml` define a variável no serviço `backend` com o `databaseURL` de `frontend/src/firebaseConfig.ts`, que é a fonte única do valor.
- **Verificação local** (container sem rede, com credencial de teste descartável): sem a variável, ou com ela vazia, o backend não sobe e exibe a mensagem de erro; com a variável, sobe e o `firebase_admin` usa exatamente o valor informado. O valor do `docker-compose.yml` é igual ao `databaseURL` de `frontend/src/firebaseConfig.ts`.
- **Validação:** em 23/10/2026, com credenciais reais, `POST /users/info` e `GET /users/info` retornaram HTTP 200 ([`evidence/baseline/backend-baseline.log`](evidence/baseline/backend-baseline.log)).

### 4.2 ACH-12 — Regras do Realtime Database restritas

- **Alteração:** dois arquivos novos na raiz do repositório. `database.rules.json` define `.read` e `.write` como `false`, e `firebase.json` aponta para ele (`database.rules`). As regras passam a ser versionadas.
- **Por que `false` e não regras por usuário:** o frontend não lê nem escreve no RTDB. Ele importa `getDatabase` (`api.ts:4`, `Nav.tsx:20`, `UserChats.tsx:4`) e cria a variável `database` (`api.ts:9`, `Nav.tsx:24`, `UserChats.tsx:10`), mas nunca a usa: não há chamada a `ref`, `get`, `set` nem `onValue` em `frontend/src`. Todo acesso ao RTDB passa pelo backend (`firebase.py`), que usa o Admin SDK e ignora as regras (comportamento documentado do Firebase). Regras por `auth.uid === $uid` em `users/$uid` só seriam necessárias se o frontend passasse a acessar o banco direto.
- **Aplicação:** publicada no projeto Firebase em 25/10/2026; as regras lidas do projeto com a conta de serviço são exatamente `.read: false` e `.write: false`. Para reaplicar: `firebase deploy --only database --project <id-do-projeto>` com o Firebase CLI autenticado, ou colando o conteúdo de `database.rules.json` no console (Realtime Database, aba Regras).
- **Verificação pós-aplicação:** (1) a leitura sem credenciais é negada com HTTP 401 (`Permission denied`), em [`evidence/ACH-12/unauth-denied-after-lock.txt`](evidence/ACH-12/unauth-denied-after-lock.txt); (2) o fluxo do baseline continua funcionando, com `GET /users/info` e `POST /users/info` retornando HTTP 200, em [`evidence/ACH-12/baseline-after-lock.txt`](evidence/ACH-12/baseline-after-lock.txt).
- **Validação local:** os dois arquivos são JSON válido e `firebase.json` aponta para um arquivo existente.

### 4.3 ACH-08 — Token no header `Authorization`

- **Causa raiz:** credencial na query string de um `GET`, que o log de acesso do Flask registra junto com a URL.
- **Alteração:**
  - `backend/endpoints.py:56-58`: `get_user_info` passou a ler o token de `request.headers.get("Authorization").split("Bearer ")[1]`, como as rotas `/hash` e `/chats/*`. A função não tem chamador interno, então a assinatura ficou `def get_user_info():`, sem o parâmetro `id_token=None` e sem o comentário sobre outro contexto. O tratamento de erro (`str(e)`) não mudou, porque é o ACH-03.
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

## 5. Confiabilidade (SRE)

_A preencher._

## 6. Recomendações priorizadas

_A preencher._
