# Evidências

Esta pasta guarda os prints e logs que sustentam o [relatório](../report.md).

- `baseline/`: evidências do ambiente de referência (Fase 0).
- `ACH-NN/`: uma pasta por achado, com o mesmo ID usado na seção 3 do relatório (ex.: `ACH-03/`). É criada quando houver evidência.

## Arquivos

| Arquivo | O que mostra | Usado em | Situação |
|---|---|---|---|
| `baseline/backend-baseline.log` | Saída de `docker compose logs backend` da execução final do baseline, depois da correção do ACH-06: duas subidas do Flask (`0.0.0.0:5000`, debug desligado; a segunda é a reinicialização dos containers), `POST /users/create` 200, `GET` e `POST /users/info` 200, `POST /users/query` 200, `POST /hash` 200 (duas vezes) e `OPTIONS /theactualbackendlink` 404. Os valores de `id_token=` foram redigidos (`eyJ...[REDACTED]`) e os códigos de cor ANSI, removidos. Antes da redação, o valor tinha 932 caracteres e prefixo de JWT (`eyJ`). | Baseline (2.4), ACH-04, ACH-06, ACH-08, ACH-11 | Completo. |
| `baseline/baseline-signup-200.png` | Deve mostrar o cadastro concluído, com `POST /users/create` em HTTP 200. | Baseline (2.4) | A adicionar |
| `baseline/baseline-profile-save-200.png` | Deve mostrar o salvamento do perfil, com `POST /users/info` em HTTP 200. | Baseline (2.4), ACH-06 | A adicionar |
| `baseline/baseline-dashboard.png` | Deve mostrar o dashboard depois do login. | Baseline (2.4) | A adicionar |
| `baseline/baseline-query.png` | Deve mostrar o chat depois da pergunta, com a bolha do bot vazia (resposta fixa do `QueryManager`) e o toast "Successfully retrieved bot response!". O toast não prova o status HTTP (ACH-07); o status está no log. | Baseline (2.4) | A adicionar |
| `tools/` | Saídas de SAST e SCA (`semgrep.json`, `bandit.json`, `pip-audit.txt`, `pip-audit.json`, `npm-audit.json`) e, em `tools/README.md`, o que cada ferramenta rodou e o mapeamento dos hits nos achados. Sem segredos: os scans leram uma cópia sem `credentials.json` e `config.json`. | Seção 2.3 e candidatos a novos achados | Capturado |
| `ACH-03/hash-no-auth-500.txt` | Saída de `curl -i -X POST http://localhost:5000/hash`, sem o header `Authorization`: HTTP 500 e, no corpo, a exceção interna (`'NoneType' object has no attribute 'split'`). A primeira linha é o comando, e os `\r` do HTTP foram removidos. | ACH-03 (antes da correção) | Capturado em 25/10/2026 |
| `ACH-03/hash-no-auth-401.txt` | `POST /hash` sem `Authorization` depois da correção do ACH-03: HTTP 401 com mensagem genérica `Missing or invalid Authorization header`, sem a exceção interna. | ACH-03 (depois da correção, seção 4.4) | Capturado em 26/10/2026 |
| `ACH-03/users-info-no-auth-401.txt` | `GET /users/info` sem `Authorization` depois da correção: HTTP 401 com a mesma mensagem genérica. | ACH-03 (depois da correção, seção 4.4) | Capturado em 26/10/2026 |
| `ACH-03/baseline-after-fix-200.log` | Log do backend com login real depois das correções do ACH-08 e do ACH-03: `GET /users/info` e `POST /users/info` em HTTP 200 (e um 401 inicial, de token expirado), sem token na URL. Comprova que o header válido continua passando. Tokens redigidos; sem códigos ANSI. | ACH-03 e ACH-08 (baseline após a correção) | Capturado em 26/10/2026 |
| `ACH-08/after-fix-no-token.log` | Log do backend depois da correção do ACH-08, com login real: `GET /users/info` (duas vezes) e `POST /users/info` com HTTP 200, e nenhuma URL com `?id_token=`. Comprova que o token saiu da URL e do log de acesso (agora vai no header `Authorization`) e que o fluxo do baseline continua em 200 depois da correção. Códigos de cor ANSI removidos. | ACH-08 (seção 4.3) | Capturado em 26/10/2026 |
| `ACH-09/users-query-no-auth.txt` | Saída de `curl -i -X POST http://localhost:5000/users/query` com `{"query":"test"}`, sem token e sem `Authorization`: HTTP 200 e a resposta fixa `"Fake implementation"`. A primeira linha é o comando, e os `\r` do HTTP foram removidos. | ACH-09 | Capturado em 25/10/2026 |
| `ACH-12/database-rules.json` | Regras do Realtime Database do projeto antes da correção, lidas com a conta de serviço (somente leitura, sem acesso a dados): `.read` e `.write` condicionados só a `now < 1795230000000` (21/11/2026), sem checar `auth`. Está no formato do console, com comentários e vírgula final, então não é JSON estrito. | ACH-12 | Capturado em 25/10/2026 |
| `ACH-12/unauth-denied-after-lock.txt` | Leitura sem credenciais ao RTDB (`.json?shallow=true`, só chaves de primeiro nível) depois da publicação das regras: HTTP 401 `Permission denied`. O `databaseURL` foi trocado por `<databaseURL>`. | ACH-12 (seção 4.2) | Capturado em 25/10/2026 |
| `ACH-12/baseline-after-lock.txt` | Log do backend depois da publicação das regras: `GET /users/info` e `POST /users/info` com HTTP 200, ou seja, o backend continua funcionando com o banco fechado para clientes. Tokens redigidos (`<REDACTED>`) e códigos de cor ANSI removidos. | ACH-12 (seção 4.2) | Capturado em 25/10/2026 |
| `ACH-12/rules-test-pass.txt` | Saída do teste de unidade das regras do RTDB no emulador do Firebase (`security/rules-tests/`): 4 testes passam, acesso de cliente negado (`permission_denied`). Previne regressão do ACH-12. | ACH-12 (seção 7.9) | Capturado em 27/10/2026 |
| `infra/load-balancing.txt` | 20 requisições a `/health` via Nginx mostrando o header `X-Backend-Instance` alternar, com o agregado 10/10 (round-robin das duas instâncias). | Seção 7.5 | Capturado em 26/10/2026 |
| `infra/backend-instances.log` | Linhas de log JSON de `backend1` e `backend2` (campo `instance`), provando que as duas instâncias atendem requisições; sem token. | Seção 7.5 | Capturado em 26/10/2026 |
| `infra/security-headers.txt` | `curl -i localhost:5000/health` via Nginx, com os quatro headers de segurança e um único `Access-Control-Allow-Origin`. | Seção 7.4 | Capturado em 26/10/2026 |
| `infra/rate-limit-global.txt` | 7 requisições a `/users/create` alternando `backend1`/`backend2`: 5 passam somadas e a 6ª dá HTTP 429 (limite global via Redis, compartilhado entre as instâncias). | Seção 6.4 | Capturado em 26/10/2026 |
| `infra/grafana-dashboard.png` | Dashboard "CourseSphere SRE" no Grafana (range de 5 min): o painel de erro 5xx plano em 0% com o eixo em 0-100%, os 2 SLIs em 100%, latência e taxa de requisição. | Seção 6.3 | Capturado em 27/10/2026 |
| `infra/metrics-hardening.txt` | `/metrics` com 404 pela porta pública (Nginx) e os dois targets do Prometheus `up`; URLs inexistentes caindo em `unmatched` sem criar séries novas; `/chats/<chat_id>` como template; baseline, headers, Grafana e SLIs funcionando. | Seções 6.1 e 7.3 | Capturado em 27/10/2026 |
| `infra/login-via-nginx.log` | Login real no navegador pelo Nginx depois da Fase 7: `GET /users/info`, `POST /users/info`, `POST /users/query` e `POST /hash` em 200, preflights em 200 e um `auth success` por chamada autenticada, nas duas instâncias. `uid` redigido; o token não aparece. | Seção 7.6 | Capturado em 27/10/2026 (horários do log em UTC) |

## Antes de salvar um arquivo

Remova ou oculte segredos: tokens, chaves de API e o conteúdo de `credentials.json` ou `config.json`. O log do backend registra o `id_token` na URL de `GET /users/info` (ACH-08), então nunca salve esse log sem redigir.

Para recapturar o log do backend com a redação aplicada:

```bash
docker compose logs backend \
  | sed -E 's/\x1b\[[0-9;]*m//g; s/(id_token=[^ &"]{0,3})[^ &"]*/\1...[REDACTED]/g' \
  > security/evidence/baseline/backend-baseline.log
```

Depois, confirme que `grep -E 'eyJ[A-Za-z0-9_-]{4,}' security/evidence/baseline/backend-baseline.log` não retorna nada.
