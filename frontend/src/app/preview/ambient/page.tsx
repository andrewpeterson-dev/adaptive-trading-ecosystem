"use client";

import { useEffect, useRef, useState } from "react";

/* ═══════════════════════════════════════════════════════════════════════════
   AMBIENT BACKGROUND PREVIEW — Compare 4 variations
   Visit: localhost:3000/preview/ambient
   ═══════════════════════════════════════════════════════════════════════════ */

const C = {
  blue:  (a: number) => `rgba(59,130,246,${a})`,
  cyan:  (a: number) => `rgba(56,189,248,${a})`,
  teal:  (a: number) => `rgba(20,184,166,${a})`,
  slate: (a: number) => `rgba(30,41,59,${a})`,
  white: (a: number) => `rgba(255,255,255,${a})`,
  green: (a: number) => `rgba(34,197,94,${a})`,
};

// ─── Shared helpers ───────────────────────────────────────────────────────

function easeOutQuart(t: number) { return 1 - Math.pow(1 - t, 4); }

function makeWaves(count: number, opBase: number) {
  return Array.from({ length: count }, (_, i) => {
    const t = i / count;
    return {
      freqX: 0.0006 + t * 0.0016, freqX2: 0.0015 + t * 0.001, freqX3: 0.004 + t * 0.002,
      amp: 16 + i * 14, yR: 0.12 + t * 0.76,
      phase: i * Math.PI * 0.31 + i * 1.1, speed: 0.0006 + t * 0.0004,
      op: opBase * (1 - t * 0.25), lw: 1.2 - t * 0.15,
    };
  });
}

function makeNodes(count: number, W: number, H: number, speed: number) {
  return Array.from({ length: count }, () => ({
    x: Math.random() * W, y: Math.random() * H,
    vx: (Math.random() - 0.5) * speed, vy: (Math.random() - 0.5) * speed,
    r: 1 + Math.random() * 1.5, phase: Math.random() * Math.PI * 2,
    energy: 0.3 + Math.random() * 0.7,
  }));
}

// ─── Variation renderers ──────────────────────────────────────────────────

type Ctx = CanvasRenderingContext2D;

// OPTION A: Subtle Intelligence — restrained, institutional
function renderA(ctx: Ctx, W: number, H: number, frame: number, state: any) {
  if (!state.waves) {
    state.waves = makeWaves(4, 0.04);
    state.nodes = makeNodes(16, W, H, 0.08);
    state.glow = 0;
  }
  state.glow += 0.00008;

  // Soft glow
  const g = ctx.createRadialGradient(W*0.25, H*0.3, 0, W*0.25, H*0.3, Math.min(W,H)*0.45);
  g.addColorStop(0, C.blue(0.06)); g.addColorStop(0.4, C.blue(0.015)); g.addColorStop(1, C.blue(0));
  ctx.fillStyle = g; ctx.fillRect(0,0,W,H);

  // Waves
  for (const w of state.waves) {
    ctx.beginPath(); ctx.strokeStyle = C.blue(w.op); ctx.lineWidth = w.lw;
    for (let x = 0; x <= W; x += 6) {
      const y = H * w.yR + Math.sin(x * w.freqX + w.phase) * w.amp + Math.sin(x * w.freqX2 + w.phase * 1.7) * w.amp * 0.25;
      if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke(); w.phase += w.speed;
  }

  // Nodes + connections
  for (const n of state.nodes) {
    n.x += n.vx; n.y += n.vy; n.phase += 0.005;
    if (n.x < -60) n.x = W+60; if (n.x > W+60) n.x = -60;
    if (n.y < -60) n.y = H+60; if (n.y > H+60) n.y = -60;
  }
  ctx.lineWidth = 0.4;
  for (let i = 0; i < state.nodes.length; i++) {
    for (let j = i+1; j < state.nodes.length; j++) {
      const a = state.nodes[i], b = state.nodes[j];
      const dx = a.x-b.x, dy = a.y-b.y, d2 = dx*dx+dy*dy;
      if (d2 < 200*200) {
        const p = 1 - Math.sqrt(d2)/200;
        const br = 0.3 + 0.7 * Math.sin(frame*0.003+(i*7+j*13)*0.1);
        const alpha = p*p*0.06*br;
        if (alpha > 0.003) {
          ctx.beginPath(); ctx.strokeStyle = C.blue(alpha);
          ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        }
      }
    }
  }
  for (const n of state.nodes) {
    const br = 0.4 + 0.6 * Math.sin(n.phase);
    ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI*2);
    ctx.fillStyle = C.blue(0.15*br); ctx.fill();
  }
}

