# 前端设计系统 V2.0

## 🎨 设计理念

**核心定位**: 专业量化平台 - 数据驱动、精准高效、科技感

**设计原则**:
- **清晰性** - 信息层次分明，关键数据突出
- **专业性** - 金融级数据展示，精确到位
- **现代感** - 渐变、毛玻璃、微动效
- **高效性** - 减少点击，快速操作

---

## 🎨 色彩系统

### 主色调 (Primary)
```css
/* 科技蓝 - 主要操作、强调 */
--primary-50: #eff6ff
--primary-100: #dbeafe
--primary-500: #3b82f6  /* 主色 */
--primary-600: #2563eb
--primary-700: #1d4ed8
--primary-gradient: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)
```

### 辅助色 (Secondary)
```css
/* 紫色 - 高级功能、VIP */
--secondary-500: #8b5cf6
--secondary-600: #7c3aed
--secondary-gradient: linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%)
```

### 功能色
```css
/* 成功 - 涨、盈利、健康 */
--success: #10b981
--success-light: #34d399
--success-gradient: linear-gradient(135deg, #10b981 0%, #059669 100%)

/* 警告 - 震荡、注意 */
--warning: #f59e0b
--warning-light: #fbbf24
--warning-gradient: linear-gradient(135deg, #f59e0b 0%, #d97706 100%)

/* 危险 - 跌、亏损、异常 */
--danger: #ef4444
--danger-light: #f87171
--danger-gradient: linear-gradient(135deg, #ef4444 0%, #dc2626 100%)

/* 信息 - 中性提示 */
--info: #06b6d4
--info-light: #22d3ee
--info-gradient: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%)
```

### 中性色 (背景、文字)
```css
/* 深色主题 */
--bg-primary: #0a0e1a      /* 主背景 */
--bg-secondary: #0f1729    /* 次级背景 */
--bg-tertiary: #1a2332     /* 卡片背景 */
--bg-elevated: #1e293b     /* 悬浮元素 */

/* 文字 */
--text-primary: #f1f5f9    /* 主要文字 */
--text-secondary: #cbd5e1  /* 次要文字 */
--text-tertiary: #94a3b8   /* 辅助文字 */
--text-disabled: #64748b   /* 禁用文字 */

/* 边框 */
--border-subtle: rgba(148, 163, 184, 0.08)
--border-default: rgba(148, 163, 184, 0.12)
--border-strong: rgba(148, 163, 184, 0.2)
```

---

## 📐 布局系统

### 间距 (Spacing)
```css
--space-xs: 4px
--space-sm: 8px
--space-md: 16px
--space-lg: 24px
--space-xl: 32px
--space-2xl: 48px
--space-3xl: 64px
```

### 圆角 (Border Radius)
```css
--radius-sm: 6px    /* 小元素 */
--radius-md: 12px   /* 卡片 */
--radius-lg: 16px   /* 大卡片 */
--radius-xl: 24px   /* 模态框 */
--radius-full: 9999px /* 圆形 */
```

### 阴影 (Shadows)
```css
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05)
--shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1)
--shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.15)
--shadow-xl: 0 20px 25px rgba(0, 0, 0, 0.2)
--shadow-glow: 0 0 20px rgba(59, 130, 246, 0.3)
```

---

## 🎭 组件规范

### 1. GlassPanel (毛玻璃卡片)
**用途**: 主要内容容器

**样式**:
```tsx
{
  background: 'rgba(15, 23, 41, 0.6)',
  backdropFilter: 'blur(20px)',
  border: '1px solid rgba(148, 163, 184, 0.08)',
  borderRadius: '16px',
  padding: '24px',
  transition: 'all 0.3s ease',
  '&:hover': {
    borderColor: 'rgba(148, 163, 184, 0.12)',
    transform: 'translateY(-2px)',
    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.15)',
  }
}
```

### 2. MetricCard (指标卡片)
**用途**: 数据展示

**布局**:
- 标签 (label) - 12px, 次要色
- 数值 (value) - 32px, 主要色, 粗体
- 趋势 (trend) - 图标 + 百分比
- 副标题 (subtitle) - 14px, 辅助色

### 3. ActionButton (操作按钮)
**主要按钮**:
```tsx
{
  background: 'linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)',
  color: '#ffffff',
  padding: '12px 24px',
  borderRadius: '12px',
  fontWeight: 600,
  '&:hover': {
    background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)',
    transform: 'translateY(-1px)',
    boxShadow: '0 8px 16px rgba(59, 130, 246, 0.3)',
  }
}
```

**次要按钮**:
```tsx
{
  background: 'rgba(148, 163, 184, 0.08)',
  color: '#cbd5e1',
  border: '1px solid rgba(148, 163, 184, 0.12)',
  '&:hover': {
    background: 'rgba(148, 163, 184, 0.12)',
    borderColor: 'rgba(148, 163, 184, 0.2)',
  }
}
```

