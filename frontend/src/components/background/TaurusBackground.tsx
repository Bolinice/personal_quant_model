import { useEffect, useRef, useCallback } from 'react';

/**
 * 纳斯达克金牛星空背景
 * - 用密集星点描摹纳斯达克铜牛轮廓（低头蓄力姿态）
 * - 金牛座星座叠加在牛身内
 * - 流星、星尘、星云氛围
 * - half模式：适配左半面分栏布局
 */

// 纳斯达克铜牛轮廓 — 低头蓄力、牛角前冲的经典姿态
// 用更多控制点实现平滑曲线，归一化坐标相对于画布中心
const BULL_OUTLINE: [number, number][] = [
  // === 左牛角（从头顶向左上弯曲） ===
  [-0.12, -0.36], [-0.14, -0.40], [-0.16, -0.44], [-0.18, -0.47],
  [-0.20, -0.48], [-0.22, -0.47], [-0.23, -0.44], [-0.22, -0.40],
  [-0.20, -0.37], [-0.17, -0.35], [-0.14, -0.34],
  // === 右牛角 ===
  [-0.06, -0.35], [-0.04, -0.38], [-0.02, -0.42], [0.00, -0.46],
  [0.02, -0.48], [0.04, -0.47], [0.05, -0.44], [0.04, -0.40],
  [0.02, -0.37], [0.00, -0.35], [-0.02, -0.34],
  // === 头顶 ===
  [-0.04, -0.34], [-0.06, -0.33], [-0.08, -0.33],
  // === 额头 → 鼻梁（向下倾斜，低头姿态） ===
  [-0.10, -0.32], [-0.12, -0.30], [-0.14, -0.28],
  [-0.16, -0.25], [-0.18, -0.22], [-0.19, -0.19],
  // === 鼻子 ===
  [-0.20, -0.16], [-0.20, -0.13], [-0.19, -0.10],
  // === 嘴部 ===
  [-0.18, -0.08], [-0.16, -0.07], [-0.14, -0.08],
  // === 下颌 → 喉部 ===
  [-0.12, -0.10], [-0.10, -0.12], [-0.08, -0.14],
  [-0.06, -0.15], [-0.04, -0.15],
  // === 颈部下方 → 胸部 ===
  [-0.02, -0.14], [0.00, -0.12], [0.02, -0.10],
  [0.04, -0.07], [0.05, -0.04],
  // === 肩部隆起（牛的标志性肌肉） ===
  [0.06, -0.01], [0.06, 0.02], [0.05, 0.05],
  // === 背部 ===
  [0.04, 0.07], [0.02, 0.09], [0.00, 0.10],
  [-0.02, 0.11], [-0.04, 0.11],
  // === 臀部 ===
  [-0.06, 0.10], [-0.08, 0.09], [-0.10, 0.07],
  [-0.11, 0.05], [-0.12, 0.03],
  // === 尾巴（从臀部向上扬起） ===
  [-0.13, 0.01], [-0.15, -0.02], [-0.17, -0.05],
  [-0.18, -0.08], [-0.17, -0.10], [-0.15, -0.08],
  // === 后腿（从臀部向下） ===
  [-0.12, 0.05], [-0.12, 0.08], [-0.13, 0.12],
  [-0.14, 0.16], [-0.14, 0.20], [-0.13, 0.23],
  // === 后蹄 ===
  [-0.12, 0.24], [-0.11, 0.23], [-0.10, 0.20],
  // === 后腿内侧 ===
  [-0.10, 0.16], [-0.09, 0.12], [-0.08, 0.09],
  // === 腹部 ===
  [-0.06, 0.10], [-0.04, 0.11], [-0.02, 0.12],
  [0.00, 0.12], [0.02, 0.11],
  // === 前腿 ===
  [0.04, 0.09], [0.04, 0.12], [0.03, 0.16],
  [0.02, 0.20], [0.02, 0.24],
  // === 前蹄 ===
  [0.01, 0.25], [0.00, 0.24], [-0.01, 0.20],
  // === 前腿内侧 → 胸部 ===
  [-0.01, 0.16], [-0.02, 0.12], [-0.03, 0.09],
  [-0.04, 0.06], [-0.05, 0.03],
  // === 胸部 → 颈部 ===
  [-0.06, 0.00], [-0.07, -0.03], [-0.08, -0.06],
  [-0.09, -0.10], [-0.10, -0.14], [-0.11, -0.18],
  // === 颈部 → 头部连接 ===
  [-0.12, -0.22], [-0.13, -0.26], [-0.13, -0.30],
  [-0.13, -0.33], [-0.12, -0.35],
];

