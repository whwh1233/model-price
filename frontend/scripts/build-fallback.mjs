#!/usr/bin/env node
// Generates frontend/public/fallback.json from backend/data/providers/*.json.
// Shipped inside the static bundle so first-time visitors always see data,
// even if the backend is cold-starting or unreachable.

import { readFile, readdir, writeFile, mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const FRONTEND_ROOT = resolve(__dirname, "..");
const PROVIDERS_DIR = resolve(FRONTEND_ROOT, "../backend/data/providers");
const INDEX_FILE = resolve(FRONTEND_ROOT, "../backend/data/index.json");
const OUTPUT_FILE = resolve(FRONTEND_ROOT, "public/fallback.json");

const DISPLAY_NAMES = {
  aws_bedrock: "AWS Bedrock",
  openai: "OpenAI",
  azure_openai: "Azure OpenAI",
  google_vertex_ai: "Google Vertex AI",
  google_gemini: "Google Vertex",
  openrouter: "OpenRouter",
  anthropic: "Anthropic",
  xai: "xAI",
};

const FAMILY_PATTERNS = [
  ["Cogito", ["cogito"]],
  ["Claude", ["claude"]],
  ["OpenAI O-Series", ["^o1", "^o3", "^o4"]],
  ["GPT", ["gpt-", "gpt ", "chatgpt", "gpt4", "gpt3", "gpt5", "babbage", "davinci", "omni moderation", "codex", "^computer use preview"]],
  ["DALL-E", ["dall-e", "dall·e"]],
  ["Whisper", ["whisper"]],
  ["OpenAI TTS", ["^tts", "-tts"]],
  ["Sora", ["sora"]],
  ["Gemini", ["gemini"]],
  ["Gemma", ["gemma"]],
  ["Imagen", ["imagen"]],
  ["Veo", ["^veo"]],
  ["Llama", ["llama", "llamaguard"]],
  ["Mistral", ["mixtral", "ministral", "pixtral", "codestral", "magistral", "voxtral", "devstral", "mistral", "saba"]],
  ["Nova", ["^nova"]],
  ["Titan", ["titan"]],
  ["Command", ["command"]],
  ["Cohere Embed", ["cohere embed", "embed 3", "embed 4"]],
  ["Rerank", ["rerank"]],
  ["Jamba", ["jamba"]],
  ["Jurassic", ["jurassic"]],
  ["Grok", ["grok"]],
  ["DeepSeek", ["deepseek", "deep-seek", "^r1"]],
  ["Qwen", ["qwen", "qwq", "tongyi"]],
  ["Nemotron", ["nemotron"]],
];

const PROVIDER_PREFIXES = [
  "Anthropic:", "OpenAI:", "Google:", "Meta:", "Mistral:", "Cohere:",
  "AI21:", "Amazon:", "Microsoft:", "NVIDIA:", "xAI:", "DeepSeek:",
  "Baidu:", "Alibaba:", "ByteDance:", "Tencent:", "Perplexity:",
  "AllenAI:", "Arcee AI:", "Arcee:", "Nous:", "TheDrummer:", "Z.AI:",
  "AionLabs:", "MiniMax:", "Inflection:", "Inception:", "Kwaipilot:",
  "Morph:", "Relace:", "TNG:", "Mancer:", "Meituan:", "EssentialAI:",
  "EleutherAI:", "Venice:", "OpenGVLab:", "StepFun:", "THUDM:",
  "IBM:", "NeverSleep:", "Xiaomi:", "AlfredPros:",
  "ByteDance Seed:", "Deep Cogito:", "Nex AGI:", "Prime Intellect:",
  "NousResearch:", "Qwen:", "TwelveLabs:",
];

function extractFamily(modelName) {
  let name = (modelName ?? "").trim();
  if (!name) return "Other";

  const lower = name.toLowerCase();
  for (const prefix of PROVIDER_PREFIXES) {
    if (lower.startsWith(prefix.toLowerCase())) {
      name = name.slice(prefix.length).trim();
      break;
    }
  }
  const target = name.toLowerCase();

  for (const [family, keywords] of FAMILY_PATTERNS) {
    for (const keyword of keywords) {
      if (keyword.startsWith("^")) {
        if (target.startsWith(keyword.slice(1))) return family;
      } else if (target.includes(keyword)) {
        return family;
      }
    }
  }
  return "Other";
}

async function loadProviderFiles() {
  if (!existsSync(PROVIDERS_DIR)) {
    throw new Error(`Provider data directory not found: ${PROVIDERS_DIR}`);
  }
  const entries = await readdir(PROVIDERS_DIR);
  const files = entries.filter((name) => name.endsWith(".json")).sort();
  const payloads = await Promise.all(
    files.map(async (name) => {
      const raw = await readFile(join(PROVIDERS_DIR, name), "utf-8");
      return JSON.parse(raw);
    }),
  );
  return payloads;
}

async function loadIndex() {
  if (!existsSync(INDEX_FILE)) return null;
  try {
    return JSON.parse(await readFile(INDEX_FILE, "utf-8"));
  } catch {
    return null;
  }
}

function buildProviders(models) {
  const stats = new Map();
  for (const model of models) {
    const current = stats.get(model.provider) ?? { count: 0, last_updated: model.last_updated };
    current.count += 1;
    if (model.last_updated && model.last_updated > current.last_updated) {
      current.last_updated = model.last_updated;
    }
    stats.set(model.provider, current);
  }
  return [...stats.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([name, value]) => ({
      name,
      display_name: DISPLAY_NAMES[name] ?? name,
      model_count: value.count,
      last_updated: value.last_updated ?? null,
    }));
}

function buildFamilies(models) {
  const counts = new Map();
  for (const model of models) {
    const family = extractFamily(model.model_name);
    counts.set(family, (counts.get(family) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0]))
    .map(([name, count]) => ({ name, count }));
}

function buildStats(models, index) {
  const inputs = models.map((m) => m.pricing?.input).filter((v) => typeof v === "number");
  const outputs = models.map((m) => m.pricing?.output).filter((v) => typeof v === "number");
  const providers = new Set(models.map((m) => m.provider));
  const avg = (arr) => (arr.length ? arr.reduce((sum, v) => sum + v, 0) / arr.length : 0);

  return {
    total_models: models.length,
    providers: providers.size,
    avg_input_price: avg(inputs),
    avg_output_price: avg(outputs),
    last_refresh: index?.last_refresh ?? new Date().toISOString(),
  };
}

async function main() {
  const payloads = await loadProviderFiles();
  const models = payloads.flatMap((payload) => payload.models ?? []);
  if (models.length === 0) {
    throw new Error("No models found in backend data — aborting fallback generation.");
  }
  models.sort((a, b) =>
    (a.model_name ?? "").localeCompare(b.model_name ?? "", "en", { sensitivity: "base" }),
  );

  const index = await loadIndex();
  const snapshot = {
    generated_at: new Date().toISOString(),
    source_last_refresh: index?.last_refresh ?? null,
    models,
    providers: buildProviders(models),
    families: buildFamilies(models),
    stats: buildStats(models, index),
  };

  await mkdir(dirname(OUTPUT_FILE), { recursive: true });
  await writeFile(OUTPUT_FILE, JSON.stringify(snapshot));
  console.log(
    `fallback.json written: ${models.length} models, ${snapshot.providers.length} providers, ${snapshot.families.length} families.`,
  );
}

main().catch((err) => {
  console.error("[build-fallback] failed:", err);
  process.exit(1);
});
