# Reconhecimento (Fase 1): inventário de rotas do backend

> Mapeamento factual, sem exploração. Fontes: leitura de `backend/endpoints.py` e `backend/blueprints/courses.py`, conferida com a tabela de rotas da aplicação em execução (`app.url_map`, na imagem do backend). Os IDs `ACH-NN` remetem aos achados do [relatório](report.md).

## 1. Rotas ativas (`backend/endpoints.py`)

São 7 registros de rota em 6 caminhos (`/users/info` tem `GET` e `POST`), mais a rota implícita `/static/<path:filename>` do Flask. Todas respondem a `OPTIONS` (preflight CORS).

| Rota | Método | Autenticação (exigida? como?) | Dados que toca | Observações / ACH |
|---|---|---|---|---|
| `/users/create` | POST | Não. Rota pública de cadastro. | Firebase Auth (`auth.create_user`, `firebase.py:19`) | Valida só e-mail e senha não vazios (`endpoints.py:21-24`): ACH-05. A resposta de sucesso devolve `user_id` e `email` (`firebase.py:20-25`). Leitura do JSON fora do `try` (`:18-20`). Erros devolvem `str(e)`: ACH-03. |
| `/users/info` | POST | Sim. `id_token` no corpo JSON (`:33`), verificado com `Firebase.verify_id_token` (`:35`). O `uid` vem do token. | Firebase Auth (verificação); RTDB (escrita em `users/{uid}/info`, `firebase.py:49`) | Grava `majors`, `minors`, `year`, `college`, `courses` e `about` como recebidos, sem validação (`:36-50`). Leitura do JSON e do token fora do `try` (`:32-33`). No frontend, a falha fica mascarada: ACH-07. Erros devolvem `str(e)`: ACH-03. |
| `/users/info` | GET | Sim. `id_token` na query string (`:58`), verificado com `Firebase.verify_id_token` (`:59`). | Firebase Auth (verificação); RTDB (leitura de `users/{uid}/info`, `firebase.py:57`) | Token na URL e no log de acesso: ACH-08. Erros devolvem `str(e)`: ACH-03. |
| `/users/query` | POST | Não exigida: rota pública por desenho. A autenticação é opcional: lê `id_token` do corpo (`:69`) e tenta verificar com `Firebase.try_get_user_info`, que devolve `None` em qualquer erro (`firebase.py:64-68`). | Firebase Auth e RTDB (leitura de `users/{uid}/info`), só se o token for válido. OpenAI: não é chamada | ACH-09: a autenticação opcional não funciona (o frontend manda `idToken` como Promise) e falha aberta; sem limite de taxa. Resposta fixa `"Fake implementation"` (`query_manager.py:104`). Erros devolvem `str(e)`: ACH-03. |
| `/hash` | POST | Sim. Header `Authorization: Bearer <id_token>` (`:77`), verificado (`:78`). | Firebase Auth (verificação). Nada é gravado: `hashFunction` (`main.py:14-18`) só gera o ID | Sem o header, ou sem o prefixo `Bearer `, retorna HTTP 500 com a exceção, e os erros devolvem `str(e)`: ACH-03. |
| `/chats/<chat_id>/messages` | POST | Sim. Header `Authorization: Bearer` (`:88`), verificado (`:89`). | Firebase Auth (verificação); RTDB (`push` de cada mensagem em `users/{uid}/chats/{chat_id}/messages`, `firebase.py:142-156`) | `chat_id` vem da URL e compõe o caminho do RTDB. Corpo: lista `messages` (`:90`), em que cada item precisa ser um objeto (`firebase.py:149`). Mesma extração do token do `/hash`, aqui com HTTP 400: ACH-03. |
| `/chats/<chat_id>` | DELETE | Sim. Header `Authorization: Bearer` (`:99`), verificado (`:100`). | Firebase Auth (verificação); RTDB (remove `users/{uid}/chats/{chat_id}`, `firebase.py:159-164`) | Mesma extração do token do `/hash`, com HTTP 400. Nenhuma função do frontend chama esta rota. ACH-03. |
| `/static/<path:filename>` | GET (HEAD, OPTIONS) | Não. | Nenhum: a pasta `static/` não existe | Rota implícita do Flask. `GET /static/x` retorna 404. |

## 2. Rotas do blueprint de cursos (`backend/blueprints/courses.py`)

**Blueprint inativo.** `courses_bp` (`courses.py:6`) não é importado nem registrado em `endpoints.py` (só existe o comentário `#app.register_blueprint(courses_bp)`, linha 11), e a tabela de rotas da aplicação em execução não tem nenhuma rota `/courses`. As condições para ativar estão no ACH-10. Nenhuma das rotas abaixo verifica autenticação no código, e todas consultam o SQLite por `execute_query` (`db.py:6-12`).

