import { useEffect, useState } from 'react';
import {
  Avatar,
  Button,
  Card,
  ColorPicker,
  Divider,
  Flex,
  Form,
  Input,
  message,
  Space,
  Switch,
  Tabs,
  Typography,
} from 'antd';
import {
  BellOutlined,
  CheckOutlined,
  KeyOutlined,
  SafetyOutlined,
  SettingOutlined,
  UserOutlined,
} from '@ant-design/icons';
import {
  changePassword,
  getNotificationPreferences,
  saveNotificationPreferences,
  saveProfile,
  saveSystemPreferences,
} from '../services/settingsService';
import { useAuth } from '../contexts/AuthContext';
import { useThemePreference } from '../contexts/ThemeContext';
import { THEME_OPTIONS } from '../theme/themes';

const { Text, Title } = Typography;

export default function Settings() {
  const { updateUser, user } = useAuth();
  const { applyTheme, themeName } = useThemePreference();
  const [profileForm] = Form.useForm();
  const [passwordForm] = Form.useForm();

  // 个人资料
  const [avatarColor, setAvatarColor] = useState('#5e6ad2');
  const [savingProfile, setSavingProfile] = useState(false);

  // 通知偏好
  const [dailyDigest, setDailyDigest] = useState(true);
  const [paperAlert, setPaperAlert] = useState(true);
  const [subscriptionAlert, setSubscriptionAlert] = useState(false);

  // 主题设置
  const [savingTheme, setSavingTheme] = useState(false);

  // 修改密码
  const [changingPassword, setChangingPassword] = useState(false);

  useEffect(() => {
    if (!user) return;
    profileForm.setFieldsValue({
      username: user.username,
      email: user.email,
      bio: user.bio || '',
    });

    // 从后端加载通知偏好
    getNotificationPreferences().then((data) => {
      if (data.email_digest !== undefined) setDailyDigest(data.email_digest);
      if (data.push_new_paper !== undefined) setPaperAlert(data.push_new_paper);
      if (data.push_recommendation !== undefined) setSubscriptionAlert(data.push_recommendation);
    }).catch(() => {});
  }, [profileForm, user]);

  /* ---------- 保存回调 ---------- */
  const handleSaveProfile = async () => {
    try {
      const values = await profileForm.validateFields();
      setSavingProfile(true);
      const updatedUser = await saveProfile(values);
      updateUser(updatedUser);
      message.success("个人资料已更新");
      setSavingProfile(false);
    } catch {
      // 校验失败，Form 会自动提示
    }
  };

  const handleChangePassword = async () => {
    try {
      const values = await passwordForm.validateFields();
      if (values.newPassword !== values.confirmPassword) {
        message.error("两次输入的新密码不一致");
        return;
      }
      setChangingPassword(true);
      await changePassword(values);
      message.success("密码修改成功");
      passwordForm.resetFields();
      setChangingPassword(false);
    } catch {
      // 校验失败，Form 会自动提示
    }
  };

  /* ---------- 各选项卡内容 ---------- */

  const profileTab = (
    <Card variant="borderless">
      <Flex vertical gap={24}>
        {/* 头像 & 基本资料 */}
        <Flex align="center" gap={24} wrap="wrap">
          <Flex vertical align="center" gap={8}>
            <Avatar
              size={80}
              icon={<UserOutlined />}
              style={{ backgroundColor: avatarColor }}
            />
            <Space size={4}>
              <Text type="secondary">头像颜色</Text>
              <ColorPicker
                size="small"
                value={avatarColor}
                onChange={(c) => setAvatarColor(c.toHexString())}
              />
            </Space>
          </Flex>

          <Form
            form={profileForm}
            layout="vertical"
            style={{ flex: 1, minWidth: 280 }}
            initialValues={{
              username: "Jeff",
              email: "jeff@sjtu.edu.cn",
              bio: "计算机科学专业，研究方向：NLP、信息检索",
            }}
          >
            <Form.Item
              label="用户名"
              name="username"
              rules={[
                { required: true, message: "请输入用户名" },
                { min: 2, max: 20, message: "用户名长度 2-20 个字符" },
              ]}
            >
              <Input placeholder="用户名" />
            </Form.Item>

            <Form.Item
              label="邮箱"
              name="email"
              rules={[
                { required: true, message: "请输入邮箱" },
                { type: "email", message: "邮箱格式不正确" },
              ]}
            >
              <Input placeholder="your@email.com" />
            </Form.Item>

            <Form.Item label="个人简介" name="bio">
              <Input.TextArea rows={3} placeholder="介绍一下自己…" maxLength={200} showCount />
            </Form.Item>

            <Button type="primary" loading={savingProfile} onClick={handleSaveProfile}>
              保存资料
            </Button>
          </Form>
        </Flex>
      </Flex>
    </Card>
  );

  const notificationTab = (
    <Card variant="borderless">
      <Flex vertical gap={20}>
        <Flex justify="space-between" align="center">
          <Flex vertical gap={4}>
            <Text strong>每日论文摘要</Text>
            <Text type="secondary">每天推送新增论文的 AI 摘要到邮箱</Text>
          </Flex>
          <Switch checked={dailyDigest} onChange={setDailyDigest} />
        </Flex>

        <Divider style={{ margin: 0 }} />

        <Flex justify="space-between" align="center">
          <Flex vertical gap={4}>
            <Text strong>论文更新提醒</Text>
            <Text type="secondary">关注的论文有新版本或被引用时通知</Text>
          </Flex>
          <Switch checked={paperAlert} onChange={setPaperAlert} />
        </Flex>

        <Divider style={{ margin: 0 }} />

        <Flex justify="space-between" align="center">
          <Flex vertical gap={4}>
            <Text strong>订阅推送</Text>
            <Text type="secondary">订阅的主题有新增论文时通知</Text>
          </Flex>
          <Switch checked={subscriptionAlert} onChange={setSubscriptionAlert} />
        </Flex>

        <Button
          type="primary"
          onClick={async () => {
            await saveNotificationPreferences({
              dailyDigest,
              paperAlert,
              subscriptionAlert,
            });
            message.success("通知偏好已保存");
          }}
        >
          保存偏好
        </Button>
      </Flex>
    </Card>
  );

  const systemTab = (
    <Card variant="borderless">
      <Flex vertical gap={24}>
        <div>
          <Title level={4} style={{ marginBottom: 4 }}>界面主题</Title>
          <Text type="secondary">选择主题后会立即预览，保存后同步到当前账户。</Text>
        </div>

        <div className="theme-picker" role="radiogroup" aria-label="界面主题">
          {THEME_OPTIONS.map((option) => {
            const selected = themeName === option.value;
            return (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={selected}
                className={`theme-option${selected ? ' active' : ''}`}
                onClick={() => applyTheme(option.value)}
              >
                <span
                  className="theme-option-preview"
                  style={{ background: option.preview[0] }}
                  aria-hidden="true"
                >
                  <span style={{ background: option.preview[1] }} />
                  <i style={{ background: option.preview[2] }} />
                </span>
                <span className="theme-option-copy">
                  <strong>{option.label}</strong>
                  <small>{option.description}</small>
                </span>
                <span className="theme-option-check" aria-hidden="true">
                  {selected && <CheckOutlined />}
                </span>
              </button>
            );
          })}
        </div>

        <Button
          type="primary"
          loading={savingTheme}
          onClick={async () => {
            try {
              setSavingTheme(true);
              await saveSystemPreferences({ theme: themeName });
              message.success('主题设置已保存');
            } catch (error) {
              message.error(error.message || '主题设置保存失败');
            } finally {
              setSavingTheme(false);
            }
          }}
        >
          保存主题
        </Button>
      </Flex>
    </Card>
  );

  const securityTab = (
    <Card variant="borderless">
      <Form
        form={passwordForm}
        layout="vertical"
        style={{ maxWidth: 400 }}
      >
        <Form.Item
          label="当前密码"
          name="currentPassword"
          rules={[{ required: true, message: "请输入当前密码" }]}
        >
          <Input.Password placeholder="输入当前密码" />
        </Form.Item>

        <Form.Item
          label="新密码"
          name="newPassword"
          rules={[
            { required: true, message: "请输入新密码" },
            { min: 8, message: "密码至少 8 个字符" },
          ]}
        >
          <Input.Password placeholder="输入新密码" />
        </Form.Item>

        <Form.Item
          label="确认新密码"
          name="confirmPassword"
          rules={[{ required: true, message: "请再次输入新密码" }]}
        >
          <Input.Password placeholder="再次输入新密码" />
        </Form.Item>

        <Button
          type="primary"
          icon={<KeyOutlined />}
          loading={changingPassword}
          onClick={handleChangePassword}
        >
          修改密码
        </Button>
      </Form>
    </Card>
  );

  /* ---------- Tabs 配置 ---------- */
  const tabItems = [
    {
      key: "profile",
      label: "个人资料",
      icon: <UserOutlined />,
      children: profileTab,
    },
    {
      key: "notification",
      label: "通知偏好",
      icon: <BellOutlined />,
      children: notificationTab,
    },
    {
      key: "system",
      label: "主题外观",
      icon: <SettingOutlined />,
      children: systemTab,
    },
    {
      key: "security",
      label: "账户安全",
      icon: <SafetyOutlined />,
      children: securityTab,
    },
  ];

  return (
    <div className="page">
      <Title level={2}>用户设置</Title>
      <Text type="secondary" style={{ display: "block", marginBottom: 24 }}>
        配置个人偏好与账户信息
      </Text>

      <Tabs items={tabItems} tabBarStyle={{ marginBottom: 0 }} />
    </div>
  );
}