// OPTION B: Active Intelligence — more waves, particles, scan line
function renderB(ctx: Ctx, W: number, H: number, frame: number, state: any) {
  if (!state.waves) {
    state.waves = makeWaves(6, 0.055);
    state.nodes = makeNodes(28, W, H, 0.12);
    state.particles = [] as any[];
    state.nextBurst = 60;
    state.glow = 0;
  }
  state.glow += 0.00012;

  // Depth glow
  const x1 = W*(0.3+0.1*Math.sin(state.glow)), y1 = H*(0.2+0.08*Math.cos(state.glow*0.6));
  const g1 = ctx.createRadialGradient(x1,y1,0,x1,y1,Math.min(W,H)*0.5);
  g1.addColorStop(0,C.blue(0.09)); g1.addColorStop(0.3,C.blue(0.03)); g1.addColorStop(1,C.blue(0));
  ctx.fillStyle = g1; ctx.fillRect(0,0,W,H);

  // Grid
  ctx.strokeStyle = C.white(0.015); ctx.lineWidth = 0.5;
  for (let x = 80; x < W; x += 80) { ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,H); ctx.stroke(); }
  for (let y = 80; y < H; y += 80) { ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke(); }

  // Waves
  for (const w of state.waves) {
    ctx.beginPath(); ctx.strokeStyle = C.blue(w.op); ctx.lineWidth = w.lw;
    for (let x = 0; x <= W; x += 4) {
      const y = H*w.yR + Math.sin(x*w.freqX+w.phase)*w.amp + Math.sin(x*w.freqX2+w.phase*1.5)*w.amp*0.35 + Math.sin(x*w.freqX3+w.phase*0.7)*w.amp*0.15;
      if (x===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
    }
    ctx.stroke(); w.phase += w.speed;
  }

  // Nodes
  for (const n of state.nodes) {
    n.x += n.vx; n.y += n.vy; n.phase += 0.006+n.energy*0.004;
    if (n.x<-80) n.x=W+80; if (n.x>W+80) n.x=-80; if (n.y<-80) n.y=H+80; if (n.y>H+80) n.y=-80;
  }
  ctx.lineWidth = 0.6;
  for (let i=0;i<state.nodes.length;i++) for (let j=i+1;j<state.nodes.length;j++) {
    const a=state.nodes[i],b=state.nodes[j],dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy;
    if (d2<220*220) {
      const dist=Math.sqrt(d2),p=1-dist/220,pp=(i*7+j*13)*0.1;
      const br=0.3+0.7*Math.sin(frame*0.004+pp);
      const alpha=p*p*0.08*br*((a.energy+b.energy)/2);
      if (alpha>0.003) {
        ctx.beginPath(); ctx.strokeStyle=C.blue(alpha);
        ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
        if ((i+j+frame)%7===0) {
          const t=(Math.sin(frame*0.015+pp)+1)/2;
          ctx.beginPath(); ctx.arc(a.x+(b.x-a.x)*t,a.y+(b.y-a.y)*t,1,0,Math.PI*2);
          ctx.fillStyle=C.cyan(alpha*3); ctx.fill();
        }
      }
    }
  }
  for (const n of state.nodes) {
    const br=0.4+0.6*Math.sin(n.phase);
    if (n.energy>0.7) { ctx.beginPath(); ctx.arc(n.x,n.y,n.r*4,0,Math.PI*2); ctx.fillStyle=C.blue(0.18*br*n.energy*0.15); ctx.fill(); }
    ctx.beginPath(); ctx.arc(n.x,n.y,n.r,0,Math.PI*2); ctx.fillStyle=C.cyan(0.18*br*n.energy); ctx.fill();
  }

  // Particles
  if (frame>=state.nextBurst && state.nodes.length>=2) {
    const src=state.nodes[Math.floor(Math.random()*state.nodes.length)];
    const dst=state.nodes[Math.floor(Math.random()*state.nodes.length)];
    if (src!==dst) {
      const dx=dst.x-src.x,dy=dst.y-src.y,dist=Math.sqrt(dx*dx+dy*dy);
      if (dist>50&&dist<350) {
        for (let k=0;k<4+Math.floor(Math.random()*3);k++) {
          const sp=0.8+Math.random()*1.2;
          state.particles.push({x:src.x,y:src.y,vx:(dx/dist)*sp+(Math.random()-0.5)*0.3,vy:(dy/dist)*sp+(Math.random()-0.5)*0.3,life:0,ml:Math.floor(dist/sp)+Math.floor(Math.random()*20),sz:0.5+Math.random()});
        }
      }
    }
    state.nextBurst=frame+30+Math.floor(Math.random()*60);
  }
  for (let i=state.particles.length-1;i>=0;i--) {
    const p=state.particles[i]; p.x+=p.vx; p.y+=p.vy; p.life++;
    const t=p.life/p.ml; const a=t<0.15?(t/0.15)*0.5:0.5*(1-(t-0.15)/0.85);
    if (a>0.01) { ctx.beginPath(); ctx.arc(p.x,p.y,p.sz,0,Math.PI*2); ctx.fillStyle=C.cyan(a); ctx.fill(); }
    if (p.life>=p.ml) state.particles.splice(i,1);
  }

  // Scan line
  const scanY = (frame%600)/600*H;
  const sg = ctx.createLinearGradient(0,scanY-30,0,scanY+30);
  sg.addColorStop(0,C.blue(0)); sg.addColorStop(0.5,C.cyan(0.025)); sg.addColorStop(1,C.blue(0));
  ctx.fillStyle = sg; ctx.fillRect(0,scanY-30,W,60);
}

