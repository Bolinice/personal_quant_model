import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';

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
}) => {
  const option = useMemo(() => {
    const pieData = data.map((item, index) => ({
      name: item.name,
      value: item.value,
      itemStyle: {
        color: COLORS[index % COLORS.length],
      },
    }));

    return {
      title: title ? {
        text: title,
        left: 'center',
        textStyle: {
          fontSize: 16,
          fontWeight: 'normal',
        },
      } : undefined,
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          const value = typeof params.value === 'number' ? (params.value * 100).toFixed(2) : '0.00';
          return `${params.marker}${params.name}: ${value}%`;
        },
      },
      legend: {
        orient: 'vertical',
        left: 'left',
        top: title ? 40 : 20,
      },
      series: [
        {
          type: 'pie',
          radius: '60%',
          center: ['50%', '55%'],
          data: pieData,
          label: {
            formatter: (params: any) => {
              const percent = typeof params.percent === 'number' ? params.percent.toFixed(1) : '0.0';
              return `${params.name}: ${percent}%`;
            },
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        },
      ],
    };
  }, [data, title]);

  return <ReactECharts option={option} style={{ height }} />;
};

export default PortfolioWeightChart;
