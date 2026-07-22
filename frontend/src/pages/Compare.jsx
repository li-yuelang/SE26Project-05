import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
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
  Segmented,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  ArrowLeftOutlined,
  BarChartOutlined,
  BookOutlined,
  BranchesOutlined,
  CheckCircleOutlined,
  ExportOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  LinkOutlined,
  PartitionOutlined,
  TagsOutlined,
} from '@ant-design/icons';
import AsyncPageState from '../components/AsyncPageState';
import useAsyncResource from '../hooks/useAsyncResource';
import {
  exportComparison,
  getLearningCenter,
} from '../services/learningService';

const { Paragraph, Text, Title } = Typography;
const { Search } = Input;

const compareDimensions = [
  {
    key: 'question',
    label: '研究问题',
    render: (paper) => paper.researchQuestion,
  },
  {
    key: 'method',
    label: '核心方法',
    render: (paper) => (
      <Space size={[6, 6]} wrap>
        {paper.methods.map((method) => (
          <Tag key={method}>{method}</Tag>
        ))}
      </Space>
    ),
  },
  {
    key: 'dataset',
    label: '数据与实验',
    render: (paper) => (
      <Space orientation="vertical" size={4}>
        <Text>{paper.datasets.join('、')}</Text>
        <Text type="secondary">{paper.experiment}</Text>
      </Space>
    ),
  },
  {
    key: 'conclusion',
    label: '主要结论',
    render: (paper) => paper.conclusion,
  },
  {
    key: 'limitations',
    label: '局限性',
    render: (paper) => paper.limitations,
  },
  {
    key: 'bestFor',
    label: '适合参考',
    render: (paper) => paper.bestFor,
  },
];

