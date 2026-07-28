import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Flex,
  Form,
  List,
  Modal,
  Progress,
  Row,
  Segmented,
  Select,
  Space,
  Statistic,
  Switch,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  BellOutlined,
  BookOutlined,
  DeleteOutlined,
  EditOutlined,
  FireOutlined,
  MailOutlined,
  PushpinOutlined,
  PlusOutlined,
  ReadOutlined,
  ScheduleOutlined,
  TagsOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import AsyncPageState from '../components/AsyncPageState';
import useAsyncResource from '../hooks/useAsyncResource';
import { addPaperToLibrary } from '../services/paperService';
import {
  createSubscription,
  deleteSubscription,
  getSubscriptionFeed,
  listSubscriptions,
  saveSubscriptionPreferences,
  updateSubscription,
} from '../services/subscriptionService';

const { Paragraph, Text, Title } = Typography;

export default function Subscriptions() {
  const feedResource = useAsyncResource(getSubscriptionFeed, []);
  const subscriptionsResource = useAsyncResource(listSubscriptions, []);
  const [subscriptionForm] = Form.useForm();
  const managementRef = useRef(null);
  const dailyDigest = feedResource.data?.dailyDigest;
  const recommendations = feedResource.data?.recommendations || [];
  const [activeTab, setActiveTab] = useState('digest');
  const [subscriptions, setSubscriptions] = useState([]);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingSubscription, setEditingSubscription] = useState(null);
  const [subscriptionSaving, setSubscriptionSaving] = useState(false);
  const [updatingSubscriptionId, setUpdatingSubscriptionId] = useState(null);
  const [addingPaperIds, setAddingPaperIds] = useState(() => new Set());
  const [addedPaperIds, setAddedPaperIds] = useState(() => new Set());
  const [digestEnabled, setDigestEnabled] = useState(true);
  const [pushTime, setPushTime] = useState('09:00');
  const [digestConfirmed, setDigestConfirmed] = useState(true);

  useEffect(() => {
    if (subscriptionsResource.data) setSubscriptions(subscriptionsResource.data);
  }, [subscriptionsResource.data]);

  const followedCount = useMemo(
    () => subscriptions.filter((subscription) => subscription.enabled).length,
    [subscriptions],
  );

  const todayNewCount = useMemo(
    () => (dailyDigest?.topics || []).reduce((sum, topic) => sum + topic.newCount, 0),
    [dailyDigest?.topics],
  );

  const openSubscriptionEditor = (subscription = null) => {
    setEditingSubscription(subscription);
    subscriptionForm.setFieldsValue({
      categories: subscription?.categories || [],
      enabled: subscription?.enabled ?? true,
      frequency: subscription?.frequency || 'daily',
      keywords: subscription?.keywords || [],
    });
    setEditorOpen(true);
  };

  const handleSubscriptionSubmit = async () => {
    const values = await subscriptionForm.validateFields();
    setSubscriptionSaving(true);
    try {
      if (editingSubscription) {
        const updated = await updateSubscription(editingSubscription.id, values);
        setSubscriptions((current) => current.map((subscription) => (
          subscription.id === updated.id ? updated : subscription
        )));
        message.success('订阅已更新');
      } else {
        const created = await createSubscription(values);
        setSubscriptions((current) => [created, ...current]);
        message.success('订阅已创建');
      }
      setEditorOpen(false);
      setEditingSubscription(null);
      subscriptionForm.resetFields();
      await feedResource.reload();
    } catch (error) {
      if (error?.errorFields) return;
      message.error(error.message || '订阅保存失败');
    } finally {
      setSubscriptionSaving(false);
    }
  };

  const handleSubscriptionToggle = async (subscription, enabled) => {
    setUpdatingSubscriptionId(subscription.id);
    try {
      const updated = await updateSubscription(subscription.id, { ...subscription, enabled });
      setSubscriptions((current) => current.map((item) => (
        item.id === updated.id ? updated : item
      )));
      message.success(enabled ? '订阅已启用' : '订阅已暂停');
      await feedResource.reload();
    } catch (error) {
      message.error(error.message || '订阅状态更新失败');
    } finally {
      setUpdatingSubscriptionId(null);
    }
  };

  const handleSubscriptionDelete = (subscription) => {
    Modal.confirm({
      title: '删除订阅？',
      content: `删除后将不再推送与「${subscription.name}」相关的论文摘要。`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteSubscription(subscription.id);
          setSubscriptions((current) => current.filter((item) => item.id !== subscription.id));
          message.success('订阅已删除');
          await feedResource.reload();
        } catch (error) {
          message.error(error.message || '订阅删除失败');
          throw error;
        }
      },
    });
  };

  const showSubscriptionManagement = () => {
    setActiveTab('topics');
    window.requestAnimationFrame(() => {
      managementRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  };

  const handleAddPaperToLibrary = async (paper) => {
    setAddingPaperIds((current) => new Set(current).add(paper.id));
    try {
      const result = await addPaperToLibrary(paper.id);
      setAddedPaperIds((current) => new Set(current).add(paper.id));
      message.success(result.added ? '已加入论文列表' : '该论文已在论文列表中');
    } catch (error) {
      message.error(error.message || '加入论文列表失败');
    } finally {
      setAddingPaperIds((current) => {
        const next = new Set(current);
        next.delete(paper.id);
        return next;
      });
    }
  };

  const isPaperInLibrary = (paper) => paper.inLibrary || addedPaperIds.has(paper.id);

  const handlePushTimeChange = async (value) => {
    setPushTime(value);
    await saveSubscriptionPreferences({ pushTime: value });
    message.success(`每日推送时间已更新为 ${value}`);
  };

  const handleDigestToggle = async (checked) => {
    setDigestEnabled(checked);
    await saveSubscriptionPreferences({ digestEnabled: checked });
    message.success(checked ? '每日摘要推送已开启' : '每日摘要推送已关闭');
  };

  // ---- 每日摘要 ----
  const renderDailyDigest = () => (
    <div className="subscriptions-section">
      <Card
        variant="borderless"
        className="subscriptions-digest-hero"
        title={
          <Space>
            <BellOutlined />
            <span>今日摘要推送 · {dailyDigest.date}</span>
            {digestConfirmed && <Tag color="success">已推送</Tag>}
          </Space>
        }
        extra={
          <Space>
            <Text type="secondary">推送时间：</Text>
            <Select
              size="small"
              value={pushTime}
              onChange={handlePushTimeChange}
              style={{ width: 100 }}
              options={[
                { label: '08:00', value: '08:00' },
                { label: '09:00', value: '09:00' },
                { label: '12:00', value: '12:00' },
                { label: '18:00', value: '18:00' },
              ]}
            />
            <Switch
              checked={digestEnabled}
              onChange={handleDigestToggle}
              checkedChildren="开"
              unCheckedChildren="关"
            />
          </Space>
        }
      >
        <Paragraph className="subscriptions-digest-summary">
          {dailyDigest.summary}
        </Paragraph>

        {dailyDigest.topics.map((topicGroup) => (
          <Card
            key={topicGroup.topicId}
            variant="borderless"
            size="small"
            className="subscriptions-digest-topic"
            title={
              <Flex align="center" gap={8}>
                <Text strong>{topicGroup.topicName}</Text>
                <Badge
                  count={`${topicGroup.newCount} 篇新增`}
                  style={{ backgroundColor: '#4f6ef7' }}
                />
              </Flex>
            }
          >
            <List
              dataSource={topicGroup.highlights}
              renderItem={(paper) => (
                <List.Item
                  key={paper.id}
                  className="subscriptions-digest-paper"
                  actions={[
                    <Button
                      key="read"
                      type="primary"
                      size="small"
                      icon={<ReadOutlined />}
                      href={paper.arxivUrl}
                      target="_blank"
                      rel="noreferrer"
                      disabled={!paper.arxivUrl}
                    >
                      阅读
                    </Button>,
                    <Button
                      key="add"
                      size="small"
                      icon={<BookOutlined />}
                      loading={addingPaperIds.has(paper.id)}
                      disabled={isPaperInLibrary(paper)}
                      onClick={() => handleAddPaperToLibrary(paper)}
                    >
                      {isPaperInLibrary(paper) ? '已在论文列表' : '加入论文列表'}
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space size={8}>
                        <Text
                          strong
                          className="subscriptions-paper-link"
                          onClick={() => paper.arxivUrl && window.open(paper.arxivUrl, '_blank', 'noopener,noreferrer')}
                        >
                          {paper.title}
                        </Text>
                        <Tag color="blue">匹配度 {paper.matchScore}%</Tag>
                      </Space>
                    }
                    description={
                      <Space orientation="vertical" size={4}>
                        <Text type="secondary">
                          {paper.authors.join(', ')} · {paper.categories.join(', ')}
                        </Text>
                        <Text className="subscriptions-reason-text">
                          <PushpinOutlined /> {paper.reason}
                        </Text>
                        <Paragraph
                          ellipsis={{ rows: 2 }}
                          className="subscriptions-paper-abstract"
                        >
                          {paper.abstract}
                        </Paragraph>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        ))}
      </Card>
    </div>
  );

  // ---- 订阅管理 ----
  const renderTopicManagement = () => (
    <div className="subscriptions-section" ref={managementRef}>
      <Card
        variant="borderless"
        title={
          <Space>
            <TagsOutlined />
            <span>研究主题订阅管理</span>
          </Space>
        }
        extra={
          <Space>
            <Text type="secondary">
              已启用 {followedCount} / {subscriptions.length} 个订阅
            </Text>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => openSubscriptionEditor()}
            >
              新增订阅
            </Button>
          </Space>
        }
      >
        <List
          dataSource={subscriptions}
          locale={{ emptyText: <Empty description="暂无订阅主题，请先新增订阅" /> }}
          renderItem={(subscription) => (
            <List.Item
              className="subscriptions-management-item"
              actions={[
                <Switch
                  key="enabled"
                  checked={subscription.enabled}
                  checkedChildren="已启用"
                  unCheckedChildren="已暂停"
                  loading={updatingSubscriptionId === subscription.id}
                  onChange={(enabled) => handleSubscriptionToggle(subscription, enabled)}
                />,
                <Button
                  key="edit"
                  type="text"
                  icon={<EditOutlined />}
                  title="编辑订阅"
                  onClick={() => openSubscriptionEditor(subscription)}
                />,
                <Button
                  key="delete"
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  title="删除订阅"
                  onClick={() => handleSubscriptionDelete(subscription)}
                />,
              ]}
            >
              <List.Item.Meta
                title={
                  <Space wrap>
                    <Text strong>{subscription.name}</Text>
                    <Tag color={subscription.frequency === 'daily' ? 'blue' : 'geekblue'}>
                      {subscription.frequency === 'daily' ? '每日推送' : '每周推送'}
                    </Tag>
                  </Space>
                }
                description={
                  <Space orientation="vertical" size={6}>
                    <Space size={[6, 6]} wrap>
                      {subscription.keywords.map((keyword) => (
                        <Tag key={keyword}>{keyword}</Tag>
                      ))}
                    </Space>
                    {subscription.categories.length > 0 && (
                      <Text type="secondary">
                        arXiv 分类：{subscription.categories.join(', ')}
                      </Text>
                    )}
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      </Card>
    </div>
  );

  const renderRecommendations = () => (
    <div className="subscriptions-section">
      <Card
        variant="borderless"
        title={
          <Space>
            <FireOutlined />
            <span>个性化论文推荐</span>
          </Space>
        }
        extra={
          <Text type="secondary">
            共 {recommendations.length} 篇推荐，基于收藏与研究主题
          </Text>
        }
      >
        <List
          className="subscriptions-personalized-list"
          dataSource={recommendations}
          renderItem={(paper) => (
            <List.Item
              className="subscriptions-personalized-item"
              actions={[
                <Button
                  key="read"
                  type="primary"
                  size="small"
                  icon={<ReadOutlined />}
                  href={paper.arxivUrl}
                  target="_blank"
                  rel="noreferrer"
                  disabled={!paper.arxivUrl}
                >
                  阅读
                </Button>,
                <Button
                  key="add"
                  size="small"
                  icon={<BookOutlined />}
                  loading={addingPaperIds.has(paper.id)}
                  disabled={isPaperInLibrary(paper)}
                  onClick={() => handleAddPaperToLibrary(paper)}
                >
                  {isPaperInLibrary(paper) ? '已在论文列表' : '加入论文列表'}
                </Button>,
              ]}
            >
              <List.Item.Meta
                avatar={
                  <Progress
                    type="circle"
                    percent={paper.matchScore}
                    size={52}
                    strokeColor={
                      paper.matchScore >= 90
                        ? '#52c41a'
                        : paper.matchScore >= 80
                          ? '#4f6ef7'
                          : '#faad14'
                    }
                    format={(percent) => `${percent}%`}
                  />
                }
                title={
                  <Flex align="center" gap={8} wrap="wrap">
                    <Text
                      strong
                      className="subscriptions-paper-link"
                      onClick={() => paper.arxivUrl && window.open(paper.arxivUrl, '_blank', 'noopener,noreferrer')}
                    >
                      {paper.title}
                    </Text>
                    <Tag
                      color={
                        paper.matchScore >= 90
                          ? 'success'
                          : paper.matchScore >= 80
                            ? 'processing'
                            : 'warning'
                      }
                    >
                      匹配 {paper.matchScore}%
                    </Tag>
                  </Flex>
                }
                description={
                  <Space orientation="vertical" size={4}>
                    <Text type="secondary">
                      {paper.authors.join(', ')} · {paper.categories.join(', ')}
                    </Text>
                    <Text className="subscriptions-reason-text">
                      <PushpinOutlined /> {paper.reason}
                    </Text>
                  </Space>
                }
              />
            </List.Item>
          )}
        />
      </Card>
    </div>
  );

  if (
    feedResource.loading || feedResource.error
    || subscriptionsResource.loading || subscriptionsResource.error
  ) {
    return (
      <main className="page-stack subscriptions-page">
        <AsyncPageState
          loading={feedResource.loading || subscriptionsResource.loading}
          error={feedResource.error || subscriptionsResource.error}
          onRetry={() => {
            feedResource.reload();
            subscriptionsResource.reload();
          }}
        />
      </main>
    );
  }

  return (
    <main className="page-stack subscriptions-page">
      {/* ---- 头部 ---- */}
      <Flex
        className="page-header"
        align="flex-start"
        justify="space-between"
        gap={16}
        wrap="wrap"
      >
        <div>
          <Title level={2}>推荐与订阅</Title>
          <Paragraph>
            按研究主题订阅，每日推送新增论文摘要，并结合收藏与关注主题推荐相关论文。
          </Paragraph>
        </div>
        <Space wrap>
          <Button
            type="primary"
            icon={<MailOutlined />}
            onClick={() => message.success('测试推送已发送')}
          >
            立即推送
          </Button>
          <Button icon={<ScheduleOutlined />} onClick={showSubscriptionManagement}>
            管理订阅
          </Button>
        </Space>
      </Flex>

      {/* ---- 统计卡片 ---- */}
      <Row gutter={[16, 16]} className="stats-strip">
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic
              title="已订阅主题"
              value={followedCount}
              suffix={`/ ${subscriptions.length}`}
              prefix={<TagsOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic
              title="今日新增论文"
              value={todayNewCount}
              suffix="篇"
              prefix={<FireOutlined />}
              valueStyle={{ color: todayNewCount > 0 ? '#ff4d4f' : undefined }}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic
              title="推荐论文"
              value={recommendations.length + dailyDigest.topics.reduce((s, t) => s + t.highlights.length, 0)}
              suffix="篇"
              prefix={<TrophyOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic
              title="摘要推送"
              value={digestEnabled ? '已开启' : '已关闭'}
              prefix={<BellOutlined />}
              valueStyle={{
                color: digestEnabled ? '#52c41a' : '#8c8c8c',
                fontSize: '1.3rem',
              }}
            />
          </Card>
        </Col>
      </Row>

      {/* ---- 标签切换 ---- */}
      <Card variant="borderless" className="subscriptions-tab-card">
        <Segmented
          value={activeTab}
          onChange={setActiveTab}
          block
          options={[
            { label: '每日摘要', value: 'digest', icon: <BellOutlined /> },
            { label: '订阅管理', value: 'topics', icon: <TagsOutlined /> },
            { label: '个性推荐', value: 'personalized', icon: <FireOutlined /> },
          ]}
        />
      </Card>

      {/* ---- 内容区 ---- */}
      {activeTab === 'digest' && renderDailyDigest()}
      {activeTab === 'topics' && renderTopicManagement()}
      {activeTab === 'personalized' && renderRecommendations()}

      <Modal
        title={editingSubscription ? '编辑订阅' : '新增订阅'}
        open={editorOpen}
        okText={editingSubscription ? '保存' : '创建'}
        cancelText="取消"
        confirmLoading={subscriptionSaving}
        onOk={handleSubscriptionSubmit}
        onCancel={() => {
          setEditorOpen(false);
          setEditingSubscription(null);
          subscriptionForm.resetFields();
        }}
        forceRender
      >
        <Form form={subscriptionForm} layout="vertical" preserve={false}>
          <Form.Item
            name="keywords"
            label="主题关键词"
            rules={[{ required: true, type: 'array', min: 1, message: '请至少输入一个主题关键词' }]}
          >
            <Select
              mode="tags"
              tokenSeparators={[',']}
              placeholder="例如：RAG、scientific question answering"
            />
          </Form.Item>
          <Form.Item name="categories" label="arXiv 分类（可选）">
            <Select
              mode="tags"
              tokenSeparators={[',']}
              placeholder="例如：cs.AI、cs.CL"
            />
          </Form.Item>
          <Form.Item name="frequency" label="推送频率" rules={[{ required: true }]}>
            <Select options={[
              { label: '每日推送', value: 'daily' },
              { label: '每周推送', value: 'weekly' },
            ]} />
          </Form.Item>
          <Form.Item name="enabled" label="订阅状态" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="暂停" />
          </Form.Item>
        </Form>
      </Modal>
    </main>
  );
}
