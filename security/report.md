# Relatório Técnico de Segurança e Confiabilidade - CourseSphere

> **Status:** rascunho preenchido de forma incremental. Fase 0 (ambiente isolado e baseline) concluída em 23/10/2026; as seções 1, 5 e 6 são placeholders e a seção 4 lista as correções aplicadas até agora.
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
- O backend sobe pelo CLI do Flask, então o `app.run(debug=True)` de `endpoints.py:108` não é executado e o debug fica desligado no container.
- O frontend usa o servidor de desenvolvimento porque o build de produção (`frontend/Dockerfile`) falha com 15 erros do compilador TypeScript (`tsc -b`) no código original.
- **Firebase.** O candidato usa um projeto Firebase próprio, para poder testar e corrigir o controle de acesso nas fases seguintes. O frontend (`frontend/src/firebaseConfig.ts`), a credencial de serviço do backend e a URL do RTDB do backend apontam para esse projeto.
- **URL do RTDB.** O código original fixava a URL em `backend/firebase.py`, apontando para o projeto Firebase do autor do repositório (commit `68e6a44`), o que causou HTTP 400 nas rotas de perfil na primeira execução do baseline. A URL agora vem da variável de ambiente `FIREBASE_DB_URL`, definida no serviço `backend` do `docker-compose.yml` com o `databaseURL` de `frontend/src/firebaseConfig.ts`. Ver ACH-06 e a seção 4.

### 2.3 Metodologia

- Análise manual guiada pelo OWASP Web Security Testing Guide (WSTG).
- SAST: Semgrep e Bandit.
- SCA: pip-audit (backend) e npm audit (frontend).
- DAST: OWASP ZAP.
- Classificação alinhada ao OWASP Top 10 2021; severidade por CVSS 3.1.

As ferramentas acima são o plano de trabalho e ainda não foram executadas. Os achados da seção 3 vêm de leitura de código e de observação do ambiente de baseline.

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
- **Resposta da query sem conteúdo.** O `QueryManager` é um stub e devolve a string `"Fake implementation"`. O frontend lê `result.botResponse` (`api.ts:198`), campo que não existe nessa resposta e fica indefinido.
- **Toast de sucesso sem checar `response.ok`.** `api.ts:167-169` exibe "Successfully saved your information!" qualquer que seja o status HTTP, o que escondeu o HTTP 400 da primeira execução. Ver ACH-07.

Alterações feitas na Fase 0 em relação ao repositório original:

- `backend/main.py`: a chamada à OpenAI e o `print` do fim do módulo foram para `if __name__ == "__main__":` (linhas 60-62). Assim, `from main import hashFunction` (`endpoints.py:5`) não dispara chamada de rede no import. As funções não foram alteradas.
- `frontend/Dockerfile`: base trocada de `node:16-alpine` para `node:20-alpine`, porque o Vite 5 exige Node 18 ou superior.
- `frontend/src/firebaseConfig.ts`: valores do projeto Firebase do candidato.
- `.gitignore`: inclusão de `credentials.json`.
- `backend/firebase.py` e `docker-compose.yml`: a URL do RTDB passou a vir da variável de ambiente `FIREBASE_DB_URL` (ACH-06). Feita depois da primeira execução do baseline, que expôs o HTTP 400, e antes da validação final.
- Arquivos novos: `docker-compose.yml`, `backend/Dockerfile`, `backend/.dockerignore`, `backend/config.example.json`, `frontend/Dockerfile.dev`.

## 3. Achados

Rascunhos da Fase 0. Cada item traz a descrição factual e a localização no código, sem exploração. Esta versão não tem CVSS; a severidade é definida na Fase 2, e ACH-04 e ACH-06 trazem só uma classificação preliminar. As evidências de cada achado entram em `security/evidence/<ID>/`.

### 3.1 ACH-01 — Container do backend executa como root

- **Localização:** `backend/Dockerfile` (sem instrução `USER`; o processo sobe no `CMD`, linha 16).
- **Descrição:** a imagem do backend não define usuário não-root. O campo `User` da imagem construída está vazio, ou seja, o Flask roda como root dentro do container.
- **Observação:** o `Dockerfile` do backend foi criado na Fase 0 (o repositório original não tinha). `frontend/Dockerfile` e `frontend/Dockerfile.dev` também não têm `USER`, e a imagem do frontend também roda como root.
- **Severidade:** a definir na Fase 2.

### 3.2 ACH-02 — `POST /hash` sem header `Authorization` retorna HTTP 500 com exceção interna

