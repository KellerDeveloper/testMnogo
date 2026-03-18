import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import AppShell from './shared/AppShell';
import KitchenOrdersPage from './modules/kitchen/KitchenOrdersPage';
import KitchenCouriersPage from './modules/kitchen/KitchenCouriersPage';
import KitchenCreateOrderPage from './modules/kitchen/KitchenCreateOrderPage';
import OfficeDecisionsPage from './modules/office/OfficeDecisionsPage';
import OfficeConfigsPage from './modules/office/OfficeConfigsPage';
import OfficeAnalyticsPage from './modules/office/OfficeAnalyticsPage';
import OfficeCouriersPage from './modules/office/OfficeCouriersPage';
import CourierOrdersPage from './modules/courier/CourierOrdersPage';
import CourierStatsPage from './modules/courier/CourierStatsPage';
import CourierSettingsPage from './modules/courier/CourierSettingsPage';

const App: React.FC = () => {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/kitchen/orders" replace />} />

        <Route path="/kitchen/orders" element={<KitchenOrdersPage />} />
        <Route path="/kitchen/orders/create" element={<KitchenCreateOrderPage />} />
        <Route path="/kitchen/couriers" element={<KitchenCouriersPage />} />

        <Route path="/office/decisions" element={<OfficeDecisionsPage />} />
        <Route path="/office/analytics" element={<OfficeAnalyticsPage />} />
        <Route path="/office/configs" element={<OfficeConfigsPage />} />
        <Route path="/office/couriers" element={<OfficeCouriersPage />} />

        <Route path="/courier/orders" element={<CourierOrdersPage />} />
        <Route path="/courier/stats" element={<CourierStatsPage />} />
        <Route path="/courier/settings" element={<CourierSettingsPage />} />
      </Routes>
    </AppShell>
  );
};

export default App;
