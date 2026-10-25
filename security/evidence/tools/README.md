# Evidências de SAST e SCA

Saídas das ferramentas automáticas rodadas em 23/10/2026 e o mapeamento dos resultados nos achados do [relatório](../../report.md). Não há CVSS aqui: as severidades abaixo são as que cada ferramenta reporta, e a classificação CVSS 3.1 dos achados está no relatório (seção 3). O DAST (OWASP ZAP) não foi executado.

## Como foi rodado

- Todas as ferramentas rodaram em containers efêmeros (`docker run --rm`), sem instalar nada no host.
- Os scans de código leram uma **cópia higienizada** de `backend/` e `frontend/src`, montada somente leitura e sem `backend/credentials.json`, `backend/config.json`, `backend/cornell-course-sphere-data` e `node_modules`. O Semgrep recebeu as mesmas exclusões por `--exclude`, e a lista de arquivos escaneados (`paths.scanned` em `semgrep.json`, 58 arquivos) não contém nenhum deles.
- Rede: o Semgrep baixa as regras do registro (`--metrics=off`, nenhum código é enviado). O pip-audit e o npm audit consultam as bases de avisos com nomes e versões de pacotes, sem código-fonte.
- Conferência de segredos nas saídas: a busca nesta pasta por padrões de token JWT, chave privada e chave de API da OpenAI retornou vazio, e buscas adicionais (chave web do Google, e-mails, nomes dos arquivos de segredo, caminhos absolutos) também. O Semgrep sem login não grava trechos de código (`lines: requires login`).
- `semgrep.json` e `pip-audit.json` foram formatados com indentação, sem mudar o conteúdo.

## Ferramentas

| Ferramenta | Versão | Escopo | Saída |
|---|---|---|---|
| Semgrep (SAST) | 1.181.1 | `backend/` e `frontend/src`: 58 arquivos, 498 regras dos pacotes `p/default`, `p/owasp-top-ten`, `p/security-audit`, `p/python`, `p/flask`, `p/javascript`, `p/typescript`, `p/react` e `p/dockerfile` | `semgrep.json` |
| Bandit (SAST Python) | 1.9.4 | `backend/`: 6 arquivos Python, 459 linhas | `bandit.json` |
| pip-audit (SCA) | 2.10.1 | Ambiente instalado da imagem `coursesphere-backend` (59 pacotes), dentro de um venv do container para não alterar o ambiente auditado | `pip-audit.txt`, `pip-audit.json` |
| npm audit (SCA) | npm 10.8.2 | `frontend/package-lock.json` (412 dependências: 218 de produção, 194 de desenvolvimento, 40 opcionais) | `npm-audit.json` |

Comandos (`$SRC` é a cópia higienizada; `$NPM` tem só `package.json` e `package-lock.json`):

```bash
tar --exclude=credentials.json --exclude=config.json --exclude=cornell-course-sphere-data \
    --exclude=node_modules --exclude=__pycache__ --exclude=.idea --exclude=.DS_Store \
    -cf - backend frontend/src | tar -C "$SRC" -xf -

docker run --rm -v "$SRC:/src:ro" -w /src -e SEMGREP_SEND_METRICS=off semgrep/semgrep \
  semgrep scan --metrics=off --disable-version-check \
    --config p/default --config p/owasp-top-ten --config p/security-audit \
    --config p/python --config p/flask --config p/javascript --config p/typescript \
    --config p/react --config p/dockerfile \
    --exclude credentials.json --exclude config.json \
    --exclude cornell-course-sphere-data --exclude node_modules \
    --json backend frontend/src > semgrep.json

docker run --rm -v "$SRC:/src:ro" -w /src python:3.12-slim sh -c \
  'pip install -q bandit && bandit -r backend -f json -x backend/cornell-course-sphere-data' > bandit.json

docker run --rm coursesphere-backend sh -c \
  'python -m venv /tmp/audit && /tmp/audit/bin/pip install -q pip-audit \
   && /tmp/audit/bin/pip-audit --path /usr/local/lib/python3.12/site-packages --desc on' > pip-audit.txt

docker run --rm -v "$NPM:/app:ro" -w /app node:20-alpine \
  npm audit --package-lock-only --json > npm-audit.json
```

## Resultados

### Semgrep: 14 achados, 0 erros de execução

