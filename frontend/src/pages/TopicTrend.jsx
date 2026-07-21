import { useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Flex,
  Progress,
  Row,
  Space,
  Table,
  Tag,
  Timeline,
  Typography,
} from 'antd';
import {
  ArrowLeftOutlined,
  BookOutlined,
  BranchesOutlined,
  CalendarOutlined,
  FileTextOutlined,
  LineChartOutlined,
  LinkOutlined,
  TagsOutlined,
} from '@ant-design/icons';
import TrendLine from '../components/TrendLine';
import AsyncPageState from '../components/AsyncPageState';
import useAsyncResource from '../hooks/useAsyncResource';
import {
  getSeriesForRange,
  getTrendDetail,
  getTrendStatus,
} from '../services/trendService';

const { Paragraph, Text, Title } = Typography;

export default function TopicTrend() {
  const { topicId } = useParams();
  const navigate = useNavigate();
  const resource = useAsyncResource(() => getTrendDetail(topicId), [topicId]);
  const topic = resource.data?.topic;
  const trendTopics = resource.data?.topics || [];

  const topicRank = useMemo(() => {
    if (!topic) return null;

    if (resource.data?.topicRank) return resource.data.topicRank;

    return (
      [...trendTopics]
        .sort((left, right) => right.trend - left.trend)
        .findIndex((item) => item.id === topic.id) + 1
    );
  }, [resource.data?.topicRank, topic, trendTopics]);

  if (resource.loading || resource.error) {
    return (
      <div className="page">
        <AsyncPageState
          loading={resource.loading}
          error={resource.error}
          onRetry={resource.reload}
        />
      </div>
    );
  }

  if (!topic) {
    return (
      <div className="page">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/trends')}>
          返回研究脉络
        </Button>
        <Empty
          className="concept-empty"
          description={`没有找到研究主题：${topicId}`}
        />
      </div>
    );
  }

  const status = getTrendStatus(topic);
  const relatedConcepts = resource.data.relatedConcepts;
  const milestones = resource.data.milestones;
  const stages = resource.data.stages;
  const topicSignals = resource.data.signals;

  const paperColumns = [
    {
      title: '论文',
      dataIndex: 'title',
      render: (_, paper) => (
        <Space orientation="vertical" size={2}>
          <Button type="link" onClick={() => navigate(`/papers/${paper.id}`)}>
            {paper.title}
          </Button>
          <Text type="secondary">arXiv: {paper.arxivId}</Text>
        </Space>
      ),
    },
    {
      title: '年份',
      dataIndex: 'year',
      width: 96,
    },
    {
      title: '研究作用',
      dataIndex: 'role',
      width: 190,
      render: (role) => <Tag color="geekblue">{role}</Tag>,
    },
  ];

  const relationColumns = [
    {
      title: '相关主题',
      dataIndex: ['concept', 'name'],
      render: (_, relation) =>
        relation.exists ? (
          <Button
            type="link"
            icon={<LinkOutlined />}
            onClick={() => navigate(`/trends/${relation.concept.id}`)}
          >
            {relation.concept.name}
          </Button>
        ) : (
          <Space>
            <Text>{relation.concept.name}</Text>
            <Tag>整理中</Tag>
          </Space>
        ),
    },
    {
      title: '关系',
      dataIndex: 'type',
      width: 120,
      render: (type) => <Tag>{type}</Tag>,
    },
    {
      title: '强度',
      dataIndex: 'strength',
      width: 170,
      render: (strength) => <Progress percent={strength} size="small" />,
    },
  ];

  return (
    <main className="topic-trend-page">
      <Space className="topic-trend-toolbar">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/trends')}>
          返回研究脉络
        </Button>
        <Button icon={<TagsOutlined />} onClick={() => navigate('/wiki')}>
          知识 Wiki
        </Button>
      </Space>

      <Card variant="borderless" className="topic-trend-hero">
        <Row gutter={[20, 20]} align="middle">
          <Col xs={24} lg={16}>
            <Space orientation="vertical" size={12}>
              <Space size={[8, 8]} wrap>
                <Tag color="blue">{topic.category}</Tag>
                <Tag color={status.color}>{status.label}</Tag>
                <Tag color="cyan">{topic.stage}</Tag>
                <Text type="secondary">更新于 {topic.updatedAt}</Text>
              </Space>
              <Title level={2}>{topic.name}</Title>
              <Paragraph>{topic.description}</Paragraph>
              <Space size={[8, 8]} wrap>
                {topic.aliases.map((alias) => (
                  <Tag key={alias}>{alias}</Tag>
                ))}
              </Space>
            </Space>
          </Col>
          <Col xs={24} lg={8}>
            <Descriptions column={1} size="small" className="topic-trend-meta">
              <Descriptions.Item label="热度排名">第 {topicRank} 位</Descriptions.Item>
              <Descriptions.Item label="当前热度">
                <Progress percent={topic.trend} size="small" />
              </Descriptions.Item>
              <Descriptions.Item label="近两月增长">
                +{topic.momentum}
              </Descriptions.Item>
              <Descriptions.Item label="来源论文">
                {topic.paperCount} 篇
              </Descriptions.Item>
            </Descriptions>
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card variant="borderless">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="提及次数">
                {topic.mentions}
              </Descriptions.Item>
              <Descriptions.Item label="速度">
                本月 +{topic.velocity}
              </Descriptions.Item>
              <Descriptions.Item label="关键词">
                <Space size={[4, 4]} wrap>
                  {topic.keywords.map((keyword) => (
                    <Tag key={keyword}>{keyword}</Tag>
                  ))}
                </Space>
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} md={16}>
          <Card
            variant="borderless"
            title={
              <Space>
                <LineChartOutlined />
                热度走势
              </Space>
            }
          >
            <TrendLine
              id={`topic-detail-${topic.id}`}
              points={getSeriesForRange(topic, 7)}
              color="#4f6ef7"
              height={240}
              ariaLabel={`${topic.name} 热度走势`}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card
            variant="borderless"
            title={
              <Space>
                <BranchesOutlined />
                研究阶段
              </Space>
            }
          >
            <div className="topic-trend-stage-list">
              {stages.map((stage) => (
                <div
                  key={stage.key}
                  className="topic-trend-stage"
                  style={{ '--stage-color': stage.color }}
                >
                  <Text type="secondary">{stage.label}</Text>
                  <Paragraph>{stage.value}</Paragraph>
                  <Tag color="geekblue">{stage.metric}</Tag>
                </div>
              ))}
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card
            variant="borderless"
            title={
              <Space>
                <CalendarOutlined />
                关键里程碑
              </Space>
            }
          >
            <Timeline
              items={milestones.map((milestone) => ({
                color: milestone.color,
                content: (
                  <Space orientation="vertical" size={2}>
                    <Text strong>
                      {milestone.year} · {milestone.title}
                    </Text>
                    <Text type="secondary">{milestone.description}</Text>
                  </Space>
                ),
              }))}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card
            variant="borderless"
            title={
              <Space>
                <BookOutlined />
                来源论文
              </Space>
            }
          >
            <Table
              rowKey="id"
              columns={paperColumns}
              dataSource={topic.papers}
              pagination={false}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card
            variant="borderless"
            title={
              <Space>
                <FileTextOutlined />
                关联主题
              </Space>
            }
          >
            <Table
              rowKey="id"
              columns={relationColumns}
              dataSource={relatedConcepts}
              pagination={false}
            />
          </Card>
        </Col>
      </Row>

      <Card
        variant="borderless"
        title={
          <Space>
            <LineChartOutlined />
            主题信号
          </Space>
        }
      >
        {topicSignals.length > 0 ? (
          <Row gutter={[16, 16]}>
            {topicSignals.map((signal) => (
              <Col xs={24} md={8} key={signal.id}>
                <div className="topic-trend-signal">
                  <Flex align="center" justify="space-between" gap={8}>
                    <Text strong>{signal.title}</Text>
                    <Tag color={signal.color}>影响 {signal.impact}</Tag>
                  </Flex>
                  <Paragraph>{signal.description}</Paragraph>
                  <Text type="secondary">{signal.time}</Text>
                </div>
              </Col>
            ))}
          </Row>
        ) : (
          <Empty description="暂无该主题的独立信号" />
        )}
      </Card>
    </main>
  );
}
