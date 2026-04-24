'use strict';

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

const {
  PRICES,
  shortModelName, priceFor,
  formatCost, stripVersion, aggregateByFamily,
  formatLabel, parseOneFile,
} = require('./hud-cost.js');

// Builds the accumulator that parseOneFile mutates.
const makeTotals = () => ({ byModel: {}, unknownNames: [], input: 0, cacheCreate: 0, cacheRead: 0 });

let tmpFileCounter = 0;
function writeTempJsonl(records) {
  const filePath = path.join(os.tmpdir(), `hud-cost-test-${process.pid}-${tmpFileCounter++}.jsonl`);
  fs.writeFileSync(filePath, records.map(r => JSON.stringify(r)).join('\n') + '\n');
  return filePath;
}

function assistantRecord(model, usage) {
  return { type: 'assistant', message: { model, usage } };
}

// ---------------------------------------------------------------------------

describe('shortModelName', () => {
  it('returns versioned family name for standard claude models (claude-opus-4-7 → Opus4.7)', () => {
    assert.equal(shortModelName('claude-opus-4-7'), 'Opus4.7');
    assert.equal(shortModelName('claude-sonnet-4-6'), 'Sonnet4.6');
    assert.equal(shortModelName('claude-haiku-4-5-20251001'), 'Haiku4.5');
  });

  it('returns family-only name when version segments are absent (claude-sonnet → Sonnet)', () => {
    assert.equal(shortModelName('claude-sonnet'), 'Sonnet');
    assert.equal(shortModelName('claude-opus'), 'Opus');
  });

  it('uppercases short acronyms (≤3 chars) for non-Anthropic models (gpt-4 → GPT)', () => {
    assert.equal(shortModelName('gpt-4'), 'GPT');
    assert.equal(shortModelName('glm-4'), 'GLM');
  });

  it('title-cases longer non-Anthropic prefixes (gemini-pro → Gemini)', () => {
    assert.equal(shortModelName('gemini-pro'), 'Gemini');
  });

  it('returns Unknown for empty, null, or undefined model ids', () => {
    assert.equal(shortModelName(null), 'Unknown');
    assert.equal(shortModelName(undefined), 'Unknown');
    assert.equal(shortModelName(''), 'Unknown');
  });
});

// ---------------------------------------------------------------------------

describe('priceFor', () => {
  it('returns opus price table for model ids containing opus', () => {
    assert.equal(priceFor('claude-opus-4-7'), PRICES.opus);
  });

  it('returns sonnet price table for model ids containing sonnet', () => {
    assert.equal(priceFor('claude-sonnet-4-6'), PRICES.sonnet);
  });

  it('returns haiku price table for model ids containing haiku', () => {
    assert.equal(priceFor('claude-haiku-4-5'), PRICES.haiku);
  });

  it('returns null for unrecognised model families', () => {
    assert.equal(priceFor('gpt-4'), null);
    assert.equal(priceFor(null), null);
    assert.equal(priceFor(''), null);
  });
});

// ---------------------------------------------------------------------------

describe('formatCost', () => {
  it('formats costs ≥$100 as whole dollars', () => {
    assert.equal(formatCost(100), '$100');
    assert.equal(formatCost(999), '$999');
  });

  it('formats costs $10–$99.99 with one decimal place', () => {
    assert.equal(formatCost(10), '$10.0');
    assert.equal(formatCost(50), '$50.0');
  });

  it('formats costs below $10 with two decimal places', () => {
    assert.equal(formatCost(5), '$5.00');
    assert.equal(formatCost(0), '$0.00');
    assert.equal(formatCost(0.15), '$0.15');
  });
});

// ---------------------------------------------------------------------------

describe('stripVersion', () => {
  it('removes trailing N.N suffix from versioned names', () => {
    assert.equal(stripVersion('Opus4.7'), 'Opus');
    assert.equal(stripVersion('Sonnet4.6'), 'Sonnet');
    assert.equal(stripVersion('Haiku4.5'), 'Haiku');
  });

  it('leaves names without a version suffix unchanged', () => {
    assert.equal(stripVersion('Gemini'), 'Gemini');
    assert.equal(stripVersion('GPT'), 'GPT');
  });
});