| Regra | Severidade (ferramenta) | Ocorrências | Locais |
|---|---|---|---|
| `dockerfile.security.missing-user` | ERROR | 1 | `backend/Dockerfile:16` |
| `python.flask.security.injection.tainted-sql-string` | ERROR | 6 | `backend/blueprints/courses.py:30, 47, 64, 80, 96, 112` |
| `python.flask.security.audit.debug-enabled` | WARNING | 1 | `backend/endpoints.py:108` |
| `typescript.react.security.react-insecure-request` | ERROR | 5 | `frontend/src/api.ts:14, 160, 186, 304` e `frontend/src/components/UserChats/UserChats.tsx:25` |
| `generic.secrets.security.detected-generic-api-key` | ERROR | 1 | `frontend/src/firebaseConfig.ts:2` |

### Bandit: 11 achados (1 HIGH, 6 MEDIUM, 4 LOW)

| Teste | Severidade / confiança (ferramenta) | Ocorrências | Locais |
|---|---|---|---|
| B608 `hardcoded_sql_expressions` | MEDIUM / LOW | 6 | `backend/blueprints/courses.py:30, 47, 64, 80, 96, 112` |
| B201 `flask_debug_true` | HIGH / MEDIUM | 1 | `backend/endpoints.py:108` |
| B311 `blacklist` (módulo `random`) | LOW / HIGH | 3 | `backend/main.py:15` (duas ocorrências) e `:16` |
| B101 `assert_used` | LOW / HIGH | 1 | `backend/query_manager.py:44` |

### pip-audit: 1 pacote com avisos em 59 auditados

Só o `pip 25.0.1` tem avisos: 6 distintos (PYSEC-2026-196, -1795, -1796, -2875, -2876 e -3721), que a ferramenta lista em 12 linhas porque repete cada um. As correções vão de pip 25.3 a 26.2 (o último aviso a fechar é o PYSEC-2026-3721). O `pip` vem da imagem base: o `backend/Dockerfile` só instala o `requirements.txt` (linha 10) e não o atualiza. As bibliotecas da aplicação não tiveram avisos, entre elas `flask` 3.1.3, `flask-cors` 6.0.5, `firebase-admin` 7.7.0, `werkzeug` 3.1.9, `openai` 3.37.0 e `pandas` 3.1.0. O `requirements.txt` não fixa versões, então o resultado vale para as versões resolvidas no build da imagem.

### npm audit: 42 pacotes com avisos em 412 dependências

Pela maior severidade de cada pacote (ferramenta): 2 critical, 23 high, 16 moderate e 1 low. São 104 avisos distintos, e só 5 pacotes são dependências diretas do `package.json`; os outros 37 são transitivos.

| Dependência direta (lockfile) | Avisos distintos | Exemplos (títulos da ferramenta) | Correção |
|---|---|---|---|
| `firebase` 10.12.3 | 17 (4 high) | `undici` (consumo de memória e exceção no cliente WebSocket) e `@fastify/busboy` (negação de serviço e injeção de CRLF) | Disponível |
| `react-router-dom` 6.24.1 | 5 (1 high) | XSS via redirecionamento aberto e variantes de redirecionamento externo, em `@remix-run/router` e `react-router` | Disponível |
| `sass` 1.77.6 | 1 (high) | `braces`: negação de serviço por esgotamento de pilha | Disponível |
| `uuid` 10.0.0 | 1 (moderate) | Falta de checagem de limites de buffer nas versões v3, v5 e v6 | Disponível (versão major) |
| `vite` 5.3.3 | 21 (3 high) | Servidor de desenvolvimento (`server.fs.deny`, `launch-editor`) e `esbuild` (qualquer site consegue enviar requisições ao servidor de desenvolvimento) | Disponível |

- **Os dois critical** são transitivos do `firebase`: `protobufjs` (via `@firebase/firestore` e `@grpc/proto-loader`) e `websocket-driver` (via `@firebase/database` e `faye-websocket`). O frontend importa apenas `firebase/app`, `firebase/auth` e `firebase/database`, sem Firestore. Se esses pacotes chegam ao bundle do navegador não foi avaliado.
- **`vite`:** os três avisos high listados têm "Windows" no título. No ambiente de teste o frontend roda o servidor de desenvolvimento do Vite em `0.0.0.0:3000` (`frontend/Dockerfile.dev`), então os avisos de servidor de desenvolvimento estão no escopo do ambiente testado.
- **`uuid`** está no `package.json`, mas nenhum arquivo de `frontend/src` o importa.