### 4. StatusChip (状态标签)
**样式映射**:
```tsx
{
  active: { bg: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: '#10b981' },
  draft: { bg: 'rgba(148, 163, 184, 0.15)', color: '#94a3b8', border: '#94a3b8' },
  archived: { bg: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: '#ef4444' },
  warning: { bg: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', border: '#f59e0b' },
}
```

---

## 📱 响应式断点

```css
xs: 0px      /* 手机竖屏 */
sm: 600px    /* 手机横屏 */
md: 900px    /* 平板 */
lg: 1200px   /* 桌面 */
xl: 1536px   /* 大屏 */
```

---

## ✨ 动画规范

### 过渡时间
```css
--duration-fast: 150ms
--duration-normal: 300ms
--duration-slow: 500ms
```

### 缓动函数
```css
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1)
--ease-out: cubic-bezier(0, 0, 0.2, 1)
--ease-in: cubic-bezier(0.4, 0, 1, 1)
```

### 常用动画
```tsx
// 淡入
fadeIn: {
  from: { opacity: 0 },
  to: { opacity: 1 },
}

// 上滑淡入
slideUp: {
  from: { opacity: 0, transform: 'translateY(20px)' },
  to: { opacity: 1, transform: 'translateY(0)' },
}

// 缩放淡入
scaleIn: {
  from: { opacity: 0, transform: 'scale(0.95)' },
  to: { opacity: 1, transform: 'scale(1)' },
}
```

---

## 🎯 页面布局模板

### 列表页 (List Page)
```
┌─────────────────────────────────────┐
│ PageHeader (标题 + 操作按钮)          │
├─────────────────────────────────────┤
│ FilterBar (筛选器 + 搜索)             │
├─────────────────────────────────────┤
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐    │
│ │Card │ │Card │ │Card │ │Card │    │
│ └─────┘ └─────┘ └─────┘ └─────┘    │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐    │
│ │Card │ │Card │ │Card │ │Card │    │
│ └─────┘ └─────┘ └─────┘ └─────┘    │
├─────────────────────────────────────┤
│ Pagination (分页)                    │
└─────────────────────────────────────┘
```

### 详情页 (Detail Page)
```
┌─────────────────────────────────────┐
│ PageHeader (返回 + 标题 + 状态 + 操作)│
├─────────────────────────────────────┤
│ ┌─────────────────────────────────┐ │
│ │ 基本信息 Panel                   │ │
│ └─────────────────────────────────┘ │
│ ┌───────────┐ ┌─────────────────┐  │
│ │ 指标卡片   │ │ 指标卡片         │  │
│ └───────────┘ └─────────────────┘  │
│ ┌─────────────────────────────────┐ │
│ │ 详细数据 Table/Chart             │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

### 表单页 (Form Page)
```
┌─────────────────────────────────────┐
│ PageHeader (返回 + 标题)             │
├─────────────────────────────────────┤
│ ┌─────────────────────────────────┐ │
│ │ 基本信息 Section                 │ │
│ │ ┌─────────┐ ┌─────────┐        │ │
│ │ │ Input   │ │ Select  │        │ │
│ │ └─────────┘ └─────────┘        │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ 配置项 Section                   │ │
│ │ (动态表单项)                     │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ [取消] [保存]                    │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

---

## 🎨 优化重点

### 策略管理页面
1. **卡片式布局** - 3列网格，响应式
2. **渐变背景** - 每个策略卡片带微妙渐变
3. **悬浮效果** - hover时上浮 + 阴影
4. **状态标签** - 彩色chip，一目了然
5. **快速操作** - 卡片内嵌操作按钮

### 策略详情页
1. **顶部概览** - 大标题 + 关键指标卡片
2. **因子权重可视化** - 进度条 + 百分比
3. **性能图表** - 折线图展示历史IC
4. **操作区** - 固定在右上角

### 策略创建表单
1. **步骤指示器** - 清晰的进度
2. **因子选择器** - 带搜索的下拉框
3. **权重滑块** - 实时预览总和
4. **验证提示** - 即时反馈

---

## 📝 实施计划

### Phase 1: 基础组件升级
- [ ] 优化 GlassPanel 组件
- [ ] 创建 PageHeader 组件
- [ ] 创建 StatusChip 组件
- [ ] 创建 ActionButton 组件

### Phase 2: 策略管理页面重构
- [ ] StrategyList - 卡片式布局
- [ ] StrategyDetail - 信息架构优化
- [ ] StrategyForm - 交互体验提升

### Phase 3: 其他页面优化
- [ ] Dashboard - 数据可视化增强
- [ ] Backtests - 结果展示优化
- [ ] Portfolios - 组合管理界面

### Phase 4: 细节打磨
- [ ] 动画过渡
- [ ] 加载状态
- [ ] 空状态设计
- [ ] 错误提示优化
