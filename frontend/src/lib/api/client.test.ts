import { describe, expect, it } from "vitest";
import { getCacheInvalidationTargets } from "@/lib/api/client";

describe("getCacheInvalidationTargets", () => {
  it("invalidates parent collections for nested bot mutations", () => {
    expect(getCacheInvalidationTargets("/api/ai/tools/bots/from-strategy")).toEqual([
      "/api/ai/tools/bots/from-strategy",
      "/api/ai/tools/bots",
      "/api/ai/tools",
      "/api/ai",
    ]);
  });

  it("ignores query strings while preserving document collection invalidation", () => {
    expect(getCacheInvalidationTargets("/api/documents/upload?token=abc123")).toEqual([
      "/api/documents/upload",
      "/api/documents",
    ]);
  });
});