// 金牛座主要恒星（嵌在牛身内部）
const TAURUS_STARS: { x: number; y: number; mag: number; name: string }[] = [
  { x: -0.06, y: -0.08, mag: 1.0, name: 'Aldebaran' },  // 毕宿五 — 牛眼
  { x: -0.10, y: -0.04, mag: 0.6, name: 'Elnath' },      // 五车五 — 牛角尖
  { x: -0.04, y: -0.14, mag: 0.5, name: 'Tianguan' },
  { x: -0.08, y: -0.02, mag: 0.4, name: 'Zeta Tau' },
  { x: -0.02, y: -0.10, mag: 0.3, name: 'Theta2 Tau' },
  { x: -0.04, y: -0.06, mag: 0.3, name: 'Theta1 Tau' },
  { x: -0.08, y: -0.12, mag: 0.3, name: 'Gamma Tau' },
  { x: -0.06, y: -0.16, mag: 0.2, name: 'Delta1 Tau' },
  { x: 0.00, y: -0.08, mag: 0.2, name: 'Lambda Tau' },
];

const TAURUS_LINES: [number, number][] = [
  [0, 1], [1, 3], [0, 5], [5, 4], [4, 7], [0, 6], [6, 7], [0, 2], [2, 8],
];

interface Star {
  x: number;
  y: number;
  size: number;
  opacity: number;
  twinkleSpeed: number;
  twinklePhase: number;
}

interface ShootingStar {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  length: number;
}

interface DustParticle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  opacity: number;
  life: number;
  maxLife: number;
}

interface TaurusBackgroundProps {
  half?: boolean;
}

