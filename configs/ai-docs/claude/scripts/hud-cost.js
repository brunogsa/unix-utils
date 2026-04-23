#!/usr/bin/env node
/**
 * claude-hud extra-cmd: session cost per model + cache hit rate.
 *
 * Usage:
 *   node hud-cost.js               emit {"label": "Opus4.7 $11 • Sonnet4.6 $9 • Haiku4.5 $0.02 | cache 89%"}
 *   node hud-cost.js --help        print this help
 *
 * Wired via claude-hud's --extra-cmd flag in ~/.claude/settings.json.
 * Scans both the main session transcript and all subagent transcripts
 * (in {sessionId}/subagents/) so Haiku costs from Explore agents are
 * included. Cached by max mtime across all files.
 *
 * Prices are April 2026 list prices. Unknown model families (e.g. GLM)
 * are shown with a trailing '?' and excluded from the cost total.
 * On a Pro/Max plan this shows API-equivalent cost, not your actual bill.
 */

'use strict';

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const readline = require('node:readline');

// Per-million-token prices (USD), April 2026. Anthropic families only.
const PRICES = {
  opus:   { in: 5, out: 25, cacheWrite5m: 6.25, cacheWrite1h: 10.0, cacheRead: 0.50 },
  sonnet: { in: 3, out: 15, cacheWrite5m: 3.75, cacheWrite1h:  6.0, cacheRead: 0.30 },
  haiku:  { in: 1, out:  5, cacheWrite5m: 1.25, cacheWrite1h:  2.0, cacheRead: 0.10 },
};

const USAGE = [
  'Usage:',
  '  node hud-cost.js               emit {"label": "Opus4.7 $11 • Sonnet4.6 $9 | cache 89%"}',
  '  node hud-cost.js --help        print this help',
].join('\n');

// Short versioned name: 'Opus4.7', 'Sonnet4.6', 'Haiku4.5', 'GLM', 'GPT'…
function shortModelName(modelId) {
  const id = String(modelId || '').toLowerCase();
  if (id.startsWith('claude-')) {
    const parts = id.slice(7).split('-'); // e.g. ['opus','4','7'] or ['haiku','4','5','20251001']
    const family = parts[0];
    const major  = parts[1];
    const minor  = parts[2];
    const name   = family.charAt(0).toUpperCase() + family.slice(1);
    if (major && minor) return `${name}${major}.${minor}`; // 'Opus4.7'
    if (major)          return `${name}${major}`;
    return name;
  }
  // Non-Anthropic: uppercase short acronyms (≤3 chars), title-case longer
  const seg = (id.split('-')[0] || '').replace(/[^a-z0-9]/g, '');
  if (!seg) return 'Unknown';
  return seg.length <= 3 ? seg.toUpperCase() : seg.charAt(0).toUpperCase() + seg.slice(1);
}

// Pricing table for a model ID, or null for unknown families.
function priceFor(modelId) {
  const id = String(modelId || '').toLowerCase();
  if (id.includes('opus'))   return PRICES.opus;
  if (id.includes('sonnet')) return PRICES.sonnet;
  if (id.includes('haiku'))  return PRICES.haiku;
  return null;
}

