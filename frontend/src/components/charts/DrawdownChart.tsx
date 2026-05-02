import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';

interface DrawdownChartProps {
  data: Array<{
    date: string;
    drawdown: number;
  }>;
  height?: number;
  title?: string;
}

const DrawdownChart: React.FC<DrawdownChartProps> = ({ data, height = 250, title }) => {
  const option = useMemo(() => {
    const dates = data.map(d => d.date);
    const drawdownValues = data.map(d => d.drawdown);

    return {
      title: title ? {
        text: title,
        left: 0,
        textStyle: {
          fontSize: 16,
          fontWeight: 'normal',
        },
      } : undefined,
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const value = typeof params[0].value === 'number'
            ? `${(params[0].value * 100).toFixed(2)}%`
            : '';
          return `日期: ${params[0].axisValue}<br/>${params[0].marker}回撤: ${value}`;
        },
      },
      grid: {
        left: 60,
        right: 30,
        top: title ? 50 : 20,
        bottom: 50,
      },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: {
          fontSize: 12,
        },
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          fontSize: 12,
          formatter: (v: number) => `${(v * 100).toFixed(1)}%`,
        },
      },
      series: [
        {
          name: '回撤',
          type: 'line',
          data: drawdownValues,
          smooth: false,
          symbol: 'none',
          lineStyle: {
            color: '#ff4d4f',
          },
          areaStyle: {
            color: '#ff4d4f',
            opacity: 0.3,
          },
        },
      ],
    };
  }, [data, title]);

  return <ReactECharts option={option} style={{ height }} />;
};

export default DrawdownChart;
