import { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Grid,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  MenuItem,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  TablePagination,
} from '@mui/material';
import { eventsApi } from '@/api';
import type { Event, RiskFlag } from '@/api';
import { PageHeader, GlassPanel, GlassTable, NeonChip } from '@/components/ui';

const eventTypes = [
  { value: '', label: '全部类型' },
  { value: 'risk', label: '风险事件' },
  { value: 'corporate', label: '公司事件' },
  { value: 'market', label: '市场事件' },
  { value: 'regulatory', label: '监管事件' },
];
const severityMap: Record<string, 'red' | 'amber' | 'default'> = {
  critical: 'red',
  high: 'red',
  medium: 'amber',
  low: 'default',
  info: 'default',
};
const severityLabel: Record<string, string> = {
  critical: '严重',
  high: '高',
  medium: '中',
  low: '低',
  info: '信息',
};

export default function EventList() {
  const [events, setEvents] = useState<Event[]>([]);
  const [riskFlags, setRiskFlags] = useState<RiskFlag[]>([]);
  const [tab, setTab] = useState<'events' | 'risk'>('events');
  const [loading, setLoading] = useState(true);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  // Filters
  const [filterType, setFilterType] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('');
  const [filterDate, setFilterDate] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(20);

  const handleChangePage = (_: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [eventsRes, flagsRes] = await Promise.all([
        eventsApi.getEvents({ page_size: 100 }).catch(() => ({ data: [] })),
        eventsApi.getRiskFlags(new Date().toISOString().slice(0, 10)).catch(() => ({ data: [] })),
      ]);
      setEvents(eventsRes.data);
      setRiskFlags(flagsRes.data);
    } finally {
      setLoading(false);
    }
  };

  const filteredEvents = events.filter((e) => {
    if (filterType && e.event_type !== filterType) return false;
    if (filterSeverity && e.severity !== filterSeverity) return false;
    if (filterDate && !e.event_date.startsWith(filterDate)) return false;
    return true;
  });

  const pagedEvents = filteredEvents.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);

  const handleViewDetail = (event: Event) => {
    setSelectedEvent(event);
    setDialogOpen(true);
  };

  if (loading) return <Typography>加载中...</Typography>;

  return (
    <Box>
      <PageHeader title="事件中心" />

      {/* Tab switch */}
      <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
        <Button
          variant={tab === 'events' ? 'contained' : 'outlined'}
          size="small"
          onClick={() => setTab('events')}
        >
          事件列表
        </Button>
        <Button
          variant={tab === 'risk' ? 'contained' : 'outlined'}
          size="small"
          onClick={() => setTab('risk')}
        >
          风险标签
        </Button>
      </Box>

      {tab === 'events' && (
        <>
          {/* Filters */}
          <GlassPanel animate={false} sx={{ mb: 2, p: 2 }}>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <TextField
                select
                size="small"
                label="事件类型"
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                sx={{ minWidth: 120 }}
              >
                {eventTypes.map((t) => (
                  <MenuItem key={t.value} value={t.value}>
                    {t.label}
                  </MenuItem>
                ))}
              </TextField>
              <TextField
                select
                size="small"
                label="严重程度"
                value={filterSeverity}
                onChange={(e) => setFilterSeverity(e.target.value)}
                sx={{ minWidth: 100 }}
              >
                <MenuItem value="">全部</MenuItem>
                <MenuItem value="critical">严重</MenuItem>
                <MenuItem value="high">高</MenuItem>
                <MenuItem value="medium">中</MenuItem>
                <MenuItem value="low">低</MenuItem>
              </TextField>
              <TextField
                size="small"
                type="date"
                label="日期"
                value={filterDate}
                onChange={(e) => setFilterDate(e.target.value)}
                sx={{ minWidth: 140 }}
                slotProps={{ inputLabel: { shrink: true } }}
              />
            </Box>
          </GlassPanel>

          {/* Event table */}
          <GlassPanel animate={false}>
            <GlassTable>
              <TableHead>
                <TableRow>
                  <TableCell>日期</TableCell>
                  <TableCell>类型</TableCell>
                  <TableCell>子类型</TableCell>
                  <TableCell>严重程度</TableCell>
                  <TableCell>评分</TableCell>
                  <TableCell>标题</TableCell>
                  <TableCell>来源</TableCell>
                  <TableCell>操作</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {pagedEvents.map((e) => (
                  <TableRow key={e.id} hover>
                    <TableCell>{e.event_date}</TableCell>
                    <TableCell>{e.event_type}</TableCell>
                    <TableCell>{e.event_subtype || '-'}</TableCell>
                    <TableCell>
                      <NeonChip
                        label={severityLabel[e.severity || ''] || e.severity || '-'}
                        size="small"
                        neonColor={severityMap[e.severity || ''] || 'default'}
                      />
                    </TableCell>
                    <TableCell>{e.score != null ? e.score.toFixed(2) : '-'}</TableCell>
                    <TableCell
                      sx={{
                        maxWidth: 200,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {e.title || '-'}
                    </TableCell>
                    <TableCell>{e.source || '-'}</TableCell>
                    <TableCell>
                      <Button size="small" onClick={() => handleViewDetail(e)}>
                        详情
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {pagedEvents.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8} align="center">
                      暂无事件数据
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </GlassTable>
            <TablePagination
              component="div"
              count={filteredEvents.length}
              page={page}
              onPageChange={handleChangePage}
              rowsPerPage={rowsPerPage}
              onRowsPerPageChange={handleChangeRowsPerPage}
              rowsPerPageOptions={[10, 20, 50, 100]}
              labelRowsPerPage="每页行数:"
              labelDisplayedRows={({ from, to, count }) => `${from}-${to} / ${count}`}
            />
          </GlassPanel>
        </>
      )}

      {tab === 'risk' && (
        <GlassPanel animate={false}>
          <GlassTable>
            <TableHead>
              <TableRow>
                <TableCell>日期</TableCell>
                <TableCell>股票ID</TableCell>
                <TableCell>黑名单</TableCell>
                <TableCell>审计问题</TableCell>
                <TableCell>违规</TableCell>
                <TableCell>高质押</TableCell>
                <TableCell>高商誉</TableCell>
                <TableCell>业绩预警</TableCell>
                <TableCell>减持</TableCell>
                <TableCell>现金流风险</TableCell>
                <TableCell>风险惩罚分</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {riskFlags.map((r, i) => (
                <TableRow key={i} hover>
                  <TableCell>{r.trade_date}</TableCell>
                  <TableCell>{r.stock_id}</TableCell>
                  <TableCell>
                    <NeonChip
                      label={r.blacklist_flag ? '是' : '否'}
                      size="small"
                      neonColor={r.blacklist_flag ? 'red' : 'green'}
                    />
                  </TableCell>
                  <TableCell>
                    <NeonChip
                      label={r.audit_issue_flag ? '是' : '否'}
                      size="small"
                      neonColor={r.audit_issue_flag ? 'red' : 'green'}
                    />
                  </TableCell>
                  <TableCell>
                    <NeonChip
                      label={r.violation_flag ? '是' : '否'}
                      size="small"
                      neonColor={r.violation_flag ? 'red' : 'green'}
                    />
                  </TableCell>
                  <TableCell>
                    <NeonChip
                      label={r.pledge_high_flag ? '是' : '否'}
                      size="small"
                      neonColor={r.pledge_high_flag ? 'amber' : 'green'}
                    />
                  </TableCell>
                  <TableCell>
                    <NeonChip
                      label={r.goodwill_high_flag ? '是' : '否'}
                      size="small"
                      neonColor={r.goodwill_high_flag ? 'amber' : 'green'}
                    />
                  </TableCell>
                  <TableCell>
                    <NeonChip
                      label={r.earnings_warning_flag ? '是' : '否'}
                      size="small"
                      neonColor={r.earnings_warning_flag ? 'amber' : 'green'}
                    />
                  </TableCell>
                  <TableCell>
                    <NeonChip
                      label={r.reduction_flag ? '是' : '否'}
                      size="small"
                      neonColor={r.reduction_flag ? 'amber' : 'green'}
                    />
                  </TableCell>
                  <TableCell>
                    <NeonChip
                      label={r.cashflow_risk_flag ? '是' : '否'}
                      size="small"
                      neonColor={r.cashflow_risk_flag ? 'red' : 'green'}
                    />
                  </TableCell>
                  <TableCell sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                    {r.risk_penalty_score?.toFixed(2) ?? '-'}
                  </TableCell>
                </TableRow>
              ))}
              {riskFlags.length === 0 && (
                <TableRow>
                  <TableCell colSpan={11} align="center">
                    暂无风险标签数据
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </GlassTable>
        </GlassPanel>
      )}

      {/* Event detail dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>事件详情</DialogTitle>
        <DialogContent>
          {selectedEvent && (
            <Box sx={{ pt: 1 }}>
              <Typography variant="subtitle2" sx={{ color: '#64748b' }}>
                标题
              </Typography>
              <Typography sx={{ mb: 1 }}>{selectedEvent.title || '-'}</Typography>
              <Typography variant="subtitle2" sx={{ color: '#64748b' }}>
                类型
              </Typography>
              <Typography sx={{ mb: 1 }}>
                {selectedEvent.event_type} / {selectedEvent.event_subtype || '-'}
              </Typography>
              <Typography variant="subtitle2" sx={{ color: '#64748b' }}>
                日期
              </Typography>
              <Typography sx={{ mb: 1 }}>{selectedEvent.event_date}</Typography>
              <Typography variant="subtitle2" sx={{ color: '#64748b' }}>
                严重程度
              </Typography>
              <Typography sx={{ mb: 1 }}>
                {severityLabel[selectedEvent.severity || ''] || selectedEvent.severity}
              </Typography>
              <Typography variant="subtitle2" sx={{ color: '#64748b' }}>
                评分
              </Typography>
              <Typography sx={{ mb: 1 }}>{selectedEvent.score ?? '-'}</Typography>
              <Typography variant="subtitle2" sx={{ color: '#64748b' }}>
                内容
              </Typography>
              <Typography sx={{ mb: 1, whiteSpace: 'pre-wrap' }}>
                {selectedEvent.content || '-'}
              </Typography>
              <Typography variant="subtitle2" sx={{ color: '#64748b' }}>
                来源
              </Typography>
              <Typography>{selectedEvent.source || '-'}</Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>关闭</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