// OPTION C: Market Flow — heavy on curves, flowing data ribbons, candlestick echoes
function renderC(ctx: Ctx, W: number, H: number, frame: number, state: any) {
  if (!state.waves) {
    state.waves = makeWaves(8, 0.06);
    state.nodes = makeNodes(12, W, H, 0.06);
    state.glow = 0;
    state.candles = Array.from({length: Math.floor(W/20)}, (_,i) => ({
      x: i*20+10, h: 10+Math.random()*30, up: Math.random()>0.4, phase: Math.random()*Math.PI*2
    }));
  }
  state.glow += 0.0001;

  // Glow
  const g1 = ctx.createRadialGradient(W*0.5,H*0.4,0,W*0.5,H*0.4,Math.min(W,H)*0.55);
  g1.addColorStop(0,C.blue(0.07)); g1.addColorStop(0.5,C.blue(0.02)); g1.addColorStop(1,C.blue(0));
  ctx.fillStyle=g1; ctx.fillRect(0,0,W,H);

  // Faint candlestick ghosts
  const candleY = H * 0.5;
  for (const c of state.candles) {
    const breathe = 0.5 + 0.5 * Math.sin(frame * 0.002 + c.phase);
    const alpha = 0.025 * breathe;
    ctx.fillStyle = c.up ? C.green(alpha) : C.blue(alpha * 0.6);
    ctx.fillRect(c.x - 3, candleY - c.h/2, 6, c.h);
    ctx.fillRect(c.x - 0.5, candleY - c.h/2 - 5, 1, c.h + 10);
  }

  // Dense wave field
  for (const w of state.waves) {
    ctx.beginPath(); ctx.strokeStyle = C.blue(w.op); ctx.lineWidth = w.lw;
    for (let x = 0; x <= W; x += 3) {
      const y = H*w.yR + Math.sin(x*w.freqX+w.phase)*w.amp + Math.sin(x*w.freqX2+w.phase*1.3)*w.amp*0.4 + Math.sin(x*w.freqX3+w.phase*0.6)*w.amp*0.2;
      if (x===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
    }
    ctx.stroke(); w.phase += w.speed;
  }

  // Flowing data ribbon — thick smooth band
  ctx.beginPath();
  ctx.strokeStyle = C.cyan(0.03);
  ctx.lineWidth = 40;
  ctx.lineCap = "round";
  const ribbonY = H * 0.45;
  for (let x = 0; x <= W; x += 8) {
    const y = ribbonY + Math.sin(x*0.003+frame*0.001)*60 + Math.sin(x*0.008+frame*0.002)*25;
    if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Sparse nodes
  for (const n of state.nodes) {
    n.x += n.vx; n.y += n.vy; n.phase += 0.004;
    if (n.x<-40) n.x=W+40; if (n.x>W+40) n.x=-40; if (n.y<-40) n.y=H+40; if (n.y>H+40) n.y=-40;
    const br = 0.5 + 0.5 * Math.sin(n.phase);
    ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI*2);
    ctx.fillStyle = C.cyan(0.12*br); ctx.fill();
  }

  // Horizontal price level lines
  ctx.lineWidth = 0.4;
  for (let i = 0; i < 5; i++) {
    const y = H * (0.2 + i * 0.15);
    const alpha = 0.02 + 0.01 * Math.sin(frame * 0.001 + i);
    ctx.beginPath(); ctx.strokeStyle = C.blue(alpha);
    ctx.setLineDash([4, 8]); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    ctx.setLineDash([]);
  }
}

// OPTION D: Neural Command — dense network, heavy data flow, execution bursts
function renderD(ctx: Ctx, W: number, H: number, frame: number, state: any) {
  if (!state.init) {
    state.init = true;
    state.nodes = makeNodes(40, W, H, 0.15);
    state.waves = makeWaves(3, 0.03);
    state.particles = [] as any[];
    state.pulses = [] as any[];
    state.nextBurst = 20;
    state.nextPulse = 100;
    state.glow = 0;
  }
  state.glow += 0.00015;

  // Intense glow
  const g1 = ctx.createRadialGradient(W*0.4,H*0.35,0,W*0.4,H*0.35,Math.min(W,H)*0.5);
  g1.addColorStop(0,C.blue(0.1)); g1.addColorStop(0.3,C.cyan(0.03)); g1.addColorStop(1,C.blue(0));
  ctx.fillStyle=g1; ctx.fillRect(0,0,W,H);
  const g2 = ctx.createRadialGradient(W*0.7,H*0.65,0,W*0.7,H*0.65,Math.min(W,H)*0.35);
  g2.addColorStop(0,C.teal(0.06)); g2.addColorStop(0.5,C.blue(0.015)); g2.addColorStop(1,C.blue(0));
  ctx.fillStyle=g2; ctx.fillRect(0,0,W,H);

  // Light grid
  ctx.strokeStyle = C.white(0.012); ctx.lineWidth = 0.5;
  for (let x=60;x<W;x+=60) { ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x,H); ctx.stroke(); }
  for (let y=60;y<H;y+=60) { ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(W,y); ctx.stroke(); }

  // Background waves
  for (const w of state.waves) {
    ctx.beginPath(); ctx.strokeStyle = C.blue(w.op); ctx.lineWidth = w.lw;
    for (let x=0;x<=W;x+=6) { const y=H*w.yR+Math.sin(x*w.freqX+w.phase)*w.amp; if(x===0) ctx.moveTo(x,y); else ctx.lineTo(x,y); }
    ctx.stroke(); w.phase += w.speed;
  }

  // Dense network
  for (const n of state.nodes) {
    n.x += n.vx; n.y += n.vy; n.phase += 0.007+n.energy*0.005;
    if (n.x<-80) n.x=W+80; if (n.x>W+80) n.x=-80; if (n.y<-80) n.y=H+80; if (n.y>H+80) n.y=-80;
  }
  ctx.lineWidth = 0.5;
  for (let i=0;i<state.nodes.length;i++) for (let j=i+1;j<state.nodes.length;j++) {
    const a=state.nodes[i],b=state.nodes[j],dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy;
    if (d2<180*180) {
      const dist=Math.sqrt(d2),p=1-dist/180;
      const br=0.3+0.7*Math.sin(frame*0.005+(i*7+j*13)*0.1);
      const alpha=p*p*0.1*br*((a.energy+b.energy)/2);
      if (alpha>0.003) {
        ctx.beginPath(); ctx.strokeStyle=C.blue(alpha); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
        // Flow dots on every connection
        if ((i+j+frame)%5===0) {
          const t=(Math.sin(frame*0.02+(i+j)*0.3)+1)/2;
          ctx.beginPath(); ctx.arc(a.x+(b.x-a.x)*t,a.y+(b.y-a.y)*t,1.2,0,Math.PI*2);
          ctx.fillStyle=C.cyan(alpha*4); ctx.fill();
        }
      }
    }
  }
  for (const n of state.nodes) {
    const br=0.4+0.6*Math.sin(n.phase);
    if (n.energy>0.6) { ctx.beginPath(); ctx.arc(n.x,n.y,n.r*5,0,Math.PI*2); ctx.fillStyle=C.cyan(0.02*br*n.energy); ctx.fill(); }
    ctx.beginPath(); ctx.arc(n.x,n.y,n.r,0,Math.PI*2); ctx.fillStyle=C.cyan(0.22*br*n.energy); ctx.fill();
  }

  // Heavy particles
  if (frame>=state.nextBurst && state.nodes.length>=2) {
    const src=state.nodes[Math.floor(Math.random()*state.nodes.length)];
    const dst=state.nodes[Math.floor(Math.random()*state.nodes.length)];
    if (src!==dst) {
      const dx=dst.x-src.x,dy=dst.y-src.y,dist=Math.sqrt(dx*dx+dy*dy);
      if (dist>30&&dist<300) {
        for (let k=0;k<5+Math.floor(Math.random()*5);k++) {
          const sp=1+Math.random()*1.5;
          state.particles.push({x:src.x,y:src.y,vx:(dx/dist)*sp+(Math.random()-0.5)*0.4,vy:(dy/dist)*sp+(Math.random()-0.5)*0.4,life:0,ml:Math.floor(dist/sp)+Math.floor(Math.random()*15),sz:0.6+Math.random()*1.2});
        }
      }
    }
    state.nextBurst=frame+15+Math.floor(Math.random()*30);
  }
  for (let i=state.particles.length-1;i>=0;i--) {
    const p=state.particles[i]; p.x+=p.vx; p.y+=p.vy; p.life++;
    const t=p.life/p.ml; const a=t<0.1?(t/0.1)*0.6:0.6*(1-(t-0.1)/0.9);
    if (a>0.01) { ctx.beginPath(); ctx.arc(p.x,p.y,p.sz,0,Math.PI*2); ctx.fillStyle=C.cyan(a); ctx.fill(); }
    if (p.life>=p.ml) state.particles.splice(i,1);
  }

  // Pulses
  if (frame>=state.nextPulse && state.pulses.length<4) {
    const n=state.nodes[Math.floor(Math.random()*state.nodes.length)];
    const colors = ["cyan","teal","blue"] as const;
    state.pulses.push({x:n.x,y:n.y,f:0,lt:120+Math.floor(Math.random()*60),c:colors[Math.floor(Math.random()*3)]});
    n.energy=Math.min(1,n.energy+0.4);
    state.nextPulse=frame+100+Math.floor(Math.random()*150);
  }
  for (let i=state.pulses.length-1;i>=0;i--) {
    const p=state.pulses[i]; const t=p.f/p.lt; const r=easeOutQuart(t)*180;
    let op: number; if (t<0.06) op=(t/0.06)*0.09; else op=0.09*Math.pow(1-(t-0.06)/0.94,2.5);
    if (op>0.001) {
      const fn=p.c==="cyan"?C.cyan:p.c==="teal"?C.teal:C.blue;
      const gr=ctx.createRadialGradient(p.x,p.y,0,p.x,p.y,r);
      gr.addColorStop(0,fn(op)); gr.addColorStop(0.3,fn(op*0.4)); gr.addColorStop(1,fn(0));
      ctx.beginPath(); ctx.arc(p.x,p.y,r,0,Math.PI*2); ctx.fillStyle=gr; ctx.fill();
      if (t<0.15) { ctx.beginPath(); ctx.arc(p.x,p.y,2.5,0,Math.PI*2); ctx.fillStyle=C.white((1-t/0.15)*0.5); ctx.fill(); }
    }
    p.f++; if (p.f>=p.lt) state.pulses.splice(i,1);
  }

  // Double scan line
  const scanY1 = (frame%400)/400*H;
  const sg1 = ctx.createLinearGradient(0,scanY1-20,0,scanY1+20);
  sg1.addColorStop(0,C.blue(0)); sg1.addColorStop(0.5,C.cyan(0.03)); sg1.addColorStop(1,C.blue(0));
  ctx.fillStyle=sg1; ctx.fillRect(0,scanY1-20,W,40);
  const scanY2 = ((frame+200)%500)/500*H;
  const sg2 = ctx.createLinearGradient(0,scanY2-15,0,scanY2+15);
  sg2.addColorStop(0,C.blue(0)); sg2.addColorStop(0.5,C.teal(0.02)); sg2.addColorStop(1,C.blue(0));
  ctx.fillStyle=sg2; ctx.fillRect(0,scanY2-15,W,30);
}

