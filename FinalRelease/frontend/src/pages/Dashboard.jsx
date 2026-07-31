import { ArrowRightOutlined, MessageOutlined, SearchOutlined } from '@ant-design/icons';
import {
  Button,
  Card,
  Col,
  Empty,
  Flex,
  Input,
  List,
  Progress,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import AsyncPageState from '../components/AsyncPageState';
import KnowledgeGraph from '../components/KnowledgeGraph';
import useAsyncResource from '../hooks/useAsyncResource';
import { getDashboard } from '../services/dashboardService';

const { Paragraph, Text, Title } = Typography;
const { Search } = Input;

export default function Dashboard() {
  const navigate = useNavigate();
  const resource = useAsyncResource(getDashboard, []);
  const paperList = resource.data?.papers || [];
  const topicList = resource.data?.topics || [];
  const recentTasks = resource.data?.recentTasks || [];
  const stats = resource.data?.stats || {};
  const [keyword, setKeyword] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');

  const categories = useMemo(() => {
    return ['all', ...new Set(paperList.map((paper) => paper.category))].map(
      (category) => ({
        label: category === 'all' ? '全部分类' : category,
        value: category,
      }),
    );
  }, [paperList]);

  const filteredPapers = useMemo(() => {
    return paperList.filter((paper) => {
      const matchesCategory =
        selectedCategory === 'all' || paper.category === selectedCategory;
      const searchText = [
        paper.title,
        paper.summary,
        paper.category,
        paper.authors.join(' '),
        paper.tags.join(' '),
      ]
        .join(' ')
        .toLowerCase();

      return matchesCategory && searchText.includes(keyword.toLowerCase());
    });
  }, [keyword, paperList, selectedCategory]);

  const paperColumns = [
    {
      title: '论文',
      dataIndex: 'title',
      render: (_, paper) => (
        <Space orientation="vertical" size={3}>
          <a href={paper.arxivUrl} target="_blank" rel="noreferrer">
            {paper.title}
          </a>
          <Text type="secondary">{paper.authors.join(', ')}</Text>
        </Space>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      width: 110,
      render: (category) => <Tag color="geekblue">{category}</Tag>,
    },
    {
      title: '发布日期',
      dataIndex: 'publishedAt',
      width: 130,
    },
    {
      title: '标签',
      dataIndex: 'tags',
      render: (tags) => (
        <Flex gap={6} wrap="wrap">
          {tags.map((tag) => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </Flex>
      ),
    },
  ];

  if (resource.loading || resource.error) {
    return (
      <main className="dashboard-page">
        <AsyncPageState
          loading={resource.loading}
          error={resource.error}
          onRetry={resource.reload}
        />
      </main>
    );
  }

  return (
    <main className="dashboard-page">
      <section className="dashboard-hero">
        <div className="dashboard-hero-copy">
          <Text className="dashboard-eyebrow">Your research, connected</Text>
          <Title level={1}>
            让每一篇论文，
            <br />
            都成为可检索的知识。
          </Title>
          <Paragraph>
            聚合 arXiv 论文，沉淀结构化笔记与概念关系，让阅读、追踪和问答自然发生在同一个工作区。
          </Paragraph>
          <Space size={10} wrap className="dashboard-actions">
            <Button
              type="primary"
              icon={<SearchOutlined />}
              onClick={() => navigate('/papers')}
            >
              浏览论文
            </Button>
            <Button icon={<MessageOutlined />} onClick={() => navigate('/chat')}>
              开始问答
            </Button>
          </Space>
        </div>

        <div className="dashboard-hero-aside">
          <div className="dashboard-knowledge-pulse">
            <div className="dashboard-pulse-heading">
              <span>
                <i aria-hidden="true" />
                Knowledge map
              </span>
              <Text type="secondary">
                {stats.concepts || 0} concepts connected
              </Text>
            </div>
            <KnowledgeGraph className="dashboard-mini-graph" />
          </div>
          <div className="dashboard-stats" aria-label="研究数据概览">
            <Statistic title="入库论文" value={stats.papers || 0} suffix="篇" />
            <Statistic title="研究主题" value={stats.topics || 0} />
            <Statistic title="知识概念" value={stats.concepts || 0} />
            <Statistic title="运行任务" value={stats.runningTasks || 0} />
          </div>
        </div>
      </section>

      <section className="dashboard-discovery" aria-label="论文检索">
        <Search
          allowClear
          prefix={<SearchOutlined />}
          placeholder="搜索标题、作者、关键词或研究方向"
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          onSearch={setKeyword}
          className="dashboard-search"
        />
        <Select
          aria-label="按分类筛选"
          options={categories}
          value={selectedCategory}
          onChange={setSelectedCategory}
          className="dashboard-category-select"
        />
      </section>

      <Row gutter={[20, 20]}>
        <Col xs={24} xl={16}>
          <Card
            title={
              <span className="section-heading">
                <span>最新论文</span>
                <Text type="secondary">{filteredPapers.length} 篇</Text>
              </span>
            }
            extra={
              <Link to="/papers" className="section-link">
                查看全部 <ArrowRightOutlined />
              </Link>
            }
            variant="borderless"
            className="dashboard-papers-card"
          >
            <Table
              className="dashboard-papers-table"
              rowKey="id"
              columns={paperColumns}
              dataSource={filteredPapers}
              pagination={false}
              locale={{ emptyText: <Empty description="没有找到匹配的论文" /> }}
            />
          </Card>
        </Col>

        <Col xs={24} xl={8}>
          <Space orientation="vertical" size={20} className="dashboard-side-stack">
            <Card
              title="最近任务"
              extra={<Link to="/tasks" className="section-link">查看全部</Link>}
              variant="borderless"
            >
              <List
                dataSource={recentTasks}
                renderItem={(task) => (
                  <List.Item>
                    <List.Item.Meta
                      title={
                        <Flex justify="space-between" gap={12}>
                          <Text strong>{task.name}</Text>
                          <Tag color={task.color}>{task.status}</Tag>
                        </Flex>
                      }
                      description={task.description}
                    />
                  </List.Item>
                )}
              />
            </Card>

            <Card
              title="热门研究方向"
              extra={<Link to="/trends" className="section-link">查看趋势</Link>}
              variant="borderless"
            >
              <List
                dataSource={topicList}
                renderItem={(topic) => (
                  <List.Item>
                    <Space orientation="vertical" className="dashboard-list-item">
                      <Flex justify="space-between">
                        <Text strong>{topic.name}</Text>
                        <Text type="secondary">{topic.count} 篇</Text>
                      </Flex>
                      <Progress percent={topic.percent} showInfo={false} />
                    </Space>
                  </List.Item>
                )}
              />
            </Card>
          </Space>
        </Col>
      </Row>
    </main>
  );
}
