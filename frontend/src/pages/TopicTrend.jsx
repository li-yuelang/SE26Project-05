import { useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Button,
  Card,
  Col,
  Empty,
  Flex,
  Progress,
  Row,
  Space,
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

    const index = [...trendTopics]
      .sort((left, right) => right.trend - left.trend)
      .findIndex((item) => item.id === topic.id);
    return index >= 0 ? index + 1 : null;
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

  return (
    <main className="topic-trend-page page-stack">
      <Flex className="topic-trend-toolbar" align="center" justify="space-between" gap={12} wrap="wrap">
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/trends')}>
          返回研究脉络
        </Button>
        <Button icon={<TagsOutlined />} onClick={() => navigate('/wiki')}>
          查看知识 Wiki
        </Button>
      </Flex>

      <Card variant="borderless" className="topic-trend-hero">
        <Space orientation="vertical" size={14} className="topic-trend-hero-copy">
          <Flex align="center" justify="space-between" gap={12} wrap="wrap">
            <Space size={[8, 8]} wrap>
              <Tag color="blue">{topic.category}</Tag>
              <Tag color={status.color}>{status.label}</Tag>
              <Tag>{topic.stage}</Tag>
            </Space>
            <Text type="secondary">更新于 {topic.updatedAt}</Text>
          </Flex>
          <div>
            <Title level={2}>{topic.name}</Title>
            <Paragraph>{topic.description}</Paragraph>
          </div>
          {topic.aliases.length > 0 && (
            <Space size={[6, 6]} wrap>
              <Text type="secondary">别名</Text>
              {topic.aliases.map((alias) => (
                <Tag key={alias}>{alias}</Tag>
              ))}
            </Space>
          )}
          <div className="topic-trend-kpi-grid">
            <div className="topic-trend-kpi">
              <Text>热度排名</Text>
              <strong>{topicRank ? `#${topicRank}` : '—'}</strong>
            </div>
            <div className="topic-trend-kpi">
              <Text>当前热度</Text>
              <strong>{topic.trend}%</strong>
            </div>
            <div className="topic-trend-kpi">
              <Text>近两月增长</Text>
              <strong>{topic.momentum >= 0 ? '+' : ''}{topic.momentum}</strong>
            </div>
            <div className="topic-trend-kpi">
              <Text>来源论文</Text>
              <strong>{topic.paperCount} 篇</strong>
            </div>
          </div>
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card
            variant="borderless"
            className="topic-trend-chart-card"
            title={
              <Space>
                <LineChartOutlined />
                热度走势
              </Space>
            }
            extra={<Text type="secondary">近 7 个月</Text>}
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
        <Col xs={24} lg={8}>
          <Card variant="borderless" title="主题摘要" className="topic-trend-summary-card">
            <div className="topic-trend-summary-stats">
              <div>
                <Text type="secondary">提及次数</Text>
                <strong>{topic.mentions}</strong>
              </div>
              <div>
                <Text type="secondary">本月速度</Text>
                <strong>{topic.velocity >= 0 ? '+' : ''}{topic.velocity}</strong>
              </div>
            </div>
            <Text strong>关键词</Text>
            <Flex gap={6} wrap="wrap" className="topic-trend-keywords">
              {topic.keywords.map((keyword) => (
                <Tag key={keyword}>{keyword}</Tag>
              ))}
            </Flex>
            {topic.summaryPoints?.length > 0 && (
              <ul className="topic-trend-summary-list">
                {topic.summaryPoints.slice(0, 3).map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            )}
          </Card>
        </Col>
      </Row>

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
          {stages.map((stage, index) => (
            <div
              key={stage.key}
              className="topic-trend-stage"
              style={{ '--stage-color': stage.color }}
            >
              <Flex align="center" justify="space-between" gap={8}>
                <Text strong>{index + 1}. {stage.label}</Text>
                <Tag>{stage.metric}</Tag>
              </Flex>
              <Paragraph>{stage.value}</Paragraph>
            </div>
          ))}
        </div>
      </Card>

      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} lg={10}>
          <Card
            variant="borderless"
            className="topic-trend-section-card"
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
        <Col xs={24} lg={14}>
          <Card
            variant="borderless"
            className="topic-trend-section-card"
            title={
              <Space>
                <LineChartOutlined />
                主题信号
              </Space>
            }
          >
            {topicSignals.length > 0 ? (
              <div className="topic-trend-signal-list">
                {topicSignals.map((signal) => (
                  <div className="topic-trend-signal" key={signal.id}>
                    <Flex align="center" justify="space-between" gap={8} wrap="wrap">
                      <Text strong>{signal.title}</Text>
                      <Tag color={signal.color}>影响 {signal.impact}</Tag>
                    </Flex>
                    <Paragraph>{signal.description}</Paragraph>
                    <Text type="secondary">{signal.time}</Text>
                  </div>
                ))}
              </div>
            ) : (
              <Empty description="暂无该主题的独立信号" />
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} lg={14}>
          <Card
            variant="borderless"
            className="topic-trend-section-card"
            title={
              <Space>
                <BookOutlined />
                来源论文
              </Space>
            }
          >
            {topic.papers.length > 0 ? (
              <div className="topic-trend-paper-list">
                {topic.papers.map((paper) => (
                  <div className="topic-trend-paper-item" key={paper.id}>
                    <Button
                      type="link"
                      onClick={() => navigate(`/papers/${paper.id}`)}
                    >
                      {paper.title}
                    </Button>
                    <Flex gap={10} wrap="wrap">
                      <Text type="secondary">{paper.year}</Text>
                      <Text type="secondary">arXiv: {paper.arxivId}</Text>
                    </Flex>
                    <Paragraph ellipsis={{ rows: 2 }}>{paper.role}</Paragraph>
                  </div>
                ))}
              </div>
            ) : (
              <Empty description="暂无来源论文" />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card
            variant="borderless"
            className="topic-trend-section-card"
            title={
              <Space>
                <FileTextOutlined />
                关联主题
              </Space>
            }
          >
            {relatedConcepts.length > 0 ? (
              <div className="topic-trend-related-list">
                {relatedConcepts.map((relation) => (
                  <button
                    type="button"
                    key={relation.id}
                    className="topic-trend-related-item"
                    disabled={!relation.exists}
                    onClick={() => navigate(`/trends/${relation.concept.id}`)}
                  >
                    <Flex align="center" justify="space-between" gap={8}>
                      <Text strong>{relation.concept.name}</Text>
                      <Tag>{relation.exists ? relation.type : '整理中'}</Tag>
                    </Flex>
                    <Progress percent={relation.strength} size="small" showInfo={false} />
                    <Text type="secondary">
                      <LinkOutlined /> {relation.strength}% 关联强度
                    </Text>
                  </button>
                ))}
              </div>
            ) : (
              <Empty description="暂无关联主题" />
            )}
          </Card>
        </Col>
      </Row>
    </main>
  );
}