export default function Compare() {
  const location = useLocation();
  const navigate = useNavigate();
  const resource = useAsyncResource(getLearningCenter, []);
  const selectionInitialized = useRef(false);
  const papers = resource.data?.papers || [];
  const statusMeta = resource.data?.statusMeta || {};
  const [selectedPaperIds, setSelectedPaperIds] = useState([]);
  const [keyword, setKeyword] = useState('');
  const [activeView, setActiveView] = useState('matrix');
  const [comparisonId, setComparisonId] = useState(null);
  const [comparisonReport, setComparisonReport] = useState('');
  const [generatingReport, setGeneratingReport] = useState(false);

  useEffect(() => {
    if (selectionInitialized.current || papers.length === 0) return;
    const initialPaperIds = location.state?.paperIds?.filter((paperId) =>
      papers.some((paper) => paper.id === paperId),
    );
    setSelectedPaperIds(initialPaperIds?.length >= 2 ? initialPaperIds.slice(0, 4) : []);
    selectionInitialized.current = true;
  }, [location.state, papers]);

  const selectedPapers = useMemo(
    () => papers.filter((paper) => selectedPaperIds.includes(paper.id)),
    [papers, selectedPaperIds],
  );

  const filteredOptions = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();

    return papers
      .filter((paper) =>
        [
          paper.title,
          paper.authors.join(' '),
          paper.direction,
          paper.categories.join(' '),
          paper.tags.join(' '),
        ]
          .join(' ')
          .toLowerCase()
          .includes(normalizedKeyword),
      )
      .map((paper) => ({
        label: `${paper.title} (${paper.id})`,
        value: paper.id,
      }));
  }, [keyword, papers]);

  const tagStats = useMemo(() => {
    if (selectedPapers.length === 0) {
      return { common: [], byPaper: [] };
    }

    const tagCounts = new Map();
    selectedPapers.forEach((paper) => {
      paper.tags.forEach((tag) => {
        tagCounts.set(tag, (tagCounts.get(tag) || 0) + 1);
      });
    });

    const common = Array.from(tagCounts.entries())
      .filter(([, count]) => count === selectedPapers.length)
      .map(([tag]) => tag);

    const byPaper = selectedPapers.map((paper) => ({
      id: paper.id,
      title: paper.title,
      direction: paper.direction,
      tags: paper.tags,
      uniqueTags: paper.tags.filter((tag) => tagCounts.get(tag) === 1),
    }));

    return { common, byPaper };
  }, [selectedPapers]);

  const matrixColumns = useMemo(
    () => [
      {
        title: '对比维度',
        dataIndex: 'label',
        width: 130,
        fixed: 'left',
        render: (label) => <Text strong>{label}</Text>,
      },
      ...selectedPapers.map((paper) => ({
        title: (
          <Space orientation="vertical" size={2} className="compare-column-title">
            <Text strong>{paper.title}</Text>
            <Text type="secondary">arXiv: {paper.id}</Text>
          </Space>
        ),
        dataIndex: paper.id,
        minWidth: 260,
      })),
    ],
    [selectedPapers],
  );

  const matrixRows = useMemo(
    () =>
      compareDimensions.map((dimension) => {
        const row = {
          key: dimension.key,
          label: dimension.label,
        };

        selectedPapers.forEach((paper) => {
          row[paper.id] = dimension.render(paper);
        });

        return row;
      }),
    [selectedPapers],
  );

  const overviewColumns = [
    {
      title: '论文',
      dataIndex: 'title',
      render: (_, paper) => (
        <Space orientation="vertical" size={4}>
          <Button
            type="link"
            className="compare-paper-title"
            onClick={() => navigate(`/papers/${paper.id}`)}
          >
            {paper.title}
          </Button>
          <Text type="secondary">{paper.authors.join(', ')}</Text>
        </Space>
      ),
    },
    {
      title: '方向',
      dataIndex: 'direction',
      width: 120,
      render: (direction) => <Tag color="geekblue">{direction}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (status) => (
        <Tag color={statusMeta[status].color === 'success' ? 'green' : 'blue'}>
          {statusMeta[status].text}
        </Tag>
      ),
    },
    {
      title: '阅读进度',
      dataIndex: 'progress',
      width: 150,
      render: (progress) => <Progress percent={progress} size="small" />,
    },
    {
      title: '笔记',
      dataIndex: 'notesCount',
      width: 90,
      render: (count) => `${count} 条`,
    },
  ];

  const methodColumns = [
    {
      title: '论文',
      dataIndex: 'title',
      width: 260,
      render: (title) => <Text strong>{title}</Text>,
    },
    {
      title: '方法组合',
      dataIndex: 'methods',
      render: (methods) => (
        <Space size={[6, 6]} wrap>
          {methods.map((method) => (
            <Tag key={method}>{method}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '数据集',
      dataIndex: 'datasets',
      render: (datasets) => datasets.join('、'),
    },
    {
      title: '实验结论',
      dataIndex: 'experiment',
    },
  ];

  const handleSelectChange = (paperIds) => {
    if (paperIds.length > 4) {
      message.warning('一次最多对比 4 篇论文');
      return;
    }
    setSelectedPaperIds(paperIds);
    setComparisonId(null);
    setComparisonReport('');
  };

  const exportCompare = async () => {
    if (selectedPaperIds.length < 2) {
      message.warning('请至少选择 2 篇论文');
      return;
    }
    setGeneratingReport(true);
    try {
      const result = await exportComparison(selectedPaperIds, comparisonId);
      if (!result?.report_content) {
        throw new Error('AI 未返回对比报告，请检查后端的大模型配置与日志');
      }
      setComparisonId(result.comparison_id);
      setComparisonReport(result.report_content);
      message.success('AI 对比报告已生成');
    } catch (error) {
      message.error(error.message || 'AI 对比报告生成失败');
    } finally {
      setGeneratingReport(false);
    }
  };

  const restoreDefaultSelection = () => {
    setSelectedPaperIds([]);
    setComparisonId(null);
    setComparisonReport('');
  };

  const removePaper = (paperId) => {
    setSelectedPaperIds((paperIds) => paperIds.filter((id) => id !== paperId));
    setComparisonId(null);
    setComparisonReport('');
  };

  if (resource.loading || resource.error) {
    return (
      <main className="page-stack compare-page">
        <AsyncPageState
          loading={resource.loading}
          error={resource.error}
          onRetry={resource.reload}
        />
      </main>
    );
  }

  return (
    <main className="page-stack compare-page">
      <Flex
        className="compare-header"
        align="flex-start"
        justify="space-between"
        gap={16}
        wrap="wrap"
      >
        <div>
          <Title level={2}>论文对比</Title>
          <Paragraph>
            选择 2 到 4 篇论文，从研究问题、方法、实验、结论、局限和阅读价值等维度进行并排分析。
          </Paragraph>
        </div>
        <Space wrap>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/learning')}>
            返回学习中心
          </Button>
          <Button
            type="primary"
            icon={<ExportOutlined />}
            loading={generatingReport}
            disabled={selectedPapers.length < 2}
            onClick={exportCompare}
          >
            生成 AI 对比报告
          </Button>
        </Space>
      </Flex>

      <Row gutter={[16, 16]} className="metric-card-row">
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic title="已选论文" value={selectedPapers.length} suffix="篇" />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic
              title="平均进度"
              value={
                selectedPapers.length
                  ? Math.round(
                      selectedPapers.reduce((sum, paper) => sum + paper.progress, 0) /
                        selectedPapers.length,
                    )
                  : 0
              }
              suffix="%"
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic title="共同标签" value={tagStats.common.length} suffix="个" />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic
              title="覆盖方向"
              value={new Set(selectedPapers.map((paper) => paper.direction)).size}
              suffix="类"
            />
          </Card>
        </Col>
      </Row>

      <Card variant="borderless" className="compare-selector-card">
        <Flex gap={12} align="center" wrap="wrap">
          <Search
            allowClear
            className="compare-search"
            placeholder="搜索可对比论文"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            onSearch={setKeyword}
          />
          <Select
            mode="multiple"
            className="compare-select"
            placeholder="选择 2 到 4 篇论文"
            value={selectedPaperIds}
            options={filteredOptions}
            onChange={handleSelectChange}
            optionFilterProp="label"
            maxTagCount="responsive"
          />
          <Button onClick={restoreDefaultSelection}>
            恢复默认
          </Button>
        </Flex>
      </Card>

      {comparisonReport && (
        <Card
          variant="borderless"
          className="compare-ai-report-card"
          title={
            <Space>
              <FileTextOutlined />
              AI 对比报告
            </Space>
          }
        >
          <div className="compare-ai-report">{comparisonReport}</div>
        </Card>
      )}

      <Card variant="borderless" className="compare-view-card">
        <Flex align="center" justify="space-between" gap={12} wrap="wrap">
          <Segmented
            value={activeView}
            onChange={setActiveView}
            options={[
              { label: '总览矩阵', value: 'matrix', icon: <BarChartOutlined /> },
              { label: '方法实验', value: 'methods', icon: <ExperimentOutlined /> },
              { label: '概念关联', value: 'concepts', icon: <BranchesOutlined /> },
              { label: '阅读决策', value: 'decision', icon: <CheckCircleOutlined /> },
            ]}
          />
          <Space size={[6, 6]} wrap>
            {selectedPapers.map((paper) => (
              <Tag
                key={paper.id}
                closable
                onClose={() => removePaper(paper.id)}
              >
                {paper.id}
              </Tag>
            ))}
          </Space>
        </Flex>
      </Card>

      {selectedPapers.length < 2 ? (
        <Card variant="borderless">
          <Empty description="请选择至少 2 篇论文开始对比" />
        </Card>
      ) : (
        <>
          {activeView === 'matrix' && (
            <Card
              variant="borderless"
              title={
                <Space>
                  <FileTextOutlined />
                  结构化对比矩阵
                </Space>
              }
            >
              <Table
                rowKey="key"
                columns={matrixColumns}
                dataSource={matrixRows}
                pagination={false}
                scroll={{ x: 900 }}
                bordered
              />
            </Card>
          )}

          {activeView === 'methods' && (
            <Card
              variant="borderless"
              title={
                <Space>
                  <ExperimentOutlined />
                  方法与实验对比
                </Space>
              }
            >
              <Table
                rowKey="id"
                columns={methodColumns}
                dataSource={selectedPapers}
                pagination={false}
                scroll={{ x: 900 }}
              />
            </Card>
          )}

          {activeView === 'concepts' && (
            <Row gutter={[16, 16]}>
              <Col xs={24} lg={8}>
                <Card
                  variant="borderless"
                  title={
                    <Space>
                      <PartitionOutlined />
                      共同概念
                    </Space>
                  }
                >
                  {tagStats.common.length > 0 ? (
                    <Space size={[6, 6]} wrap>
                      {tagStats.common.map((tag) => (
                        <Tag color="blue" key={tag}>
                          {tag}
                        </Tag>
                      ))}
                    </Space>
                  ) : (
                    <Empty description="暂无完全重叠标签" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  )}
                </Card>
              </Col>
              <Col xs={24} lg={16}>
                <Card
                  variant="borderless"
                  title={
                    <Space>
                      <TagsOutlined />
                      差异标签
                    </Space>
                  }
                >
                  <List
                    dataSource={tagStats.byPaper}
                    renderItem={(paper) => (
                      <List.Item>
                        <List.Item.Meta
                          title={
                            <Space wrap>
                              <Text strong>{paper.title}</Text>
                              <Tag color="geekblue">{paper.direction}</Tag>
                            </Space>
                          }
                          description={
                            <Space size={[6, 6]} wrap>
                              {(paper.uniqueTags.length ? paper.uniqueTags : paper.tags).map((tag) => (
                                <Tag key={tag}>{tag}</Tag>
                              ))}
                            </Space>
                          }
                        />
                      </List.Item>
                    )}
                  />
                </Card>
              </Col>
            </Row>
          )}

          {activeView === 'decision' && (
            <Row gutter={[16, 16]}>
              <Col xs={24} xl={15}>
                <Card
                  variant="borderless"
                  title={
                    <Space>
                      <BookOutlined />
                      阅读优先级
                    </Space>
                  }
                >
                  <Table
                    rowKey="id"
                    columns={overviewColumns}
                    dataSource={[...selectedPapers].sort((a, b) => {
                      const priorityScore = { 高: 3, 中: 2, 低: 1 };
                      return priorityScore[b.priority] - priorityScore[a.priority];
                    })}
                    pagination={false}
                    scroll={{ x: 780 }}
                  />
                </Card>
              </Col>
              <Col xs={24} xl={9}>
                <Card
                  variant="borderless"
                  title={
                    <Space>
                      <LinkOutlined />
                      适用场景建议
                    </Space>
                  }
                >
                  <List
                    dataSource={selectedPapers}
                    renderItem={(paper) => (
                      <List.Item>
                        <Space orientation="vertical" size={6}>
                          <Text strong>{paper.title}</Text>
                          <Text type="secondary">{paper.bestFor}</Text>
                          <Space size={[6, 6]} wrap>
                            <Tag color={paper.priority === '高' ? 'red' : 'gold'}>
                              {paper.priority}优先级
                            </Tag>
                            <Button
                              type="link"
                              className="compare-inline-link"
                              href={paper.arxivUrl}
                              target="_blank"
                            >
                              arXiv
                            </Button>
                          </Space>
                        </Space>
                      </List.Item>
                    )}
                  />
                </Card>
              </Col>
            </Row>
          )}
        </>
      )}
    </main>
  );
}
