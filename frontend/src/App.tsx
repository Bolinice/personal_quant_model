import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import FactorList from './pages/Factors/FactorList';
import FactorDetail from './pages/Factors/FactorDetail';
import ModelList from './pages/Models/ModelList';
import ModelDetail from './pages/Models/ModelDetail';
import TimingList from './pages/Timing/TimingList';
import PortfolioList from './pages/Portfolios/PortfolioList';
import PortfolioDetail from './pages/Portfolios/PortfolioDetail';
import BacktestList from './pages/Backtests/BacktestList';
import BacktestCreate from './pages/Backtests/BacktestCreate';
import BacktestResult from './pages/Backtests/BacktestResult';
import PerformanceReport from './pages/Performance/PerformanceReport';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/factors" element={<FactorList />} />
        <Route path="/factors/:id" element={<FactorDetail />} />
        <Route path="/models" element={<ModelList />} />
        <Route path="/models/:id" element={<ModelDetail />} />
        <Route path="/timing" element={<TimingList />} />
        <Route path="/portfolios" element={<PortfolioList />} />
        <Route path="/portfolios/:id" element={<PortfolioDetail />} />
        <Route path="/backtests" element={<BacktestList />} />
        <Route path="/backtests/create" element={<BacktestCreate />} />
        <Route path="/backtests/:id" element={<BacktestResult />} />
        <Route path="/performance" element={<PerformanceReport />} />
      </Route>
    </Routes>
  );
}
