import {
  BellOutlined,
  BookOutlined,
  BranchesOutlined,
  CloudDownloadOutlined,
  DashboardOutlined,
  DownOutlined,
  FileTextOutlined,
  LogoutOutlined,
  MenuOutlined,
  MessageOutlined,
  ReadOutlined,
  SettingOutlined,
  SwapOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Avatar, Dropdown, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const { Text } = Typography;

const navGroups = [
  {
    label: '工作区',
    items: [
      { to: '/dashboard', label: '首页', icon: <DashboardOutlined /> },
      { to: '/papers', label: '论文列表', icon: <FileTextOutlined /> },
      { to: '/chat', label: '智能问答', icon: <MessageOutlined /> },
      { to: '/wiki', label: '知识 Wiki', icon: <BookOutlined /> },
    ],
  },
  {
    label: '研究工具',
    items: [
      { to: '/learning', label: '学习中心', icon: <ReadOutlined /> },
      { to: '/compare', label: '论文对比', icon: <SwapOutlined /> },
      { to: '/tasks', label: '抓取任务', icon: <CloudDownloadOutlined /> },
      { to: '/trends', label: '研究脉络', icon: <BranchesOutlined /> },
    ],
  },
  {
    label: '个人',
    items: [
      { to: '/subscriptions', label: '推荐与订阅', icon: <BellOutlined /> },
    ],
  },
];

export default function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, user } = useAuth();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const accountMenu = {
    items: [
      {
        key: 'settings',
        icon: <SettingOutlined />,
        label: '用户设置',
      },
      { type: 'divider' },
      {
        key: 'logout',
        icon: <LogoutOutlined />,
        label: '退出登录',
        danger: true,
      },
    ],
    onClick: ({ key }) => {
      if (key === 'settings') {
        navigate('/settings');
      } else if (key === 'logout') {
        handleLogout();
      }
    },
  };

  return (
    <div className="app-layout">
      <header className="mobile-topbar">
        <button
          type="button"
          className="mobile-menu-trigger"
          onClick={() => setMobileNavOpen(true)}
          aria-label="打开主导航"
          aria-expanded={mobileNavOpen}
        >
          <MenuOutlined />
        </button>
        <span className="mobile-brand">
          <span className="sidebar-logo-mark" aria-hidden="true">P</span>
          <strong>PaperMate</strong>
        </span>
        <Avatar size={30} icon={<UserOutlined />} />
      </header>
      <button
        type="button"
        className={`sidebar-backdrop${mobileNavOpen ? ' visible' : ''}`}
        onClick={() => setMobileNavOpen(false)}
        aria-label="关闭主导航"
      />
      <aside className={`sidebar${mobileNavOpen ? ' mobile-open' : ''}`}>
        <div className="sidebar-brand">
          <span className="sidebar-logo-mark" aria-hidden="true">P</span>
          <span className="sidebar-brand-copy">
            <h1>PaperMate</h1>
            <span className="sidebar-subtitle">Research OS</span>
          </span>
        </div>
        <nav className="sidebar-nav" aria-label="主导航">
          {navGroups.map((group) => (
            <div className="nav-group" key={group.label}>
              <span className="nav-group-label">{group.label}</span>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  title={item.label}
                  className={({ isActive }) =>
                    `nav-item${isActive ? ' active' : ''}`
                  }
                >
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-label">{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-account">
          <Dropdown menu={accountMenu} trigger={['click']} placement="topLeft">
            <button
              type="button"
              className={`sidebar-account-trigger${
                location.pathname.startsWith('/settings') ? ' active' : ''
              }`}
              aria-label="打开账户菜单"
            >
              <Avatar size={30} icon={<UserOutlined />} />
              <span className="sidebar-user-copy">
                <Text>{user?.display_name || user?.username}</Text>
                <Text>{user?.email}</Text>
              </span>
              <DownOutlined className="sidebar-account-chevron" />
            </button>
          </Dropdown>
        </div>
      </aside>
      <main
        className={`main-content${
          location.pathname.startsWith('/chat') ? ' chat-main-content' : ''
        }`}
      >
        <Outlet />
      </main>
    </div>
  );
}