- **Localização:** `backend/endpoints.py:77` (extração do token) e `:82-83` (tratamento da exceção).
- **Descrição:** a rota faz `request.headers.get('Authorization').split('Bearer ')[1]` sem verificar se o header existe nem se tem o prefixo `Bearer `. Sem o header, `get` devolve `None` e `.split` levanta `AttributeError`. Com o header sem o prefixo, o índice `[1]` levanta `IndexError`. O `except Exception` da rota devolve HTTP 500 com `{"error": str(e)}`.
- **Observado:** requisição sem o header: HTTP 500 e corpo com `'NoneType' object has no attribute 'split'`. Header sem o prefixo `Bearer `: HTTP 500 e corpo com `list index out of range`.
- **Observação:** o mesmo trecho existe em `endpoints.py:88` (`POST /chats/<chat_id>/messages`) e `:99` (`DELETE /chats/<chat_id>`). Nessas rotas o `except` devolve HTTP 400 (linhas 94 e 104), com a mesma exceção dentro da mensagem.
- **Severidade:** a definir na Fase 2.

### 3.3 ACH-03 — Respostas de erro devolvem `str(e)` ao cliente

- **Localização:** `backend/endpoints.py:28, 53, 63, 72, 83, 94, 104`, uma por rota (as 7 rotas). As mensagens passam por `backend/firebase.py`, que reencapsula cada exceção com `str(e)` (linhas 27, 36, 44, 52, 61, 78, 93, 109, 124, 138, 156, 164, na numeração atual).
- **Descrição:** todas as rotas capturam `Exception` e devolvem o texto da exceção no corpo da resposta (HTTP 400; HTTP 500 em `/hash`). O texto vem de Python e do `firebase_admin` e não é filtrado.
- **Observado:** `GET /users/info` com `id_token` inválido: HTTP 400 e corpo `Error getting user info: Error verifying ID token: Wrong number of segments in token: b'x'`, que inclui o valor enviado. `POST /users/create` com senha de 5 caracteres: HTTP 400 e a mensagem de validação do `firebase_admin`.
- **Severidade:** a definir na Fase 2.

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

- **Localização:** `frontend/src/api.ts:167-169` (`saveProfileChanges`: o `.then` exibe "Successfully saved your information!" sem verificar `response.ok`).
- **Descrição:** `fetch` só rejeita a promessa em falha de rede; respostas HTTP 4xx e 5xx resolvem normalmente. Como o `.then` não examina o status, o toast de sucesso aparece mesmo quando o backend rejeita a gravação, e o `.catch` (linhas 170-172) só trata falha de rede. O erro do backend fica mascarado para o usuário.
- **Mesmo padrão em outros fluxos** (sem verificação de `response.ok`): cadastro, em que `createUser` devolve o corpo da resposta (`api.ts:13-24`) e `performSignup` segue para o login (`:31-37`); leitura do perfil, em que `setProfileInfoIfLoggedIn` trata o corpo de erro como dados do perfil e não preenche nenhum campo, sem aviso (`:91-98`); e a query, em que `fetchCourseSphereResponse` exibe "Successfully retrieved bot response!" (`:194-196`). Os fluxos de chat e `/hash` verificam `response.ok` (`:247`, `:273`, `:292`, `:313`).
- **Observado:** na primeira execução do baseline, antes da correção do ACH-06, `POST /users/info` retornou HTTP 400 e a interface exibiu o toast de sucesso. O log dessa execução não foi preservado.
- **Severidade:** a definir na Fase 2.

### 3.8 ACH-08 — `id_token` na URL de `GET /users/info` e registrado no log do Flask

- **Localização:** `frontend/src/api.ts:91` (monta a URL com `?id_token=${idToken}`) e `backend/endpoints.py:58` (lê `request.args.get("id_token")`). O backend não tem configuração de log própria, então vale o log de acesso padrão do servidor Flask.
- **Descrição:** o ID token do Firebase, credencial que o backend usa para identificar o usuário (`Firebase.verify_id_token`, `endpoints.py:59`), vai na query string. O log de acesso grava a linha de requisição inteira, e o token fica em texto claro no log do backend. As demais rotas autenticadas recebem o token no header `Authorization` (`/hash` e `/chats/...`) ou no corpo da requisição (`POST /users/info`, `api.ts:157`).
- **Observado:** o log de acesso do backend registra `GET /users/info?id_token=<valor> HTTP/1.1` e também o preflight `OPTIONS` da mesma URL. Antes da redação, o valor tinha 932 caracteres e prefixo de JWT (`eyJ`).
- **Evidência:** [`evidence/baseline/backend-baseline.log`](evidence/baseline/backend-baseline.log) (linhas `GET` e `OPTIONS /users/info?id_token=eyJ...[REDACTED]`; o valor completo foi redigido antes de salvar).
- **Severidade:** a definir na Fase 2.

