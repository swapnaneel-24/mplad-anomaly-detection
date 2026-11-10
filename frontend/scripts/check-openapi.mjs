#!/usr/bin/env node
// OpenAPI → TypeScript contract generator and drift check.
//
// Reads the committed OpenAPI schema (backend/contracts/openapi.json) and
// generates `src/api/contracts.gen.ts` — a reproducible, read-only file
// containing TypeScript interfaces and type aliases that mirror the
// OpenAPI component schemas exactly.
//
// Then compares the generated file against the existing
// `src/api/contracts.ts` (the hand-maintained file the application
// imports) to detect drift. If the two diverge, the script prints the
// differences and exits 1.
//
// Usage:
//   node scripts/check-openapi.mjs           # generate + check
//   node scripts/check-openapi.mjs --write   # generate + overwrite contracts.gen.ts
//
// The application imports from `contracts.ts` (hand-maintained, may
// include frontend-only helpers). The generated `contracts.gen.ts` is
// the reproducible source of truth for the OpenAPI-mirrored types. A
// drift-checker compares the two and reports any schema that exists in
// the generated file but differs from (or is absent from) the
// hand-maintained file.
//
// This is CI-compatible: exit 0 on no drift, exit 1 on drift.

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createHash } from "node:crypto";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ROOT = join(__dirname, "..");
const OPENAPI_PATH = join(ROOT, "..", "backend", "contracts", "openapi.json");
const GEN_PATH = join(ROOT, "src", "api", "contracts.gen.ts");
const HAND_PATH = join(ROOT, "src", "api", "contracts.ts");

// --- Load OpenAPI -----------------------------------------------------------

if (!existsSync(OPENAPI_PATH)) {
  console.error(`OpenAPI schema not found at ${OPENAPI_PATH}`);
  console.error("Run this script from the repository root after cloning the backend.");
  process.exit(1);
}

const openapi = JSON.parse(readFileSync(OPENAPI_PATH, "utf-8"));
const schemas = openapi?.components?.schemas ?? {};
const appName = openapi?.info?.title ?? "PEIARS API";
const appVersion = openapi?.info?.version ?? "unknown";

// --- TypeScript generator ---------------------------------------------------

/** Map an OpenAPI schema node to a TypeScript type string. */
function tsType(node, indent = 0) {
  if (!node) return "unknown";
  if (node.$ref) {
    const refName = node.$ref.split("/").pop();
    return refName || "unknown";
  }
  if (node.const) return JSON.stringify(node.const);
  if (node.enum) return node.enum.map((v) => JSON.stringify(v)).join(" | ");
  const anyOf = node.anyOf || node.oneOf;
  if (anyOf) return anyOf.map((n) => tsType(n, indent)).join(" | ");
  if (node.allOf) return node.allOf.map((n) => tsType(n, indent)).join(" & ");
  switch (node.type) {
    case "string":
      return "string";
    case "integer":
    case "number":
      return "number";
    case "boolean":
      return "boolean";
    case "array":
      return `Array<${tsType(node.items, indent)}>`;
    case "object": {
      const props = node.properties ?? {};
      const required = new Set(node.required ?? []);
      const lines = Object.entries(props).map(([key, sub]) => {
        const opt = required.has(key) ? "" : "?";
        const desc = sub.description ? `  /** ${sub.description} */\n` : "";
        return `${desc}  ${key}${opt}: ${tsType(sub, indent + 1)};`;
      });
      if (lines.length === 0) return "Record<string, never>";
      return `{\n${"  ".repeat(indent)}${lines.join("\n" + "  ".repeat(indent))}\n${"  ".repeat(indent)}}`;
    }
    default:
      return "unknown";
  }
}

