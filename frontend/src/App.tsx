import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout, MarketingLayout } from '@/components/layout';
import HomePage from '@/pages/Home';
import PricingPage from '@/pages/Pricing';
import AboutPage from '@/pages/About';
import FactorList from '@/pages/Factors/FactorList';
import ModelList from '@/pages/Models/ModelList';
import ModelDetail from '@/pages/Models/ModelDetail';
import ModelOverview from '@/pages/Models/ModelOverview';
import ModelTemplates from '@/pages/Models/ModelTemplates';
import ModelBacktests from '@/pages/Models/ModelBacktests';
import ModelPlan from '@/pages/Models/ModelPlan';
import Subscribe from '@/pages/Subscribe';

export default function App() {
  return (
    <Routes>
      {/* 官网 - 公开页面 */}
      <Route element={<MarketingLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/pricing" element={<PricingPage />} />
        <Route path="/about" element={<AboutPage />} />
      </Route>

      {/* 内部系统 */}
      <Route path="/app" element={<Layout />}>
        <Route index element={<Navigate to="/app/factors" replace />} />
        <Route path="factors" element={<FactorList />} />
        <Route path="models" element={<ModelList />} />
        <Route path="models/overview" element={<ModelOverview />} />
        <Route path="models/templates" element={<ModelTemplates />} />
        <Route path="models/backtests" element={<ModelBacktests />} />
        <Route path="models/plan" element={<ModelPlan />} />
        <Route path="models/:code" element={<ModelDetail />} />
        <Route path="subscribe" element={<Subscribe />} />
      </Route>
    </Routes>
  );
}
