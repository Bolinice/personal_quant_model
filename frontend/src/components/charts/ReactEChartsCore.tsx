/**
 * 自定义ReactECharts组件，使用按需引入的ECharts核心
 * 替代echarts-for-react以减少打包体积
 */

import React, { useEffect, useRef } from 'react';
import type { EChartsOption } from 'echarts';
import * as echarts from 'echarts/core';
import type { EChartsType } from 'echarts/core';

interface ReactEChartsProps {
  option: EChartsOption;
  style?: React.CSSProperties;
  opts?: {
    renderer?: 'canvas' | 'svg';
    width?: number | string;
    height?: number | string;
  };
  onEvents?: Record<string, (params: any) => void>;
  notMerge?: boolean;
  lazyUpdate?: boolean;
}

const ReactEChartsCore: React.FC<ReactEChartsProps> = ({
  option,
  style,
  opts,
  onEvents,
  notMerge = false,
  lazyUpdate = false,
}) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<EChartsType | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;

    // 初始化图表实例
    if (!instanceRef.current) {
      instanceRef.current = echarts.init(chartRef.current, undefined, opts);
    }

    // 设置配置项
    instanceRef.current.setOption(option, notMerge, lazyUpdate);

    // 绑定事件
    if (onEvents) {
      Object.entries(onEvents).forEach(([eventName, handler]) => {
        instanceRef.current?.on(eventName, handler);
      });
    }

    // 响应式调整大小
    const handleResize = () => {
      instanceRef.current?.resize();
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);

      // 解绑事件
      if (onEvents && instanceRef.current) {
        Object.keys(onEvents).forEach((eventName) => {
          instanceRef.current?.off(eventName);
        });
      }
    };
  }, [option, opts, onEvents, notMerge, lazyUpdate]);

  // 组件卸载时销毁实例
  useEffect(() => {
    return () => {
      instanceRef.current?.dispose();
      instanceRef.current = null;
    };
  }, []);

  return <div ref={chartRef} style={{ width: '100%', height: '400px', ...style }} />;
};

export default ReactEChartsCore;
