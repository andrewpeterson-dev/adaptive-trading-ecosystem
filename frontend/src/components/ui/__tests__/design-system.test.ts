import { describe, it, expect } from "vitest";

// Verify the design system component exports are correctly set up
// These are smoke tests ensuring the module structure is valid

describe("Design System Components", () => {
  it("exports MetricTile", async () => {
    const mod = await import("../metric-tile");
    expect(mod.MetricTile).toBeDefined();
    expect(typeof mod.MetricTile).toBe("function");
  });

  it("exports PillTabs", async () => {
    const mod = await import("../pill-tabs");
    expect(mod.PillTabs).toBeDefined();
    expect(typeof mod.PillTabs).toBe("function");
  });

  it("exports StatusChip", async () => {
    const mod = await import("../status-chip");
    expect(mod.StatusChip).toBeDefined();
    expect(typeof mod.StatusChip).toBe("function");
  });

  it("exports Panel from shared panel module", async () => {
    const mod = await import("../panel");
    expect(mod.Panel).toBeDefined();
    expect(mod.PanelContainer).toBeDefined();
    expect(mod.PanelHeader).toBeDefined();
    expect(mod.PanelBody).toBeDefined();
  });

  it("exports Skeleton variants", async () => {
    const mod = await import("../skeleton");
    expect(mod.Skeleton).toBeDefined();
    expect(mod.MetricSkeleton).toBeDefined();
    expect(mod.CardSkeleton).toBeDefined();
    expect(mod.ChartSkeleton).toBeDefined();
    expect(mod.TableRowSkeleton).toBeDefined();
    expect(mod.DashboardSkeleton).toBeDefined();
  });

  it("exports EmptyState", async () => {
    const mod = await import("../empty-state");
    expect(mod.EmptyState).toBeDefined();
    expect(typeof mod.EmptyState).toBe("function");
  });

  it("exports Badge with variants", async () => {
    const mod = await import("../badge");
    expect(mod.Badge).toBeDefined();
    expect(typeof mod.Badge).toBe("function");
  });

  it("exports Button with variants", async () => {
    const mod = await import("../button");
    expect(mod.Button).toBeDefined();
    expect(mod.buttonVariants).toBeDefined();
  });

  it("exports Surface components", async () => {
    const mod = await import("../surface");
    expect(mod.Surface).toBeDefined();
    expect(mod.SurfaceHeader).toBeDefined();
    expect(mod.SurfaceTitle).toBeDefined();
    expect(mod.SurfaceBody).toBeDefined();
  });
});
