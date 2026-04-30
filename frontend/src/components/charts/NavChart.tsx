import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

interface NavChartProps {
  data: Array<{
    date: string;
    nav: number;
    benchmark?: number;
  }>;
  height?: number;
  title?: string;
}

const NavChart: React.FC<NavChartProps> = ({ data, height = 400, title }) => (
  <div>
    {title && <h4 style={{ marginBottom: 8 }}>{title}</h4>}
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} domain={['auto', 'auto']} />
        <Tooltip
          formatter={(value: number) => value.toFixed(4)}
          labelFormatter={(label) => `日期: ${label}`}
        />
        <Legend />
        <ReferenceLine y={1} stroke="#999" strokeDasharray="3 3" />
        <Line
          type="monotone"
          dataKey="nav"
          stroke="#1890ff"
          strokeWidth={2}
          dot={false}
          name="策略净值"
        />
        {data[0]?.benchmark !== undefined && (
          <Line
            type="monotone"
            dataKey="benchmark"
            stroke="#52c41a"
            strokeWidth={1.5}
            dot={false}
            name="基准净值"
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  </div>
);

export default NavChart;
