import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

interface FactorICChartProps {
  data: Array<{
    date: string;
    ic: number;
    rank_ic?: number;
  }>;
  height?: number;
  title?: string;
}

const FactorICChart: React.FC<FactorICChartProps> = ({ data, height = 300, title }) => (
  <div>
    {title && <h4 style={{ marginBottom: 8 }}>{title}</h4>}
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip
          formatter={(value: number) => value.toFixed(4)}
          labelFormatter={(label) => `日期: ${label}`}
        />
        <ReferenceLine y={0} stroke="#999" />
        <ReferenceLine y={0.03} stroke="#52c41a" strokeDasharray="3 3" label="有效阈值" />
        <Bar dataKey="ic" fill="#1890ff" name="IC" />
        {data[0]?.rank_ic !== undefined && <Bar dataKey="rank_ic" fill="#722ed1" name="Rank IC" />}
      </BarChart>
    </ResponsiveContainer>
  </div>
);

export default FactorICChart;
