import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from '@/contexts/AuthContext';
import { OnboardingProvider } from '@/contexts/OnboardingContext';
import { ProtectedRoute, PublicRoute } from '@/components/auth/AuthGuard';
import { Layout, MarketingLayout } from '@/components/layout';
import HomePage from '@/pages/Home';
import PricingPage from '@/pages/Pricing';
import AboutPage from '@/pages/About';
import Login from '@/pages/Auth/Login';
import Register from '@/pages/Auth/Register';
import ForgotPassword from '@/pages/Auth/ForgotPassword';
import ResetPassword from '@/pages/Auth/ResetPassword';
import Dashboard from '@/pages/Dashboard';
import FactorList from '@/pages/Factors/FactorList';
import ModelList from '@/pages/Models/ModelList';
import ModelDetail from '@/pages/Models/ModelDetail';
import ModelOverview from '@/pages/Models/ModelOverview';
import ModelTemplates from '@/pages/Models/ModelTemplates';
import ModelBacktests from '@/pages/Models/ModelBacktests';
import ModelPlan from '@/pages/Models/ModelPlan';
import BacktestList from '@/pages/Backtests/BacktestList';
import BacktestCreate from '@/pages/Backtests/BacktestCreate';
import BacktestResult from '@/pages/Backtests/BacktestResult';
import TimingList from '@/pages/Timing/TimingList';
import PortfolioList from '@/pages/Portfolios/PortfolioList';
import PortfolioDetail from '@/pages/Portfolios/PortfolioDetail';
import PerformanceReport from '@/pages/Performance/PerformanceReport';
import MonitorDashboard from '@/pages/Monitor/MonitorDashboard';
import EventList from '@/pages/Events/EventList';
import DataCenter from '@/pages/DataCenter';
import Profile from '@/pages/Settings/Profile';
import RiskAssessment from '@/pages/Settings/RiskAssessment';
import SubscriptionPage from '@/pages/Settings/SubscriptionPage';
import Subscribe from '@/pages/Subscribe';
import StrategyList from '@/pages/Strategies/StrategyList';
import StrategyDetail from '@/pages/Strategies/StrategyDetail';
import StrategyForm from '@/pages/Strategies/StrategyForm';
import TemplateStrategies from '@/pages/Strategies/TemplateStrategies';

function AppRoutes() {
  return (
    <Routes>
      {/* 公开页面 */}
      <Route element={<MarketingLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/pricing" element={<PricingPage />} />
        <Route path="/about" element={<AboutPage />} />
      </Route>

      {/* 认证页面 — 已登录则跳转 dashboard */}
      <Route
        path="/login"
        element={
          <PublicRoute>
            <Login />
          </PublicRoute>
        }
      />
      <Route
        path="/register"
        element={
          <PublicRoute>
            <Register />
          </PublicRoute>
        }
      />
      <Route
        path="/forgot-password"
        element={
          <PublicRoute>
            <ForgotPassword />
          </PublicRoute>
        }
      />
      <Route
        path="/reset-password"
        element={
          <PublicRoute>
            <ResetPassword />
          </PublicRoute>
        }
      />

      {/* 应用页面 - 可浏览，操作需要认证 */}
      <Route path="/app" element={<Layout />}>
        <Route index element={<Navigate to="/app/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="factors" element={<FactorList />} />
        <Route path="models" element={<ModelList />} />
        <Route path="models/overview" element={<ModelOverview />} />
        <Route path="models/templates" element={<ModelTemplates />} />
        <Route path="models/backtests" element={<ModelBacktests />} />
        <Route path="models/plan" element={<ModelPlan />} />
        <Route path="models/:code" element={<ModelDetail />} />
        <Route path="backtests" element={<BacktestList />} />
        <Route
          path="backtests/create"
          element={
            <ProtectedRoute>
              <BacktestCreate />
            </ProtectedRoute>
          }
        />
        <Route path="backtests/:id" element={<BacktestResult />} />
        <Route path="strategies" element={<StrategyList />} />
        <Route path="strategies/templates" element={<TemplateStrategies />} />
        <Route
          path="strategies/create"
          element={
            <ProtectedRoute>
              <StrategyForm />
            </ProtectedRoute>
          }
        />
        <Route
          path="strategies/:id/edit"
          element={
            <ProtectedRoute>
              <StrategyForm />
            </ProtectedRoute>
          }
        />
        <Route path="strategies/:id" element={<StrategyDetail />} />
        <Route path="timing" element={<TimingList />} />
        <Route path="portfolios" element={<PortfolioList />} />
        <Route path="portfolios/:id" element={<PortfolioDetail />} />
        <Route path="performance" element={<PerformanceReport />} />
        <Route path="monitor" element={<MonitorDashboard />} />
        <Route path="events" element={<EventList />} />
        <Route path="data" element={<DataCenter />} />
        <Route
          path="settings"
          element={
            <ProtectedRoute>
              <Profile />
            </ProtectedRoute>
          }
        />
        <Route
          path="settings/subscription"
          element={
            <ProtectedRoute>
              <SubscriptionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="settings/risk-assessment"
          element={
            <ProtectedRoute>
              <RiskAssessment />
            </ProtectedRoute>
          }
        />
        <Route
          path="subscribe"
          element={
            <ProtectedRoute>
              <Subscribe />
            </ProtectedRoute>
          }
        />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <OnboardingProvider>
        <AppRoutes />
      </OnboardingProvider>
    </AuthProvider>
  );
}