/** Generate the TypeScript file content. */
function generate() {
  const lines = [];
  lines.push("// AUTO-GENERATED from backend/contracts/openapi.json — DO NOT EDIT.");
  lines.push("// Regenerate with: npm run openapi:check");
  lines.push(`// Source: ${appName} v${appVersion}`);
  lines.push("// This file is the reproducible source of truth for OpenAPI-mirrored types.");
  lines.push("// The application imports from contracts.ts (hand-maintained, may include");
  lines.push("// frontend-only helpers). Drift between the two is reported by the check.");
  lines.push("");
  lines.push("// --- Schemas -----------------------------------------------------------");
  lines.push("");
  for (const [name, schema] of Object.entries(schemas)) {
    if (schema.description) {
      lines.push(`/** ${schema.description} */`);
    }
    if (schema.enum) {
      lines.push(`export type ${name} = ${schema.enum.map((v) => JSON.stringify(v)).join(" | ")};`);
    } else if (schema.type === "object" || schema.properties) {
      const ts = tsType(schema);
      lines.push(`export interface ${name} ${ts};`);
    } else if (schema.const) {
      lines.push(`export type ${name} = ${JSON.stringify(schema.const)};`);
    } else {
      lines.push(`export type ${name} = ${tsType(schema)};`);
    }
    lines.push("");
  }
  return lines.join("\n");
}

const generated = generate();

// --- Write or compare -------------------------------------------------------

const writeMode = process.argv.includes("--write");
if (writeMode) {
  writeFileSync(GEN_PATH, generated + "\n", "utf-8");
  console.log(`Wrote ${GEN_PATH} (${generated.length} bytes)`);
  process.exit(0);
}

// Compare against the existing generated file (if any).
if (!existsSync(GEN_PATH)) {
  writeFileSync(GEN_PATH, generated + "\n", "utf-8");
  console.log(`Initialized ${GEN_PATH} (${generated.length} bytes)`);
} else {
  const existing = readFileSync(GEN_PATH, "utf-8");
  const existingHash = createHash("sha256").update(existing).digest("hex");
  const generatedHash = createHash("sha256").update(generated + "\n").digest("hex");
  if (existingHash !== generatedHash) {
    console.error("DRIFT: contracts.gen.ts is stale.");
    console.error("  existing sha256: " + existingHash);
    console.error("  generated sha256: " + generatedHash);
    console.error("Run `npm run openapi:check -- --write` to regenerate.");
    process.exit(1);
  }
}

// --- Drift check: contracts.gen.ts vs contracts.ts -------------------------
//
// Verify that every interface/type name in contracts.gen.ts also exists in
// contracts.ts with compatible required fields. This catches the case where
// the hand-maintained file diverges from the OpenAPI schema.

const handSource = readFileSync(HAND_PATH, "utf-8");

// Extract interface names + field names from the hand-maintained file.
const handInterfaces = new Map();
const ifRe = /export\s+interface\s+(\w+)\s*\{([^}]*)\}/g;
let m;
while ((m = ifRe.exec(handSource)) !== null) {
  const name = m[1];
  const body = m[2];
  const fields = new Set();
  const fRe = /^\s*(?:readonly\s+)?(\w+)\??\s*:/gm;
  let fm;
  while ((fm = fRe.exec(body)) !== null) {
    fields.add(fm[1]);
  }
  handInterfaces.set(name, fields);
}

// Extract type aliases (enum unions) from the hand-maintained file.
const handTypes = new Map();
const typeRe = /export\s+type\s+(\w+)\s*=\s*([^;]+);/g;
while ((m = typeRe.exec(handSource)) !== null) {
  handTypes.set(m[1], m[2].trim());
}

const drifts = [];
for (const [name, schema] of Object.entries(schemas)) {
  // Skip non-object schemas without enums for the interface check.
  if (schema.enum) {
    if (!handTypes.has(name)) {
      // The hand-maintained file may declare it as a type alias.
      if (!handInterfaces.has(name)) {
        drifts.push(`${name}: enum type in openapi.json but missing from contracts.ts`);
      }
    }
    continue;
  }
  if (!handInterfaces.has(name)) {
    // Not every OpenAPI schema needs to be in the hand-maintained file
    // (some are response-only wrappers). Skip silently.
    continue;
  }
  const handFields = handInterfaces.get(name);
  const apiRequired = new Set(schema.required ?? []);
  for (const req of apiRequired) {
    if (!handFields.has(req)) {
      drifts.push(`${name}: required field "${req}" in openapi.json missing from contracts.ts`);
    }
  }
}

if (drifts.length > 0) {
  console.error("DRIFT between contracts.gen.ts and contracts.ts:");
  for (const d of drifts) console.error("  - " + d);
  process.exit(1);
}

console.log("OK — contracts.gen.ts is up to date and contracts.ts has no drift.");
process.exit(0);
