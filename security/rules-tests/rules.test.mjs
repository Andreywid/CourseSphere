// Teste de autorização das regras do Realtime Database (ACH-12).
// Carrega database.rules.json no emulador e prova que o acesso de cliente é negado,
// prevenindo regressão da correção (as regras originais em modo de teste eram abertas).
// Roda offline, sem tocar o projeto real nem usar segredos.
import { readFileSync } from "node:fs";
import { test, before, after } from "node:test";
import { initializeTestEnvironment, assertFails } from "@firebase/rules-unit-testing";
import { ref, get, set } from "firebase/database";

const rules = readFileSync(new URL("../../database.rules.json", import.meta.url), "utf8");
let env;

before(async () => {
  env = await initializeTestEnvironment({
    projectId: "demo-coursesphere",
    database: { rules },
  });
});

after(async () => {
  await env?.cleanup();
});

test("leitura de cliente NÃO autenticado é negada", async () => {
  const db = env.unauthenticatedContext().database();
  await assertFails(get(ref(db, "users/alice/info")));
});

test("escrita de cliente NÃO autenticado é negada", async () => {
  const db = env.unauthenticatedContext().database();
  await assertFails(set(ref(db, "users/alice/info"), { about: "x" }));
});

test("leitura de cliente autenticado também é negada (deny-all; backend usa Admin SDK)", async () => {
  const db = env.authenticatedContext("alice").database();
  await assertFails(get(ref(db, "users/alice/info")));
});

test("escrita de cliente autenticado também é negada", async () => {
  const db = env.authenticatedContext("alice").database();
  await assertFails(set(ref(db, "users/alice/info"), { about: "x" }));
});

// Se as regras passarem a ser por usuário (auth.uid === $uid em users/$uid), acrescentar:
// - usuário "alice" lê/escreve users/alice -> PERMITIDO (assertSucceeds)
// - usuário "alice" lê/escreve users/bob   -> NEGADO    (assertFails)
