import { useMemo, useState } from 'react';
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
  Space,
  Statistic,
  Table,
  Tag,
  Timeline,
  Tooltip,
  Typography,
} from 'antd';
import {
  BookOutlined,
  BranchesOutlined,
  FileTextOutlined,
  LinkOutlined,
  SearchOutlined,
  TagsOutlined,
} from '@ant-design/icons';
import {
  getRelatedConcepts,
  getWikiStats,
  wikiActivity,
  wikiCategoryOptions,
  wikiConcepts,
} from '../data/wikiData';

const { Paragraph, Text, Title } = Typography;
const { Search } = Input;

export default function Wiki() {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState('');
  const [category, setCategory] = useState('全部');
  const [activeConceptId, setActiveConceptId] = useState(wikiConcepts[0].id);
  const stats = useMemo(() => getWikiStats(), []);

  const filteredConcepts = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();

    return wikiConcepts.filter((concept) => {
      const matchesCategory =
        category === '全部' || concept.category === category;
      const searchableText = [
        concept.name,
        concept.category,
        concept.description,
        concept.aliases.join(' '),
        concept.keywords.join(' '),
        concept.papers.map((paper) => paper.title).join(' '),
      ]
        .join(' ')
        .toLowerCase();

      return matchesCategory && searchableText.includes(normalizedKeyword);
    });
  }, [category, keyword]);

  const activeConcept =
    filteredConcepts.find((concept) => concept.id === activeConceptId) ||
    filteredConcepts[0] ||
    null;

  const relatedConcepts = useMemo(
    () => getRelatedConcepts(activeConcept),
    [activeConcept],
  );

  const paperColumns = [
    {
      title: '论文',
      dataIndex: 'title',
      render: (_, paper) => (
        <Space orientation="vertical" size={2}>
          <Button
            type="link"
            className="wiki-paper-link"
            onClick={() => navigate(`/papers/${paper.id}`)}
          >
            {paper.title}
          </Button>
          <Text type="secondary">arXiv: {paper.id}</Text>
        </Space>
      ),
    },
    {
      title: '年份',
      dataIndex: 'year',
      width: 88,
    },
    {
      title: '知识作用',
      dataIndex: 'role',
      width: 180,
      render: (role) => <Tag color="geekblue">{role}</Tag>,
    },
  ];

  const resetFilters = () => {
    setKeyword('');
    setCategory('全部');
    setActiveConceptId(wikiConcepts[0].id);
  };

  return (
    <main className="wiki-page">
      <Flex
        className="wiki-page-header"
        align="flex-start"
        justify="space-between"
        gap={16}
        wrap="wrap"
      >
        <div>
          <Title level={2}>知识 Wiki</Title>
          <Paragraph>
            浏览论文中抽取出的研究概念、关联路径和来源论文，快速定位一个主题在知识库中的上下文。
          </Paragraph>
        </div>
        <Space>
          <Button icon={<BranchesOutlined />} onClick={() => navigate('/trends')}>
            研究脉络
          </Button>
          <Button type="primary" icon={<SearchOutlined />} onClick={resetFilters}>
            重置筛选
          </Button>
        </Space>
      </Flex>

      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic title="概念节点" value={stats.concepts} suffix="个" />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic title="来源论文" value={stats.papers} suffix="篇" />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic title="关系边" value={stats.relations} suffix="条" />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic title="强关联" value={stats.strongRelations} suffix="条" />
          </Card>
        </Col>
      </Row>

      <Card variant="borderless" className="wiki-filter-card">
        <Flex gap={12} align="center" wrap="wrap">
          <Search
            allowClear
            className="wiki-search"
            placeholder="搜索概念、别名、论文标题或关键词"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            onSearch={setKeyword}
          />
          <Segmented
            value={category}
            onChange={setCategory}
            options={wikiCategoryOptions}
          />
        </Flex>
      </Card>

      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} xl={7}>
          <Card
            variant="borderless"
            className="wiki-panel wiki-concept-list-card"
            title={
              <Space>
                <TagsOutlined />
                概念索引
                <Badge count={filteredConcepts.length} color="#4f6ef7" />
              </Space>
            }
          >
            {filteredConcepts.length > 0 ? (
              <div className="wiki-concept-list">
                {filteredConcepts.map((concept) => {
                  const isActive = activeConcept?.id === concept.id;

                  return (
                    <button
                      type="button"
                      key={concept.id}
                      className={`wiki-concept-item${isActive ? ' active' : ''}`}
                      onClick={() => setActiveConceptId(concept.id)}
                    >
                      <Flex vertical gap={8} className="wiki-concept-item-body">
                        <Flex align="center" justify="space-between" gap={8}>
                          <Text strong>{concept.name}</Text>
                          <Tag color={isActive ? 'blue' : 'default'}>
                            {concept.category}
                          </Tag>
                        </Flex>
                        <Paragraph ellipsis={{ rows: 2 }}>
                          {concept.description}
                        </Paragraph>
                        <Flex align="center" justify="space-between">
                          <Text type="secondary">
                            {concept.paperCount} 篇论文 · {concept.mentions} 次提及
                          </Text>
                          <Progress
                            percent={concept.trend}
                            size="small"
                            showInfo={false}
                            className="wiki-concept-trend"
                          />
                        </Flex>
                      </Flex>
                    </button>
                  );
                })}
              </div>
            ) : (
              <Empty description="没有找到匹配的概念" />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={11}>
          <Card
            variant="borderless"
            className="wiki-panel"
            title={
              <Space>
                <FileTextOutlined />
                概念详情
              </Space>
            }
            extra={
              activeConcept && (
                <Button
                  type="link"
                  icon={<LinkOutlined />}
                  onClick={() => navigate(`/wiki/concepts/${activeConcept.id}`)}
                >
                  打开详情
                </Button>
              )
            }
          >
            {activeConcept ? (
              <Space orientation="vertical" size={18} className="wiki-detail">
                <div>
                  <Flex align="center" gap={10} wrap="wrap">
                    <Title level={3}>{activeConcept.name}</Title>
                    <Tag color="blue">{activeConcept.category}</Tag>
                    <Text type="secondary">更新于 {activeConcept.updatedAt}</Text>
                  </Flex>
                  <Paragraph>{activeConcept.description}</Paragraph>
                  <Space size={[8, 8]} wrap>
                    {activeConcept.aliases.map((alias) => (
                      <Tag key={alias}>{alias}</Tag>
                    ))}
                  </Space>
                </div>

                <div>
                  <Text strong>核心笔记</Text>
                  <ul className="wiki-note-list">
                    {activeConcept.summaryPoints.map((point) => (
                      <li key={point} className="wiki-note-item">
                        <Text>{point}</Text>
                      </li>
                    ))}
                  </ul>
                </div>

                <div>
                  <Text strong>来源论文</Text>
                  <Table
                    rowKey="id"
                    columns={paperColumns}
                    dataSource={activeConcept.papers}
                    pagination={false}
                    size="small"
                    className="wiki-paper-table"
                  />
                </div>
              </Space>
            ) : (
              <Empty description="请选择一个概念" />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={6}>
          <Space orientation="vertical" size={16} className="wiki-side-stack">
            <Card
              variant="borderless"
              className="wiki-panel"
              title={
                <Space>
                  <BranchesOutlined />
                  关系图谱
                </Space>
              }
            >
              {activeConcept ? (
                <div className="wiki-network">
                  <div className="wiki-network-center">{activeConcept.name}</div>
                  <Space orientation="vertical" size={10} className="wiki-relation-list">
                    {relatedConcepts.map((relation) => (
                      <Tooltip
                        key={relation.id}
                        title={`${relation.type} · 关联强度 ${relation.strength}%`}
                      >
                        <button
                          type="button"
                          className="wiki-relation-node"
                          disabled={!relation.exists}
                          onClick={() => {
                            setKeyword('');
                            setCategory('全部');
                            setActiveConceptId(relation.concept.id);
                          }}
                        >
                          <span>{relation.concept.name}</span>
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
              className="wiki-panel"
              title={
                <Space>
                  <BookOutlined />
                  最近更新
                </Space>
              }
            >
              <Timeline
                items={wikiActivity.map((activity) => ({
                  color: activity.color,
                  content: (
                    <Space orientation="vertical" size={2}>
                      <Text strong>{activity.title}</Text>
                      <Text type="secondary">{activity.description}</Text>
                      <Text type="secondary" className="wiki-activity-time">
                        {activity.time}
                      </Text>
                    </Space>
                  ),
                }))}
              />
            </Card>
          </Space>
        </Col>
      </Row>
    </main>
  );
}
