import { useRef, useEffect } from 'react';
import { Box } from '@mui/material';

interface Star {
  x: number;
  y: number;
  radius: number;
  alpha: number;
  speed: number;
}

export default function StarfieldBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationId: number;
    const STAR_COUNT = 260;
    const SHOOTING_STAR_INTERVAL = 4000;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    const stars: Star[] = Array.from({ length: STAR_COUNT }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      radius: Math.random() * 1.5 + 0.3,
      alpha: Math.random() * 0.8 + 0.2,
      speed: Math.random() * 0.005 + 0.002,
    }));

    let shootingStar: { x: number; y: number; len: number; speed: number; alpha: number; angle: number } | null = null;

    const spawnShootingStar = () => {
      shootingStar = {
        x: Math.random() * canvas.width * 0.8,
        y: Math.random() * canvas.height * 0.4,
        len: Math.random() * 80 + 40,
        speed: Math.random() * 6 + 4,
        alpha: 1,
        angle: Math.PI / 4 + Math.random() * 0.3,
      };
    };

    const shootingInterval = setInterval(spawnShootingStar, SHOOTING_STAR_INTERVAL);

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Stars
      for (const star of stars) {
        star.alpha += Math.sin(Date.now() * star.speed) * 0.01;
        const a = Math.max(0.1, Math.min(1, star.alpha));
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(200, 220, 255, ${a})`;
        ctx.fill();
      }

      // Shooting star
      if (shootingStar) {
        const s = shootingStar;
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(s.x - Math.cos(s.angle) * s.len, s.y - Math.sin(s.angle) * s.len);
        const grad = ctx.createLinearGradient(s.x, s.y, s.x - Math.cos(s.angle) * s.len, s.y - Math.sin(s.angle) * s.len);
        grad.addColorStop(0, `rgba(200, 230, 255, ${s.alpha})`);
        grad.addColorStop(1, 'rgba(200, 230, 255, 0)');
        ctx.strokeStyle = grad;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        s.x += Math.cos(s.angle) * s.speed;
        s.y += Math.sin(s.angle) * s.speed;
        s.alpha -= 0.012;
        if (s.alpha <= 0 || s.x > canvas.width || s.y > canvas.height) {
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
  }, []);

  return (
    <Box
      sx={{
        position: 'fixed',
        inset: 0,
        zIndex: -1,
        bgcolor: '#030712',
      }}
    >
      <canvas ref={canvasRef} style={{ display: 'block', width: '100%', height: '100%' }} />
      {/* Gradient overlay for depth */}
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          background: 'radial-gradient(ellipse at 20% 50%, rgba(59,130,246,0.08) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(139,92,246,0.06) 0%, transparent 50%)',
          pointerEvents: 'none',
        }}
      />
    </Box>
  );
}
