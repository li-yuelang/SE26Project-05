import { NavLink, Outlet } from 'react-router-dom';

const navItems = [
  { to: '/dashboard',      label: '首页',        icon: '📊' },
  { to: '/papers',         label: '论文列表',    icon: '📄' },
  { to: '/chat',           label: '智能问答',    icon: '💬' },
  { to: '/wiki',           label: '知识 Wiki',   icon: '📚' },
  { to: '/learning',       label: '学习中心',    icon: '📝' },
  { to: '/compare',        label: '论文对比',    icon: '⚖️' },
  { to: '/tasks',          label: '抓取任务',    icon: '📥' },
  { to: '/trends',         label: '研究脉络',    icon: '🔬' },
  { to: '/subscriptions',  label: '推荐与订阅',  icon: '🔔' },
  { to: '/settings',       label: '用户设置',    icon: '⚙️' },
];

export default function Layout() {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <h1>PaperMate</h1>
          <span className="sidebar-subtitle">ArXiv 论文阅读工具</span>
        </div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `nav-item${isActive ? ' active' : ''}`
              }
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