// ---------------------------------------------------------------------------

describe('aggregateByFamily', () => {
  it('sums costs for multiple versioned models of the same family', () => {
    assert.deepEqual(aggregateByFamily({ 'Opus4.7': 10, 'Opus4.6': 5 }), { Opus: 15 });
  });

  it('keeps distinct families separate', () => {
    assert.deepEqual(aggregateByFamily({ 'Opus4.7': 10, 'Sonnet4.6': 5 }), { Opus: 10, Sonnet: 5 });
  });
});

// ---------------------------------------------------------------------------

// Tests assume SHOW_COSTS=true and SHOW_CACHE=true (current defaults).
describe('formatLabel', () => {
  it('emits per-model breakdown with cache when label fits in 48 chars', () => {
    // 'Sonnet4.6 $0.15 | cache 25%' = 27 chars
    const label = formatLabel({
      byModel: { 'Sonnet4.6': 0.15 },
      unknownNames: [],
      input: 150, cacheCreate: 0, cacheRead: 50,
    });
    assert.equal(label, 'Sonnet4.6 $0.15 | cache 25%');
  });

  it('collapses to compact per-family names when per-model strings all exceed 48 chars', () => {
    // Per-model verbose (60) and compact (54) both exceed 48; per-family verbose (51) also; compact fits at 45.
    const label = formatLabel({
      byModel: { 'Opus4.7': 11.55, 'Sonnet4.6': 9.22, 'Haiku4.5': 0.03 },
      unknownNames: [],
      input: 1000, cacheCreate: 0, cacheRead: 0,
    });
    assert.equal(label, 'Opus $12 • Sonnet $9 • Haiku $0.03 | cache 0%');
  });

  it('appends ? to unknown model names', () => {
    const label = formatLabel({
      byModel: {},
      unknownNames: ['GPT'],
      input: 0, cacheCreate: 0, cacheRead: 0,
    });
    assert.equal(label, 'GPT? | cache 0%');
  });

  it('shows zero-cost label for a new or empty session', () => {
    const label = formatLabel({ byModel: {}, unknownNames: [], input: 0, cacheCreate: 0, cacheRead: 0 });
    assert.equal(label, '$0.00 | cache 0%');
  });

  it('computes cache hit rate as cacheRead / (input + cacheCreate + cacheRead)', () => {
    // hitPct = round(500 / 1000 * 100) = 50
    const label = formatLabel({
      byModel: {},
      unknownNames: [],
      input: 400, cacheCreate: 100, cacheRead: 500,
    });
    assert.equal(label, '$0.00 | cache 50%');
  });

  it('falls back to single total cost when even compact family breakdown exceeds 48 chars', () => {
    // All four attempts exceed 48 chars due to two unknown names widening every pass.
    // total = 999.99 + 888.88 + 777.77 = 2666.64 → formatCost → '$2667'
    const label = formatLabel({
      byModel: { 'Opus4.7': 999.99, 'Sonnet4.6': 888.88, 'Haiku4.5': 777.77 },
      unknownNames: ['Gemini', 'Llama'],
      input: 0, cacheCreate: 0, cacheRead: 0,
    });
    assert.equal(label, '$2667 | cache 0%');
  });
});

// ---------------------------------------------------------------------------

