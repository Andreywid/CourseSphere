# CourseSphere: Avaliação de Segurança e Confiabilidade

> Desafio técnico de AppSec e SRE. Este repositório parte da aplicação de referência [LambdaAK/CourseSphere](https://github.com/LambdaAK/CourseSphere) e acrescenta uma avaliação de segurança (análise de vulnerabilidades, correções e hardening) e de confiabilidade (observabilidade e operação), em um ambiente isolado e reprodutível.

[![security](https://github.com/Andreywid/CourseSphere/actions/workflows/security.yml/badge.svg)](https://github.com/Andreywid/CourseSphere/actions/workflows/security.yml)

## Sobre a aplicação

CourseSphere é um assistente de recomendação de cursos e professores.

- **Backend:** Flask (Python). Autenticação e dados de usuário no Firebase (Authentication e Realtime Database). SQLite e OpenAI existem no código, mas estão inativos em runtime.
- **Frontend:** React, Vite, TypeScript e MUI, com o SDK web do Firebase.

O foco do trabalho não é a funcionalidade, e sim identificar e corrigir falhas reais, endurecer a postura de segurança e instrumentar a aplicação para operação.

## O que este repositório acrescenta

| Entrega | Onde |
|---|---|
| Ambiente de teste isolado em Docker | [`docker-compose.yml`](docker-compose.yml), [`backend/Dockerfile`](backend/Dockerfile), [`frontend/Dockerfile.dev`](frontend/Dockerfile.dev) |
| Relatório técnico: escopo, metodologia, achados, severidade e correções | [`security/report.md`](security/report.md) |
| Inventário de rotas e superfície de ataque | [`security/recon.md`](security/recon.md) |
| Nginx balanceando 2 instâncias do backend (gunicorn) + headers de segurança | [`docker-compose.yml`](docker-compose.yml), [`nginx/nginx.conf`](nginx/nginx.conf) |
| CI de segurança (SAST/SCA a cada push/PR) e Dependabot | [`.github/workflows/security.yml`](.github/workflows/security.yml), [`.github/dependabot.yml`](.github/dependabot.yml) |
| Teste de autorização das regras do RTDB (emulador do Firebase, ACH-12) | [`security/rules-tests/`](security/rules-tests/) |
| Regras do Realtime Database restritas (correção do ACH-12) | [`database.rules.json`](database.rules.json), [`firebase.json`](firebase.json) |
| Evidências (logs e prints) e saídas das ferramentas | [`security/evidence/`](security/evidence/README.md) |

Metodologia: análise manual guiada pelo OWASP WSTG, mais SAST, SCA e DAST, com classificação alinhada ao OWASP Top 10 2021 e severidade por CVSS 3.1 (relatório, seção 2).

## Status

| Fase | Escopo | Situação |
|---|---|---|
| 0 | Ambiente isolado e baseline | Concluída em 23/10/2026 |
| 1 | Reconhecimento (inventário de rotas) | Concluída em 23/10/2026 |
| 2 | SAST, SCA, DAST e formalização dos achados (CVSS 3.1, reprodução e impacto) | Em andamento: SAST e SCA concluídos; ACH-01, 03, 08, 09, 10, 11 e 12 formalizados; evidência do ACH-03, ACH-09 e ACH-12 capturada |
| Próximas | Infra (Fase 7) | Fases 5 e 6 concluídas; Fase 7 parte 1 (Nginx + 2 backends gunicorn + headers) e parte 2, diferencial (Prometheus + Grafana provisionado + Redis + bucket 0,3s) feitas; falta TLS/HSTS e alertas |

## Como rodar

### Pré-requisitos

- Docker e Docker Compose v2.
- Um projeto Firebase próprio, com **Authentication (e-mail/senha)** e **Realtime Database** ativados.

### 1. Segredos

Ficam em `backend/`, fora da imagem e do git (estão no `.gitignore`).

- `backend/config.json`: chave da OpenAI. Um placeholder basta, porque o fluxo de query devolve uma resposta fixa e não chama a OpenAI em runtime. A chave não pode ficar vazia: o cliente da OpenAI é criado no import do backend e recusa chave vazia.

  ```bash
  cp backend/config.example.json backend/config.json   # {"openai_api_key": "sk-placeholder"}
  ```

- `backend/credentials.json`: chave privada da conta de serviço do seu projeto Firebase (Configurações do projeto, aba Contas de serviço, Gerar nova chave privada).

### 2. Configuração do Firebase

- `frontend/src/firebaseConfig.ts`: cole a configuração web do seu projeto.
- `docker-compose.yml`: ajuste `FIREBASE_DB_URL` para o `databaseURL` do seu projeto, o mesmo valor do `firebaseConfig.ts`. Sem essa variável o backend não sobe.
- Regras do Realtime Database: publique `database.rules.json`, que nega todo acesso de cliente (o backend usa o Admin SDK e continua funcionando; o frontend não acessa o banco), com `firebase deploy --only database --project <id-do-projeto>`. Sem isso o banco mantém as regras do projeto, que no modo de teste são abertas (ACH-12).

### 3. Subir

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend (via Nginx): http://localhost:5000
- Grafana (dashboard SRE, login anônimo): http://localhost:3001
- Prometheus: http://localhost:9090

O frontend chama o backend em `http://127.0.0.1:5000`, endereço fixo no código, então abra o frontend na mesma máquina que roda o Docker. Para parar: `docker compose down`.

### Verificação rápida

Refaça o fluxo do baseline: cadastro, login, salvar o perfil no Dashboard e uma pergunta no chat. As chamadas ao backend devem retornar HTTP 200, e a resposta do chat é fixa porque o `QueryManager` é um stub. O único erro esperado é o 404 de `/theactualbackendlink` (ACH-04), que aparece como "Failed to fetch your chats". O resultado de referência está no relatório, seção 2.4.

### Problemas comuns

| Sintoma | Causa |
|---|---|
| `bind source path does not exist` ao subir | Falta `backend/config.json` ou `backend/credentials.json`. |
| Backend encerra com `RuntimeError: FIREBASE_DB_URL is not set` | Variável ausente ou vazia no `docker-compose.yml`. |
| Backend encerra com `OpenAIError: Missing credentials` | `openai_api_key` vazia em `backend/config.json`. |
| Salvar ou ler o perfil retorna HTTP 400 | `FIREBASE_DB_URL` não corresponde ao RTDB do projeto do `credentials.json`. |

## Ambiente isolado

- Rede Docker dedicada (`coursesphere-net`). Só as portas 3000 e 5000 são publicadas, em todas as interfaces do host.
- Segredos montados como volume somente leitura, fora da imagem. O Compose falha se um segredo faltar, em vez de criar um diretório vazio no lugar.
- Backend: `python:3.12-slim`, Flask pelo CLI (debug desligado) em `0.0.0.0:5000`. Frontend: `node:20-alpine`, Vite em `0.0.0.0:3000`.

O build de produção do frontend (`frontend/Dockerfile`) ainda falha em 15 erros de TypeScript herdados do código original, então o ambiente de teste usa o modo de desenvolvimento do Vite (`frontend/Dockerfile.dev`). O build de produção é tratado na etapa de infraestrutura.

## Ferramentas

| Tipo | Ferramenta | Alvo | Saída |
|---|---|---|---|
| SAST | Semgrep | `backend/` e `frontend/src` | [`semgrep.json`](security/evidence/tools/semgrep.json) |
| SAST | Bandit | `backend/` | [`bandit.json`](security/evidence/tools/bandit.json) |
| SCA | pip-audit | Ambiente instalado na imagem do backend | [`pip-audit.txt`](security/evidence/tools/pip-audit.txt) |
| SCA | npm audit | `frontend/package-lock.json` | [`npm-audit.json`](security/evidence/tools/npm-audit.json) |
| DAST | OWASP ZAP | Aplicação em execução | Planejado |

As ferramentas rodaram em containers Docker efêmeros, sobre uma cópia do código sem segredos. Versões, comandos e o mapeamento dos resultados nos achados estão em [`security/evidence/tools/README.md`](security/evidence/tools/README.md).

## Achados

Os achados ficam no relatório (seção 3), cada um com ID `ACH-xx`, na ordem de prioridade abaixo. Os formalizados trazem CWE, OWASP Top 10 2021, passos de reprodução, impacto de negócio e causa raiz, e CVSS 3.1 quando aplicável; os demais seguem como rascunho.

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

As ferramentas apontaram também candidatos novos, como uso de `random` não criptográfico, HTTP em claro com URL fixa e dependências do frontend com avisos conhecidos. Eles estão em [`security/evidence/tools/README.md`](security/evidence/tools/README.md) e ainda não entraram no relatório.

## Como reproduzir os achados

Pré-requisitos: Docker e Docker Compose. Para o teste de regras do banco, também Node 20 e um JDK 11 ou superior.

Suba o ambiente a partir da raiz do repositório:

```bash
docker compose up --build
```

Portas: frontend em `localhost:3000`, backend via Nginx em `localhost:5000`, Grafana em `localhost:3001`, Prometheus em `localhost:9090`. As saídas de cada verificação estão gravadas em [`security/evidence/`](security/evidence/README.md), com os tokens redigidos.

**ACH-12 (regras do RTDB abertas).** O `databaseURL` é público (está em `frontend/src/firebaseConfig.ts`). Exporte-o e tente ler o banco sem credenciais:

```bash
export FIREBASE_DB_URL="https://SEU-PROJETO-default-rtdb.firebaseio.com"
curl -i "$FIREBASE_DB_URL/.json?shallow=true"
```

Esperado: HTTP 401 `Permission denied`. Evidência: `security/evidence/ACH-12/unauth-denied-after-lock.txt`; o export das regras corrigidas está em `ACH-12/database-rules.json`.

**ACH-03 (erro genérico e validação do header).**

```bash
curl -i -X POST localhost:5000/hash
curl -i localhost:5000/users/info
```

Esperado: HTTP 401 com `{"error":"Missing or invalid Authorization header"}`, sem vazar exceção. Antes da correção o `/hash` dava HTTP 500 com a exceção interna (`ACH-03/hash-no-auth-500.txt`); depois, 401 (`ACH-03/hash-no-auth-401.txt`, `ACH-03/users-info-no-auth-401.txt`).

**ACH-09 (autenticação opcional quebrada).**

```bash
curl -i -X POST localhost:5000/users/query -H "Content-Type: application/json" -d '{"query":"teste"}'
```

Esperado: HTTP 200 com `"Fake implementation"` sem token, ou seja, a rota responde sem autenticar. Evidência: `security/evidence/ACH-09/users-query-no-auth.txt`.

**ACH-08 (token fora da URL).** Faça login em `localhost:3000`, abra o Dashboard e salve o perfil. Depois:

```bash
docker compose logs backend1 backend2 | grep "/users/info"
```

Esperado: linhas `GET` e `POST /users/info` sem `?id_token=` na URL. Evidência: `security/evidence/ACH-08/after-fix-no-token.log` (token redigido).

**ACH-11 (debug desligado).** O backend roda sob gunicorn, sem o debugger do Werkzeug:

```bash
curl -s -o /dev/null -w "%{http_code}\n" localhost:5000/console
```

Esperado: 404, o console do debugger não existe. O ponto de entrada usa `app.run(debug=os.environ.get("FLASK_DEBUG") == "1")`, desligado por padrão.

**ACH-01 (container não-root).**

```bash
docker compose exec backend1 id
```

Esperado: `uid=10001(appuser)`, não root.

**ACH-10 (SQL por f-string).** Latente: o blueprint de cursos não está registrado (a linha está comentada em `backend/endpoints.py`) e não há rota `/courses` ativa, então não há reprodução no ambiente. O padrão está sinalizado por Semgrep e Bandit em `security/evidence/tools/`.

### Infraestrutura

Balanceamento de carga (alterna entre as instâncias):

```bash
for i in $(seq 1 10); do curl -s -i localhost:5000/health | grep -i X-Backend-Instance; done
```

Headers de segurança no Nginx:

```bash
curl -i localhost:5000/health | grep -iE "X-Content-Type-Options|X-Frame-Options|Referrer-Policy|Content-Security-Policy"
```

Evidências em `security/evidence/infra/` (distribuição, headers, logs das instâncias e o rate limit global).

### SAST, SCA e CI

A cada push e pull request, a aba **Actions** do GitHub roda Semgrep, Bandit, pip-audit e npm audit (`.github/workflows/security.yml`). Para rodar localmente, em containers (sem instalar no host e sem analisar os segredos):

```bash
docker run --rm -e SEMGREP_SEND_METRICS=off -v "$PWD:/src" -w /src semgrep/semgrep \
  semgrep scan --config p/python --config p/flask --config p/javascript \
  --exclude config.json --exclude credentials.json --exclude cornell-course-sphere-data \
  backend frontend/src
docker run --rm -v "$PWD/frontend:/app" -w /app node:20-alpine npm audit --audit-level=high
```

### Teste das regras do RTDB (emulador, offline)

```bash
cd security/rules-tests
npm install
npm run emulate
```

Esperado: 4 testes passam (acesso de cliente negado). Roda só no emulador, sem tocar o projeto real nem usar segredos. Evidência: `security/evidence/ACH-12/rules-test-pass.txt`.

## Alterações em relação ao repositório original

Mudanças mínimas, registradas no relatório (seções 2.4 e 4):

- `backend/main.py`: a chamada à OpenAI que ficava solta no fim do módulo foi para `if __name__ == "__main__":`, para o import não disparar chamada de rede.
- `backend/firebase.py`: a URL do RTDB vem de `FIREBASE_DB_URL`, sem valor padrão (correção do ACH-06).
- `backend/endpoints.py` (`GET /users/info`) e `frontend/src/api.ts` (`setProfileInfoIfLoggedIn`): o token saiu da query string e foi para o header `Authorization` (correção do ACH-08).
- `backend/endpoints.py`: respostas de erro genéricas (detalhe só no log), validação do header `Authorization` com HTTP 401 e errorhandler global (correção do ACH-03).
- `frontend/Dockerfile`: base `node:20-alpine`, porque o Vite 5 exige Node 18 ou superior.
- `frontend/src/firebaseConfig.ts`: configuração do projeto Firebase usado na avaliação.
- `database.rules.json` e `firebase.json`: regras do Realtime Database versionadas, com acesso de cliente negado (correção do ACH-12, publicada e validada em 25/10/2026).
- Hardening da Fase 5 (`backend/endpoints.py`, `requirements.txt`, Dockerfiles): debug desligado por padrão (fecha ACH-11), CORS por allowlist, rate limiting com `flask-limiter` (endurece ACH-09) e containers não-root (fecha ACH-01). Headers de segurança (CSP, HSTS...) ficam para o Nginx na Fase 7.
- Observabilidade da Fase 6 (`backend/endpoints.py`, `requirements.txt`): logs estruturados em JSON (sem token), eventos de autenticação, `/health` e `/metrics` (Prometheus). SLIs/SLOs e o dashboard estão no relatório (seção 6); Grafana + Prometheus funcional entra na Fase 7.
- Infra da Fase 7, parte 1 (`docker-compose.yml`, `nginx/nginx.conf`, `backend/Dockerfile`, `requirements.txt`): backend sob gunicorn, duas instâncias (`backend1`/`backend2`) atrás de um Nginx que balanceia em round-robin, com headers de segurança no Nginx. O frontend chama `localhost:5000`, que agora é o Nginx (seção 7).
- Infra da Fase 7, parte 2, diferencial (`docker-compose.yml`, `observability/`, `backend/`): Prometheus + Grafana provisionado (dashboard SRE), Redis como store compartilhado do rate limiter (limite global entre instâncias) e bucket de latência de 0,3 s. Prometheus/Grafana/Redis são do ambiente de teste (seção 6).
- CI de segurança, diferencial (`.github/`): workflow do GitHub Actions que roda Semgrep, Bandit, pip-audit e npm audit a cada push/PR (em modo report), mais Dependabot para atualização de dependências. Os resultados aparecem na aba **Actions** do repositório (seção 7.8).
- Teste de autorização das regras do RTDB, diferencial (`security/rules-tests/`): teste de unidade das regras com o emulador do Firebase, provando que o acesso de cliente é negado (regressão do ACH-12). Rodar com `cd security/rules-tests && npm install && npm run emulate` (seção 7.9).
- Higiene do repositório: removidos arquivos `.DS_Store`, pastas `.idea/` e um `package-lock.json` vazio na raiz, versionados por engano no original. No `.gitignore`, o padrão `*config.json` virou `config.json`, porque também casava com `frontend/tsconfig.json`, e `__pycache__/` foi incluído.

## Estrutura do repositório

```
backend/                        aplicação Flask
  Dockerfile                    imagem do backend
  config.example.json           modelo do config.json, com placeholder da OpenAI
  cornell-course-sphere-data/   dados do repositório original, não usados em runtime
frontend/                       aplicação React
  Dockerfile                    build de produção (hoje falha em erros de TypeScript)
  Dockerfile.dev                Vite em modo de desenvolvimento, usado pelo Compose
experiment/                     notebook de experimento do repositório original
docker-compose.yml              ambiente isolado (Nginx + 2 backends + frontend)
nginx/nginx.conf                balanceador e headers de segurança
observability/                  Prometheus e Grafana provisionado (dashboard SRE)
.github/                        CI de segurança (Actions) e Dependabot
security/rules-tests/           teste das regras do RTDB (emulador do Firebase)
database.rules.json             regras do Realtime Database (acesso de cliente negado)
firebase.json                   aponta o Firebase CLI para as regras
security/
  report.md                     relatório técnico
  recon.md                      inventário de rotas e superfície de ataque
  evidence/
    baseline/                   log e prints do baseline
    tools/                      saídas de SAST e SCA
```
