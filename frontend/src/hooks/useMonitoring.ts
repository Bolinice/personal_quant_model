import { useEffect } from 'react';

/**
 * 页面性能监控 Hook
 */
export function usePagePerformance(pageName: string) {
  useEffect(() => {
    // 记录页面加载时间
    const navigationTiming = performance.getEntriesByType(
      'navigation'
    )[0] as PerformanceNavigationTiming;

    if (navigationTiming) {
      const loadTime = navigationTiming.loadEventEnd - navigationTiming.fetchStart;
      const domContentLoaded =
        navigationTiming.domContentLoadedEventEnd - navigationTiming.fetchStart;

      console.log(`[Performance] ${pageName}:`, {
        loadTime: `${loadTime.toFixed(0)}ms`,
        domContentLoaded: `${domContentLoaded.toFixed(0)}ms`,
        ttfb: `${(navigationTiming.responseStart - navigationTiming.fetchStart).toFixed(0)}ms`,
      });
    }

    // 记录首次内容绘制 (FCP)
    const paintEntries = performance.getEntriesByType('paint');
    const fcp = paintEntries.find((entry) => entry.name === 'first-contentful-paint');
    if (fcp) {
      console.log(`[Performance] ${pageName} FCP:`, `${fcp.startTime.toFixed(0)}ms`);
    }
  }, [pageName]);
}

/**
 * 组件渲染性能监控
 */
export function useRenderPerformance(componentName: string) {
  const renderCount = useRef(0);
  const startTime = useRef(performance.now());

  useEffect(() => {
    renderCount.current += 1;
    const renderTime = performance.now() - startTime.current;

    if (renderTime > 16) {
      // 超过一帧的时间
      console.warn(`[Performance] ${componentName} slow render:`, {
        renderTime: `${renderTime.toFixed(2)}ms`,
        renderCount: renderCount.current,
      });
    }

    startTime.current = performance.now();
  });
}

import { useRef } from 'react';