| Rota | Método | Autenticação (exigida? como?) | Dados que toca | Observações / ACH |
|---|---|---|---|---|
| `/courses` | GET | Não | SQLite (`courses`) | `SELECT` fixo (`courses.py:17`). |
| `/courses/<int:course_id>` | GET | Não | SQLite (`courses`) | Consulta por f-string com `int` (`:30`): ACH-10. |
| `/courses/description/<int:course_id>` | GET | Não | SQLite (`course_descriptions`) | f-string com `int` (`:47`): ACH-10. |
| `/courses/bysection/<int:section_id>` | GET | Não | SQLite (`courses`) | f-string com `int` (`:64`): ACH-10. |
| `/courses/<string:semester>` | GET | Não | SQLite (`courses`) | f-string com o valor entre aspas simples (`:80`): ACH-10. |
| `/courses/<string:department>` | GET | Não | SQLite (`courses`) | f-string entre aspas simples (`:96`): ACH-10. Mesma regra de URL de `semester` e `instructor` (`:71`, `:87`, `:103`). |
| `/courses/<string:instructor>` | GET | Não | SQLite (`courses`) | f-string entre aspas simples (`:112`): ACH-10. Mesma regra de URL de `semester` e `department`. |

Nota: as três rotas `/courses/<string:...>` (linhas 71, 87 e 103) colidem na mesma regra de URL. Em teste local, registrando o blueprint do arquivo real numa aplicação nova (imports `backend.*` substituídos por stubs), qualquer `/courses/<texto>` é atendido por `get_courses_by_semester`, a primeira registrada, e `get_courses_by_department` e `get_courses_by_instructor` ficam inalcançáveis. `/courses/5` vai para `get_course`, porque a rota `int` tem prioridade.

## 3. Chamadas do frontend ao backend

O frontend chama o backend em `http://127.0.0.1:5000` (endereço fixo no código). A tabela mostra quais chamadas têm rota correspondente.

| Função (`frontend/src/api.ts`) | Requisição | Rota no backend |
|---|---|---|
| `createUser` (`:13`), via `performSignup` | `POST http://127.0.0.1:5000/users/create` (`:14`) | `POST /users/create` |
| `setProfileInfoIfLoggedIn` (`:78`) | `GET http://127.0.0.1:5000/users/info?id_token=…` (`:91`) | `GET /users/info` (ACH-08) |
| `saveProfileChanges` (`:142`) | `POST http://127.0.0.1:5000/users/info` (`:160`) | `POST /users/info` (ACH-07) |
| `fetchCourseSphereResponse` (`:182`) | `POST http://127.0.0.1:5000/users/query` (`:186`) | `POST /users/query` (ACH-09) |
| `h` (`:298`) | `POST http://127.0.0.1:5000/hash` (`:304`) | `POST /hash` (ACH-03) |
| `saveCourseSphereChat` (`:223`) | `POST /chats/{chatId}/messages`, URL relativa (`:229`) | `POST /chats/<chat_id>/messages`. O caminho é o mesmo, mas a URL relativa resolve para a origem da página (no ambiente de teste, o Vite na porta 3000), não para o backend. |
| `updateCourseSphereChat` (`:256`) | `PUT /chats/{chatId}/messages/{messageId}`, URL relativa (`:261`) | Nenhuma. Nenhum componente importa a função. |
| `deleteCourseSphereChat` (`:278`) | `DELETE /chats/{chatId}/messages/{messageId}`, URL relativa (`:283`) | Nenhuma (o backend só tem `DELETE /chats/<chat_id>`). Nenhum componente importa a função. |
| `UserChats` (`components/UserChats/UserChats.tsx:25`) | `GET http://127.0.0.1:5000/theactualbackendlink` | Nenhuma (ACH-04). |

## 4. Notas transversais

- **Autenticação por rota.** Não há middleware, `before_request` nem decorator de autenticação: cada rota verifica o token por conta própria. O token chega de três formas: header `Authorization` (`/hash` e `/chats/...`), corpo JSON `id_token` (`POST /users/info` e `/users/query`) e query string (`GET /users/info`).
- **Origem do `uid`.** Nas rotas que usam o RTDB, o `uid` vem sempre do token verificado (`endpoints.py:35, 59, 89, 100`). Nenhuma rota recebe o `uid` do cliente.
- **CORS.** `CORS(app)` sem parâmetros (`endpoints.py:8`). Em teste local (container sem rede), o preflight com `Origin: http://other.example` retornou HTTP 200, com `Access-Control-Allow-Origin` igual à origem enviada e `Access-Control-Allow-Methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT`.
- **RTDB.** Caminhos tocados pelas rotas: `users/{uid}/info`, `users/{uid}/chats/{chat_id}/messages` e `users/{uid}/chats/{chat_id}`. As regras originais do projeto (modo de teste, abertas até 21/11/2026) ficavam só no console do Firebase: o export está em [`evidence/ACH-12/`](evidence/ACH-12/database-rules.json) (ACH-12). O repositório agora versiona `database.rules.json` e `firebase.json`, com acesso de cliente negado, ainda não publicados no projeto.
- **Helpers sem rota.** `Firebase.delete_user`, `update_user_info`, `create_document`, `get_document`, `update_document` e `delete_document` (`firebase.py:30, 73, 81, 96, 112, 127`) não são chamados por nenhuma rota. Os quatro últimos montam o caminho do RTDB a partir de `collection` e `document_id`.
- **Sem limitação de taxa.** Não há código nem dependência de rate limit (`requirements.txt`: firebase-admin, flask, flask-cors, openai, pandas). O backend também não configura log próprio; vale o log de acesso padrão do servidor (ACH-08).
- **Execução.** Servidor de desenvolvimento do Flask pelo CLI (`backend/Dockerfile:16`), com debug desligado. O `app.run(debug=True)` está em `endpoints.py:107-108` e só roda se o arquivo for executado diretamente (ACH-11).
