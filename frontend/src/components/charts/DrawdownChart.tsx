import React from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface DrawdownChartProps {
  data: Array<{
    date: string;
    drawdown: number;
  }>;
  height?: number;
  title?: string;
}

const DrawdownChart: React.FC<DrawdownChartProps> = ({ data, height = 250, title }) => (
  <div>
    {title && <h4 style={{ marginBottom: 8 }}>{title}</h4>}
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
        <YAxis
          tick={{ fontSize: 12 }}
          tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`}
        />
        <Tooltip
          formatter={(value: number) => `${(value * 100).toFixed(2)}%`}
          labelFormatter={(label) => `日期: ${label}`}
        />
        <Area
          type="monotone"
          dataKey="drawdown"
          stroke="#ff4d4f"
          fill="#ff4d4f"
          fillOpacity={0.3}
          name="回撤"
        />
      </AreaChart>
    </ResponsiveContainer>
  </div>
);

export default DrawdownChart;
