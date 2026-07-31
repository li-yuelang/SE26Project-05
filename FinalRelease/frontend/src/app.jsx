import { lazy, Suspense } from 'react';
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { Spin } from 'antd';
import AppLayout from './layouts/AppLayout';
import { useAuth } from './contexts/AuthContext';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const ProductLanding = lazy(() => import('./pages/ProductLanding'));
const PaperList = lazy(() => import('./pages/PaperList'));
const PaperDetail = lazy(() => import('./pages/PaperDetail'));
const AnalysisResult = lazy(() => import('./pages/AnalysisResult'));
const Chat = lazy(() => import('./pages/Chat'));
const Wiki = lazy(() => import('./pages/Wiki'));
const ConceptDetail = lazy(() => import('./pages/ConceptDetail'));
const Learning = lazy(() => import('./pages/Learning'));
const Compare = lazy(() => import('./pages/Compare'));
const TaskList = lazy(() => import('./pages/TaskList'));
const TaskDetail = lazy(() => import('./pages/TaskDetail'));
const Trends = lazy(() => import('./pages/Trends'));
const TopicTrend = lazy(() => import('./pages/TopicTrend'));
const Subscriptions = lazy(() => import('./pages/Subscriptions'));
const Settings = lazy(() => import('./pages/Settings'));
const Login = lazy(() => import('./pages/Login'));

function PageFallback() {
  return (
    <div className="page-loading" role="status" aria-label="页面加载中">
      <Spin size="large" />
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route index element={<ProductLanding />} />
        <Route path="login" element={<Login />} />
        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>
            {/* 首页 */}
            <Route path="dashboard" element={<Dashboard />} />

            {/* 论文 */}
            <Route path="papers" element={<PaperList />} />
            <Route path="papers/:paperId" element={<PaperDetail />} />
            <Route path="papers/:paperId/analysis" element={<AnalysisResult />} />

            {/* 智能问答 */}
            <Route path="chat/:conversationId?" element={<Chat />} />

            {/* 知识 Wiki */}
            <Route path="wiki" element={<Wiki />} />
            <Route path="wiki/concepts/:conceptId" element={<ConceptDetail />} />

            {/* 学习中心 */}
            <Route path="learning" element={<Learning />} />

            {/* 论文对比 */}
            <Route path="compare" element={<Compare />} />

            {/* 抓取任务 */}
            <Route path="tasks" element={<TaskList />} />
            <Route path="tasks/:taskId" element={<TaskDetail />} />

            {/* 研究脉络 */}
            <Route path="trends" element={<Trends />} />
            <Route path="trends/:topicId" element={<TopicTrend />} />

            {/* 推荐与订阅 */}
            <Route path="subscriptions" element={<Subscriptions />} />

            {/* 用户设置 */}
            <Route path="settings" element={<Settings />} />

            {/* 404 */}
            <Route path="*" element={<NotFound />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}

function RequireAuth() {
  const location = useLocation();
  const { loading, user } = useAuth();

  if (loading) return <PageFallback />;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}

function NotFound() {
  return (
    <div className="page">
      <h2>404 - 页面未找到</h2>
      <p>您访问的页面不存在。</p>
    </div>
  );
}
