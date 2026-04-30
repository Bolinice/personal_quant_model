import React from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';

interface PortfolioWeightChartProps {
  data: Array<{
    name: string;
    value: number;
  }>;
  height?: number;
  title?: string;
}

const COLORS = [
  '#1890ff',
  '#52c41a',
  '#faad14',
  '#722ed1',
  '#eb2f96',
  '#13c2c2',
  '#2f54eb',
  '#f5222d',
  '#a0d911',
  '#fa541c',
];

const PortfolioWeightChart: React.FC<PortfolioWeightChartProps> = ({
  data,
  height = 350,
  title,
}) => (
  <div>
    {title && <h4 style={{ marginBottom: 8 }}>{title}</h4>}
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx="50%"
          cy="50%"
          outerRadius={120}
          label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(1)}%`}
          labelLine
        >
          {data.map((_, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(value: number) => `${(value * 100).toFixed(2)}%`} />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  </div>
);

export default PortfolioWeightChart;
