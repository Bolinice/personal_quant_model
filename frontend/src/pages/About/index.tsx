import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography, Button, Container, Chip } from '@mui/material';
import { motion } from 'framer-motion';
import { contentApi } from '@/api';
import { getContent } from '@/api/content';
import { useLang } from '@/i18n';

interface ContentSection {
  title: string;
  subtitle?: string;
  body?: string;
  extra?: Record<string, unknown>;
}

interface PageData {
  sections: Record<string, ContentSection>;
}

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-50px' },
  transition: { duration: 0.6 },
};

export default function AboutPage() {
  const navigate = useNavigate();
  const { lang, t } = useLang();
  const [data, setData] = useState<PageData | null>(null);

  useEffect(() => {
    contentApi
      .getPage('about', lang)
      .then((res) => {
        const apiData = (res.data as { data?: PageData })?.data || res.data;
        const sections = (apiData as PageData)?.sections;
        const fallback = getContent(lang).about || {};
        setData(
          sections && Object.keys(sections).length > 0 ? { sections } : { sections: fallback }
        );
      })
      .catch(() => setData({ sections: getContent(lang).about || {} }));
  }, [lang]);

  const s = (key: string) => data?.sections?.[key];

  return (
    <Box>
      {/* Header */}
      <Box sx={{ py: { xs: 8, md: 12 }, position: 'relative', overflow: 'hidden' }}>
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            background:
              'radial-gradient(ellipse at 50% 0%, rgba(139,92,246,0.08) 0%, transparent 60%)',
          }}
        />
        <Container maxWidth="sm" sx={{ position: 'relative', textAlign: 'center' }}>
          <motion.div {...fadeUp}>
            <Typography
              sx={{
                color: '#a78bfa',
                fontSize: '0.85rem',
                fontWeight: 600,
                mb: 2,
                letterSpacing: '0.05em',
              }}
            >
              {t.about.label}
            </Typography>
            <Typography variant="h3" sx={{ fontWeight: 800, mb: 2 }}>
              {s('about_story')?.title || '我们为什么做这件事'}
            </Typography>
          </motion.div>
        </Container>
      </Box>

      {/* Story */}
      {s('about_story') && (
        <Box sx={{ py: 8 }}>
          <Container maxWidth="sm">
            <motion.div {...fadeUp}>
              {(s('about_story')?.body || '').split('\n\n').map((p, i) => (
                <Typography
                  key={i}
                  sx={{ color: '#94a3b8', lineHeight: 2, mb: 2, fontSize: '0.95rem' }}
                >
                  {p}
                </Typography>
              ))}
            </motion.div>
          </Container>
        </Box>
      )}

      {/* Team */}
      {s('about_team') && (
        <Box sx={{ py: 10, backgroundColor: 'rgba(15,23,42,0.3)' }}>
          <Container maxWidth="md">
            <motion.div {...fadeUp}>
              <Typography
                sx={{
                  color: '#a78bfa',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  mb: 1,
                  textAlign: 'center',
                  letterSpacing: '0.05em',
                }}
              >
                {t.about.teamLabel}
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 4, textAlign: 'center' }}>
                {s('about_team')?.title}
              </Typography>
              {(s('about_team')?.body || '').split('\n\n').map((p, i) => (
                <Typography
                  key={i}
                  sx={{ color: '#94a3b8', lineHeight: 1.9, mb: 2, textAlign: 'center' }}
                >
                  {p}
                </Typography>
              ))}
            </motion.div>

            {/* Tags */}
            {(s('about_team')?.extra?.tags || []).length > 0 && (
              <motion.div {...fadeUp}>
                <Box
                  sx={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 1,
                    justifyContent: 'center',
                    mt: 3,
                    mb: 4,
                  }}
                >
                  {s('about_team')?.extra?.tags.map((tag: string) => (
                    <Chip
                      key={tag}
                      label={tag}
                      size="small"
                      sx={{
                        backgroundColor: 'rgba(139,92,246,0.1)',
                        color: '#a78bfa',
                        border: '1px solid rgba(139,92,246,0.2)',
                      }}
                    />
                  ))}
                </Box>
              </motion.div>
            )}

            {/* Principles */}
            {(s('about_team')?.extra?.principles || []).length > 0 && (
              <motion.div {...fadeUp}>
                <Box
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: { xs: '1fr', md: 'repeat(5, 1fr)' },
                    gap: 2,
                    mt: 4,
                  }}
                >
                  {s('about_team')?.extra?.principles.map((p: string, i: number) => (
                    <Box
                      key={i}
                      sx={{
                        p: 2,
                        borderRadius: 2,
                        textAlign: 'center',
                        border: '1px solid rgba(139,92,246,0.15)',
                        background: 'rgba(139,92,246,0.04)',
                      }}
                    >
                      <Typography
                        sx={{ color: '#a78bfa', fontWeight: 700, fontSize: '1.2rem', mb: 0.5 }}
                      >
                        {String(i + 1).padStart(2, '0')}
                      </Typography>
                      <Typography sx={{ color: '#cbd5e1', fontSize: '0.8rem', lineHeight: 1.6 }}>
                        {p}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </motion.div>
            )}
          </Container>
        </Box>
      )}

      {/* Team Advantages */}
      {s('team_advantages') && (
        <Box sx={{ py: 10 }}>
          <Container maxWidth="md">
            <motion.div {...fadeUp}>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 6, textAlign: 'center' }}>
                {s('team_advantages')?.title}
              </Typography>
            </motion.div>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {(
                (s('team_advantages')?.extra?.advantages as Array<{
                  icon: string;
                  title: string;
                  desc: string;
                }>) || []
              ).map((adv, i: number) => (
                <motion.div key={i} {...fadeUp} transition={{ duration: 0.5, delay: i * 0.1 }}>
                  <Box
                    sx={{
                      p: 3,
                      borderRadius: 3,
                      background: 'rgba(15,23,42,0.6)',
                      border: '1px solid rgba(148,163,184,0.1)',
                      backdropFilter: 'blur(16px)',
                      display: 'flex',
                      gap: 3,
                      alignItems: 'center',
                      '&:hover': { borderColor: 'rgba(139,92,246,0.3)' },
                      transition: 'border-color 0.3s',
                    }}
                  >
                    <Box
                      sx={{
                        width: 48,
                        height: 48,
                        borderRadius: 2,
                        flexShrink: 0,
                        background:
                          'linear-gradient(135deg, rgba(139,92,246,0.15), rgba(34,211,238,0.15))',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Typography
                        sx={{
                          fontWeight: 800,
                          fontSize: '1.1rem',
                          background: 'linear-gradient(135deg, #a78bfa, #22d3ee)',
                          backgroundClip: 'text',
                          WebkitBackgroundClip: 'text',
                          WebkitTextFillColor: 'transparent',
                        }}
                      >
                        {String(i + 1).padStart(2, '0')}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography sx={{ fontWeight: 700, mb: 0.5 }}>{adv.title}</Typography>
                      <Typography sx={{ color: '#94a3b8', fontSize: '0.85rem', lineHeight: 1.6 }}>
                        {adv.desc}
                      </Typography>
                    </Box>
                  </Box>
                </motion.div>
              ))}
            </Box>
          </Container>
        </Box>
      )}

      {/* CTA */}
      {s('cta') && (
        <Box
          sx={{
            py: 12,
            position: 'relative',
            overflow: 'hidden',
            backgroundColor: 'rgba(15,23,42,0.3)',
          }}
        >
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              background:
                'radial-gradient(ellipse at 50% 100%, rgba(139,92,246,0.08) 0%, transparent 60%)',
            }}
          />
          <Container maxWidth="sm" sx={{ position: 'relative', textAlign: 'center' }}>
            <motion.div {...fadeUp}>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>
                {s('cta')?.title}
              </Typography>
              <Typography sx={{ color: '#94a3b8', mb: 4, lineHeight: 1.8 }}>
                {s('cta')?.subtitle}
              </Typography>
              <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
                <Button variant="contained" size="large" onClick={() => navigate('/pricing')}>
                  {t.btn.trial}
                </Button>
                <Button variant="outlined" size="large" onClick={() => navigate('/pricing')}>
                  {t.btn.bookDemo}
                </Button>
                <Button size="large" sx={{ color: '#94a3b8' }}>
                  {t.btn.contactAdvisor}
                </Button>
              </Box>
            </motion.div>
          </Container>
        </Box>
      )}
    </Box>
  );
}