// ─── Preview Panel ────────────────────────────────────────────────────────

function PreviewPanel({ label, description, renderFn, active, onClick }: {
  label: string; description: string;
  renderFn: (ctx: Ctx, W: number, H: number, frame: number, state: any) => void;
  active: boolean; onClick: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef<any>({});
  const rafRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let W = 0, H = 0, frame = 0, lastTime = 0;

    function resize() {
      const rect = canvas!.parentElement!.getBoundingClientRect();
      W = rect.width; H = rect.height;
      canvas!.width = W * dpr; canvas!.height = H * dpr;
      canvas!.style.width = W + "px"; canvas!.style.height = H + "px";
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      stateRef.current = {}; // Reset state on resize
    }

    function tick(timestamp: number) {
      rafRef.current = requestAnimationFrame(tick);
      if (timestamp - lastTime < 1000 / 24) return;
      lastTime = timestamp; frame++;
      ctx!.clearRect(0, 0, W, H);
      renderFn(ctx!, W, H, frame, stateRef.current);
    }

    resize();
    window.addEventListener("resize", resize);
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", resize);
    };
  }, [renderFn]);

  return (
    <button
      type="button"
      onClick={onClick}
      className="relative overflow-hidden rounded-2xl border-2 transition-all duration-300 text-left"
      style={{
        borderColor: active ? "rgba(56,189,248,0.6)" : "rgba(255,255,255,0.08)",
        background: "hsl(228 29% 8%)",
        boxShadow: active ? "0 0 30px rgba(56,189,248,0.15)" : "none",
      }}
    >
      <div className="relative" style={{ height: "340px" }}>
        <canvas ref={canvasRef} className="absolute inset-0" />
        {/* Mock UI overlay to show how it looks behind content */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] backdrop-blur-sm px-8 py-6 text-center" style={{ minWidth: 200 }}>
            <div className="text-xs text-white/30 mb-1">Portfolio Equity</div>
            <div className="text-2xl font-semibold text-white/70 font-mono">$124,850</div>
            <div className="text-xs text-emerald-400/60 mt-1">+2.4% today</div>
          </div>
        </div>
      </div>
      <div className="px-5 py-4 border-t" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-semibold text-white/90">{label}</span>
          {active && <span className="text-[9px] font-semibold uppercase tracking-widest text-cyan-400 bg-cyan-400/10 px-2 py-0.5 rounded-full">Selected</span>}
        </div>
        <p className="text-xs text-white/40 leading-relaxed">{description}</p>
      </div>
    </button>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────

export default function AmbientPreview() {
  const [selected, setSelected] = useState("B");

  return (
    <div className="min-h-screen p-8" style={{ background: "hsl(228 29% 6%)" }}>
      <div className="max-w-[1400px] mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-white/90 tracking-tight">Ambient Background — Compare</h1>
          <p className="text-sm text-white/40 mt-1">Click to select. Each runs at 24fps with identical architecture.</p>
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <PreviewPanel
            label="A — Subtle Intelligence"
            description="Restrained and institutional. Soft glow, sparse nodes, quiet wave traces. Felt more than seen."
            renderFn={renderA}
            active={selected === "A"}
            onClick={() => setSelected("A")}
          />
          <PreviewPanel
            label="B — Active Intelligence"
            description="Rich but controlled. Grid, 6 waves, 28-node network, flowing data particles, scan line, execution pulses."
            renderFn={renderB}
            active={selected === "B"}
            onClick={() => setSelected("B")}
          />
          <PreviewPanel
            label="C — Market Flow"
            description="Chart-inspired. Dense wave field, data ribbon, ghost candlesticks, dashed price levels. Feels like live market data."
            renderFn={renderC}
            active={selected === "C"}
            onClick={() => setSelected("C")}
          />
          <PreviewPanel
            label="D — Neural Command"
            description="Maximum intensity. 40-node dense network, heavy particle flow, frequent execution bursts, dual scan lines."
            renderFn={renderD}
            active={selected === "D"}
            onClick={() => setSelected("D")}
          />
        </div>

        <div className="mt-6 text-center text-xs text-white/30">
          Selected: <span className="text-cyan-400 font-semibold">{selected}</span> — tell Claude which one you want
        </div>
      </div>
    </div>
  );
}
