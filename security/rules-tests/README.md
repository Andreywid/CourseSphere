# Teste de autorização das regras do RTDB (ACH-12)

Teste automatizado das regras do Realtime Database (`../../database.rules.json`) com o
Firebase Local Emulator Suite e o `@firebase/rules-unit-testing`. Prova que o acesso de
cliente é negado (leitura/escrita, autenticado e não), prevenindo regressão da correção
do ACH-12.

Roda offline, num projeto `demo-*`: **não toca o projeto real, não usa segredos**. Precisa
de Node e Java (o emulador baixa sozinho).

## Rodar

```bash
cd security/rules-tests
npm install
npm run emulate   # firebase emulators:exec --project demo-coursesphere --only database "npm test"
```

Esperado: os 4 testes passam (acesso de cliente negado).

## É um teste de unidade das regras

Diferente da verificação por REST do ACH-12 (relatório, seção 4.2), que checa a regra já
publicada no projeto. Se as regras passarem a ser por usuário (`auth.uid === $uid`),
`rules.test.mjs` já traz o esqueleto para afirmar que um usuário acessa só o próprio nó.
