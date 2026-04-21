import { useRef, useEffect } from 'react';
import { Box } from '@mui/material';
import { useBackground } from './BackgroundContext';
import type { ConstellationTheme } from './BackgroundContext';

interface Star {
  x: number;
  y: number;
  radius: number;
  alpha: number;
  speed: number;
}

export default function StarfieldBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { theme } = useBackground();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationId: number;
    const STAR_COUNT = Math.round(320 * theme.starDensity);
    const SHOOTING_STAR_INTERVAL = 3500;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    const stars: Star[] = Array.from({ length: STAR_COUNT }, () => ({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      radius: Math.random() * 1.5 + 0.3,
      alpha: Math.random() * 0.8 + 0.2,
      speed: (Math.random() * 0.005 + 0.002) * theme.twinkleSpeed,
    }));

    let shootingStar: { x: number; y: number; len: number; speed: number; alpha: number; angle: number } | null = null;

    const spawnShootingStar = () => {
      shootingStar = {
        x: Math.random() * window.innerWidth * 0.8,
        y: Math.random() * window.innerHeight * 0.4,
        len: Math.random() * 80 + 40,
        speed: Math.random() * 6 + 4,
        alpha: 1,
        angle: Math.PI / 4 + Math.random() * 0.3,
      };
    };

    const shootingInterval = setInterval(spawnShootingStar, SHOOTING_STAR_INTERVAL);

    const [sr, sg, sb] = theme.starColor;
    const [cr, cg, cb] = theme.shootingColor;

    const draw = () => {
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

      // Stars
      for (const star of stars) {
        star.alpha += Math.sin(Date.now() * star.speed) * 0.01;
        const a = Math.max(0.1, Math.min(1, star.alpha));
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${sr}, ${sg}, ${sb}, ${a})`;
        ctx.fill();
      }

      // Shooting star
      if (shootingStar) {
        const s = shootingStar;
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(s.x - Math.cos(s.angle) * s.len, s.y - Math.sin(s.angle) * s.len);
        const grad = ctx.createLinearGradient(s.x, s.y, s.x - Math.cos(s.angle) * s.len, s.y - Math.sin(s.angle) * s.len);
        grad.addColorStop(0, `rgba(${cr}, ${cg}, ${cb}, ${s.alpha})`);
        grad.addColorStop(1, `rgba(${cr}, ${cg}, ${cb}, 0)`);
        ctx.strokeStyle = grad;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        s.x += Math.cos(s.angle) * s.speed;
        s.y += Math.sin(s.angle) * s.speed;
        s.alpha -= 0.012;
        if (s.alpha <= 0 || s.x > window.innerWidth || s.y > window.innerHeight) {
          shootingStar = null;
        }
      }

      animationId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      cancelAnimationFrame(animationId);
      clearInterval(shootingInterval);
      window.removeEventListener('resize', resize);
    };
  }, [theme]);

  return (
    <Box
      sx={{
        position: 'fixed',
        inset: 0,
        zIndex: -1,
        bgcolor: theme.bgColor,
        transition: 'background-color 1.5s ease',
      }}
    >
      <canvas ref={canvasRef} style={{ display: 'block' }} />
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          background: theme.nebula,
          pointerEvents: 'none',
          transition: 'background 1.5s ease',
        }}
      />
    </Box>
  );
}
