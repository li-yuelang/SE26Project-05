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
  Row,
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
  BookOutlined,
  FileTextOutlined,
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

/** 矩阵维度定义 */
const MATRIX_DIMENSIONS = [
  { key: 'question', label: '研究问题' },
  { key: 'method', label: '核心方法' },
  { key: 'dataset', label: '数据与实验' },
  { key: 'conclusion', label: '主要结论' },
  { key: 'limitations', label: '局限性' },
  { key: 'bestFor', label: '适合参考' },
];

export default function Compare() {
  const location = useLocation();
  const navigate = useNavigate();
  const resource = useAsyncResource(getLearningCenter, []);
  const selectionInitialized = useRef(false);
  const exportTriggered = useRef(false);
  const papers = resource.data?.papers || [];
  const [selectedPaperIds, setSelectedPaperIds] = useState([]);
  const [keyword, setKeyword] = useState('');
  const [matrixData, setMatrixData] = useState(null); // { "研究问题": {"paperId": "content", ...}, ... }
  const [loadingMatrix, setLoadingMatrix] = useState(false);

  // 从学习中心跳转来时自动选中论文
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

  // 选中论文后自动触发 AI 对比，用返回的 matrix 填充表格
  useEffect(() => {
    if (selectedPaperIds.length < 2) return;
    if (exportTriggered.current) return;
    if (selectedPapers.some((p) => p.parsedStatus !== 'completed')) return;
    exportTriggered.current = true;
    fetchComparison();
  }, [selectedPaperIds]);

  const fetchComparison = async () => {
    setLoadingMatrix(true);
    try {
      const result = await exportComparison(selectedPaperIds, null);
      if (result.matrix) {
        setMatrixData(result.matrix);
      }
    } catch (error) {
      // fallback to individual paper data if comparison fails
      message.error(error.message || 'AI 对比生成失败，使用本地数据填充');
    } finally {
      setLoadingMatrix(false);
    }
  };

  // ---- 当选中论文变化时重置 matrix ----
  useEffect(() => {
    setMatrixData(null);
    exportTriggered.current = false;
  }, [selectedPaperIds]);

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
      (paper.tags || []).forEach((tag) => {
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
      tags: paper.tags || [],
      uniqueTags: (paper.tags || []).filter((tag) => tagCounts.get(tag) === 1),
    }));

    return { common, byPaper };
  }, [selectedPapers]);

  // 获取某篇论文在某个维度的内容（优先使用 AI matrix，fallback 到论文自身字段）
  const getCellValue = useMemo(() => {
    const fieldMap = {
      '研究问题': 'researchQuestion',
      '核心方法': 'methods',
      '数据与实验': 'experiment',
      '主要结论': 'conclusion',
      '局限性': 'limitations',
      '适合参考': 'bestFor',
    };

    return (dimLabel, paper) => {
      if (matrixData && matrixData[dimLabel] && matrixData[dimLabel][paper.id]) {
        return matrixData[dimLabel][paper.id];
      }
      return paper[fieldMap[dimLabel]];
    };
  }, [matrixData]);

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
        minWidth: 280,
      })),
    ],
    [selectedPapers],
  );

  const matrixRows = useMemo(
    () =>
      MATRIX_DIMENSIONS.map((dim) => {
        const row = { key: dim.key, label: dim.label };

        selectedPapers.forEach((paper) => {
          const val = getCellValue(dim.label, paper);
          if (dim.key === 'method' && Array.isArray(val)) {
            row[paper.id] = (
              <Space size={[6, 6]} wrap>
                {val.map((m) => (
                  <Tag key={m}>{m}</Tag>
                ))}
              </Space>
            );
          } else if (dim.key === 'dataset' && Array.isArray(val)) {
            row[paper.id] = (
              <Space orientation="vertical" size={4}>
                <Text>{val.join('、')}</Text>
              </Space>
            );
          } else {
            row[paper.id] = val || <Text type="secondary">—</Text>;
          }
        });

        return row;
      }),
    [selectedPapers, getCellValue],
  );

  const handleSelectChange = (paperIds) => {
    if (paperIds.length > 4) {
      message.warning('一次最多对比 4 篇论文');
      return;
    }
    setSelectedPaperIds(paperIds);
  };

  const restoreDefaultSelection = () => {
    setSelectedPaperIds([]);
  };

  const removePaper = (paperId) => {
    setSelectedPaperIds((ids) => ids.filter((id) => id !== paperId));
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

  const hasUnparsed = selectedPapers.some((p) => p.parsedStatus !== 'completed');

  return (
    <main className="page-stack compare-page">
      <Flex
        className="page-header"
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
        </Space>
      </Flex>

      <Row gutter={[16, 16]} className="stats-strip">
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic title="已选论文" value={selectedPapers.length} suffix="篇" />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic
              title="学习笔记"
              value={selectedPapers.reduce((sum, paper) => sum + paper.notesCount, 0)}
              suffix="条"
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

      <Card variant="borderless" className="filter-panel">
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

      {selectedPapers.length < 2 ? (
        <Card variant="borderless">
          <Empty description="请选择至少 2 篇论文开始对比" />
        </Card>
      ) : hasUnparsed ? (
        <Card
          variant="borderless"
          title={
            <Space>
              <FileTextOutlined />
              论文尚未解析
            </Space>
          }
        >
          <Paragraph type="secondary" style={{ marginBottom: 16 }}>
            以下论文尚未完成解析，无法进行对比分析。请前往论文详情页手动解析后再试：
          </Paragraph>
          <List
            size="small"
            dataSource={selectedPapers.filter((p) => p.parsedStatus !== 'completed')}
            renderItem={(paper) => (
              <List.Item
                actions={[
                  <Button
                    key="parse"
                    type="link"
                    onClick={() => navigate(`/papers/${paper.id}`)}
                  >
                    去解析
                  </Button>,
                ]}
              >
                <Space direction="vertical" size={2}>
                  <Text strong>{paper.title}</Text>
                  <Text type="secondary">
                    状态：
                    <Tag color={paper.parsedStatus === 'failed' ? 'red' : 'default'}>
                      {paper.parsedStatus === 'failed' ? '解析失败' : '未解析'}
                    </Tag>
                  </Text>
                </Space>
              </List.Item>
            )}
          />
        </Card>
      ) : (
        <>
          {/* 已选论文标签 */}
          <Flex wrap="wrap" gap={8} style={{ marginBottom: 12 }}>
            {selectedPapers.map((paper) => (
              <Tag
                key={paper.id}
                closable
                onClose={() => removePaper(paper.id)}
                style={{ fontSize: 13, padding: '2px 8px' }}
              >
                <BookOutlined style={{ marginRight: 4 }} />
                {paper.title.slice(0, 30)}…
              </Tag>
            ))}
          </Flex>

          {/* 总览矩阵 */}
          <Card
            variant="borderless"
            title={
              <Space>
                <FileTextOutlined />
                结构化对比矩阵
                {loadingMatrix && <Text type="secondary" style={{ fontSize: 13 }}>（AI 对比生成中…）</Text>}
                {matrixData && !loadingMatrix && (
                  <Tag color="green" style={{ marginLeft: 8 }}>AI 对比</Tag>
                )}
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
              loading={loadingMatrix}
              locale={{
                emptyText: (
                  <Empty
                    description="暂无对比数据"
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                  />
                ),
              }}
            />
          </Card>

          {/* 标签对比总览 */}
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} lg={8}>
              <Card
                variant="borderless"
                size="small"
                title={
                  <Space>
                    <TagsOutlined />
                    共同标签
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
                  <Empty description="暂无" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                )}
              </Card>
            </Col>
            <Col xs={24} lg={16}>
              <Card
                variant="borderless"
                size="small"
                title={
                  <Space>
                    <TagsOutlined />
                    各论文标签
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
        </>
      )}
    </main>
  );
}