export default function TaurusBackground({ half = false }: TaurusBackgroundProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const starsRef = useRef<Star[]>([]);
  const shootingRef = useRef<ShootingStar[]>([]);
  const dustRef = useRef<DustParticle[]>([]);
  const timeRef = useRef(0);

  const initStars = useCallback((w: number, h: number) => {
    const stars: Star[] = [];
    const count = half ? 150 : 250;
    for (let i = 0; i < count; i++) {
      stars.push({
        x: Math.random() * w,
        y: Math.random() * h,
        size: Math.random() * 1.2 + 0.2,
        opacity: Math.random() * 0.5 + 0.15,
        twinkleSpeed: Math.random() * 2 + 0.5,
        twinklePhase: Math.random() * Math.PI * 2,
      });
    }
    starsRef.current = stars;
  }, [half]);

  const spawnShootingStar = useCallback((w: number, h: number) => {
    if (shootingRef.current.length >= 2) return;
    const angle = Math.PI * 0.15 + Math.random() * Math.PI * 0.2;
    const speed = 4 + Math.random() * 4;
    shootingRef.current.push({
      x: Math.random() * w * 0.6,
      y: Math.random() * h * 0.4,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      life: 1,
      maxLife: 40 + Math.random() * 30,
      length: 30 + Math.random() * 40,
    });
  }, []);

  const spawnDust = useCallback((w: number, h: number) => {
    if (dustRef.current.length >= 25) return;
    dustRef.current.push({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.2 - 0.1,
      size: Math.random() * 1.5 + 0.3,
      opacity: Math.random() * 0.2 + 0.05,
      life: 1,
      maxLife: 200 + Math.random() * 200,
    });
  }, []);

  // 在轮廓点之间插值，生成更密集的星点
  const interpolateOutline = (points: [number, number][], steps: number): [number, number][] => {
    const result: [number, number][] = [];
    for (let i = 0; i < points.length; i++) {
      const [x1, y1] = points[i];
      const [x2, y2] = points[(i + 1) % points.length];
      for (let s = 0; s < steps; s++) {
        const t = s / steps;
        result.push([x1 + (x2 - x1) * t, y1 + (y2 - y1) * t]);
      }
    }
    return result;
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 预计算密集轮廓点
    const denseOutline = interpolateOutline(BULL_OUTLINE, 3);

    const resize = () => {
      const parent = canvas.parentElement;
      if (parent) {
        canvas.width = parent.clientWidth;
        canvas.height = parent.clientHeight;
      } else {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
      }
      initStars(canvas.width, canvas.height);
    };
    resize();
    window.addEventListener('resize', resize);

    const draw = () => {
      const w = canvas.width;
      const h = canvas.height;
      const t = timeRef.current;
      timeRef.current += 0.016;

      ctx.clearRect(0, 0, w, h);

      // 深空背景
      const bgGrad = ctx.createRadialGradient(w * 0.5, h * 0.45, 0, w * 0.5, h * 0.45, Math.max(w, h) * 0.85);
      bgGrad.addColorStop(0, '#0c1033');
      bgGrad.addColorStop(0.4, '#070b22');
      bgGrad.addColorStop(1, '#020408');
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, w, h);

      // 星云 — 暖金色（呼应金牛主题）
      const neb1 = ctx.createRadialGradient(w * 0.45, h * 0.4, 0, w * 0.45, h * 0.4, w * 0.45);
      neb1.addColorStop(0, 'rgba(120, 80, 20, 0.06)');
      neb1.addColorStop(0.4, 'rgba(80, 50, 10, 0.03)');
      neb1.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = neb1;
      ctx.fillRect(0, 0, w, h);

      // 星云 — 冷蓝色
      const neb2 = ctx.createRadialGradient(w * 0.6, h * 0.55, 0, w * 0.6, h * 0.55, w * 0.35);
      neb2.addColorStop(0, 'rgba(30, 58, 138, 0.06)');
      neb2.addColorStop(0.5, 'rgba(59, 130, 246, 0.02)');
      neb2.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = neb2;
      ctx.fillRect(0, 0, w, h);

      // 金牛中心与缩放
      const cx = w * 0.5;
      const cy = h * 0.48;
      const scale = Math.min(w, h) * 0.72;

      // === 铜牛轮廓 — 星星描边 ===
      const bullPulse = 0.65 + Math.sin(t * 0.6) * 0.12;

      // 轮廓连线（极淡，只做暗示）
      ctx.beginPath();
      ctx.strokeStyle = `rgba(251, 191, 36, ${0.04 + Math.sin(t * 0.4) * 0.015})`;
      ctx.lineWidth = 0.5;
      for (let i = 0; i < BULL_OUTLINE.length; i++) {
        const [bx, by] = BULL_OUTLINE[i];
        const px = cx + bx * scale;
        const py = cy + by * scale;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.stroke();

      // 密集星点描边
      for (let i = 0; i < denseOutline.length; i++) {
        const [bx, by] = denseOutline[i];
        const px = cx + bx * scale;
        const py = cy + by * scale;

        // 不同位置的星点大小和亮度有变化
        const hash = Math.sin(i * 127.1) * 43758.5453;
        const sizeVar = (hash - Math.floor(hash));
        const twinkle = 0.35 + Math.sin(t * 1.2 + i * 0.3) * 0.25;
        const starSize = 0.8 + sizeVar * 1.2 + Math.sin(t * 0.5 + i * 0.2) * 0.3;

        // 大星点加光晕
        if (sizeVar > 0.7) {
          const glowR = starSize * 6;
          const glow = ctx.createRadialGradient(px, py, 0, px, py, glowR);
          glow.addColorStop(0, `rgba(251, 191, 36, ${twinkle * bullPulse * 0.35})`);
          glow.addColorStop(0.3, `rgba(245, 158, 11, ${twinkle * bullPulse * 0.1})`);
          glow.addColorStop(1, 'rgba(0, 0, 0, 0)');
          ctx.fillStyle = glow;
          ctx.fillRect(px - glowR, py - glowR, glowR * 2, glowR * 2);
        }

        // 星点本体
        ctx.beginPath();
        ctx.arc(px, py, starSize, 0, Math.PI * 2);
        const warmth = sizeVar > 0.5 ? '255, 220, 120' : '255, 235, 170';
        ctx.fillStyle = `rgba(${warmth}, ${twinkle * bullPulse})`;
        ctx.fill();
      }

      // === 金牛座星座（嵌在牛身内） ===
      ctx.strokeStyle = 'rgba(147, 197, 253, 0.12)';
      ctx.lineWidth = 0.5;
      for (const [a, b] of TAURUS_LINES) {
        const sa = TAURUS_STARS[a];
        const sb = TAURUS_STARS[b];
        ctx.beginPath();
        ctx.moveTo(cx + sa.x * scale, cy + sa.y * scale);
        ctx.lineTo(cx + sb.x * scale, cy + sb.y * scale);
        ctx.stroke();
      }

      for (const star of TAURUS_STARS) {
        const sx = cx + star.x * scale;
        const sy = cy + star.y * scale;
        const mag = star.mag;
        const twinkle = 0.6 + Math.sin(t * 1.0 + star.x * 10) * 0.3;

        const glowSize = mag * 6 + 2;
        const glow = ctx.createRadialGradient(sx, sy, 0, sx, sy, glowSize);
        glow.addColorStop(0, `rgba(147, 197, 253, ${twinkle * 0.4 * mag})`);
        glow.addColorStop(0.5, `rgba(96, 165, 250, ${twinkle * 0.1 * mag})`);
        glow.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = glow;
        ctx.fillRect(sx - glowSize, sy - glowSize, glowSize * 2, glowSize * 2);

        ctx.beginPath();
        ctx.arc(sx, sy, mag * 1.5 + 0.8, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(219, 234, 254, ${twinkle * 0.85})`;
        ctx.fill();

        // 毕宿五 — 金牛之眼，橙红色
        if (star.name === 'Aldebaran') {
          const alGlow = ctx.createRadialGradient(sx, sy, 0, sx, sy, 16);
          alGlow.addColorStop(0, `rgba(251, 146, 60, ${0.45 + Math.sin(t * 0.5) * 0.15})`);
          alGlow.addColorStop(0.4, 'rgba(234, 88, 12, 0.1)');
          alGlow.addColorStop(1, 'rgba(0, 0, 0, 0)');
          ctx.fillStyle = alGlow;
          ctx.fillRect(sx - 16, sy - 16, 32, 32);

          ctx.beginPath();
          ctx.arc(sx, sy, 2.5, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(253, 186, 116, ${0.85 + Math.sin(t * 0.5) * 0.1})`;
          ctx.fill();
        }
      }

      // === 背景星星 ===
      for (const star of starsRef.current) {
        const twinkle = star.opacity * (0.5 + Math.sin(t * star.twinkleSpeed + star.twinklePhase) * 0.4);
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(190, 200, 220, ${twinkle})`;
        ctx.fill();
      }

      // === 流星 ===
      if (Math.random() < 0.006) spawnShootingStar(w, h);
      for (let i = shootingRef.current.length - 1; i >= 0; i--) {
        const s = shootingRef.current[i];
        s.x += s.vx;
        s.y += s.vy;
        s.life -= 1 / s.maxLife;

        if (s.life <= 0) {
          shootingRef.current.splice(i, 1);
          continue;
        }

        const alpha = s.life * 0.7;
        const speed = Math.sqrt(s.vx * s.vx + s.vy * s.vy);
        const tailX = s.x - (s.vx / speed) * s.length * 0.5;
        const tailY = s.y - (s.vy / speed) * s.length * 0.5;

        const grad = ctx.createLinearGradient(tailX, tailY, s.x, s.y);
        grad.addColorStop(0, 'rgba(255, 255, 255, 0)');
        grad.addColorStop(1, `rgba(255, 255, 255, ${alpha})`);

        ctx.beginPath();
        ctx.moveTo(tailX, tailY);
        ctx.lineTo(s.x, s.y);
        ctx.strokeStyle = grad;
        ctx.lineWidth = 1.2;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(s.x, s.y, 1.2, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
        ctx.fill();
      }

      // === 星尘 ===
      if (Math.random() < 0.04) spawnDust(w, h);
      for (let i = dustRef.current.length - 1; i >= 0; i--) {
        const d = dustRef.current[i];
        d.x += d.vx;
        d.y += d.vy;
        d.life -= 1 / d.maxLife;

        if (d.life <= 0) {
          dustRef.current.splice(i, 1);
          continue;
        }

        const alpha = d.opacity * d.life;
        ctx.beginPath();
        ctx.arc(d.x, d.y, d.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(170, 190, 240, ${alpha})`;
        ctx.fill();
      }

      // half模式：右侧渐变过渡
      if (half) {
        const edgeGrad = ctx.createLinearGradient(w * 0.82, 0, w, 0);
        edgeGrad.addColorStop(0, 'rgba(2, 4, 8, 0)');
        edgeGrad.addColorStop(1, 'rgba(2, 4, 8, 0.7)');
        ctx.fillStyle = edgeGrad;
        ctx.fillRect(w * 0.82, 0, w * 0.18, h);
      }

      animRef.current = requestAnimationFrame(draw);
    };

    animRef.current = requestAnimationFrame(draw);

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animRef.current);
    };
  }, [initStars, spawnShootingStar, spawnDust, half]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        zIndex: 0,
      }}
    />
  );
}
