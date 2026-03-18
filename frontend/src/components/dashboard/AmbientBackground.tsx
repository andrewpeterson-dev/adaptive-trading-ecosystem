"use client";

import { useEffect, useRef } from "react";

interface Wave {
  frequency: number;
  amplitude: number;
  phase: number;
  phaseIncrement: number;
  color: string;
  yOffset: number;
}

interface Pulse {
  x: number;
  y: number;
  frame: number;
  maxFrames: number;
}

export function AmbientBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const prefersReduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)"
    ).matches;
    if (prefersReduced) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let rafId: number;
    let lastTime = 0;
    let frameCount = 0;

    const waves: Wave[] = [
      {
        frequency: 0.002,
        amplitude: 35,
        phase: 0,
        phaseIncrement: 0.003,
        color: "rgba(56, 189, 248, 0.04)",
        yOffset: 0.3,
      },
      {
        frequency: 0.0035,
        amplitude: 25,
        phase: Math.PI * 0.6,
        phaseIncrement: 0.0025,
        color: "rgba(99, 102, 241, 0.03)",
        yOffset: 0.5,
      },
      {
        frequency: 0.005,
        amplitude: 20,
        phase: Math.PI * 1.2,
        phaseIncrement: 0.0035,
        color: "rgba(16, 185, 129, 0.03)",
        yOffset: 0.7,
      },
      {
        frequency: 0.0028,
        amplitude: 40,
        phase: Math.PI * 1.8,
        phaseIncrement: 0.002,
        color: "rgba(56, 189, 248, 0.025)",
        yOffset: 0.85,
      },
    ];

    const pulses: Pulse[] = [];

    function spawnPulse() {
      if (!canvas) return;
      pulses.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        frame: 0,
        maxFrames: 80,
      });
    }

    function resize() {
      if (!canvas) return;
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }

    function drawWaves() {
      if (!canvas || !ctx) return;
      const { width, height } = canvas;

      for (const wave of waves) {
        ctx.beginPath();
        ctx.strokeStyle = wave.color;
        ctx.lineWidth = 1.5;
        ctx.lineCap = "round";

        const baseY = height * wave.yOffset;

        for (let x = 0; x <= width; x += 2) {
          const y = baseY + Math.sin(x * wave.frequency + wave.phase) * wave.amplitude;
          if (x === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        }

        ctx.stroke();
        wave.phase += wave.phaseIncrement;
      }
    }

    function drawPulses() {
      if (!canvas || !ctx) return;

      for (let i = pulses.length - 1; i >= 0; i--) {
        const pulse = pulses[i];
        const progress = pulse.frame / pulse.maxFrames;
        const radius = progress * 180;
        const opacity = (1 - progress) * 0.06;

        const gradient = ctx.createRadialGradient(
          pulse.x,
          pulse.y,
          0,
          pulse.x,
          pulse.y,
          radius
        );
        gradient.addColorStop(0, `rgba(56, 189, 248, ${opacity})`);
        gradient.addColorStop(0.5, `rgba(99, 102, 241, ${opacity * 0.5})`);
        gradient.addColorStop(1, "rgba(56, 189, 248, 0)");

        ctx.beginPath();
        ctx.arc(pulse.x, pulse.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();

        pulse.frame++;
        if (pulse.frame >= pulse.maxFrames) {
          pulses.splice(i, 1);
        }
      }
    }

    function tick(timestamp: number) {
      rafId = requestAnimationFrame(tick);

      const elapsed = timestamp - lastTime;
      if (elapsed < 33) return; // ~30fps cap

      lastTime = timestamp;
      frameCount++;

      if (!canvas || !ctx) return;

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      drawWaves();
      drawPulses();

      if (frameCount % 200 === 0) {
        spawnPulse();
      }
    }

    const observer = new ResizeObserver(resize);
    observer.observe(document.documentElement);
    resize();

    rafId = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(rafId);
      observer.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: -1,
        pointerEvents: "none",
      }}
      aria-hidden="true"
    />
  );
}
