// Lightweight canvas confetti — fired on real achievement unlocks.
export function confetti(x?: number, y?: number) {
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
  let c = document.getElementById("vi-confetti") as HTMLCanvasElement | null;
  if (!c) {
    c = document.createElement("canvas");
    c.id = "vi-confetti";
    c.style.cssText = "position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:9999";
    document.body.appendChild(c);
  }
  const ctx = c.getContext("2d")!;
  const W = (c.width = innerWidth);
  const H = (c.height = innerHeight);
  const ox = x ?? W / 2;
  const oy = y ?? H * 0.32;
  const cols = ["#f59e0b", "#fcd34d", "#a3e635", "#fb7185", "#7c83ff", "#38bda0"];
  const P = Array.from({ length: 90 }, () => {
    const a = Math.random() * Math.PI * 2;
    const sp = 4 + Math.random() * 7;
    return {
      x: ox, y: oy, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp - 4,
      s: 4 + Math.random() * 5, col: cols[(Math.random() * cols.length) | 0],
      rot: Math.random() * 6.28, vr: (Math.random() - 0.5) * 0.4, life: 1,
    };
  });
  let t0: number | null = null;
  function frame(ts: number) {
    if (t0 == null) t0 = ts;
    const dt = Math.min((ts - t0) / 16.7, 2);
    t0 = ts;
    ctx.clearRect(0, 0, W, H);
    let alive = false;
    for (const p of P) {
      if (p.life <= 0) continue;
      alive = true;
      p.vy += 0.22 * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.rot += p.vr * dt;
      p.life -= 0.012 * dt;
      ctx.save();
      ctx.globalAlpha = Math.max(p.life, 0);
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.fillStyle = p.col;
      ctx.fillRect(-p.s / 2, -p.s / 2, p.s, p.s * 0.6);
      ctx.restore();
    }
    if (alive) requestAnimationFrame(frame);
    else c!.remove();
  }
  requestAnimationFrame(frame);
}
