import React, { useMemo } from 'react';
import ReactECharts from './ReactEChartsCore';

interface FactorICChartProps {
  data: Array<{
    date: string;
    ic: number;
    rank_ic?: number;
  }>;
  height?: number;
  title?: string;
}

const FactorICChart: React.FC<FactorICChartProps> = ({ data, height = 300, title }) => {
  const option = useMemo(() => {
    const dates = data.map(d => d.date);
    const icValues = data.map(d => d.ic);
    const hasRankIC = data[0]?.rank_ic !== undefined;
    const rankICValues = hasRankIC ? data.map(d => d.rank_ic) : [];

    const series: any[] = [
      {
        name: 'IC',
        type: 'bar' as const,
        data: icValues,
        itemStyle: {
          color: '#1890ff',
        },
      },
    ];

    if (hasRankIC) {
      series.push({
        name: 'Rank IC',
        type: 'bar' as const,
        data: rankICValues,
        itemStyle: {
          color: '#722ed1',
        },
      });
    }

    return {
      title: title ? {
        text: title,
        left: 0,
        textStyle: {
          fontSize: 16,
          fontWeight: 'normal' as const,
        },
      } : undefined,
      tooltip: {
        trigger: 'axis' as const,
        formatter: (params: any) => {
          let result = `日期: ${params[0].axisValue}<br/>`;
          params.forEach((param: any) => {
            const value = typeof param.value === 'number' ? param.value.toFixed(4) : '';
            result += `${param.marker}${param.seriesName}: ${value}<br/>`;
          });
          return result;
        },
      },
      legend: {
        data: hasRankIC ? ['IC', 'Rank IC'] : ['IC'],
        top: title ? 30 : 0,
      },
      grid: {
        left: 60,
        right: 30,
        top: title ? 60 : 40,
        bottom: 50,
      },
      xAxis: {
        type: 'category' as const,
        data: dates,
        axisLabel: {
          fontSize: 12,
        },
      },
      yAxis: {
        type: 'value' as const,
        axisLabel: {
          fontSize: 12,
        },
      },
      series,
      // Reference lines
      markLine: {
        silent: true,
        symbol: 'none',
        data: [
          {
            yAxis: 0,
            lineStyle: {
              color: '#999',
              type: 'solid',
            },
          },
          {
            yAxis: 0.03,
            lineStyle: {
              color: '#52c41a',
              type: 'dashed',
            },
            label: {
              show: true,
              position: 'end',
              formatter: '有效阈值',
            },
          },
        ],
      },
    };
  }, [data, title]);

  return <ReactECharts option={option} style={{ height }} />;
};

export default FactorICChart;
