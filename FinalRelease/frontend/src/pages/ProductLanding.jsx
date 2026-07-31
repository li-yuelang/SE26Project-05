import {
  ArrowRightOutlined,
  BookOutlined,
  BranchesOutlined,
  MessageOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { Link } from 'react-router-dom';
import KnowledgeGraph from '../components/KnowledgeGraph';
import { useAuth } from '../contexts/AuthContext';

const features = [
  {
    icon: <SearchOutlined />,
    index: '01',
    title: '持续发现',
    description: '自动聚合关注领域的新论文，让重要进展主动来到你面前。',
  },
  {
    icon: <BookOutlined />,
    index: '02',
    title: '结构化理解',
    description: '从摘要、方法到实验结论，把长论文转化为可复用的研究笔记。',
  },
  {
    icon: <BranchesOutlined />,
    index: '03',
    title: '连接知识',
    description: '建立论文与概念之间的关系，逐步形成你的个人研究脉络。',
  },
];

export default function ProductLanding() {
  const { user } = useAuth();
  const destination = user ? '/dashboard' : '/login';

  return (
    <main className="landing-page">
      <header className="landing-nav">
        <Link to="/" className="landing-brand" aria-label="PaperMate 首页">
          <span className="landing-brand-mark">P</span>
          <span>PaperMate</span>
        </Link>
        <nav aria-label="产品导航">
          <a href="#product">产品</a>
          <a href="#workflow">工作方式</a>
          <a href="#features">能力</a>
        </nav>
        <div className="landing-nav-actions">
          {!user && <Link to="/login" className="landing-login-link">登录</Link>}
          <Link to={destination} className="landing-primary-link">
            {user ? '进入工作区' : '免费开始'} <ArrowRightOutlined />
          </Link>
        </div>
      </header>

      <section className="landing-hero" id="product">
        <div className="landing-kicker">
          <span className="landing-kicker-dot" />
          AI-powered research workspace
        </div>
        <h1>
          把散落的论文，
          <span>变成可对话的知识。</span>
        </h1>
        <p>
          PaperMate 将论文发现、深度阅读、知识组织与智能问答连接在一起，
          让你的每一次阅读都成为下一次研究的起点。
        </p>
        <div className="landing-hero-actions">
          <Link to={destination} className="landing-hero-primary">
            {user ? '继续研究' : '创建研究工作区'} <ArrowRightOutlined />
          </Link>
          <a href="#workflow" className="landing-hero-secondary">了解工作方式</a>
        </div>
      </section>

      <section className="landing-graph-shell" id="workflow">
        <div className="landing-graph-toolbar">
          <span>
            <span className="landing-live-dot" />
            Knowledge graph
          </span>
          <span>31 nodes · 63 connections</span>
        </div>
        <KnowledgeGraph className="landing-graph" />
        <div className="landing-graph-caption">
          <span>论文</span>
          <ArrowRightOutlined />
          <span>方法</span>
          <ArrowRightOutlined />
          <span>概念</span>
          <ArrowRightOutlined />
          <span>新问题</span>
        </div>
      </section>

      <section className="landing-features" id="features">
        <div className="landing-section-heading">
          <span>从阅读，到洞察</span>
          <h2>一个安静、连续的研究空间。</h2>
          <p>减少工具切换，把注意力留给真正重要的问题。</p>
        </div>
        <div className="landing-feature-grid">
          {features.map((feature) => (
            <article key={feature.title} className="landing-feature">
              <div className="landing-feature-meta">
                <span>{feature.index}</span>
                <span className="landing-feature-icon">{feature.icon}</span>
              </div>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-cta">
        <div>
          <MessageOutlined />
          <span>Ready when you are</span>
        </div>
        <h2>从下一篇论文开始，<br />建立你的研究知识库。</h2>
        <Link to={destination}>
          {user ? '进入 PaperMate' : '开始使用 PaperMate'} <ArrowRightOutlined />
        </Link>
      </section>

      <footer className="landing-footer">
        <span>© 2026 PaperMate</span>
        <span>Designed for focused research.</span>
      </footer>
    </main>
  );
}
