"use client";

import { useEffect, useRef } from "react";

/* ═══════════════════════════════════════════════════════════════════════════
   AMBIENT MARKET INTELLIGENCE LAYER — v2

   A visually rich but non-competing background that communicates:
   "there is a serious AI trading system running behind this product."

   Layers:
   1. Depth glow — volumetric atmosphere
   2. Grid underlay — faint chart-like coordinate system
   3. Market waves — flowing price-curve-inspired signal traces
   4. Neural network — nodes with pulsing data-flow connections
   5. Data streams — particles flowing along paths
   6. Trade pulses — execution-event flashes from nodes
   7. Scan line — horizontal processing sweep
   ═══════════════════════════════════════════════════════════════════════════ */

const C = {
  blue:  (a: number) => `rgba(59,130,246,${a})`,
  cyan:  (a: number) => `rgba(56,189,248,${a})`,
  teal:  (a: number) => `rgba(20,184,166,${a})`,
  slate: (a: number) => `rgba(30,41,59,${a})`,
  white: (a: number) => `rgba(255,255,255,${a})`,
};

export function AmbientIntelligenceLayer() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef(0);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let W = 0, H = 0;
    let frame = 0, lastTime = 0, visible = true, glowAngle = 0;
    const FRAME_BUDGET = 1000 / 24;

    // ── Waves — 6 market-curve traces ──────────────────────────────
    const waves = Array.from({ length: 6 }, (_, i) => {
      const t = i / 6;
      return {
        freqX: 0.0006 + t * 0.0016,
        freqX2: 0.0015 + t * 0.001,
        freqX3: 0.004 + t * 0.002,
        amplitude: 16 + i * 14,
        yRatio: 0.12 + t * 0.76,
        phase: i * Math.PI * 0.31 + i * 1.1,
        speed: 0.0006 + t * 0.0004,
        opacity: 0.1 * (1 - t * 0.25),
        lineWidth: 1.2 - t * 0.15,
      };
    });

    // ── Nodes — neural network ─────────────────────────────────────
    type N = { x: number; y: number; vx: number; vy: number; r: number; phase: number; energy: number };
    let nodes: N[] = [];

    function initNodes() {
      nodes = Array.from({ length: 28 }, () => ({
        x: Math.random() * W,
        y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.12,
        vy: (Math.random() - 0.5) * 0.12,
        r: 1 + Math.random() * 1.5,
        phase: Math.random() * Math.PI * 2,
        energy: 0.3 + Math.random() * 0.7,
      }));
    }

    // ── Data stream particles ──────────────────────────────────────
    type Particle = { x: number; y: number; vx: number; vy: number; life: number; maxLife: number; size: number };
    const particles: Particle[] = [];
    let nextParticleBurst = 60;

    function spawnParticles() {
      if (nodes.length < 2) return;
      const src = nodes[Math.floor(Math.random() * nodes.length)];
      const dst = nodes[Math.floor(Math.random() * nodes.length)];
      if (src === dst) return;
      const dx = dst.x - src.x, dy = dst.y - src.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist > 350 || dist < 50) return;
      const count = 3 + Math.floor(Math.random() * 4);
      for (let i = 0; i < count; i++) {
        const speed = 0.8 + Math.random() * 1.2;
        particles.push({
          x: src.x + (Math.random() - 0.5) * 4,
          y: src.y + (Math.random() - 0.5) * 4,
          vx: (dx / dist) * speed + (Math.random() - 0.5) * 0.3,
          vy: (dy / dist) * speed + (Math.random() - 0.5) * 0.3,
          life: 0,
          maxLife: Math.floor(dist / speed) + Math.floor(Math.random() * 20),
          size: 0.5 + Math.random() * 1,
        });
      }
    }

    // ── Trade pulses — execution events ────────────────────────────
    type Pulse = { x: number; y: number; frame: number; lifetime: number; color: "cyan" | "teal" | "blue" };
    const pulses: Pulse[] = [];
    let nextPulseAt = 80 + Math.floor(Math.random() * 120);

    // ── Resize ─────────────────────────────────────────────────────

    function resize() {
      W = window.innerWidth;
      H = window.innerHeight;
      canvas!.width = W * dpr;
      canvas!.height = H * dpr;
      canvas!.style.width = W + "px";
      canvas!.style.height = H + "px";
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    // ── Layer: Depth Glow ──────────────────────────────────────────

    function drawDepth() {
      glowAngle += 0.00012;

      // Primary glow — upper area
      const x1 = W * (0.3 + 0.1 * Math.sin(glowAngle));
      const y1 = H * (0.2 + 0.08 * Math.cos(glowAngle * 0.6));
      const r1 = Math.min(W, H) * 0.5;
      const g1 = ctx!.createRadialGradient(x1, y1, 0, x1, y1, r1);
      g1.addColorStop(0, C.blue(0.15));
      g1.addColorStop(0.3, C.blue(0.05));
      g1.addColorStop(1, C.blue(0));
      ctx!.fillStyle = g1;
      ctx!.fillRect(0, 0, W, H);

      // Secondary glow — lower right
      const x2 = W * (0.75 + 0.06 * Math.sin(glowAngle * 0.4 + 2));
      const y2 = H * (0.7 + 0.06 * Math.cos(glowAngle * 0.5 + 1));
      const r2 = Math.min(W, H) * 0.4;
      const g2 = ctx!.createRadialGradient(x2, y2, 0, x2, y2, r2);
      g2.addColorStop(0, C.cyan(0.045));
      g2.addColorStop(0.4, C.teal(0.012));
      g2.addColorStop(1, C.slate(0));
      ctx!.fillStyle = g2;
      ctx!.fillRect(0, 0, W, H);
    }

    // ── Layer: Grid ────────────────────────────────────────────────

    function drawGrid() {
      const gridSize = 80;
      ctx!.strokeStyle = C.white(0.04);
      ctx!.lineWidth = 0.5;

      // Vertical lines
      for (let x = gridSize; x < W; x += gridSize) {
        ctx!.beginPath();
        ctx!.moveTo(x, 0);
        ctx!.lineTo(x, H);
        ctx!.stroke();
      }
      // Horizontal lines
      for (let y = gridSize; y < H; y += gridSize) {
        ctx!.beginPath();
        ctx!.moveTo(0, y);
        ctx!.lineTo(W, y);
        ctx!.stroke();
      }
    }

    // ── Layer: Waves ───────────────────────────────────────────────

    function drawWaves() {
      for (const w of waves) {
        ctx!.beginPath();
        ctx!.strokeStyle = C.blue(w.opacity);
        ctx!.lineWidth = w.lineWidth;
        const baseY = H * w.yRatio;
        for (let x = 0; x <= W; x += 4) {
          const y = baseY
            + Math.sin(x * w.freqX + w.phase) * w.amplitude
            + Math.sin(x * w.freqX2 + w.phase * 1.5) * w.amplitude * 0.35
            + Math.sin(x * w.freqX3 + w.phase * 0.7) * w.amplitude * 0.15;
          if (x === 0) ctx!.moveTo(x, y); else ctx!.lineTo(x, y);
        }
        ctx!.stroke();
        w.phase += w.speed;
      }
    }

    // ── Layer: Neural Network ──────────────────────────────────────

    function drawNetwork() {
      // Move nodes
      for (const n of nodes) {
        n.x += n.vx;
        n.y += n.vy;
        n.phase += 0.006 + n.energy * 0.004;
        const m = 80;
        if (n.x < -m) n.x = W + m;
        if (n.x > W + m) n.x = -m;
        if (n.y < -m) n.y = H + m;
        if (n.y > H + m) n.y = -m;
      }

      // Connections with data-flow pulsing
      ctx!.lineWidth = 0.6;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j];
          const dx = a.x - b.x, dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;
          if (d2 < 220 * 220) {
            const dist = Math.sqrt(d2);
            const proximity = 1 - dist / 220;
            const pairPhase = (i * 7 + j * 13) * 0.1;
            const breathe = 0.3 + 0.7 * Math.sin(frame * 0.004 + pairPhase);
            const alpha = proximity * proximity * 0.15 * breathe * ((a.energy + b.energy) / 2);

            if (alpha > 0.003) {
              ctx!.beginPath();
              ctx!.strokeStyle = C.blue(alpha);
              ctx!.moveTo(a.x, a.y);
              ctx!.lineTo(b.x, b.y);
              ctx!.stroke();

              // Data flow dot along connection (every ~3rd connection)
              if ((i + j + frame) % 7 === 0) {
                const t = (Math.sin(frame * 0.015 + pairPhase) + 1) / 2;
                const px = a.x + (b.x - a.x) * t;
                const py = a.y + (b.y - a.y) * t;
                ctx!.beginPath();
                ctx!.arc(px, py, 1, 0, Math.PI * 2);
                ctx!.fillStyle = C.cyan(alpha * 3);
                ctx!.fill();
              }
            }
          }
        }
      }

      // Node dots with energy glow
      for (const n of nodes) {
        const breathe = 0.4 + 0.6 * Math.sin(n.phase);
        const baseAlpha = 0.18 * breathe * n.energy;

        // Outer glow for high-energy nodes
        if (n.energy > 0.7) {
          ctx!.beginPath();
          ctx!.arc(n.x, n.y, n.r * 4, 0, Math.PI * 2);
          ctx!.fillStyle = C.blue(baseAlpha * 0.15);
          ctx!.fill();
        }

        // Core dot
        ctx!.beginPath();
        ctx!.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx!.fillStyle = C.cyan(baseAlpha);
        ctx!.fill();
      }
    }

    // ── Layer: Data Stream Particles ───────────────────────────────

    function drawParticles() {
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.life++;

        const t = p.life / p.maxLife;
        let alpha: number;
        if (t < 0.15) alpha = (t / 0.15) * 0.5;
        else alpha = 0.5 * (1 - (t - 0.15) / 0.85);

        if (alpha > 0.01) {
          ctx!.beginPath();
          ctx!.arc(p.x, p.y, p.size, 0, Math.PI * 2);
          ctx!.fillStyle = C.cyan(alpha);
          ctx!.fill();
        }

        if (p.life >= p.maxLife) particles.splice(i, 1);
      }

      // Spawn bursts periodically
      if (frame >= nextParticleBurst) {
        spawnParticles();
        nextParticleBurst = frame + 30 + Math.floor(Math.random() * 60); // every 1.5-3.5s
      }
    }

    // ── Layer: Trade Pulses ────────────────────────────────────────

    function drawPulses() {
      for (let i = pulses.length - 1; i >= 0; i--) {
        const p = pulses[i];
        const t = p.frame / p.lifetime;
        const radius = (1 - Math.pow(1 - t, 4)) * 200;

        let opacity: number;
        if (t < 0.06) opacity = (t / 0.06) * 0.07;
        else opacity = 0.07 * Math.pow(1 - (t - 0.06) / 0.94, 2.5);

        if (opacity > 0.001) {
          const colorFn = p.color === "cyan" ? C.cyan : p.color === "teal" ? C.teal : C.blue;
          const grad = ctx!.createRadialGradient(p.x, p.y, 0, p.x, p.y, radius);
          grad.addColorStop(0, colorFn(opacity));
          grad.addColorStop(0.25, colorFn(opacity * 0.5));
          grad.addColorStop(1, colorFn(0));
          ctx!.beginPath();
          ctx!.arc(p.x, p.y, radius, 0, Math.PI * 2);
          ctx!.fillStyle = grad;
          ctx!.fill();

          // Bright center point
          if (t < 0.2) {
            ctx!.beginPath();
            ctx!.arc(p.x, p.y, 2, 0, Math.PI * 2);
            ctx!.fillStyle = C.white((1 - t / 0.2) * 0.3);
            ctx!.fill();
          }
        }

        p.frame++;
        if (p.frame >= p.lifetime) pulses.splice(i, 1);
      }

      // Schedule pulses
      if (frame >= nextPulseAt && pulses.length < 3 && nodes.length > 0) {
        const n = nodes[Math.floor(Math.random() * nodes.length)];
        const colors: Array<"cyan" | "teal" | "blue"> = ["cyan", "teal", "blue"];
        pulses.push({
          x: n.x, y: n.y, frame: 0,
          lifetime: 160 + Math.floor(Math.random() * 80),
          color: colors[Math.floor(Math.random() * colors.length)],
        });
        // Boost node energy when it fires
        n.energy = Math.min(1, n.energy + 0.3);
        nextPulseAt = frame + 180 + Math.floor(Math.random() * 240); // 9-17s at 24fps
      }
    }

    // ── Layer: Scan Line ───────────────────────────────────────────

    function drawScanLine() {
      const period = 600; // frames per full sweep
      const scanY = (frame % period) / period * H;
      const grad = ctx!.createLinearGradient(0, scanY - 30, 0, scanY + 30);
      grad.addColorStop(0, C.blue(0));
      grad.addColorStop(0.5, C.cyan(0.025));
      grad.addColorStop(1, C.blue(0));
      ctx!.fillStyle = grad;
      ctx!.fillRect(0, scanY - 30, W, 60);
    }

    // ── Main Loop ──────────────────────────────────────────────────

    function tick(timestamp: number) {
      rafRef.current = requestAnimationFrame(tick);
      if (!visible) return;
      const elapsed = timestamp - lastTime;
      if (elapsed < FRAME_BUDGET) return;
      lastTime = timestamp;
      frame++;

      ctx!.clearRect(0, 0, W, H);

      drawDepth();
      drawGrid();
      drawWaves();
      drawNetwork();
      drawParticles();
      drawPulses();
      drawScanLine();
    }

    // ── Init ───────────────────────────────────────────────────────

    resize();
    initNodes();

    function onResize() {
      const oldW = W, oldH = H;
      resize();
      if (oldW > 0 && oldH > 0) {
        for (const n of nodes) { n.x *= W / oldW; n.y *= H / oldH; }
      }
    }

    function onVis() { visible = !document.hidden; }

    window.addEventListener("resize", onResize);
    document.addEventListener("visibilitychange", onVis);
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0"
      style={{ zIndex: 0 }}
    />
  );
}
