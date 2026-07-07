import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';

import Dashboard        from './pages/Dashboard';
import PaperList        from './pages/PaperList';
import PaperDetail      from './pages/PaperDetail';
import Chat             from './pages/Chat';
import ChatConversation from './pages/ChatConversation';
import Wiki             from './pages/Wiki';
import ConceptDetail    from './pages/ConceptDetail';
import Learning         from './pages/Learning';
import Compare          from './pages/Compare';
import TaskList         from './pages/TaskList';
import TaskDetail       from './pages/TaskDetail';
import Trends           from './pages/Trends';
import TopicTrend       from './pages/TopicTrend';
import Subscriptions    from './pages/Subscriptions';
import Settings         from './pages/Settings';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* 默认跳转到首页 */}
        <Route index element={<Navigate to="/dashboard" replace />} />

        {/* 首页 */}
        <Route path="dashboard" element={<Dashboard />} />

        {/* 论文 */}
        <Route path="papers" element={<PaperList />} />
        <Route path="papers/:paperId" element={<PaperDetail />} />

        {/* 智能问答 */}
        <Route path="chat" element={<Chat />} />
        <Route path="chat/:conversationId" element={<ChatConversation />} />

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
    </Routes>
  );
}

function NotFound() {
  return (
    <div className="page">
      <h2>404 - 页面未找到</h2>
      <p>您访问的页面不存在。</p>
    </div>
  );
}