## Mapeamento nos achados

| Hit | Ferramenta e regra | Local | ACH |
|---|---|---|---|
| Container sem usuário não-root | Semgrep `missing-user` (CWE-250) | `backend/Dockerfile:16` | ACH-01 |
| SQL montado por f-string | Semgrep `tainted-sql-string` (6) e Bandit B608 (6, CWE-89) | `backend/blueprints/courses.py:30, 47, 64, 80, 96, 112` | ACH-10. As duas ferramentas marcam também as três rotas `<int:...>` (linhas 30, 47 e 64), em que o conversor do Flask limita o valor a dígitos. |
| `debug=True` | Semgrep `debug-enabled` (CWE-489) e Bandit B201 | `backend/endpoints.py:108` | **ACH-11.** A linha só roda se o arquivo for executado direto (`python endpoints.py`). No container o Flask sobe pelo CLI e o log mostra `Debug mode: off` ([`backend-baseline.log`](../baseline/backend-baseline.log)). |
| Gerador pseudoaleatório não criptográfico | Bandit B311 (3, CWE-330) | `backend/main.py:15` e `:16` | **Candidato novo.** `hashFunction` (`main.py:14-18`) gera o ID de `POST /hash` (ACH-03) misturando `random` e `numpy.random` com `secrets.token_hex(16)` (linha 17). O backend só devolve o ID (`endpoints.py:80-81`) e não o usa em decisão de acesso; a relevância fica a avaliar. O `random.shuffle` da linha 11 não é sinalizado pelo Bandit. |
| `assert` como validação de entrada | Bandit B101 (CWE-703) | `backend/query_manager.py:44` | **Candidato novo.** O `assert` é removido com `python -O`. |
| HTTP em claro e URL do backend fixa | Semgrep `react-insecure-request` (5, CWE-319) | `frontend/src/api.ts:14, 160, 186, 304` e `frontend/src/components/UserChats/UserChats.tsx:25` | **Candidato novo.** A URL `http://127.0.0.1:5000` aparece fixa em 6 pontos: a regra não marcou `api.ts:91`, que também usa `http://` e é o ACH-08. As chamadas envolvem os ACH-03, 04, 07, 08 e 09. |
| Chave web do Firebase no código | Semgrep `detected-generic-api-key` (confiança LOW, CWE-798) | `frontend/src/firebaseConfig.ts:2` (`apiKey`) | **Candidato novo (informativo).** É a chave web do Firebase, que acompanha o cliente por desenho. O hit não indica vazamento de `credentials.json`. O que vale checar na Fase 2 são as restrições da chave e as regras do RTDB (ACH-12). |
| `pip` desatualizado na imagem | pip-audit (6 avisos) | Imagem `coursesphere-backend`, `pip 25.0.1` | **Candidato novo (SCA).** Fica na camada da imagem base, não é dependência da aplicação. |
| Dependências do frontend com avisos | npm audit (42 pacotes, 104 avisos) | `frontend/package-lock.json` | **Candidato novo (SCA).** Ver a tabela de dependências diretas acima. |

**ACH sem hit de ferramenta:** ACH-03 (que absorveu o ACH-02), ACH-04, ACH-05, ACH-06, ACH-07, ACH-08, ACH-09 e ACH-12. São lógica de aplicação, tratamento de erro, autenticação e configuração, que as regras usadas não cobrem. Vieram da leitura do código e do baseline. O ACH-06 já estava corrigido no código escaneado.

## Limitações

- As severidades são as de cada ferramenta e não a classificação do relatório.
- O SAST não cobre autenticação e autorização, CORS nem as regras do RTDB. Esses pontos vêm da análise manual ([`recon.md`](../../recon.md)).
- O escopo pedido foi `backend/` e `frontend/src`: o `docker-compose.yml` e os Dockerfiles do frontend ficaram de fora.
- O SCA depende dos bancos de avisos de 23/10/2026. Não foi avaliado se cada pacote vulnerável é alcançável pelo código da aplicação.
