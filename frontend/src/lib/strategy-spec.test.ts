import { describe, it, expect } from "vitest";
import { extractJson, parseStrategySpec, specToBuilderFields, type StrategySpec } from "./strategy-spec";

const VALID_SPEC: StrategySpec = {
  name: "RSI Oversold Bounce",
  description: "Buy when RSI drops below 30 on the daily timeframe",
  action: "BUY",
  stopLossPct: 2,
  takeProfitPct: 5,
  positionPct: 10,
  timeframe: "1D",
  entryConditions: [
    {
      logic: "AND",
      indicator: "rsi",
      params: { period: 14 },
      operator: "<",
      value: 30,
      signal: "RSI(14) drops below 30",
    },
  ],
  exitConditions: [
    {
      logic: "AND",
      indicator: "rsi",
      params: { period: 14 },
      operator: ">",
      value: 70,
      signal: "RSI(14) rises above 70",
    },
  ],
};

// ---------------------------------------------------------------------------
// extractJson
// ---------------------------------------------------------------------------

describe("extractJson", () => {
  it("extracts JSON from fenced code block", () => {
    const text = 'Some intro.\n```json\n{"name":"test"}\n```\nTrailing text.';
    expect(extractJson(text)).toBe('{"name":"test"}');
  });

  it("extracts JSON from unfenced code block", () => {
    const text = 'Intro.\n```\n{"a":1}\n```';
    expect(extractJson(text)).toBe('{"a":1}');
  });

  it("extracts raw JSON object from text", () => {
    const text = 'Here is the strategy: {"name":"test","action":"BUY"} and more text.';
    expect(extractJson(text)).toBe('{"name":"test","action":"BUY"}');
  });

  it("handles nested braces", () => {
    const text = '{"a":{"b":1},"c":[{"d":2}]}';
    expect(extractJson(text)).toBe('{"a":{"b":1},"c":[{"d":2}]}');
  });

  it("returns null when no JSON present", () => {
    expect(extractJson("No JSON here at all")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// parseStrategySpec — valid
// ---------------------------------------------------------------------------

describe("parseStrategySpec — valid JSON", () => {
  it("parses a valid spec from raw JSON text", () => {
    const text = `Summary sentence.\n${JSON.stringify(VALID_SPEC)}\nRisks: none.`;
    const result = parseStrategySpec(text);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.spec.name).toBe("RSI Oversold Bounce");
      expect(result.spec.action).toBe("BUY");
      expect(result.spec.stopLossPct).toBe(2);
      expect(result.spec.takeProfitPct).toBe(5);
      expect(result.spec.positionPct).toBe(10);
      expect(result.spec.timeframe).toBe("1D");
      expect(result.spec.entryConditions).toHaveLength(1);
      expect(result.spec.entryConditions[0].indicator).toBe("rsi");
    }
  });

  it("parses spec from fenced code block", () => {
    const text = `Summary.\n\`\`\`json\n${JSON.stringify(VALID_SPEC)}\n\`\`\`\nRisks.`;
    const result = parseStrategySpec(text);
    expect(result.ok).toBe(true);
  });

  it("accepts SELL action", () => {
    const spec = { ...VALID_SPEC, action: "SELL" };
    const result = parseStrategySpec(JSON.stringify(spec));
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.spec.action).toBe("SELL");
  });

  it("accepts all valid timeframes", () => {
    for (const tf of ["1m", "5m", "15m", "1H", "4H", "1D", "1W"]) {
      const spec = { ...VALID_SPEC, timeframe: tf };
      const result = parseStrategySpec(JSON.stringify(spec));
      expect(result.ok).toBe(true);
    }
  });
});

// ---------------------------------------------------------------------------
// parseStrategySpec — invalid
// ---------------------------------------------------------------------------

describe("parseStrategySpec — invalid JSON", () => {
  it("rejects text with no JSON", () => {
    const result = parseStrategySpec("No JSON here.");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain("No JSON");
  });

  it("rejects malformed JSON", () => {
    const result = parseStrategySpec("{name: bad}");
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBe("Invalid strategy JSON");
  });

  it("rejects missing name", () => {
    const spec = { ...VALID_SPEC, name: "" };
    const result = parseStrategySpec(JSON.stringify(spec));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain("name");
  });

  it("rejects invalid action", () => {
    const spec = { ...VALID_SPEC, action: "HOLD" };
    const result = parseStrategySpec(JSON.stringify(spec));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain("action");
  });

  it("rejects invalid timeframe", () => {
    const spec = { ...VALID_SPEC, timeframe: "2H" };
    const result = parseStrategySpec(JSON.stringify(spec));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain("timeframe");
  });

  it("rejects zero stopLossPct", () => {
    const spec = { ...VALID_SPEC, stopLossPct: 0 };
    const result = parseStrategySpec(JSON.stringify(spec));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain("stopLossPct");
  });

  it("rejects missing entryConditions", () => {
    const { entryConditions, ...rest } = VALID_SPEC;
    const result = parseStrategySpec(JSON.stringify(rest));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain("entryConditions");
  });

  it("rejects empty entryConditions array", () => {
    const spec = { ...VALID_SPEC, entryConditions: [] };
    const result = parseStrategySpec(JSON.stringify(spec));
    expect(result.ok).toBe(false);
  });

  it("rejects condition without indicator", () => {
    const spec = {
      ...VALID_SPEC,
      entryConditions: [{ logic: "AND", params: {}, operator: "<", value: 30 }],
    };
    const result = parseStrategySpec(JSON.stringify(spec));
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain("indicator");
  });
});

// ---------------------------------------------------------------------------
// specToBuilderFields
// ---------------------------------------------------------------------------

describe("specToBuilderFields", () => {
  it("maps spec fields to builder fields", () => {
    const result = parseStrategySpec(JSON.stringify(VALID_SPEC));
    expect(result.ok).toBe(true);
    if (!result.ok) return;

    const fields = specToBuilderFields(result.spec);
    expect(fields.name).toBe("RSI Oversold Bounce");
    expect(fields.description).toBe("Buy when RSI drops below 30 on the daily timeframe");
    expect(fields.action).toBe("BUY");
    expect(fields.stopLoss).toBe(2);
    expect(fields.takeProfit).toBe(5);
    expect(fields.positionSize).toBe(10);
    expect(fields.timeframe).toBe("1D");
    expect(fields.conditions).toHaveLength(1);
    expect(fields.conditions[0].indicator).toBe("rsi");
    expect(fields.conditions[0].operator).toBe("<");
    expect(fields.conditions[0].value).toBe(30);
    expect(fields.conditions[0].params).toEqual({ period: 14 });
    expect(fields.conditions[0].action).toBe("BUY");
  });

  it("defaults operator to < when missing", () => {
    const spec: StrategySpec = {
      ...VALID_SPEC,
      entryConditions: [
        { logic: "AND" as const, indicator: "rsi", params: { period: 14 }, signal: "RSI low" },
      ],
    };
    const fields = specToBuilderFields(spec);
    expect(fields.conditions[0].operator).toBe("<");
  });

  it("defaults value to 0 when missing", () => {
    const spec: StrategySpec = {
      ...VALID_SPEC,
      entryConditions: [
        { logic: "AND" as const, indicator: "sma", params: { period: 20 }, operator: "crosses_above" },
      ],
    };
    const fields = specToBuilderFields(spec);
    expect(fields.conditions[0].value).toBe(0);
    expect(fields.conditions[0].operator).toBe("crosses_above");
  });

  it("maps multiple conditions", () => {
    const spec: StrategySpec = {
      ...VALID_SPEC,
      entryConditions: [
        { logic: "AND" as const, indicator: "rsi", params: { period: 14 }, operator: "<", value: 30 },
        { logic: "AND" as const, indicator: "macd", params: { fast: 12, slow: 26 }, operator: "crosses_above", value: 0 },
      ],
    };
    const fields = specToBuilderFields(spec);
    expect(fields.conditions).toHaveLength(2);
    expect(fields.conditions[0].indicator).toBe("rsi");
    expect(fields.conditions[1].indicator).toBe("macd");
  });

  it("splits OR logic into multiple condition groups", () => {
    const spec: StrategySpec = {
      ...VALID_SPEC,
      entryConditions: [
        { logic: "AND" as const, indicator: "rsi", params: { period: 14 }, operator: "<", value: 30 },
        { logic: "OR" as const, indicator: "macd", params: { fast: 12, slow: 26, signal: 9 }, operator: ">", value: 0 },
      ],
    };
    const fields = specToBuilderFields(spec);
    expect(fields.conditionGroups).toHaveLength(2);
    expect(fields.conditionGroups[0].conditions).toHaveLength(1);
    expect(fields.conditionGroups[1].conditions[0].indicator).toBe("macd");
  });

  it("preserves AI metadata for the builder", () => {
    const spec: StrategySpec = {
      ...VALID_SPEC,
      strategyType: "ai_generated",
      sourcePrompt: "Build a momentum bot",
      overview: "AI-generated overview",
      featureSignals: ["rsi", "macd"],
    };
    const fields = specToBuilderFields(spec);
    expect(fields.strategyType).toBe("ai_generated");
    expect(fields.sourcePrompt).toBe("Build a momentum bot");
    expect(fields.aiContext?.overview).toBe("AI-generated overview");
    expect(fields.aiContext?.feature_signals).toEqual(["rsi", "macd"]);
  });
});
