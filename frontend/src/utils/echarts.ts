/**
 * ECharts按需引入配置
 * 只导入项目中实际使用的组件，减少打包体积
 */

import * as echarts from 'echarts/core';

// 引入图表类型
import {
  LineChart,
  BarChart,
  HeatmapChart,
  ScatterChart,
  PieChart,
} from 'echarts/charts';

// 引入组件
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkPointComponent,
  ToolboxComponent,
  VisualMapComponent,
} from 'echarts/components';

// 引入渲染器
import { CanvasRenderer } from 'echarts/renderers';

// 注册必需的组件
echarts.use([
  // 图表类型
  LineChart,
  BarChart,
  HeatmapChart,
  ScatterChart,
  PieChart,

  // 组件
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkPointComponent,
  ToolboxComponent,
  VisualMapComponent,

  // 渲染器
  CanvasRenderer,
]);

export default echarts;
