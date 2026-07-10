import { useMemo, useState } from 'react';
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
import {
  followedTopics,
  learningPapers,
  readingHistory,
} from '../data/learningData';

const { Paragraph, Text, Title } = Typography;

// ---- 每日摘要模拟数据 ----
const dailyDigest = {
  date: '2026-07-09',
  summary:
    '今日共追踪到你关注的 5 个主题中有 12 篇新增论文，其中 3 篇与你的阅读历史高度相关，建议优先阅读。',
  topics: [
    {
      topicId: 'rag',
      topicName: 'Retrieval-Augmented Generation',
      newCount: 5,
      highlights: [
        {
          id: '2501.01001',
          title: 'RAG with Multi-Hop Evidence Retrieval for Scientific QA',
          authors: ['Jun Wang', 'Alice Chen'],
          categories: ['cs.CL', 'cs.AI'],
          matchScore: 94,
          reason: '与你近期阅读的 Agent 检索链高度相关',
          abstract:
            '提出多跳证据检索增强生成框架，通过迭代查询分解和证据链构建，提升科学问答中的复杂推理能力。',
        },
        {
          id: '2501.01002',
          title: 'Citation-Aware RAG: Grounding LLM Answers with Paper Evidence',
          authors: ['Bo Wang', 'Carol Smith'],
          categories: ['cs.CL'],
          matchScore: 88,
          reason: '与问答出处定位研究方向匹配',
          abstract:
            '在 RAG 流程中引入引用感知机制，确保生成答案可追溯到具体论文段落，降低幻觉率。',
        },
      ],
    },
    {
      topicId: 'concept-graph',
      topicName: '论文概念图谱',
      newCount: 2,
      highlights: [
        {
          id: '2501.02001',
          title: 'Iterative Concept Graph Refinement via Section-Aware Parsing',
          authors: ['David Liu', 'Emma Brown'],
          categories: ['cs.CL', 'cs.IR'],
          matchScore: 91,
          reason: '与你关注的章节解析和概念合并策略一致',
          abstract:
            '通过章节结构感知解析和迭代归并，构建高质量学术概念图谱，减少重复节点和错误关系。',
        },
      ],
    },
    {
      topicId: 'paper-recommendation',
      topicName: '个性化论文推荐',
      newCount: 1,
      highlights: [
        {
          id: '2501.03001',
          title: 'Collaborative Filtering Meets Semantic Search for ArXiv Papers',
          authors: ['Olivia Martin', 'Hao Chen'],
          categories: ['cs.IR'],
          matchScore: 79,
          reason: '与阅读行为建模研究相关',
          abstract:
            '结合协同过滤和语义搜索的混合推荐方法，在 ArXiv 数据集上取得优于纯协同或纯语义方法的效果。',
        },
      ],
    },
    {
      topicId: 'llm-finetuning',
      topicName: '大模型高效微调',
      newCount: 3,
      highlights: [
        {
          id: '2501.04001',
          title: 'Dynamic LoRA Allocation with Importance Ranking',
          authors: ['Sarah Chen', 'Raj Patel'],
          categories: ['cs.LG', 'cs.CL'],
          matchScore: 86,
          reason: '与你已读的 Adaptive LoRA 论文延续性很强',
          abstract:
            '提出基于参数重要性排名的动态 LoRA 秩分配策略，在更少的可训练参数下实现更优的领域适配效果。',
        },
      ],
    },
    {
      topicId: 'qa',
      topicName: '科学问答与引用定位',
      newCount: 1,
      highlights: [
        {
          id: '2501.05001',
          title: 'Long-Range Citation Grounding for Multi-Paper QA',
          authors: ['Nora Kim', 'Ivan Petrov'],
          categories: ['cs.CL'],
          matchScore: 82,
          reason: '与 Long-Context Scientific QA 方法论互补',
          abstract:
            '面向多论文场景的长距离引用定位方法，在 Qasper 和 PaperQA 基准上显著提升答案可验证性。',
        },
      ],
    },
  ],
};

