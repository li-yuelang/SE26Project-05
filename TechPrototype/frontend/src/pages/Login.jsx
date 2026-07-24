import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Button, Card, Form, Input, Segmented, Space, Spin, Typography, message } from 'antd';
import { LockOutlined, MailOutlined, UserOutlined } from '@ant-design/icons';
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
      <Card className="auth-card" variant="borderless">
        <Space orientation="vertical" size={6} className="auth-heading">
          <Text className="auth-eyebrow">PaperMate</Text>
          <Title level={2}>连接你的论文知识库</Title>
          <Paragraph type="secondary">登录后访问论文、任务、Wiki 和智能问答。</Paragraph>
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
            <>
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
            </>
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
          <Button type="primary" htmlType="submit" block size="large" loading={submitting}>
            {mode === 'login' ? '登录' : '创建账户'}
          </Button>
        </Form>
      </Card>
    </main>
  );
}
