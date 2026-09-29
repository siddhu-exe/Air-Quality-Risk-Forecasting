import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';

// Views
import { ForecastsView } from './views/ForecastsView';
import { ModelPerformanceView } from './views/ModelPerformanceView';
import { CausalImpactView } from './views/CausalImpactView';
import { RiskThresholdView } from './views/RiskThresholdView';
import { MethodologyView } from './views/MethodologyView';

function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<ForecastsView />} />
        <Route path="/performance" element={<ModelPerformanceView />} />
        <Route path="/causal" element={<CausalImpactView />} />
        <Route path="/thresholds" element={<RiskThresholdView />} />
        <Route path="/methodology" element={<MethodologyView />} />
      </Routes>
    </AppShell>
  );
}

export default App;
