import { Routes, Route, Navigate } from 'react-router-dom';
import UploadPage from './pages/UploadPage';
import DashboardPage from './pages/DashboardPage';
import RiskPage from './pages/RiskPage';
import TradesPage from './pages/TradesPage';
import InsightsPage from './pages/InsightsPage';
import ProgressPage from './pages/ProgressPage';
import Navbar from './components/Navbar';

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="max-w-7xl mx-auto w-full px-4 py-8 flex-1">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/portfolio/:id" element={<DashboardPage />} />
          <Route path="/portfolio/:id/risk" element={<RiskPage />} />
          <Route path="/portfolio/:id/trades" element={<TradesPage />} />
          <Route path="/portfolio/:id/insights" element={<InsightsPage />} />
          <Route path="/portfolio/:id/progress" element={<ProgressPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <footer className="py-4 text-center text-xs text-gray-400">
        PortfolioLens
      </footer>
    </div>
  );
}
