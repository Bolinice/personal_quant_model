import { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormControl,
  Button,
  Alert,
  LinearProgress,
} from '@mui/material';
import { PageHeader, GlassPanel } from '@/components/ui';
import client from '@/api/client';

interface Question {
  id: number;
  question: string;
  options: string[];
  scores: number[];
}

interface AssessmentResult {
  score: number;
  level: string;
  level_name: string;
  description: string;
}

const levelColors: Record<string, string> = {
  C1: '#64748b',
  C2: '#22d3ee',
  C3: '#f59e0b',
  C4: '#f43f5e',
};

export default function RiskAssessment() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [existingResult, setExistingResult] = useState<AssessmentResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      client.get('/risk-assessment/questions').then((res) => setQuestions(res.data || [])),
      client.get('/risk-assessment/latest').then((res) => {
        if (res.data) setExistingResult(res.data);
      }),
    ]).finally(() => setLoading(false));
  }, []);

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const answerList = Object.entries(answers).map(([qid, ans]) => ({
        question_id: Number(qid),
        answer: ans,
      }));
      const res = await client.post('/risk-assessment/submit', { answers: answerList });
      setResult(res.data);
      setExistingResult(res.data);
    } catch (e: any) {
      console.error('提交失败:', e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const allAnswered = questions.length > 0 && Object.keys(answers).length === questions.length;

  if (loading) return <Typography>加载中...</Typography>;

  return (
    <Box>
      <PageHeader title="风险测评" />

      {existingResult && !result && (
        <GlassPanel sx={{ mb: 3, p: 3 }}>
          <Typography sx={{ fontWeight: 600, mb: 1 }}>您当前的风险等级</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
            <Typography
              sx={{
                fontWeight: 800,
                fontSize: '1.5rem',
                color: levelColors[existingResult.level] || '#22d3ee',
              }}
            >
              {existingResult.level_name}
            </Typography>
            <Typography sx={{ color: '#64748b' }}>
              ({existingResult.level}) · 得分 {existingResult.score}
            </Typography>
          </Box>
          <Typography sx={{ color: '#94a3b8', fontSize: '0.85rem', lineHeight: 1.8 }}>
            {existingResult.description}
          </Typography>
          <Button variant="outlined" sx={{ mt: 2 }} onClick={() => setExistingResult(null)}>
            重新测评
          </Button>
        </GlassPanel>
      )}

      {(!existingResult || result) && questions.length > 0 && (
        <>
          {questions.map((q, i) => (
            <GlassPanel key={q.id} sx={{ mb: 2, p: 3 }}>
              <Typography sx={{ fontWeight: 600, mb: 2 }}>
                {i + 1}. {q.question}
              </Typography>
              <FormControl>
                <RadioGroup
                  value={answers[q.id] ?? ''}
                  onChange={(e) => setAnswers({ ...answers, [q.id]: Number(e.target.value) })}
                >
                  {q.options.map((opt, j) => (
                    <FormControlLabel
                      key={j}
                      value={j}
                      control={
                        <Radio
                          size="small"
                          sx={{ color: '#94a3b8', '&.Mui-checked': { color: '#22d3ee' } }}
                        />
                      }
                      label={
                        <Typography sx={{ color: '#e2e8f0', fontSize: '0.85rem' }}>
                          {opt}
                        </Typography>
                      }
                    />
                  ))}
                </RadioGroup>
              </FormControl>
            </GlassPanel>
          ))}

          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
            <Button
              variant="contained"
              size="large"
              disabled={!allAnswered || submitting}
              onClick={handleSubmit}
              sx={{
                py: 1.5,
                borderRadius: 2,
                fontWeight: 700,
                background: 'linear-gradient(135deg, #22d3ee, #8b5cf6)',
                '&:hover': { background: 'linear-gradient(135deg, #06b6d4, #7c3aed)' },
              }}
            >
              {submitting ? '提交中...' : '提交测评'}
            </Button>
          </Box>

          {!allAnswered && Object.keys(answers).length > 0 && (
            <Box sx={{ mt: 2 }}>
              <LinearProgress
                variant="determinate"
                value={(Object.keys(answers).length / questions.length) * 100}
                sx={{
                  height: 6,
                  borderRadius: 3,
                  backgroundColor: 'rgba(148,163,184,0.1)',
                  '& .MuiLinearProgress-bar': { backgroundColor: '#22d3ee', borderRadius: 3 },
                }}
              />
              <Typography
                sx={{ color: '#64748b', fontSize: '0.75rem', mt: 0.5, textAlign: 'center' }}
              >
                已完成 {Object.keys(answers).length}/{questions.length} 题
              </Typography>
            </Box>
          )}
        </>
      )}

      {result && (
        <GlassPanel sx={{ mt: 3, p: 4 }}>
          <Typography
            sx={{
              fontWeight: 800,
              fontSize: '1.5rem',
              mb: 1,
              color: levelColors[result.level] || '#22d3ee',
            }}
          >
            {result.level_name} ({result.level})
          </Typography>
          <Typography sx={{ color: '#94a3b8', fontSize: '0.85rem', lineHeight: 1.8, mb: 2 }}>
            {result.description}
          </Typography>
          <Typography sx={{ color: '#64748b', fontSize: '0.8rem' }}>
            测评得分: {result.score}/20
          </Typography>
        </GlassPanel>
      )}
    </Box>
  );
}
