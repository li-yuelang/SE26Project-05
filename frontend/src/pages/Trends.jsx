import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Flex,
  Input,
  Progress,
  Row,
  Segmented,
  Select,
  Space,
  Statistic,
  Tag,
  Timeline,
  Tooltip,
  Typography,
} from 'antd';
import {
  ArrowRightOutlined,
  BarChartOutlined,
  BranchesOutlined,
  DownOutlined,
  FireOutlined,
  LineChartOutlined,
  SearchOutlined,
  TagsOutlined,
  ThunderboltOutlined,
  UpOutlined,
} from '@ant-design/icons';
import TrendLine from '../components/TrendLine';
import AsyncPageState from '../components/AsyncPageState';
import useAsyncResource from '../hooks/useAsyncResource';
import {
  getSeriesForRange,
  getTrendOverview,
  getTrendStats,
  getTrendStatus,
} from '../services/trendService';

const { Paragraph, Text, Title } = Typography;
const { Search } = Input;

export default function Trends() {
  const navigate = useNavigate();
  const resource = useAsyncResource(getTrendOverview, []);
  const trendTopics = resource.data?.topics || [];
  const trendSignals = resource.data?.signals || [];
  const trendRangeOptions = resource.data?.rangeOptions || [];
  const trendSortOptions = resource.data?.sortOptions || [];
  const wikiCategoryOptions = resource.data?.categoryOptions || [];
  const categoryFilters = useMemo(() => {
    const counts = trendTopics.reduce((result, topic) => {
      result.set(topic.category, (result.get(topic.category) || 0) + 1);
      return result;
    }, new Map());
    const categories = [...new Set(
      wikiCategoryOptions
        .map((option) => (typeof option === 'string' ? option : option.value))
        .filter((option) => option && option !== '全部'),
    )];
    const topCategories = [...categories]
      .sort((left, right) => (counts.get(right) || 0) - (counts.get(left) || 0))
      .slice(0, 3);

    return {
      featured: [
        { label: '全部', value: '全部' },
        ...topCategories.map((value) => ({
          label: `${value} (${counts.get(value) || 0})`,
          value,
        })),
      ],
      featuredValues: new Set(['全部', ...topCategories]),
      more: categories
        .filter((value) => !topCategories.includes(value))
        .map((value) => ({
          label: `${value} (${counts.get(value) || 0})`,
          value,
        })),
    };
  }, [trendTopics, wikiCategoryOptions]);
  const [keyword, setKeyword] = useState('');
  const [category, setCategory] = useState('全部');
  const [sortBy, setSortBy] = useState('momentum');
  const [range, setRange] = useState(6);
  const [activeTopicId, setActiveTopicId] = useState(null);
  const [showAllCategories, setShowAllCategories] = useState(false);

  const categoryDistribution = useMemo(() => {
    const counts = trendTopics.reduce((result, topic) => {
      result.set(topic.category, (result.get(topic.category) || 0) + 1);
      return result;
    }, new Map());
    const categories = [...new Set(
      wikiCategoryOptions
        .map((option) => (typeof option === 'string' ? option : option.value))
        .filter((option) => option && option !== '全部'),
    )];

    return categories
      .map((name) => ({
        count: counts.get(name) || 0,
        name,
        percent: trendTopics.length
          ? Math.round(((counts.get(name) || 0) / trendTopics.length) * 100)
          : 0,
      }))
      .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name));
  }, [trendTopics, wikiCategoryOptions]);

  useEffect(() => {
    if (!activeTopicId && trendTopics.length > 0) {
      setActiveTopicId(trendTopics[0].id);
    }
  }, [activeTopicId, trendTopics]);

  const filteredTopics = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();

    return trendTopics
      .filter((topic) => {
        const matchesCategory =
          category === '全部' || topic.category === category;
        const searchableText = [
          topic.name,
          topic.category,
          topic.description,
          topic.aliases.join(' '),
          topic.keywords.join(' '),
          topic.papers.map((paper) => paper.title).join(' '),
        ]
          .join(' ')
          .toLowerCase();

        return matchesCategory && searchableText.includes(normalizedKeyword);
      })
      .sort((left, right) => {
        switch (sortBy) {
          case 'trend':
            return right.trend - left.trend;
          case 'paperCount':
            return right.paperCount - left.paperCount;
          case 'updatedAt':
            return right.updatedAt.localeCompare(left.updatedAt);
          case 'momentum':
          default:
            return right.momentum - left.momentum;
        }
      });
  }, [category, keyword, sortBy, trendTopics]);

  const stats = useMemo(() => getTrendStats(filteredTopics), [filteredTopics]);
  const activeTopic =
    filteredTopics.find((topic) => topic.id === activeTopicId) ||
    filteredTopics[0] ||
    null;
  const activeStatus = activeTopic ? getTrendStatus(activeTopic) : null;
  const relatedConcepts = activeTopic
    ? resource.data?.relatedConceptsByTopicId?.[activeTopic.id] || []
    : [];
  const activeSignals = activeTopic
    ? trendSignals.filter((signal) => signal.topicIds.includes(activeTopic.id))
    : [];

  const resetFilters = () => {
    setKeyword('');
    setCategory('全部');
    setSortBy('momentum');
    setRange(6);
    setActiveTopicId(trendTopics[0]?.id || null);
  };

  if (resource.loading || resource.error) {
    return (
      <main className="page-stack trend-page">
        <AsyncPageState
          loading={resource.loading}
          error={resource.error}
          onRetry={resource.reload}
        />
      </main>
    );
  }

  return (
    <main className="page-stack trend-page">
      <Flex
        className="trend-page-header"
        align="flex-start"
        justify="space-between"
        gap={16}
        wrap="wrap"
      >
        <div>
          <Title level={2}>研究脉络</Title>
          <Paragraph>
            汇总 Wiki 概念、来源论文和关系边，观察主题热度、增长速度和相邻研究方向的变化。
          </Paragraph>
        </div>
        <Space wrap>
          <Button icon={<TagsOutlined />} onClick={() => navigate('/wiki')}>
            知识 Wiki
          </Button>
          <Button type="primary" icon={<SearchOutlined />} onClick={resetFilters}>
            重置视图
          </Button>
        </Space>
      </Flex>

      <Row gutter={[16, 16]} className="metric-card-row">
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic title="追踪主题" value={stats.topics} suffix="个" />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic title="来源论文" value={stats.papers} suffix="篇" />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic title="平均热度" value={stats.averageTrend} suffix="%" />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic title="升温主题" value={stats.risingTopics} suffix="个" />
          </Card>
        </Col>
      </Row>

      <Card variant="borderless" className="trend-filter-card">
        <Flex className="trend-filter-row" gap={12} align="center" wrap="wrap">
          <Search
            allowClear
            className="trend-search"
            placeholder="搜索主题、关键词、论文标题或别名"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            onSearch={setKeyword}
          />
          <Segmented
            className="trend-featured-categories"
            value={categoryFilters.featuredValues.has(category) ? category : null}
            onChange={setCategory}
            options={categoryFilters.featured}
          />
          {categoryFilters.more.length > 0 && (
            <Select
              allowClear
              showSearch
              className="trend-more-categories"
              placeholder="更多分类"
              value={
                categoryFilters.featuredValues.has(category) ? undefined : category
              }
              onChange={(value) => setCategory(value || '全部')}
              options={categoryFilters.more}
              optionFilterProp="label"
              popupMatchSelectWidth={false}
              aria-label="更多研究主题分类"
            />
          )}
          <Segmented
            value={range}
            onChange={setRange}
            options={trendRangeOptions}
          />
          <Select
            className="trend-sort-select"
            value={sortBy}
            onChange={setSortBy}
            options={trendSortOptions}
          />
        </Flex>
      </Card>

      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} xl={8}>
          <Card
            variant="borderless"
            className="trend-panel trend-topic-list-card"
            title={
              <Space>
                <FireOutlined />
                主题趋势
                <Badge count={filteredTopics.length} color="#4f6ef7" />
              </Space>
            }
          >
            {filteredTopics.length > 0 ? (
              <div className="trend-topic-list">
                {filteredTopics.map((topic) => {
                  const isActive = activeTopic?.id === topic.id;
                  const status = getTrendStatus(topic);

                  return (
                    <button
                      type="button"
                      key={topic.id}
                      className={`trend-topic-item${isActive ? ' active' : ''}`}
                      onClick={() => setActiveTopicId(topic.id)}
                    >
                      <Flex vertical gap={10}>
                        <Flex align="flex-start" justify="space-between" gap={12}>
                          <div className="trend-topic-copy">
                            <Flex align="center" gap={8} wrap="wrap">
                              <Text strong>{topic.name}</Text>
                              <Tag color={status.color}>{status.label}</Tag>
                            </Flex>
                            <Paragraph ellipsis={{ rows: 2 }}>
                              {topic.description}
                            </Paragraph>
                          </div>
                          <div className="trend-sparkline">
                            <TrendLine
                              compact
                              id={`topic-${topic.id}`}
                              points={getSeriesForRange(topic, range)}
                              color={isActive ? '#4f6ef7' : '#16a085'}
                              height={54}
                              ariaLabel={`${topic.name} 趋势缩略图`}
                            />
                          </div>
                        </Flex>
                        <Flex align="center" justify="space-between" gap={12}>
                          <Text type="secondary">
                            {topic.paperCount} 篇论文 · 近两月 +{topic.momentum}
                          </Text>
                          <Progress
                            percent={topic.trend}
                            size="small"
                            showInfo={false}
                            className="trend-topic-progress"
                          />
                        </Flex>
                      </Flex>
                    </button>
                  );
                })}
              </div>
            ) : (
              <Empty
                description={
                  trendTopics.length === 0
                    ? '暂无可分析的研究主题，请先抓取并完成论文解析'
                    : '没有找到匹配的主题'
                }
              />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={10}>
          <Card
            variant="borderless"
            className="trend-panel"
            title={
              <Space>
                <LineChartOutlined />
                趋势走势
              </Space>
            }
            extra={
              activeTopic && (
                <Button
                  type="link"
                  icon={<ArrowRightOutlined />}
                  onClick={() => navigate(`/trends/${activeTopic.id}`)}
                >
                  打开主题
                </Button>
              )
            }
          >
            {activeTopic ? (
              <Space orientation="vertical" size={18} className="trend-detail">
                <div className="trend-detail-header">
                  <Flex align="center" gap={10} wrap="wrap">
                    <Title level={3}>{activeTopic.name}</Title>
                    <Tag color="blue">{activeTopic.category}</Tag>
                    <Tag color={activeStatus.color}>{activeTopic.stage}</Tag>
                    <Text type="secondary">更新于 {activeTopic.updatedAt}</Text>
                  </Flex>
                  <Paragraph>{activeTopic.description}</Paragraph>
                </div>

                <TrendLine
                  id={`detail-${activeTopic.id}`}
                  points={getSeriesForRange(activeTopic, range)}
                  color="#4f6ef7"
                  height={220}
                  ariaLabel={`${activeTopic.name} 研究热度趋势`}
                />

                <div className="trend-metric-grid">
                  <div className="trend-metric">
                    <Text type="secondary">当前热度</Text>
                    <strong>{activeTopic.trend}%</strong>
                  </div>
                  <div className="trend-metric">
                    <Text type="secondary">增长动量</Text>
                    <strong>+{activeTopic.momentum}</strong>
                  </div>
                  <div className="trend-metric">
                    <Text type="secondary">提及次数</Text>
                    <strong>{activeTopic.mentions}</strong>
                  </div>
                </div>

                <div>
                  <Text strong>核心观察</Text>
                  <ul className="wiki-note-list trend-note-list">
                    {activeTopic.summaryPoints.map((point) => (
                      <li key={point} className="wiki-note-item">
                        <Text>{point}</Text>
                      </li>
                    ))}
                  </ul>
                </div>
              </Space>
            ) : (
              <Empty description="请选择一个主题" />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={6}>
          <Space orientation="vertical" size={16} className="trend-side-stack">
            <Card
              variant="borderless"
              className="trend-panel"
              title={
                <Space>
                  <BranchesOutlined />
                  关系强度
                </Space>
              }
            >
              {activeTopic ? (
                <div className="trend-map">
                  <div className="trend-map-center">{activeTopic.name}</div>
                  <Space orientation="vertical" size={10} className="trend-map-list">
                    {relatedConcepts.map((relation) => (
                      <Tooltip
                        key={relation.id}
                        title={`${relation.type} · 关联强度 ${relation.strength}%`}
                      >
                        <button
                          type="button"
                          className="trend-map-node"
                          disabled={!relation.exists}
                          onClick={() => setActiveTopicId(relation.concept.id)}
                        >
                          <Flex align="center" justify="space-between" gap={8}>
                            <Text strong>{relation.concept.name}</Text>
                            <Tag>{relation.type}</Tag>
                          </Flex>
                          <Progress
                            percent={relation.strength}
                            size="small"
                            showInfo={false}
                          />
                        </button>
                      </Tooltip>
                    ))}
                  </Space>
                </div>
              ) : (
                <Empty description="暂无关系数据" />
              )}
            </Card>

            <Card
              variant="borderless"
              className="trend-panel"
              title={
                <Space>
                  <ThunderboltOutlined />
                  趋势信号
                </Space>
              }
            >
              <Timeline
                items={(activeSignals.length > 0 ? activeSignals : trendSignals).map(
                  (signal) => ({
                    color: signal.color,
                    content: (
                      <Space orientation="vertical" size={2}>
                        <Flex align="center" gap={8} wrap="wrap">
                          <Text strong>{signal.title}</Text>
                          <Tag color="geekblue">影响 {signal.impact}</Tag>
                        </Flex>
                        <Text type="secondary">{signal.description}</Text>
                        <Text type="secondary" className="trend-signal-time">
                          {signal.time}
                        </Text>
                      </Space>
                    ),
                  }),
                )}
              />
            </Card>

            <Card
              variant="borderless"
              className="trend-panel"
              title={
                <Space>
                  <BarChartOutlined />
                  分类分布
                </Space>
              }
            >
              <Space orientation="vertical" size={12} className="trend-category-list">
                {(showAllCategories
                  ? categoryDistribution
                  : categoryDistribution.slice(0, 3)
                ).map((item) => (
                  <div key={item.name}>
                    <Flex justify="space-between" gap={8}>
                      <Text ellipsis={{ tooltip: item.name }}>{item.name}</Text>
                      <Text type="secondary">{item.count} 个</Text>
                    </Flex>
                    <Progress percent={item.percent} size="small" showInfo={false} />
                  </div>
                ))}
              </Space>
              {categoryDistribution.length > 3 && (
                <Button
                  type="text"
                  block
                  className="trend-category-toggle"
                  icon={showAllCategories ? <UpOutlined /> : <DownOutlined />}
                  onClick={() => setShowAllCategories((visible) => !visible)}
                >
                  {showAllCategories
                    ? '收起分类'
                    : `展开其余 ${categoryDistribution.length - 3} 个分类`}
                </Button>
              )}
            </Card>
          </Space>
        </Col>
      </Row>
    </main>
  );
}
