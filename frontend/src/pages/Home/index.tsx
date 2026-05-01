import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Box, Typography, Button, Container, Chip } from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import { motion } from 'framer-motion';
import { contentApi } from '@/api';
import { getContent } from '@/api/content';
import { Logo } from '@/components/ui';
import { useLang } from '@/i18n';

interface ContentSection {
  title: string;
  subtitle?: string;
  body?: string;
  extra?: Record<string, any>;
}

interface PageData {
  sections: Record<string, ContentSection>;
}

const fadeUp: any = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-80px' },
  transition: { duration: 0.7, ease: 'easeInOut' },
};

export default function HomePage() {
  const navigate = useNavigate();
  const { lang, t } = useLang();
  const [data, setData] = useState<PageData | null>(null);

  useEffect(() => {
    contentApi
      .getPage('home', lang)
      .then((res: any) => {
        const apiData = res.data?.data || res.data;
        const sections = apiData?.sections;
        const fallback = getContent(lang).home || {};
        setData(
          sections && Object.keys(sections).length > 0 ? { sections } : { sections: fallback }
        );
      })
      .catch(() => setData({ sections: getContent(lang).home || {} }));
  }, [lang]);

  const s = (key: string) => data?.sections?.[key];

  return (
    <Box>
      {/* ─── Hero ─── */}
      <Box
        sx={{
          position: 'relative',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: { xs: '80vh', md: '90vh' },
          px: { xs: 4, md: 8 },
        }}
      >
        {/* 背景光晕: 更大更柔和 */}
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            background:
              'radial-gradient(ellipse 80% 60% at 50% 35%, rgba(34,211,238,0.06) 0%, transparent 100%)',
          }}
        />
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            background:
              'radial-gradient(ellipse 60% 50% at 60% 70%, rgba(139,92,246,0.04) 0%, transparent 100%)',
          }}
        />

        {/* Slogan: 两行，幻方风格 */}
        <motion.div {...fadeUp}>
          <Box sx={{ textAlign: 'center', mb: 8 }}>
            <Typography
              sx={{
                color: '#f1f5f9',
                fontSize: { xs: '2rem', md: '3rem' },
                fontWeight: 600,
                lineHeight: 1.5,
                letterSpacing: '0.04em',
              }}
            >
              {t.brand.slogan1}
            </Typography>
            <Typography
              sx={{
                color: '#f1f5f9',
                fontSize: { xs: '2rem', md: '3rem' },
                fontWeight: 600,
                lineHeight: 1.5,
                letterSpacing: '0.04em',
              }}
            >
              {t.brand.slogan2}
            </Typography>
          </Box>
        </motion.div>

        {/* 品牌行: Logo + 名称 + 竖线 + 管道 */}
        <motion.div
          {...fadeUp}
          transition={{ duration: 0.7, delay: 0.2, ease: 'easeInOut' }}
        >
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 2.5,
              flexWrap: 'wrap',
            }}
          >
            <Logo size={40} />
            <Typography
              sx={{
                fontWeight: 600,
                fontSize: { xs: '1.1rem', md: '1.4rem' },
                color: '#e2e8f0',
                letterSpacing: '0.06em',
              }}
            >
              {t.brand.name}
            </Typography>
            <Box sx={{ width: 1.5, height: 20, backgroundColor: 'rgba(148,163,184,0.3)' }} />
            <Typography
              sx={{
                fontWeight: 400,
                fontSize: { xs: '0.8rem', md: '0.95rem' },
                color: '#64748b',
                letterSpacing: '0.08em',
              }}
            >
              {t.brand.tagline}
            </Typography>
          </Box>
        </motion.div>
      </Box>

      {/* ─── Brand Position ─── */}
      {s('brand') && (
        <Box sx={{ py: 12 }}>
          <Container maxWidth="sm" sx={{ textAlign: 'center' }}>
            <motion.div {...fadeUp}>
              <Typography
                sx={{
                  fontWeight: 300,
                  fontSize: '1.6rem',
                  lineHeight: 1.8,
                  mb: 4,
                  color: '#e2e8f0',
                }}
              >
                {s('brand')?.title}
              </Typography>
              {(s('brand')?.body || '').split('\n\n').map((p, i) => (
                <Typography
                  key={i}
                  sx={{ color: '#94a3b8', fontSize: '0.95rem', lineHeight: 2, mb: i === 0 ? 2 : 0 }}
                >
                  {p}
                </Typography>
              ))}
            </motion.div>
          </Container>
        </Box>
      )}

      {/* ─── Core Values ─── */}
      {s('core_values') && (
        <Box sx={{ py: 14, backgroundColor: 'rgba(15,23,42,0.4)' }} id="features">
          <Container maxWidth="lg">
            <motion.div {...fadeUp}>
              <Typography
                sx={{
                  color: '#22d3ee',
                  fontSize: '0.7rem',
                  fontWeight: 500,
                  mb: 2,
                  textAlign: 'center',
                  letterSpacing: '0.15em',
                  textTransform: 'uppercase',
                }}
              >
                {t.home.coreValue}
              </Typography>
              <Typography
                sx={{
                  fontWeight: 300,
                  fontSize: '1.8rem',
                  mb: 8,
                  textAlign: 'center',
                  color: '#e2e8f0',
                  lineHeight: 1.5,
                }}
              >
                {s('core_values')?.title}
              </Typography>
            </motion.div>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', md: 'repeat(4, 1fr)' },
                gap: 4,
              }}
            >
              {(s('core_values')?.extra?.cards || []).map((card: any, i: number) => (
                <motion.div key={i} {...fadeUp} transition={{ duration: 0.6, delay: i * 0.12 }}>
                  <Box
                    sx={{
                      p: 4,
                      borderRadius: 4,
                      height: '100%',
                      background:
                        'linear-gradient(180deg, rgba(15,23,42,0.8) 0%, rgba(15,23,42,0.4) 100%)',
                      border: '1px solid rgba(148,163,184,0.08)',
                      borderTop: '1px solid rgba(34,211,238,0.12)',
                      '&:hover': {
                        borderColor: 'rgba(34,211,238,0.2)',
                        borderTopColor: 'rgba(34,211,238,0.4)',
                        transform: 'translateY(-6px)',
                      },
                      transition: 'all 0.4s cubic-bezier(0.25,0.1,0.25,1)',
                    }}
                  >
                    <Typography sx={{ fontWeight: 600, mb: 2, fontSize: '1rem', color: '#f1f5f9' }}>
                      {card.title}
                    </Typography>
                    <Typography sx={{ color: '#94a3b8', fontSize: '0.85rem', lineHeight: 1.8 }}>
                      {card.body}
                    </Typography>
                  </Box>
                </motion.div>
              ))}
            </Box>
          </Container>
        </Box>
      )}

      {/* ─── Product Modules ─── */}
      {s('product_modules') && (
        <Box sx={{ py: 16 }}>
          <Container maxWidth="lg">
            <motion.div {...fadeUp}>
              <Typography
                sx={{
                  color: '#22d3ee',
                  fontSize: '0.7rem',
                  fontWeight: 500,
                  mb: 2,
                  textAlign: 'center',
                  letterSpacing: '0.15em',
                }}
              >
                {t.home.capability}
              </Typography>
              <Typography
                sx={{
                  fontWeight: 300,
                  fontSize: '1.8rem',
                  mb: 3,
                  textAlign: 'center',
                  color: '#e2e8f0',
                  lineHeight: 1.5,
                }}
              >
                {s('product_modules')?.title}
              </Typography>
              <Typography
                sx={{
                  color: '#94a3b8',
                  textAlign: 'center',
                  maxWidth: 640,
                  mx: 'auto',
                  mb: 10,
                  lineHeight: 1.9,
                  fontSize: '0.95rem',
                }}
              >
                {s('product_modules')?.subtitle}
              </Typography>
            </motion.div>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)' },
                gap: 4,
              }}
            >
              {(s('product_modules')?.extra?.modules || []).map((mod: any, i: number) => (
                <motion.div key={i} {...fadeUp} transition={{ duration: 0.6, delay: i * 0.1 }}>
                  <Box
                    sx={{
                      p: 4,
                      borderRadius: 4,
                      background: 'rgba(15,23,42,0.5)',
                      border: '1px solid rgba(148,163,184,0.06)',
                      '&:hover': { borderColor: 'rgba(34,211,238,0.15)' },
                      transition: 'border-color 0.4s',
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5, mb: 3 }}>
                      <Typography
                        sx={{
                          fontWeight: 800,
                          fontSize: '1.8rem',
                          background: 'linear-gradient(135deg, #22d3ee, #8b5cf6)',
                          backgroundClip: 'text',
                          WebkitBackgroundClip: 'text',
                          WebkitTextFillColor: 'transparent',
                          opacity: 0.7,
                        }}
                      >
                        {mod.index}
                      </Typography>
                      <Typography sx={{ fontWeight: 600, fontSize: '1rem', color: '#f1f5f9' }}>
                        {mod.title}
                      </Typography>
                    </Box>
                    {(mod.items || []).map((item: string, j: number) => (
                      <Box
                        key={j}
                        sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5, mb: 1 }}
                      >
                        <CheckCircleIcon
                          sx={{
                            color: '#22d3ee',
                            fontSize: 14,
                            mt: 0.5,
                            flexShrink: 0,
                            opacity: 0.7,
                          }}
                        />
                        <Typography sx={{ color: '#94a3b8', fontSize: '0.85rem', lineHeight: 1.7 }}>
                          {item}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                </motion.div>
              ))}
            </Box>
          </Container>
        </Box>
      )}

      {/* ─── Workflow ─── */}
      {s('workflow') && (
        <Box sx={{ py: 14, backgroundColor: 'rgba(15,23,42,0.4)' }}>
          <Container maxWidth="sm">
            <motion.div {...fadeUp}>
              <Typography
                sx={{
                  color: '#22d3ee',
                  fontSize: '0.7rem',
                  fontWeight: 500,
                  mb: 2,
                  textAlign: 'center',
                  letterSpacing: '0.15em',
                }}
              >
                {t.home.workflow}
              </Typography>
              <Typography
                sx={{
                  fontWeight: 300,
                  fontSize: '1.8rem',
                  mb: 3,
                  textAlign: 'center',
                  color: '#e2e8f0',
                  lineHeight: 1.5,
                }}
              >
                {s('workflow')?.title}
              </Typography>
              <Typography
                sx={{ color: '#94a3b8', textAlign: 'center', mb: 8, fontSize: '0.95rem' }}
              >
                {s('workflow')?.subtitle}
              </Typography>
            </motion.div>
            <Box sx={{ position: 'relative', pl: 5 }}>
              <Box
                sx={{
                  position: 'absolute',
                  left: 22,
                  top: 8,
                  bottom: 8,
                  width: 1,
                  background: 'linear-gradient(180deg, rgba(34,211,238,0.4), rgba(139,92,246,0.4))',
                  borderRadius: 1,
                }}
              />
              {(s('workflow')?.extra?.timeline || []).map((step: any, i: number) => (
                <motion.div key={i} {...fadeUp} transition={{ duration: 0.5, delay: i * 0.12 }}>
                  <Box sx={{ display: 'flex', gap: 3, mb: 5, position: 'relative' }}>
                    <Box
                      sx={{
                        width: 10,
                        height: 10,
                        borderRadius: '50%',
                        flexShrink: 0,
                        background: '#22d3ee',
                        position: 'absolute',
                        left: -22,
                        top: 6,
                        boxShadow: '0 0 10px rgba(34,211,238,0.4)',
                      }}
                    />
                    <Box sx={{ pl: 1 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.75 }}>
                        <AccessTimeIcon sx={{ color: '#22d3ee', fontSize: 16, opacity: 0.8 }} />
                        <Typography
                          sx={{
                            fontWeight: 600,
                            color: '#22d3ee',
                            fontSize: '0.85rem',
                            letterSpacing: '0.02em',
                          }}
                        >
                          {step.time}
                        </Typography>
                      </Box>
                      <Typography
                        sx={{ fontWeight: 500, mb: 0.5, color: '#e2e8f0', fontSize: '0.95rem' }}
                      >
                        {step.title}
                      </Typography>
                      <Typography sx={{ color: '#94a3b8', fontSize: '0.85rem', lineHeight: 1.7 }}>
                        {step.body}
                      </Typography>
                    </Box>
                  </Box>
                </motion.div>
              ))}
            </Box>
            {s('workflow')?.extra?.note && (
              <motion.div {...fadeUp}>
                <Box
                  sx={{
                    p: 3,
                    borderRadius: 3,
                    border: '1px solid rgba(34,211,238,0.15)',
                    background: 'rgba(34,211,238,0.03)',
                    mt: 3,
                  }}
                >
                  <Typography sx={{ color: '#cbd5e1', fontSize: '0.9rem', lineHeight: 1.8 }}>
                    {s('workflow')?.extra?.note}
                  </Typography>
                </Box>
              </motion.div>
            )}
          </Container>
        </Box>
      )}

      {/* ─── Advantages ─── */}
      {s('advantages') && (
        <Box sx={{ py: 16 }}>
          <Container maxWidth="lg">
            <motion.div {...fadeUp}>
              <Typography
                sx={{
                  color: '#22d3ee',
                  fontSize: '0.7rem',
                  fontWeight: 500,
                  mb: 2,
                  textAlign: 'center',
                  letterSpacing: '0.15em',
                }}
              >
                {t.home.advantage}
              </Typography>
              <Typography
                sx={{
                  fontWeight: 300,
                  fontSize: '1.8rem',
                  mb: 8,
                  textAlign: 'center',
                  color: '#e2e8f0',
                  lineHeight: 1.5,
                }}
              >
                {s('advantages')?.title}
              </Typography>
            </motion.div>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' },
                gap: 4,
              }}
            >
              {(s('advantages')?.extra?.cards || []).map((card: any, i: number) => (
                <motion.div key={i} {...fadeUp} transition={{ duration: 0.5, delay: i * 0.1 }}>
                  <Box
                    sx={{
                      p: 4,
                      borderRadius: 4,
                      height: '100%',
                      background: 'rgba(15,23,42,0.5)',
                      border: '1px solid rgba(148,163,184,0.06)',
                      '&:hover': {
                        borderColor: 'rgba(34,211,238,0.2)',
                        transform: 'translateY(-4px)',
                      },
                      transition: 'all 0.4s cubic-bezier(0.25,0.1,0.25,1)',
                    }}
                  >
                    <Typography sx={{ fontWeight: 600, mb: 2, fontSize: '1rem', color: '#f1f5f9' }}>
                      {card.title}
                    </Typography>
                    <Typography sx={{ color: '#94a3b8', fontSize: '0.85rem', lineHeight: 1.8 }}>
                      {card.body}
                    </Typography>
                  </Box>
                </motion.div>
              ))}
            </Box>
          </Container>
        </Box>
      )}

      {/* ─── Team ─── */}
      {s('team') && (
        <Box sx={{ py: 14, backgroundColor: 'rgba(15,23,42,0.4)' }}>
          <Container maxWidth="md">
            <motion.div {...fadeUp}>
              <Typography
                sx={{
                  color: '#a78bfa',
                  fontSize: '0.7rem',
                  fontWeight: 500,
                  mb: 2,
                  textAlign: 'center',
                  letterSpacing: '0.15em',
                }}
              >
                {t.home.team}
              </Typography>
              <Typography
                sx={{
                  fontWeight: 300,
                  fontSize: '1.6rem',
                  mb: 5,
                  textAlign: 'center',
                  color: '#e2e8f0',
                  lineHeight: 1.6,
                }}
              >
                {s('team')?.title}
              </Typography>
              {(s('team')?.body || '').split('\n\n').map((p, i) => (
                <Typography
                  key={i}
                  sx={{
                    color: '#94a3b8',
                    lineHeight: 2,
                    mb: 2,
                    textAlign: 'center',
                    fontSize: '0.95rem',
                  }}
                >
                  {p}
                </Typography>
              ))}
              <Box
                sx={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 1.5,
                  justifyContent: 'center',
                  mt: 4,
                }}
              >
                {(s('team')?.extra?.tags || []).map((tag: string) => (
                  <Chip
                    key={tag}
                    label={tag}
                    size="small"
                    sx={{
                      backgroundColor: 'rgba(139,92,246,0.06)',
                      color: '#a78bfa',
                      border: '1px solid rgba(139,92,246,0.15)',
                      fontWeight: 400,
                      fontSize: '0.75rem',
                    }}
                  />
                ))}
              </Box>
            </motion.div>
          </Container>
        </Box>
      )}

      {/* ─── Audience ─── */}
      {s('audience') && (
        <Box sx={{ py: 14 }}>
          <Container maxWidth="lg">
            <motion.div {...fadeUp}>
              <Typography
                sx={{
                  color: '#22d3ee',
                  fontSize: '0.7rem',
                  fontWeight: 500,
                  mb: 2,
                  textAlign: 'center',
                  letterSpacing: '0.15em',
                }}
              >
                {t.home.audience}
              </Typography>
              <Typography
                sx={{
                  fontWeight: 300,
                  fontSize: '1.8rem',
                  mb: 8,
                  textAlign: 'center',
                  color: '#e2e8f0',
                  lineHeight: 1.5,
                }}
              >
                {s('audience')?.title}
              </Typography>
            </motion.div>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' },
                gap: 4,
              }}
            >
              {(s('audience')?.extra?.cards || []).map((card: any, i: number) => (
                <motion.div key={i} {...fadeUp} transition={{ duration: 0.5, delay: i * 0.12 }}>
                  <Box
                    sx={{
                      p: 4,
                      borderRadius: 4,
                      background: 'rgba(15,23,42,0.5)',
                      border: '1px solid rgba(148,163,184,0.06)',
                      '&:hover': { borderColor: 'rgba(34,211,238,0.2)' },
                      transition: 'border-color 0.4s',
                    }}
                  >
                    <Typography sx={{ fontWeight: 600, mb: 2, fontSize: '1rem', color: '#f1f5f9' }}>
                      {card.title}
                    </Typography>
                    <Typography sx={{ color: '#94a3b8', fontSize: '0.85rem', lineHeight: 1.8 }}>
                      {card.body}
                    </Typography>
                  </Box>
                </motion.div>
              ))}
            </Box>
          </Container>
        </Box>
      )}

      {/* ─── Pricing Entry ─── */}
      {s('pricing_entry') && (
        <Box sx={{ py: 16, backgroundColor: 'rgba(15,23,42,0.4)' }}>
          <Container maxWidth="sm" sx={{ textAlign: 'center' }}>
            <motion.div {...fadeUp}>
              <Typography
                sx={{
                  fontWeight: 300,
                  fontSize: '1.6rem',
                  mb: 3,
                  color: '#e2e8f0',
                  lineHeight: 1.5,
                }}
              >
                {s('pricing_entry')?.title}
              </Typography>
              <Typography sx={{ color: '#94a3b8', mb: 6, lineHeight: 1.9, fontSize: '0.95rem' }}>
                {s('pricing_entry')?.subtitle}
              </Typography>
            </motion.div>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2.5, mb: 6 }}>
              {(s('pricing_entry')?.extra?.plans || []).map((plan: any) => (
                <Box
                  key={plan.name}
                  sx={{
                    p: 2.5,
                    borderRadius: 3,
                    border: '1px solid rgba(148,163,184,0.08)',
                    background: 'rgba(15,23,42,0.6)',
                  }}
                >
                  <Typography
                    sx={{ fontWeight: 600, fontSize: '0.9rem', mb: 0.5, color: '#e2e8f0' }}
                  >
                    {plan.name}
                  </Typography>
                  <Typography sx={{ color: '#94a3b8', fontSize: '0.8rem' }}>{plan.desc}</Typography>
                </Box>
              ))}
            </Box>
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
              <Button variant="contained" onClick={() => navigate('/pricing')}>
                {t.btn.viewPricing}
              </Button>
              <Button variant="outlined" onClick={() => navigate('/about')}>
                {t.btn.getQuote}
              </Button>
            </Box>
          </Container>
        </Box>
      )}

      {/* ─── Risk Disclaimer ─── */}
      {s('risk_disclaimer') && (
        <Box sx={{ py: 8 }}>
          <Container maxWidth="sm">
            <Typography
              sx={{
                fontWeight: 500,
                fontSize: '0.85rem',
                mb: 1.5,
                textAlign: 'center',
                color: '#64748b',
              }}
            >
              {s('risk_disclaimer')?.title}
            </Typography>
            <Typography
              sx={{ color: '#475569', fontSize: '0.8rem', lineHeight: 2, textAlign: 'center' }}
            >
              {s('risk_disclaimer')?.body}
            </Typography>
          </Container>
        </Box>
      )}

      {/* ─── CTA ─── */}
      {s('cta') && (
        <Box sx={{ py: 16, position: 'relative', overflow: 'hidden' }}>
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              background:
                'radial-gradient(ellipse 70% 60% at 50% 80%, rgba(139,92,246,0.06) 0%, transparent 100%)',
            }}
          />
          <Container maxWidth="sm" sx={{ position: 'relative', textAlign: 'center' }}>
            <motion.div {...fadeUp}>
              <Typography
                sx={{
                  fontWeight: 300,
                  fontSize: '1.6rem',
                  mb: 3,
                  color: '#e2e8f0',
                  lineHeight: 1.6,
                }}
              >
                {s('cta')?.title}
              </Typography>
              <Typography sx={{ color: '#94a3b8', mb: 6, lineHeight: 1.9, fontSize: '0.95rem' }}>
                {s('cta')?.subtitle}
              </Typography>
              <Box
                sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap', mb: 4 }}
              >
                <Button variant="contained" size="large" onClick={() => navigate('/pricing')}>
                  {t.btn.trial}
                </Button>
                <Button variant="outlined" size="large" onClick={() => navigate('/pricing')}>
                  {t.btn.bookDemo}
                </Button>
                <Button size="large" sx={{ color: '#94a3b8' }} onClick={() => navigate('/about')}>
                  {t.btn.contactAdvisor}
                </Button>
              </Box>
              <Typography sx={{ color: '#64748b', fontSize: '0.85rem', letterSpacing: '0.02em' }}>
                {s('cta')?.body}
              </Typography>
            </motion.div>
          </Container>
        </Box>
      )}
    </Box>
  );
}
