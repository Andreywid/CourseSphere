# Evidências

Esta pasta guarda os prints e logs que sustentam o [relatório](../report.md).

- `baseline/`: evidências do ambiente de referência (Fase 0).
- `ACH-NN/`: uma pasta por achado, com o mesmo ID usado na seção 3 do relatório (ex.: `ACH-02/`). É criada quando houver evidência.

## Arquivos

| Arquivo | O que mostra | Usado em | Situação |
|---|---|---|---|
| `baseline/backend-baseline.log` | Saída de `docker compose logs backend` da execução final do baseline, depois da correção do ACH-06: duas subidas do Flask (`0.0.0.0:5000`, debug desligado; a segunda é a reinicialização dos containers), `POST /users/create` 200, `GET` e `POST /users/info` 200, `POST /users/query` 200, `POST /hash` 200 (duas vezes) e `OPTIONS /theactualbackendlink` 404. Os valores de `id_token=` foram redigidos (`eyJ...[REDACTED]`) e os códigos de cor ANSI, removidos. Antes da redação, o valor tinha 932 caracteres e prefixo de JWT (`eyJ`). | Baseline (2.4), ACH-04, ACH-06, ACH-08 | Completo. |
| `baseline/baseline-signup-200.png` | Deve mostrar o cadastro concluído, com `POST /users/create` em HTTP 200. | Baseline (2.4) | A adicionar |
| `baseline/baseline-profile-save-200.png` | Deve mostrar o salvamento do perfil, com `POST /users/info` em HTTP 200. | Baseline (2.4), ACH-06 | A adicionar |
| `baseline/baseline-dashboard.png` | Deve mostrar o dashboard depois do login. | Baseline (2.4) | A adicionar |
| `baseline/baseline-query.png` | Deve mostrar o chat depois da pergunta, com a bolha do bot vazia (resposta fixa do `QueryManager`) e o toast "Successfully retrieved bot response!". O toast não prova o status HTTP (ACH-07); o status está no log. | Baseline (2.4) | A adicionar |
| `tools/` | Saídas de SAST e SCA (`semgrep.json`, `bandit.json`, `pip-audit.txt`, `pip-audit.json`, `npm-audit.json`) e, em `tools/README.md`, o que cada ferramenta rodou e o mapeamento dos hits nos achados. Sem segredos: os scans leram uma cópia sem `credentials.json` e `config.json`. | Seção 2.3 e candidatos a novos achados | Capturado |

## Antes de salvar um arquivo

Remova ou oculte segredos: tokens, chaves de API e o conteúdo de `credentials.json` ou `config.json`. O log do backend registra o `id_token` na URL de `GET /users/info` (ACH-08), então nunca salve esse log sem redigir.

Para recapturar o log do backend com a redação aplicada:

```bash
docker compose logs backend \
  | sed -E 's/\x1b\[[0-9;]*m//g; s/(id_token=[^ &"]{0,3})[^ &"]*/\1...[REDACTED]/g' \
  > security/evidence/baseline/backend-baseline.log
```

Depois, confirme que `grep -E 'eyJ[A-Za-z0-9_-]{4,}' security/evidence/baseline/backend-baseline.log` não retorna nada.