// Returns { mainPath, subagentPaths, maxMtime, sessionId } for the
// most-recently-modified session in the project directory.
function findSession(cwd) {
  const mangled    = cwd.replace(/\//g, '-');
  const projectDir = path.join(os.homedir(), '.claude', 'projects', mangled);
  if (!fs.existsSync(projectDir)) return null;

  // Find the newest flat JSONL (main session transcript).
  let newest = null;
  for (const name of fs.readdirSync(projectDir)) {
    if (!name.endsWith('.jsonl')) continue;
    const full = path.join(projectDir, name);
    const stat = fs.statSync(full);
    if (!newest || stat.mtimeMs > newest.mainMtime) {
      newest = { mainPath: full, sessionId: name.slice(0, -6), mainMtime: stat.mtimeMs, projectDir };
    }
  }
  if (!newest) return null;

  // Collect subagent transcripts from {sessionId}/subagents/*.jsonl
  const subagentDir  = path.join(newest.projectDir, newest.sessionId, 'subagents');
  const subagentPaths = [];
  let maxMtime        = newest.mainMtime;

  if (fs.existsSync(subagentDir)) {
    for (const name of fs.readdirSync(subagentDir)) {
      if (!name.endsWith('.jsonl')) continue;
      const full = path.join(subagentDir, name);
      const stat = fs.statSync(full);
      subagentPaths.push(full);
      if (stat.mtimeMs > maxMtime) maxMtime = stat.mtimeMs;
    }
  }

  return { ...newest, subagentPaths, maxMtime };
}

function readCache(cacheFile) {
  try { return JSON.parse(fs.readFileSync(cacheFile, 'utf8')); } catch { return null; }
}

function writeCache(cacheFile, data) {
  try { fs.writeFileSync(cacheFile, JSON.stringify(data)); } catch {
    // Non-fatal: next call just re-parses.
  }
}

async function parseOneFile(filePath, totals) {
  const stream = fs.createReadStream(filePath, { encoding: 'utf8' });
  const rl     = readline.createInterface({ input: stream, crlfDelay: Infinity });

  for await (const line of rl) {
    if (!line) continue;
    let record;
    try { record = JSON.parse(line); } catch { continue; }
    if (record.type !== 'assistant') continue;
    const usage = record.message && record.message.usage;
    if (!usage) continue;

    const inTok      = usage.input_tokens                || 0;
    const outTok     = usage.output_tokens               || 0;
    const cacheTotal = usage.cache_creation_input_tokens || 0;
    const cacheRead  = usage.cache_read_input_tokens     || 0;
    const cc5m       = (usage.cache_creation && usage.cache_creation.ephemeral_5m_input_tokens) || 0;
    const cc1h       = (usage.cache_creation && usage.cache_creation.ephemeral_1h_input_tokens) || 0;
    // Remainder priced at 5m — conservative vs. the 2x 1h rate.
    const ccUnknown  = Math.max(0, cacheTotal - cc5m - cc1h);

    // Always accumulate for cache hit rate.
    totals.input       += inTok;
    totals.cacheCreate += cacheTotal;
    totals.cacheRead   += cacheRead;

    const modelId = record.message && record.message.model;
    const p       = priceFor(modelId);
    const name    = shortModelName(modelId);

    if (!p) {
      if ((inTok + outTok + cacheTotal + cacheRead) > 0 && !totals.unknownNames.includes(name)) {
        totals.unknownNames.push(name);
      }
      continue;
    }

    const cost = (inTok * p.in + outTok * p.out +
                  (cc5m + ccUnknown) * p.cacheWrite5m +
                  cc1h * p.cacheWrite1h +
                  cacheRead * p.cacheRead) / 1_000_000;

    totals.byModel[name] = (totals.byModel[name] || 0) + cost;
  }
}

async function accumulateUsage({ mainPath, subagentPaths }) {
  const totals = { byModel: {}, unknownNames: [], input: 0, cacheCreate: 0, cacheRead: 0 };
  for (const filePath of [mainPath, ...subagentPaths]) {
    await parseOneFile(filePath, totals);
  }
  return totals;
}

function formatCost(n) {
  if (n >= 100) return `$${n.toFixed(0)}`;
  if (n >= 10)  return `$${n.toFixed(1)}`;
  return `$${n.toFixed(2)}`;
}

// 'Opus4.7' → 'Opus', 'Sonnet4.6' → 'Sonnet'. Non-versioned names pass through.
function stripVersion(name) {
  return name.replace(/\d+\.\d+$/, '');
}

function aggregateByFamily(byModel) {
  const out = {};
  for (const [name, cost] of Object.entries(byModel)) {
    const f = stripVersion(name);
    out[f] = (out[f] || 0) + cost;
  }
  return out;
}

function formatLabel({ byModel, unknownNames, input, cacheCreate, cacheRead }) {
  const denom     = input + cacheCreate + cacheRead;
  const hitPct    = denom > 0 ? Math.round((cacheRead / denom) * 100) : 0;
  const cachePart = `cache ${hitPct}%`;

  const sorted = (obj) => Object.entries(obj).sort(([, a], [, b]) => b - a);

  // compact=true: round costs ≥$1 to whole dollars (sub-$1 kept precise)
  const buildParts = (entries, compact) => {
    const parts = entries.map(([name, cost]) => {
      const costStr = compact && cost >= 1 ? `$${Math.round(cost)}` : formatCost(cost);
      return `${name} ${costStr}`;
    });
    unknownNames.forEach(n => parts.push(`${n}?`));
    return parts;
  };

  const byFamily = aggregateByFamily(byModel);

  // Try four levels of detail before falling back to single total.
  for (const entries of [sorted(byModel), sorted(byFamily)]) {
    for (const compact of [false, true]) {
      const parts = buildParts(entries, compact);
      if (parts.length === 0) parts.push(formatCost(0));
      const label = parts.join(' • ') + ' | ' + cachePart;
      if (label.length <= 48) return label;
    }
  }

  const total = Object.values(byModel).reduce((a, b) => a + b, 0);
  return `${formatCost(total)} | ${cachePart}`;
}

async function main() {
  if (process.argv.includes('--help') || process.argv.includes('-h')) {
    process.stdout.write(USAGE + '\n');
    process.exit(0);
  }

  try {
    const session = findSession(process.cwd());
    if (!session) {
      process.stdout.write(JSON.stringify({ label: '$0.00 | cache 0%' }));
      return;
    }

    const cacheFile = path.join(os.tmpdir(), `claude-hud-cost-${session.sessionId}.json`);
    const cached    = readCache(cacheFile);
    if (cached && cached.maxMtime === session.maxMtime && typeof cached.label === 'string') {
      process.stdout.write(JSON.stringify({ label: cached.label }));
      return;
    }

    const totals = await accumulateUsage(session);
    const label  = formatLabel(totals);
    writeCache(cacheFile, { maxMtime: session.maxMtime, label });
    process.stdout.write(JSON.stringify({ label }));
  } catch {
    process.stdout.write(JSON.stringify({ label: '' }));
  }
}

main();