### 3.9 ACH-09 — `/users/query` sem autenticação efetiva

- **Localização:** `frontend/src/api.ts:184` (`const idToken = user?.getIdToken();`, sem `await`), `:185` (`{ query, idToken }`) e `:190` (header `Authorization`); `backend/endpoints.py:65-72` (rota, com a leitura de `id_token` na linha 69) e `backend/firebase.py:64-68` (`try_get_user_info`).
- **Descrição:** `getIdToken()` devolve uma Promise, e o frontend não a aguarda. No corpo JSON ela vira `{}` (campo `idToken`) e no header vira `Bearer [object Promise]`. O backend procura outra chave (`id_token`), não lê o header `Authorization` e usa `Firebase.try_get_user_info`, que devolve `None` em qualquer falha. A rota segue com `user_info=None`, chama o `QueryManager` e responde HTTP 200 em vez de rejeitar a requisição sem autenticação.
- **Indício no baseline:** o log do baseline (seção 2.4) registra `POST /users/query` com HTTP 200 para a requisição do próprio frontend, que não leva `id_token` válido. É só um indício: a prova de que a rota não exige autenticação, com uma requisição sem token, fica para a Fase 2.
- **Status:** confirmar reproduzindo uma requisição sem autenticação na Fase 2.
- **Severidade:** a definir na Fase 2.

### 3.10 ACH-10 — SQL montado por f-string em `blueprints/courses.py` (blueprint inativo)

- **Localização:** `backend/blueprints/courses.py:30, 47, 64, 80, 96, 112` (consultas montadas com f-string) e `backend/db.py:9` (`cursor.execute(query)`, sem parâmetros).
- **Descrição:** os valores vindos da URL são interpolados direto no texto SQL. Nas rotas com parâmetro `string` (`semester`, `department` e `instructor`; linhas 80, 96 e 112) o valor fica entre aspas simples, o que permite alterar a consulta (padrão de injeção de SQL). Nas rotas com `<int:...>` (linhas 30, 47 e 64) o conversor do Flask restringe o valor a dígitos.
- **Condição de ativação (inativo hoje):** o código só é alcançável se (1) `courses_bp` for importado e registrado em `endpoints.py`, onde hoje só existe o comentário `#app.register_blueprint(courses_bp)` (linha 11); (2) os imports `backend.db` e `backend.endpoints` (`courses.py:3-4`) passarem a resolver, o que hoje não ocorre porque a aplicação roda a partir do diretório `backend/` e não existe um pacote `backend`; e (3) existir o banco SQLite no caminho de `db.py:4` (`cournell-course-sphere-data/roster_reviews.sqlite.db`): o repositório não traz arquivo SQLite, e o nome da pasta está grafado diferente da pasta de dados (`cornell-course-sphere-data`).
- **Observado:** na imagem do backend, a tabela de rotas da aplicação não contém nenhuma rota `/courses`, e `import backend.db` falha com `ModuleNotFoundError`.
- **Severidade:** a definir na Fase 2; depende da ativação.

## 4. Correções

Correções aplicadas até agora. As demais entram aqui conforme forem feitas.

### 4.1 ACH-06 — URL do RTDB externalizada

- **Alteração:** `backend/firebase.py` (linhas 6-11) lê a URL de `FIREBASE_DB_URL`, sem valor padrão, e levanta `RuntimeError` com mensagem explícita se a variável estiver ausente ou vazia. O `docker-compose.yml` define a variável no serviço `backend` com o `databaseURL` de `frontend/src/firebaseConfig.ts`, que é a fonte única do valor.
- **Verificação local** (container sem rede, com credencial de teste descartável): sem a variável, ou com ela vazia, o backend não sobe e exibe a mensagem de erro; com a variável, sobe e o `firebase_admin` usa exatamente o valor informado. O valor do `docker-compose.yml` é igual ao `databaseURL` de `frontend/src/firebaseConfig.ts`.
- **Validação:** em 23/10/2026, com credenciais reais, `POST /users/info` e `GET /users/info` retornaram HTTP 200 ([`evidence/baseline/backend-baseline.log`](evidence/baseline/backend-baseline.log)).

## 5. Confiabilidade (SRE)

_A preencher._

## 6. Recomendações priorizadas

_A preencher._
