import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from '@/components/layout';
import FactorList from '@/pages/Factors/FactorList';
import ModelList from '@/pages/Models/ModelList';
import ModelDetail from '@/pages/Models/ModelDetail';
import Subscribe from '@/pages/Subscribe';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/factors" replace />} />
        <Route path="/factors" element={<FactorList />} />
        <Route path="/models" element={<ModelList />} />
        <Route path="/models/:code" element={<ModelDetail />} />
        <Route path="/subscribe" element={<Subscribe />} />
      </Route>
    </Routes>
  );
}