// ---- 基于阅读历史的推荐 ----
const historyBasedRecommendations = [
  {
    id: '2502.06001',
    title: 'Self-Evolving Agent Architectures for Continuous Literature Monitoring',
    authors: ['Alice Chen', 'David Liu'],
    categories: ['cs.AI', 'cs.CL'],
    matchScore: 93,
    sourcePaperId: '2406.01234',
    sourcePaperTitle: 'Retrieval-Augmented Agents for Scientific Literature Review',
    reason: '基于你阅读的 RAG Agent 论文，该工作将检索增强智能体从单次综述扩展为持续监听框架',
    abstract:
      '提出一种自进化智能体架构，可持续监听新发表文献，自动更新知识库和综述摘要。',
  },
  {
    id: '2502.06002',
    title: 'Multi-Granularity Concept Alignment Across Research Communities',
    authors: ['Emma Brown', 'David Liu'],
    categories: ['cs.CL', 'cs.IR'],
    matchScore: 89,
    sourcePaperId: '2406.05678',
    sourcePaperTitle: 'Concept Graph Construction from Research Papers',
    reason: '基于你阅读的概念图谱论文，该工作解决了跨社区概念对齐和归并问题',
    abstract:
      '提出多粒度概念对齐方法，桥接不同研究社区对相似概念的命名差异，提升知识图谱互操作性。',
  },
  {
    id: '2502.06003',
    title: 'Behavior-Aware Cold-Start Recommendation via Topic Priors',
    authors: ['Olivia Martin', 'Grace Miller'],
    categories: ['cs.IR', 'cs.HC'],
    matchScore: 85,
    sourcePaperId: '2404.06543',
    sourcePaperTitle: 'Reading Behavior Modeling for Personalized Paper Recommendation',
    reason: '基于你阅读的推荐建模论文，该工作解决了冷启动推荐的难题',
    abstract:
      '利用显式主题订阅作为先验信息，为新用户提供可靠推荐，并在行为数据积累后平滑过渡到行为模型。',
  },
  {
    id: '2502.06004',
    title: 'Reasoning over Citation Graphs with Hierarchical Attention',
    authors: ['Nora Kim', 'Maya Singh'],
    categories: ['cs.CL'],
    matchScore: 83,
    sourcePaperId: '2405.11890',
    sourcePaperTitle: 'Long-Context Scientific Question Answering with Citation Grounding',
    reason: '基于你阅读的引用定位论文，该工作引入层次注意力机制提升引用图推理',
    abstract:
      '提出层次注意力引用图推理方法，在问答中同时考虑引用关系和段落内容，提升推理深度。',
  },
  {
    id: '2502.06005',
    title: 'Sparse-Gated Mixture of LoRA Experts for Multi-Domain Adaptation',
    authors: ['Raj Patel', 'Sarah Chen'],
    categories: ['cs.LG', 'cs.CL'],
    matchScore: 81,
    sourcePaperId: '2405.08777',
    sourcePaperTitle: 'Adaptive LoRA for Efficient Domain Adaptation of Large Language Models',
    reason: '基于你关注的 LoRA 微调方向，该工作探索多领域适配',
    abstract:
      '使用稀疏门控混合专家机制，让多个 LoRA 模块协同工作，实现单模型多领域高效适配。',
  },
];

export default function Subscriptions() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('digest');
  const [topics, setTopics] = useState(followedTopics);
  const [digestEnabled, setDigestEnabled] = useState(true);
  const [pushTime, setPushTime] = useState('09:00');
  const [digestConfirmed, setDigestConfirmed] = useState(true);

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

  const toggleTopic = (topicId) => {
    setTopics((prev) =>
      prev.map((t) =>
        t.id === topicId ? { ...t, followed: !t.followed } : t,
      ),
    );
    const topic = topics.find((t) => t.id === topicId);
    if (topic) {
      message.success(
        topic.followed ? `已取消关注「${topic.name}」` : `已关注「${topic.name}」`,
      );
    }
  };

  const handlePushTimeChange = (value) => {
    setPushTime(value);
    message.success(`每日推送时间已更新为 ${value}`);
  };

  const handleDigestToggle = (checked) => {
    setDigestEnabled(checked);
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
                      <Space direction="vertical" size={4}>
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
                      <Space direction="vertical" size={4}>
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
                <Space direction="vertical" size={10} className="subscriptions-topic-body">
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
                  <Space direction="vertical" size={4}>
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
                <Space direction="vertical" size={2}>
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
