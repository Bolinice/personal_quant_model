import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, Button, Container, Chip, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Paper, Accordion, AccordionSummary,
  AccordionDetails, ToggleButtonGroup, ToggleButton,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import StarIcon from '@mui/icons-material/Star';
import { motion } from 'framer-motion';
import { contentApi, subscriptionApi } from '@/api';
import { getContent } from '@/api/content';
import type { PricingOverview, SubscriptionPlan, PricingMatrix as PricingMatrixType, UpgradePackage as UpgradePackageType } from '@/api/types/subscriptions';
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

const fadeUp = {
  initial: { opacity: 0, y: 30 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-50px' },
  transition: { duration: 0.6 },
};

export default function PricingPage() {
  const navigate = useNavigate();
  const { lang, t } = useLang();
  const [data, setData] = useState<PageData | null>(null);
  const [billingCycle, setBillingCycle] = useState<'yearly' | 'monthly'>('yearly');

  // API 定价数据
  const [apiPlans, setApiPlans] = useState<SubscriptionPlan[]>([]);
  const [apiMatrix, setApiMatrix] = useState<PricingMatrixType[]>([]);
  const [apiUpgradePkgs, setApiUpgradePkgs] = useState<UpgradePackageType[]>([]);

  useEffect(() => {
    // 加载文案
    contentApi.getPage('pricing', lang).then((res: any) => {
      const apiData = res.data?.data || res.data;
      const sections = apiData?.sections;
      const fallback = getContent(lang).pricing || {};
      setData(sections && Object.keys(sections).length > 0 ? { sections } : { sections: fallback });
    }).catch(() => setData({ sections: getContent(lang).pricing || {} }));

    // 加载定价数据
    subscriptionApi.getPricingOverview().then((res: any) => {
      const overview: PricingOverview = res.data;
      if (overview?.plans?.length > 0) setApiPlans(overview.plans);
      if (overview?.pricing_matrix?.length > 0) setApiMatrix(overview.pricing_matrix);
      if (overview?.upgrade_packages?.length > 0) setApiUpgradePkgs(overview.upgrade_packages);
    }).catch(() => {});
  }, [lang]);

  const s = (key: string) => data?.sections?.[key];

  // 方案数据：优先 API，fallback 文案
  const contentPlans = s('pricing_plans')?.extra?.plans || [];
  const plans = apiPlans.length > 0 ? apiPlans : contentPlans;

  // 价格矩阵：优先 API，fallback 文案
  const apiMatrixForCycle = apiMatrix.find(m => m.billing_cycle === billingCycle);
  const contentMatrixData = billingCycle === 'yearly' ? s('pricing_matrix')?.extra?.yearly : s('pricing_matrix')?.extra?.monthly;
  const matrixPools = apiMatrixForCycle ? apiMatrixForCycle.pools : (contentMatrixData?.pools || []);
  const matrixFrequencies = apiMatrixForCycle ? apiMatrixForCycle.frequencies : (contentMatrixData?.frequencies || []);
  const matrixPrices = apiMatrixForCycle ? apiMatrixForCycle.prices : (contentMatrixData?.prices || []);

  // 升级包：优先 API，fallback 文案
  const contentUpgradePkgs = s('upgrade_packages')?.extra?.packages || [];
  const upgradePkgs = apiUpgradePkgs.length > 0 ? apiUpgradePkgs : contentUpgradePkgs;

  // 判断是否为 API 方案数据
  const isApiPlan = apiPlans.length > 0;

  return (
    <Box>
      {/* Header */}
      <Box sx={{ py: { xs: 8, md: 12 }, position: 'relative', overflow: 'hidden' }}>
        <Box sx={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 0%, rgba(34,211,238,0.08) 0%, transparent 60%)' }} />
        <Container maxWidth="sm" sx={{ position: 'relative', textAlign: 'center' }}>
          <motion.div {...fadeUp}>
            <Typography variant="h3" sx={{ fontWeight: 800, mb: 2 }}>{s('pricing_header')?.title || '定价方案'}</Typography>
            <Typography sx={{ color: '#94a3b8', mb: 2, lineHeight: 1.8 }}>{s('pricing_header')?.subtitle}</Typography>
            <Typography sx={{ color: '#94a3b8', fontSize: '0.9rem', lineHeight: 1.8 }}>{s('pricing_header')?.body}</Typography>
          </motion.div>
        </Container>
      </Box>

      {/* Pricing Philosophy */}
      {s('pricing_philosophy') && (
        <Box sx={{ py: 8, backgroundColor: 'rgba(15,23,42,0.3)' }}>
          <Container maxWidth="md">
            <motion.div {...fadeUp}>
              <Typography variant="h5" sx={{ fontWeight: 700, mb: 2, textAlign: 'center' }}>{s('pricing_philosophy')?.title}</Typography>
              <Typography sx={{ color: '#94a3b8', textAlign: 'center', mb: 4 }}>{s('pricing_philosophy')?.body}</Typography>
            </motion.div>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' }, gap: 2 }}>
              {(s('pricing_philosophy')?.extra?.dimensions || []).map((dim: any, i: number) => (
                <motion.div key={i} {...fadeUp} transition={{ duration: 0.5, delay: i * 0.1 }}>
                  <Box sx={{ p: 2.5, borderRadius: 2, border: '1px solid rgba(148,163,184,0.1)', background: 'rgba(15,23,42,0.6)', textAlign: 'center' }}>
                    <Typography sx={{ fontWeight: 700, mb: 0.5, fontSize: '0.95rem' }}>{dim.name}</Typography>
                    <Typography sx={{ color: '#94a3b8', fontSize: '0.8rem' }}>{dim.desc}</Typography>
                  </Box>
                </motion.div>
              ))}
            </Box>
          </Container>
        </Box>
      )}

      {/* Pricing Plans */}
      {plans.length > 0 && (
        <Box sx={{ py: 10 }}>
          <Container maxWidth="lg">
            <motion.div {...fadeUp}>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 6, textAlign: 'center' }}>{s('pricing_plans')?.title || '标准订阅方案'}</Typography>
            </motion.div>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(5, 1fr)' }, gap: 2.5 }}>
              {plans.map((plan: any, i: number) => (
                <motion.div key={i} {...fadeUp} transition={{ duration: 0.5, delay: i * 0.08 }}>
                  <Box sx={{
                    p: 3, borderRadius: 3, height: '100%', display: 'flex', flexDirection: 'column',
                    background: plan.highlight ? 'rgba(34,211,238,0.05)' : 'rgba(15,23,42,0.6)',
                    border: plan.highlight ? '1px solid rgba(34,211,238,0.4)' : '1px solid rgba(148,163,184,0.1)',
                    backdropFilter: 'blur(16px)',
                    position: 'relative', overflow: 'hidden',
                  }}>
                    {plan.highlight && (
                      <Chip icon={<StarIcon />} label="推荐" size="small" sx={{ position: 'absolute', top: 12, right: 12, backgroundColor: 'rgba(34,211,238,0.15)', color: '#22d3ee' }} />
                    )}
                    <Typography sx={{ fontWeight: 700, fontSize: '1.1rem', mb: 0.5 }}>{plan.plan_name || plan.name}</Typography>
                    <Typography sx={{ color: '#94a3b8', fontSize: '0.8rem', mb: 2 }}>{plan.description || plan.desc}</Typography>

                    {/* Price */}
                    <Box sx={{ mb: 2 }}>
                      {plan.price_monthly && (
                        <Typography sx={{ color: '#94a3b8', fontSize: '0.75rem' }}>¥{plan.price_monthly}/月</Typography>
                      )}
                      {plan.price_yearly && (
                        <Typography sx={{ fontWeight: 800, fontSize: '1.5rem' }}>
                          ¥{plan.price_yearly}<Typography component="span" sx={{ color: '#94a3b8', fontSize: '0.8rem', fontWeight: 400 }}>/年</Typography>
                        </Typography>
                      )}
                      {plan.price_unit && (
                        <Typography sx={{ fontWeight: 700, fontSize: '1.2rem' }}>{plan.price_unit}</Typography>
                      )}
                      {plan.custom_price && (
                        <Typography sx={{ color: '#64748b', fontSize: '0.75rem', mt: 0.5 }}>{plan.custom_price}</Typography>
                      )}
                    </Box>

                    {/* Stock Pools & Frequencies */}
                    <Box sx={{ mb: 2 }}>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
                        {(plan.stock_pools || []).map((sp: string) => (
                          <Chip key={sp} label={sp} size="small" sx={{ backgroundColor: 'rgba(34,211,238,0.08)', color: '#22d3ee', fontSize: '0.7rem' }} />
                        ))}
                      </Box>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {(plan.frequencies || []).map((f: string) => (
                          <Chip key={f} label={f} size="small" variant="outlined" sx={{ borderColor: 'rgba(148,163,184,0.2)', color: '#94a3b8', fontSize: '0.7rem' }} />
                        ))}
                      </Box>
                    </Box>

                    {/* Features */}
                    <Box sx={{ flex: 1, mb: 2 }}>
                      {(plan.features || []).map((feat: string) => (
                        <Box key={feat} sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.75, mb: 0.5 }}>
                          <CheckCircleIcon sx={{ color: '#22d3ee', fontSize: 14, mt: 0.3, flexShrink: 0 }} />
                          <Typography sx={{ color: '#cbd5e1', fontSize: '0.8rem', lineHeight: 1.5 }}>{feat}</Typography>
                        </Box>
                      ))}
                    </Box>

                    {/* Buttons */}
                    <Box sx={{ mt: 'auto' }}>
                      <Button
                        variant={plan.highlight ? 'contained' : 'outlined'}
                        fullWidth
                        size="small"
                        onClick={() => isApiPlan ? navigate('/app/subscribe') : navigate('/pricing')}
                        sx={plan.highlight ? {} : { borderColor: 'rgba(148,163,184,0.25)', color: '#e2e8f0' }}
                      >
                        {(plan.buttons?.[0]) || '选择方案'}
                      </Button>
                    </Box>
                  </Box>
                </motion.div>
              ))}
            </Box>
          </Container>
        </Box>
      )}

      {/* Comparison Table */}
      {s('pricing_comparison') && (
        <Box sx={{ py: 10, backgroundColor: 'rgba(15,23,42,0.3)' }}>
          <Container maxWidth="lg">
            <motion.div {...fadeUp}>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 4, textAlign: 'center' }}>{s('pricing_comparison')?.title}</Typography>
            </motion.div>
            <motion.div {...fadeUp}>
              <TableContainer component={Paper} sx={{ background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(148,163,184,0.1)' }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      {(s('pricing_comparison')?.extra?.headers || []).map((h: string) => (
                        <TableCell key={h} sx={{ fontWeight: 700, color: '#e2e8f0', borderBottom: '1px solid rgba(148,163,184,0.15)', py: 2 }}>{h}</TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {(s('pricing_comparison')?.extra?.rows || []).map((row: string[], i: number) => (
                      <TableRow key={i}>
                        {row.map((cell, j) => (
                          <TableCell key={j} sx={{ color: j === 0 ? '#e2e8f0' : '#94a3b8', borderBottom: '1px solid rgba(148,163,184,0.08)', py: 1.5, fontSize: '0.85rem', fontWeight: j === 0 ? 600 : 400 }}>
                            {cell}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </motion.div>
          </Container>
        </Box>
      )}

      {/* Single Model Pricing Matrix */}
      {(apiMatrix.length > 0 || s('pricing_matrix')) && (
        <Box sx={{ py: 10 }}>
          <Container maxWidth="md">
            <motion.div {...fadeUp}>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 2, textAlign: 'center' }}>{s('pricing_matrix')?.title || '单模型订阅价格'}</Typography>
              <Typography sx={{ color: '#94a3b8', textAlign: 'center', mb: 3 }}>{s('pricing_matrix')?.subtitle}</Typography>
            </motion.div>
            <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
              <ToggleButtonGroup
                value={billingCycle}
                exclusive
                onChange={(_, v) => v && setBillingCycle(v)}
                size="small"
                sx={{ '& .MuiToggleButton-root': { color: '#94a3b8', borderColor: 'rgba(148,163,184,0.2)', '&.Mui-selected': { color: '#22d3ee', borderColor: 'rgba(34,211,238,0.4)', backgroundColor: 'rgba(34,211,238,0.08)' } } }}
              >
                <ToggleButton value="yearly">{t.pricing.yearly}</ToggleButton>
                <ToggleButton value="monthly">{t.pricing.monthly}</ToggleButton>
              </ToggleButtonGroup>
            </Box>
            <motion.div {...fadeUp}>
              <TableContainer component={Paper} sx={{ background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(148,163,184,0.1)' }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 700, color: '#e2e8f0' }}>股票池 \ 频率</TableCell>
                      {matrixFrequencies.map((f: string) => (
                        <TableCell key={f} align="center" sx={{ fontWeight: 700, color: '#e2e8f0' }}>{f}</TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {matrixPools.map((pool: string, i: number) => (
                      <TableRow key={pool}>
                        <TableCell sx={{ fontWeight: 600, color: '#e2e8f0' }}>{pool}</TableCell>
                        {(matrixPrices[i] || []).map((price: number, j: number) => (
                          <TableCell key={j} align="center" sx={{ color: '#22d3ee', fontWeight: 600 }}>¥{price}</TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </motion.div>
            {(apiMatrixForCycle?.note || s('pricing_matrix')?.extra?.note) && (
              <Typography sx={{ color: '#64748b', fontSize: '0.8rem', mt: 2, textAlign: 'center' }}>{apiMatrixForCycle?.note || s('pricing_matrix')?.extra?.note}</Typography>
            )}
          </Container>
        </Box>
      )}

      {/* Upgrade Packages */}
      {upgradePkgs.length > 0 && (
        <Box sx={{ py: 10, backgroundColor: 'rgba(15,23,42,0.3)' }}>
          <Container maxWidth="lg">
            <motion.div {...fadeUp}>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 6, textAlign: 'center' }}>{s('upgrade_packages')?.title || '可选升级项'}</Typography>
            </motion.div>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(4, 1fr)' }, gap: 3 }}>
              {upgradePkgs.map((pkg: any, i: number) => (
                <motion.div key={i} {...fadeUp} transition={{ duration: 0.5, delay: i * 0.1 }}>
                  <Box sx={{
                    p: 3, borderRadius: 3,
                    background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(148,163,184,0.1)',
                    backdropFilter: 'blur(16px)', height: '100%',
                  }}>
                    <Typography sx={{ fontWeight: 700, mb: 1 }}>{pkg.name}</Typography>
                    <Typography sx={{ color: '#94a3b8', fontSize: '0.85rem', mb: 2, lineHeight: 1.7 }}>{pkg.description || pkg.desc}</Typography>
                    <Box sx={{ mt: 'auto' }}>
                      {pkg.price_monthly && <Typography sx={{ color: '#22d3ee', fontWeight: 600, fontSize: '0.9rem' }}>¥{pkg.price_monthly}/月</Typography>}
                      {pkg.price_yearly && <Typography sx={{ color: '#22d3ee', fontWeight: 600, fontSize: '0.9rem' }}>¥{pkg.price_yearly}/年</Typography>}
                      {pkg.price_standard && <Typography sx={{ color: '#22d3ee', fontWeight: 600, fontSize: '0.9rem' }}>标准: {pkg.price_standard}</Typography>}
                      {pkg.price_advanced && <Typography sx={{ color: '#22d3ee', fontWeight: 600, fontSize: '0.9rem' }}>增强: {pkg.price_advanced}</Typography>}
                      {pkg.price_unit && <Typography sx={{ color: '#22d3ee', fontWeight: 600, fontSize: '0.9rem' }}>{pkg.price_unit}</Typography>}
                    </Box>
                  </Box>
                </motion.div>
              ))}
            </Box>
          </Container>
        </Box>
      )}

      {/* Combo Discounts */}
      {s('combo_discounts') && (
        <Box sx={{ py: 8 }}>
          <Container maxWidth="sm">
            <motion.div {...fadeUp}>
              <Typography variant="h5" sx={{ fontWeight: 700, mb: 3, textAlign: 'center' }}>{s('combo_discounts')?.title}</Typography>
              {(s('combo_discounts')?.extra?.rules || []).map((rule: any) => (
                <Box key={rule.desc} sx={{ display: 'flex', justifyContent: 'space-between', py: 1, borderBottom: '1px solid rgba(148,163,184,0.08)' }}>
                  <Typography sx={{ color: '#94a3b8', fontSize: '0.9rem' }}>{rule.desc}</Typography>
                  <Chip label={rule.discount} size="small" sx={{ backgroundColor: 'rgba(34,211,238,0.1)', color: '#22d3ee' }} />
                </Box>
              ))}
              {s('combo_discounts')?.extra?.same_pool_rules && (
                <>
                  <Typography sx={{ color: '#64748b', fontSize: '0.8rem', mt: 2, mb: 1 }}>{t.pricing.samePool}</Typography>
                  {s('combo_discounts')?.extra?.same_pool_rules.map((rule: any) => (
                    <Box key={rule.desc} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                      <Typography sx={{ color: '#94a3b8', fontSize: '0.85rem' }}>{rule.desc}</Typography>
                      <Chip label={rule.discount} size="small" sx={{ backgroundColor: 'rgba(34,211,238,0.1)', color: '#22d3ee' }} />
                    </Box>
                  ))}
                </>
              )}
              {s('combo_discounts')?.extra?.same_freq_rules && (
                <>
                  <Typography sx={{ color: '#64748b', fontSize: '0.8rem', mt: 2, mb: 1 }}>{t.pricing.sameFreq}</Typography>
                  {s('combo_discounts')?.extra?.same_freq_rules.map((rule: any) => (
                    <Box key={rule.desc} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                      <Typography sx={{ color: '#94a3b8', fontSize: '0.85rem' }}>{rule.desc}</Typography>
                      <Chip label={rule.discount} size="small" sx={{ backgroundColor: 'rgba(34,211,238,0.1)', color: '#22d3ee' }} />
                    </Box>
                  ))}
                </>
              )}
            </motion.div>
          </Container>
        </Box>
      )}

      {/* Audience Selector */}
      {s('audience_selector') && (
        <Box sx={{ py: 10, backgroundColor: 'rgba(15,23,42,0.3)' }}>
          <Container maxWidth="md">
            <motion.div {...fadeUp}>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 6, textAlign: 'center' }}>{s('audience_selector')?.title}</Typography>
            </motion.div>
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)' }, gap: 3 }}>
              {(s('audience_selector')?.extra?.options || []).map((opt: any, i: number) => (
                <motion.div key={i} {...fadeUp} transition={{ duration: 0.5, delay: i * 0.1 }}>
                  <Box sx={{
                    p: 3, borderRadius: 3,
                    background: 'rgba(15,23,42,0.6)', border: '1px solid rgba(148,163,184,0.1)',
                    backdropFilter: 'blur(16px)',
                  }}>
                    <Typography sx={{ color: '#64748b', fontSize: '0.8rem', mb: 0.5 }}>{opt.audience}</Typography>
                    <Typography sx={{ fontWeight: 700, color: '#22d3ee', mb: 1 }}>{opt.recommendation}</Typography>
                    <Typography sx={{ color: '#94a3b8', fontSize: '0.85rem', lineHeight: 1.7 }}>{opt.reason}</Typography>
                  </Box>
                </motion.div>
              ))}
            </Box>
          </Container>
        </Box>
      )}

      {/* FAQ */}
      {s('faq') && (
        <Box sx={{ py: 10 }}>
          <Container maxWidth="md">
            <motion.div {...fadeUp}>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 6, textAlign: 'center' }}>{s('faq')?.title}</Typography>
            </motion.div>
            {(s('faq')?.extra?.items || []).map((item: any, i: number) => (
              <motion.div key={i} {...fadeUp} transition={{ duration: 0.4, delay: i * 0.05 }}>
                <Accordion sx={{
                  backgroundColor: 'rgba(15,23,42,0.6)', border: '1px solid rgba(148,163,184,0.1)',
                  '&:before': { display: 'none' }, mb: 1,
                }}>
                  <AccordionSummary expandIcon={<ExpandMoreIcon sx={{ color: '#94a3b8' }} />}>
                    <Typography sx={{ fontWeight: 600, fontSize: '0.9rem' }}>{item.q}</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Typography sx={{ color: '#94a3b8', fontSize: '0.85rem', lineHeight: 1.8 }}>{item.a}</Typography>
                  </AccordionDetails>
                </Accordion>
              </motion.div>
            ))}
          </Container>
        </Box>
      )}

      {/* Risk Disclaimer */}
      {s('risk_disclaimer') && (
        <Box sx={{ py: 6, backgroundColor: 'rgba(15,23,42,0.3)' }}>
          <Container maxWidth="sm">
            <Typography sx={{ fontWeight: 600, fontSize: '0.9rem', mb: 1, textAlign: 'center' }}>{s('risk_disclaimer')?.title}</Typography>
            <Typography sx={{ color: '#64748b', fontSize: '0.8rem', lineHeight: 1.8, textAlign: 'center' }}>{s('risk_disclaimer')?.body}</Typography>
          </Container>
        </Box>
      )}

      {/* CTA */}
      {s('cta') && (
        <Box sx={{ py: 12, position: 'relative', overflow: 'hidden' }}>
          <Box sx={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 50% 100%, rgba(139,92,246,0.08) 0%, transparent 60%)' }} />
          <Container maxWidth="sm" sx={{ position: 'relative', textAlign: 'center' }}>
            <motion.div {...fadeUp}>
              <Typography variant="h4" sx={{ fontWeight: 700, mb: 2 }}>{s('cta')?.title}</Typography>
              <Typography sx={{ color: '#94a3b8', mb: 4, lineHeight: 1.8 }}>{s('cta')?.subtitle}</Typography>
              <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
                <Button variant="contained" size="large" onClick={() => navigate('/app/subscribe')}>{t.btn.trial}</Button>
                <Button variant="outlined" size="large" onClick={() => navigate('/about')}>{t.btn.contactSales}</Button>
                <Button size="large" sx={{ color: '#94a3b8' }} onClick={() => navigate('/about')}>{t.btn.getQuote}</Button>
              </Box>
            </motion.div>
          </Container>
        </Box>
      )}
    </Box>
  );
}
