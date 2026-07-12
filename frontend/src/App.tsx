import { useEffect, useState, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import type { WSMessage } from './types';
import { Toolbar } from './components/Toolbar';
import { Canvas } from './components/Canvas';

import { CanvasListModal } from './components/CanvasListModal';
import { AgentChat } from './components/AgentChat';
import { AssetPanel } from './components/AssetPanel';
import { Timeline } from './components/Timeline';
import { HomeView } from './components/HomeView';
import { useEditorStore } from './store/editor';
import { useAgentStore } from './store/agent';
import { useAuthStore } from './store/auth';
import { useWebSocket } from './hooks/useWebSocket';
import LoginPage from './pages/LoginPage';
import LandingPage from './pages/LandingPage';
import ProfilePage from './pages/ProfilePage';
import RechargePage from './pages/RechargePage';
import AdminPage from './pages/AdminPage';
import AgentPage from './pages/AgentPage';
import SkillPage from './pages/SkillPage';
import BrainResultPage from './pages/BrainResultPage';
import ProtectedRoute from './components/ProtectedRoute';
const DirectorDeskPage = lazy(() => import('./pages/DirectorDeskPage'));

function MainApp() {
  const canvas = useEditorStore((s) => s.canvas);
  const loadCanvasList = useEditorStore((s) => s.loadCanvasList);
  const loadCanvas = useEditorStore((s) => s.loadCanvas);
  const showList = useEditorStore((s) => s.showCanvasList);
  const setShowCanvasList = useEditorStore((s) => s.setShowCanvasList);
  const setWsConnected = useEditorStore((s) => s.setWsConnected);
  const handleWSMessage = useEditorStore((s) => s.handleWSMessage);
  const { reset: resetAgent } = useAgentStore();
  const navigate = useNavigate();
  const [agentPanelOpen, setAgentPanelOpen] = useState(false);

  const { connected } = useWebSocket({
    canvasId: canvas?.id,
    enabled: !!canvas,
    onTaskUpdate: (update) => handleWSMessage(update as unknown as WSMessage),
  });

  useEffect(() => {
    setWsConnected(connected);
  }, [connected, setWsConnected]);

  useEffect(() => {
    loadCanvasList();
    const savedId = localStorage.getItem('currentCanvasId');
    if (savedId) {
      loadCanvas(savedId);
    }
    const handler = () => setShowCanvasList(true);
    window.addEventListener('openCanvasList', handler);
    return () => window.removeEventListener('openCanvasList', handler);
  }, [loadCanvasList, loadCanvas, setShowCanvasList]);

  // 有画布时：切换 Agent 浮动面板；无画布时：跳转独立 Agent 页面
  const handleOpenAgent = () => {
    if (canvas) {
      setAgentPanelOpen((v) => !v);
    } else {
      resetAgent();
      navigate('/agent');
    }
  };

  if (!canvas) {
    return (
      <div className="h-screen w-screen overflow-hidden bg-canvas-bg pt-20">
        <Toolbar onOpenAgent={handleOpenAgent} />
        <HomeView onOpenAgent={handleOpenAgent} />
        <CanvasListModal isOpen={showList} onClose={() => setShowCanvasList(false)} />
        <AssetPanel />
      </div>
    );
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-canvas-bg overflow-hidden pt-20">
      <Toolbar onOpenAgent={handleOpenAgent} />
      <div className="flex-1 flex overflow-hidden relative">
        <Canvas onOpenAgent={handleOpenAgent} />
        {agentPanelOpen && (
          <div className="absolute right-0 top-0 bottom-0 z-30 w-[560px] max-w-[calc(100vw-2rem)]">
            <AgentChat docked onClose={() => setAgentPanelOpen(false)} />
          </div>
        )}
      </div>
      <CanvasListModal isOpen={showList} onClose={() => setShowCanvasList(false)} />
      <AssetPanel />
      <Timeline />
    </div>
  );
}

function AuthInit() {
  const { fetchMe } = useAuthStore();
  useEffect(() => {
    fetchMe();
  }, [fetchMe]);
  return null;
}

function App() {
  return (
    <BrowserRouter>
      <AuthInit />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/home"
          element={
            <ProtectedRoute>
              <MainApp />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfilePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/recharge"
          element={
            <ProtectedRoute>
              <RechargePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <ProtectedRoute adminOnly>
              <AdminPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/agent"
          element={
            <ProtectedRoute>
              <AgentPage />
            </ProtectedRoute>
          }
        />
        <Route path="/skill" element={<ProtectedRoute><SkillPage /></ProtectedRoute>} />
        <Route path="/skill-result" element={<ProtectedRoute><BrainResultPage /></ProtectedRoute>} />
        <Route path="/director" element={<ProtectedRoute><DirectorDeskPage /></ProtectedRoute>} />
        <Route path="*" element={<LandingPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
