import { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Button, Card, Form, Input, Segmented, Space, Spin, Typography, message } from 'antd';
import {
  ArrowLeftOutlined,
  ArrowRightOutlined,
  LockOutlined,
  MailOutlined,
  UserOutlined,
} from '@ant-design/icons';
import KnowledgeGraph from '../components/KnowledgeGraph';
import { useAuth } from '../contexts/AuthContext';

const { Paragraph, Text, Title } = Typography;

export default function Login() {
  const location = useLocation();
  const navigate = useNavigate();
  const { loading: sessionLoading, login, register, user } = useAuth();
  const [mode, setMode] = useState('login');
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  if (sessionLoading) {
    return <div className="auth-loading"><Spin size="large" /></div>;
  }
  if (user) return <Navigate to="/dashboard" replace />;

  const handleSubmit = async (values) => {
    setSubmitting(true);
    try {
      if (mode === 'register') {
        await register({
          display_name: values.displayName,
          email: values.email,
          password: values.password,
          username: values.username,
        });
        message.success('注册成功');
      } else {
        await login({ email: values.email, password: values.password });
        message.success('登录成功');
      }
      const destination = location.state?.from?.pathname || '/dashboard';
      navigate(destination, { replace: true });
    } catch (error) {
      message.error(error.message || (mode === 'login' ? '登录失败' : '注册失败'));
    } finally {
      setSubmitting(false);
    }
  };

  const changeMode = (nextMode) => {
    setMode(nextMode);
    form.resetFields();
  };

  return (
    <main className="auth-page">
      <section className="auth-showcase">
        <Link to="/" className="auth-back-link">
          <ArrowLeftOutlined /> 返回产品首页
        </Link>
        <div className="auth-showcase-orb auth-showcase-orb-one" />
        <div className="auth-showcase-orb auth-showcase-orb-two" />
        <div className="auth-graph-wrap">
          <KnowledgeGraph className="auth-graph" />
        </div>
        <div className="auth-showcase-copy">
          <span className="auth-showcase-label">Research, connected.</span>
          <h1>让下一次发现，<br />从已有的知识开始。</h1>
          <p>聚合论文、连接概念，并与整个研究知识库自然对话。</p>
        </div>
        <div className="auth-showcase-foot">
          <span>PaperMate</span>
          <span>Focused research workspace</span>
        </div>
      </section>

      <section className="auth-panel">
        <Link to="/" className="auth-mobile-brand" aria-label="返回 PaperMate 产品首页">
          <span>P</span>
          <strong>PaperMate</strong>
        </Link>
        <Card className="auth-card" variant="borderless">
          <Space orientation="vertical" size={6} className="auth-heading">
            <Text className="auth-eyebrow">
              {mode === 'login' ? 'Welcome back' : 'Create your workspace'}
            </Text>
            <Title level={2}>
              {mode === 'login' ? '继续你的研究旅程' : '建立你的研究知识库'}
            </Title>
            <Paragraph type="secondary">
              {mode === 'login'
                ? '登录后继续访问论文、任务、Wiki 和智能问答。'
                : '只需一分钟，即可创建专属研究工作区。'}
            </Paragraph>
          </Space>
          <Segmented
            block
            value={mode}
            onChange={changeMode}
            options={[
              { label: '登录', value: 'login' },
              { label: '注册', value: 'register' },
            ]}
          />
          <Form form={form} layout="vertical" onFinish={handleSubmit} className="auth-form">
            {mode === 'register' && (
              <div className="auth-form-grid">
                <Form.Item
                  label="用户名"
                  name="username"
                  rules={[
                    { required: true, message: '请输入用户名' },
                    { min: 3, max: 50, message: '用户名长度应为 3–50 个字符' },
                    { pattern: /^[A-Za-z0-9_]+$/, message: '仅支持字母、数字和下划线' },
                  ]}
                >
                  <Input prefix={<UserOutlined />} autoComplete="username" placeholder="paper_reader" />
                </Form.Item>
                <Form.Item label="显示名称" name="displayName">
                  <Input prefix={<UserOutlined />} placeholder="你的昵称（可选）" />
                </Form.Item>
              </div>
            )}
            <Form.Item
              label="邮箱"
              name="email"
              rules={[
                { required: true, message: '请输入邮箱' },
                { type: 'email', message: '请输入有效邮箱地址' },
              ]}
            >
              <Input prefix={<MailOutlined />} autoComplete="email" placeholder="you@example.com" />
            </Form.Item>
            <Form.Item
              label="密码"
              name="password"
              rules={[
                { required: true, message: '请输入密码' },
                ...(mode === 'register' ? [{ min: 8, message: '密码至少需要 8 个字符' }] : []),
              ]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                placeholder={mode === 'register' ? '至少 8 个字符' : '请输入密码'}
              />
            </Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              block
              size="large"
              loading={submitting}
              className="auth-submit"
            >
              {mode === 'login' ? '进入工作区' : '创建账户'}
              {!submitting && <ArrowRightOutlined />}
            </Button>
          </Form>
          <Text className="auth-terms">
            继续即表示你同意以 PaperMate 管理个人研究资料。
          </Text>
        </Card>
      </section>
    </main>
  );
}
