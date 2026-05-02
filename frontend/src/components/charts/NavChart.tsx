import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';

interface NavChartProps {
  data: Array<{
    date: string;
    nav: number;
    benchmark?: number;
  }>;
  height?: number;
  title?: string;
}

const NavChart: React.FC<NavChartProps> = ({ data, height = 400, title }) => {
  const option = useMemo(() => {
    const dates = data.map(d => d.date);
    const navValues = data.map(d => d.nav);
    const hasBenchmark = data[0]?.benchmark !== undefined;
    const benchmarkValues = hasBenchmark ? data.map(d => d.benchmark) : [];

    const series: any[] = [
      {
        name: '策略净值',
        type: 'line',
        data: navValues,
        smooth: false,
        symbol: 'none',
        lineStyle: {
          color: '#1890ff',
          width: 2,
        },
      },
    ];

    if (hasBenchmark) {
      series.push({
        name: '基准净值',
        type: 'line',
        data: benchmarkValues,
        smooth: false,
        symbol: 'none',
        lineStyle: {
          color: '#52c41a',
          width: 1.5,
        },
      });
    }

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
          let result = `日期: ${params[0].axisValue}<br/>`;
          params.forEach((param: any) => {
            const value = typeof param.value === 'number' ? param.value.toFixed(4) : '';
            result += `${param.marker}${param.seriesName}: ${value}<br/>`;
          });
          return result;
        },
      },
      legend: {
        data: hasBenchmark ? ['策略净值', '基准净值'] : ['策略净值'],
        top: title ? 30 : 0,
      },
      grid: {
        left: 60,
        right: 30,
        top: title ? 60 : 40,
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
        },
      },
      series,
      // Reference line at y=1
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: {
          color: '#999',
          type: 'dashed',
        },
        data: [{ yAxis: 1 }],
      },
    };
  }, [data, title]);

  return <ReactECharts option={option} style={{ height }} />;
};

export default NavChart;
