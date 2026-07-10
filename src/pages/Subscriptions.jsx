import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Flex,
  List,
  Progress,
  Row,
  Segmented,
  Select,
  Space,
  Statistic,
  Switch,
  Tag,
  Timeline,
  Typography,
  message,
} from 'antd';
import {
  BellOutlined,
  BookOutlined,
  ClockCircleOutlined,
  FireOutlined,
  HistoryOutlined,
  LinkOutlined,
  MailOutlined,
  PushpinOutlined,
  ReadOutlined,
  ScheduleOutlined,
  StarOutlined,
  TagsOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import AsyncPageState from '../components/AsyncPageState';
import useAsyncResource from '../hooks/useAsyncResource';
import {
  getLearningCenter,
  updateFollowedTopic,
} from '../services/learningService';
import {
  getSubscriptionFeed,
  saveSubscriptionPreferences,
} from '../services/subscriptionService';

const { Paragraph, Text, Title } = Typography;

export default function Subscriptions() {
  const navigate = useNavigate();
  const resource = useAsyncResource(getLearningCenter, []);
  const feedResource = useAsyncResource(getSubscriptionFeed, []);
  const dailyDigest = feedResource.data?.dailyDigest;
  const historyBasedRecommendations = feedResource.data?.historyBasedRecommendations || [];
  const learningPapers = resource.data?.papers || [];
  const readingHistory = resource.data?.readingHistory || [];
  const [activeTab, setActiveTab] = useState('digest');
  const [topics, setTopics] = useState([]);
  const [digestEnabled, setDigestEnabled] = useState(true);
  const [pushTime, setPushTime] = useState('09:00');
  const [digestConfirmed, setDigestConfirmed] = useState(true);

  useEffect(() => {
    if (resource.data) setTopics(resource.data.topics);
  }, [resource.data]);

  const followedCount = useMemo(
    () => topics.filter((t) => t.followed).length,
    [topics],
  );

  const todayNewCount = useMemo(
    () =>
      topics
        .filter((t) => t.followed)
        .reduce((sum, t) => sum + t.newToday, 0),
    [topics],
  );

  const toggleTopic = async (topicId) => {
    const topic = topics.find((t) => t.id === topicId);
    if (!topic) return;
    try {
      const updatedTopic = await updateFollowedTopic(topicId, !topic.followed);
      setTopics((currentTopics) => currentTopics.map((item) => (
        item.id === topicId ? updatedTopic : item
      )));
      message.success(
        topic.followed ? `已取消关注「${topic.name}」` : `已关注「${topic.name}」`,
      );
    } catch (error) {
      message.error(error.message || '主题关注状态更新失败');
    }
  };

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
                      onClick={() => navigate(`/papers/${paper.id}`)}
                    >
                      阅读
                    </Button>,
                    <Button
                      key="arxiv"
                      type="link"
                      size="small"
                      icon={<LinkOutlined />}
                      href={`https://arxiv.org/abs/${paper.id}`}
                      target="_blank"
                    >
                      arXiv
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space size={8}>
                        <Text
                          strong
                          className="subscriptions-paper-link"
                          onClick={() => navigate(`/papers/${paper.id}`)}
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

  // ---- 主题推荐 ----
  const renderTopicRecommendations = () => {
    const followedTopicIds = topics
      .filter((t) => t.followed)
      .map((t) => t.id);

    const allHighlightPapers = dailyDigest.topics
      .filter((tg) => followedTopicIds.includes(tg.topicId))
      .flatMap((tg) =>
        tg.highlights.map((p) => ({
          ...p,
          topicName: tg.topicName,
        })),
      )
      .sort((a, b) => b.matchScore - a.matchScore);

    return (
      <div className="subscriptions-section">
        <Card
          variant="borderless"
          title={
            <Space>
              <FireOutlined />
              <span>基于关注主题的论文推荐</span>
            </Space>
          }
          extra={
            <Text type="secondary">
              共 {allHighlightPapers.length} 篇推荐论文，按匹配度排序
            </Text>
          }
        >
          {allHighlightPapers.length === 0 ? (
            <Empty description="暂无关註主题的推荐论文，请先关注感兴趣的研究主题" />
          ) : (
            <List
              className="subscriptions-recommend-list"
              dataSource={allHighlightPapers}
              renderItem={(paper) => (
                <List.Item
                  className="subscriptions-recommend-item"
                  actions={[
                    <Button
                      key="read"
                      type="primary"
                      size="small"
                      icon={<ReadOutlined />}
                      onClick={() => navigate(`/papers/${paper.id}`)}
                    >
                      阅读
                    </Button>,
                    <Button
                      key="save"
                      size="small"
                      icon={<BookOutlined />}
                      onClick={() => message.success('已加入阅读队列')}
                    >
                      加入队列
                    </Button>,
                    <Button
                      key="arxiv"
                      type="link"
                      size="small"
                      icon={<LinkOutlined />}
                      href={`https://arxiv.org/abs/${paper.id}`}
                      target="_blank"
                    >
                      arXiv
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
                          onClick={() => navigate(`/papers/${paper.id}`)}
                        >
                          {paper.title}
                        </Text>
                        <Tag color="geekblue">{paper.topicName}</Tag>
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
          )}
        </Card>
      </div>
    );
  };

  // ---- 订阅管理 ----
  const renderTopicManagement = () => (
    <div className="subscriptions-section">
      <Card
        variant="borderless"
        title={
          <Space>
            <TagsOutlined />
            <span>研究主题订阅管理</span>
          </Space>
        }
        extra={
          <Text type="secondary">
            已关注 {followedCount} / {topics.length} 个主题
          </Text>
        }
      >
        <Row gutter={[16, 16]} className="subscriptions-topic-grid">
          {topics.map((topic) => (
            <Col xs={24} md={12} key={topic.id}>
              <Card
                variant="borderless"
                className={
                  topic.followed
                    ? 'subscriptions-topic-card subscriptions-topic-card--active'
                    : 'subscriptions-topic-card'
                }
                size="small"
                title={
                  <Flex align="center" justify="space-between" gap={8}>
                    <Text strong>{topic.name}</Text>
                    <Switch
                      checked={topic.followed}
                      onChange={() => toggleTopic(topic.id)}
                      checkedChildren="已关注"
                      unCheckedChildren="未关注"
                    />
                  </Flex>
                }
              >
                <Space orientation="vertical" size={10} className="subscriptions-topic-body">
                  <Row gutter={[16, 8]}>
                    <Col span={8}>
                      <Statistic
                        title="收录论文"
                        value={topic.paperCount}
                        suffix="篇"
                        valueStyle={{ fontSize: '1.1rem' }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title="今日新增"
                        value={topic.newToday}
                        suffix="篇"
                        valueStyle={{
                          fontSize: '1.1rem',
                          color: topic.newToday > 0 ? '#ff4d4f' : undefined,
                        }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title="匹配度"
                        value={topic.matchRate}
                        suffix="%"
                        valueStyle={{ fontSize: '1.1rem' }}
                      />
                    </Col>
                  </Row>
                  <div>
                    <Text type="secondary">匹配度趋势</Text>
                    <Progress
                      percent={topic.matchRate}
                      size="small"
                      strokeColor={
                        topic.matchRate >= 80
                          ? '#52c41a'
                          : topic.matchRate >= 60
                            ? '#4f6ef7'
                            : '#faad14'
                      }
                    />
                  </div>
                  <Flex align="center" gap={6}>
                    <ScheduleOutlined />
                    <Text type="secondary">推送频率：{topic.digestTime}</Text>
                  </Flex>
                  <Space size={[6, 6]} wrap>
                    {topic.keywords.map((kw) => (
                      <Tag key={kw} color={topic.followed ? 'blue' : 'default'}>
                        {kw}
                      </Tag>
                    ))}
                  </Space>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      </Card>
    </div>
  );

  // ---- 基于阅读历史的推荐 ----
  const renderHistoryRecommendations = () => (
    <div className="subscriptions-section">
      <Card
        variant="borderless"
        title={
          <Space>
            <HistoryOutlined />
            <span>基于阅读历史的论文推荐</span>
          </Space>
        }
        extra={
          <Text type="secondary">
            共 {historyBasedRecommendations.length} 篇推荐，来源自你的阅读记录
          </Text>
        }
      >
        <List
          className="subscriptions-history-list"
          dataSource={historyBasedRecommendations}
          renderItem={(paper) => (
            <List.Item
              className="subscriptions-history-item"
              actions={[
                <Button
                  key="read"
                  type="primary"
                  size="small"
                  icon={<ReadOutlined />}
                  onClick={() => navigate(`/papers/${paper.id}`)}
                >
                  阅读
                </Button>,
                <Button
                  key="save"
                  size="small"
                  icon={<BookOutlined />}
                  onClick={() => message.success('已加入阅读队列')}
                >
                  加入队列
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
                      onClick={() => navigate(`/papers/${paper.id}`)}
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
                    <div className="subscriptions-source-paper">
                      <BookOutlined />
                      <Text type="secondary">
                        来源阅读：
                        <Button
                          type="link"
                          size="small"
                          className="subscriptions-source-link"
                          onClick={() =>
                            navigate(`/papers/${paper.sourcePaperId}`)
                          }
                        >
                          {paper.sourcePaperTitle}
                        </Button>
                      </Text>
                    </div>
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

  // ---- 阅读历史时间线 ----
  const renderReadingTimeline = () => (
    <div className="subscriptions-section">
      <Card
        variant="borderless"
        title={
          <Space>
            <ClockCircleOutlined />
            <span>最近阅读动态</span>
          </Space>
        }
      >
        <Timeline
          items={readingHistory.map((item) => {
            const paper = learningPapers.find((p) => p.id === item.paperId);
            return {
              color: item.action === '完成阅读' ? 'green' : 'blue',
              children: (
                <Space orientation="vertical" size={2}>
                  <Flex align="center" gap={8}>
                    <Tag
                      color={item.action === '完成阅读' ? 'success' : 'processing'}
                    >
                      {item.action}
                    </Tag>
                    <Text strong>{paper?.title || item.paperId}</Text>
                  </Flex>
                  <Text type="secondary">{item.detail}</Text>
                  <Text type="secondary">{item.time}</Text>
                </Space>
              ),
            };
          })}
        />
      </Card>
    </div>
  );

  if (resource.loading || resource.error || feedResource.loading || feedResource.error) {
    return (
      <main className="subscriptions-page">
        <AsyncPageState
          loading={resource.loading || feedResource.loading}
          error={resource.error || feedResource.error}
          onRetry={() => {
            resource.reload();
            feedResource.reload();
          }}
        />
      </main>
    );
  }

  return (
    <main className="subscriptions-page">
      {/* ---- 头部 ---- */}
      <Flex
        className="subscriptions-header"
        align="flex-start"
        justify="space-between"
        gap={16}
        wrap="wrap"
      >
        <div>
          <Title level={2}>推荐与订阅</Title>
          <Paragraph>
            按研究主题订阅，每日推送新增论文摘要。基于你的关注主题和阅读历史，智能推荐最相关的论文。
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
          <Button icon={<ScheduleOutlined />} onClick={() => setActiveTab('topics')}>
            管理订阅
          </Button>
        </Space>
      </Flex>

      {/* ---- 统计卡片 ---- */}
      <Row gutter={[16, 16]} className="subscriptions-stats">
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic
              title="已订阅主题"
              value={followedCount}
              suffix={`/ ${topics.length}`}
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
              value={historyBasedRecommendations.length + dailyDigest.topics.reduce((s, t) => s + t.highlights.length, 0)}
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
            { label: '主题推荐', value: 'recommend', icon: <FireOutlined /> },
            { label: '订阅管理', value: 'topics', icon: <TagsOutlined /> },
            { label: '历史推荐', value: 'history', icon: <HistoryOutlined /> },
            { label: '阅读动态', value: 'timeline', icon: <ClockCircleOutlined /> },
          ]}
        />
      </Card>

      {/* ---- 内容区 ---- */}
      {activeTab === 'digest' && renderDailyDigest()}
      {activeTab === 'recommend' && renderTopicRecommendations()}
      {activeTab === 'topics' && renderTopicManagement()}
      {activeTab === 'history' && renderHistoryRecommendations()}
      {activeTab === 'timeline' && renderReadingTimeline()}
    </main>
  );
}