describe('parseOneFile', () => {
  it('accumulates input, cache creation, and cache read tokens from assistant records', async () => {
    const filePath = writeTempJsonl([
      assistantRecord('claude-sonnet-4-6', {
        input_tokens: 100,
        output_tokens: 50,
        cache_creation_input_tokens: 20,
        cache_read_input_tokens: 30,
      }),
    ]);
    try {
      const totals = makeTotals();
      await parseOneFile(filePath, totals);

      assert.equal(totals.input, 100);
      assert.equal(totals.cacheCreate, 20);
      assert.equal(totals.cacheRead, 30);
      // cost = (100*3 + 50*15 + 20*3.75 + 30*0.30) / 1_000_000 = 1134e-6
      assert.ok(Math.abs(totals.byModel['Sonnet4.6'] - 1134e-6) < 1e-12,
        `expected ~1134e-6 but got ${totals.byModel['Sonnet4.6']}`);
    } finally {
      fs.unlinkSync(filePath);
    }
  });

  it('skips non-assistant record types without affecting totals', async () => {
    const filePath = writeTempJsonl([
      { type: 'user', message: { content: 'hello' } },
      { type: 'system', content: 'some system message' },
    ]);
    try {
      const totals = makeTotals();
      await parseOneFile(filePath, totals);

      assert.equal(totals.input, 0);
      assert.equal(totals.cacheCreate, 0);
      assert.equal(totals.cacheRead, 0);
      assert.deepEqual(totals.byModel, {});
    } finally {
      fs.unlinkSync(filePath);
    }
  });

  it('skips malformed JSON lines without affecting totals', async () => {
    const filePath = path.join(os.tmpdir(), `hud-cost-test-${process.pid}-${tmpFileCounter++}.jsonl`);
    fs.writeFileSync(filePath, 'not-json\n{"broken":\n');
    try {
      const totals = makeTotals();
      await parseOneFile(filePath, totals);
      assert.equal(totals.input, 0);
    } finally {
      fs.unlinkSync(filePath);
    }
  });

  it('sums tokens across multiple records in the same file', async () => {
    const filePath = writeTempJsonl([
      assistantRecord('claude-sonnet-4-6', { input_tokens: 100, output_tokens: 0, cache_creation_input_tokens: 0, cache_read_input_tokens: 0 }),
      assistantRecord('claude-sonnet-4-6', { input_tokens: 200, output_tokens: 0, cache_creation_input_tokens: 0, cache_read_input_tokens: 0 }),
    ]);
    try {
      const totals = makeTotals();
      await parseOneFile(filePath, totals);
      assert.equal(totals.input, 300);
    } finally {
      fs.unlinkSync(filePath);
    }
  });

  it('a file with only non-assistant records leaves totals at zero (new session baseline)', async () => {
    const filePath = writeTempJsonl([
      { type: 'user', message: { content: 'hello' } },
    ]);
    try {
      const totals = makeTotals();
      await parseOneFile(filePath, totals);
      assert.equal(formatLabel(totals), '$0.00 | cache 0%');
    } finally {
      fs.unlinkSync(filePath);
    }
  });

  it('records unknown model families in unknownNames instead of byModel', async () => {
    const filePath = writeTempJsonl([
      assistantRecord('gpt-4', { input_tokens: 100, output_tokens: 50, cache_creation_input_tokens: 0, cache_read_input_tokens: 0 }),
    ]);
    try {
      const totals = makeTotals();
      await parseOneFile(filePath, totals);
      assert.deepEqual(totals.byModel, {});
      assert.deepEqual(totals.unknownNames, ['GPT']);
    } finally {
      fs.unlinkSync(filePath);
    }
  });

  it('handles cache_creation sub-bucket breakdown for 5m and 1h buckets', async () => {
    const filePath = writeTempJsonl([
      assistantRecord('claude-opus-4-7', {
        input_tokens: 0,
        output_tokens: 0,
        cache_creation_input_tokens: 30,
        cache_read_input_tokens: 0,
        cache_creation: {
          ephemeral_5m_input_tokens: 10,
          ephemeral_1h_input_tokens: 20,
        },
      }),
    ]);
    try {
      const totals = makeTotals();
      await parseOneFile(filePath, totals);
      // cost = (10 * 6.25 + 20 * 10.0) / 1_000_000 = 262.5e-6
      assert.ok(Math.abs(totals.byModel['Opus4.7'] - 262.5e-6) < 1e-12,
        `expected ~262.5e-6 but got ${totals.byModel['Opus4.7']}`);
    } finally {
      fs.unlinkSync(filePath);
    }
  });
});
