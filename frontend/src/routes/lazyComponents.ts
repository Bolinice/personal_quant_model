import { lazy } from 'react';

/**
 * 路由懒加载配置
 * 将大型页面组件拆分为独立的 chunk，按需加载
 */

// 认证页面
export const Login = lazy(() => import('@/pages/Auth/Login'));
export const Register = lazy(() => import('@/pages/Auth/Register'));
export const ForgotPassword = lazy(() => import('@/pages/Auth/ForgotPassword'));
export const ResetPassword = lazy(() => import('@/pages/Auth/ResetPassword'));

// 营销页面
export const HomePage = lazy(() => import('@/pages/Home'));
export const AboutPage = lazy(() => import('@/pages/About'));
export const PricingPage = lazy(() => import('@/pages/Pricing'));

// 应用页面
export const Dashboard = lazy(() => import('@/pages/Dashboard'));
export const FactorList = lazy(() => import('@/pages/Factors/FactorList'));
export const FactorDetail = lazy(() => import('@/pages/Factors/FactorDetail'));
export const ModelList = lazy(() => import('@/pages/Models/ModelList'));
export const ModelDetail = lazy(() => import('@/pages/Models/ModelDetail'));
export const ModelOverview = lazy(() => import('@/pages/Models/ModelOverview'));
export const ModelBacktests = lazy(() => import('@/pages/Models/ModelBacktests'));
export const ModelPlan = lazy(() => import('@/pages/Models/ModelPlan'));
export const ModelTemplates = lazy(() => import('@/pages/Models/ModelTemplates'));
export const BacktestList = lazy(() => import('@/pages/Backtests/BacktestList'));
export const BacktestCreate = lazy(() => import('@/pages/Backtests/BacktestCreate'));
export const BacktestResult = lazy(() => import('@/pages/Backtests/BacktestResult'));
export const TimingList = lazy(() => import('@/pages/Timing/TimingList'));
export const PortfolioList = lazy(() => import('@/pages/Portfolios/PortfolioList'));
export const PortfolioDetail = lazy(() => import('@/pages/Portfolios/PortfolioDetail'));
export const MonitorDashboard = lazy(() => import('@/pages/Monitor/MonitorDashboard'));
export const EventList = lazy(() => import('@/pages/Events/EventList'));
export const PerformanceReport = lazy(() => import('@/pages/Performance/PerformanceReport'));
export const DataCenter = lazy(() => import('@/pages/DataCenter'));

// 设置页面
export const Profile = lazy(() => import('@/pages/Settings/Profile'));
export const SubscriptionPage = lazy(() => import('@/pages/Settings/SubscriptionPage'));
export const RiskAssessment = lazy(() => import('@/pages/Settings/RiskAssessment'));
export const SubscribePage = lazy(() => import('@/pages/Subscribe'));
