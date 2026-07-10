import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Input,
  Select,
  Table,
  Tag,
  Button,
  Space,
  Tooltip,
  Empty,
  Spin,
  message,
  Row,
  Col,
  Card,
  Typography,
  Badge,
} from 'antd';
import {
  SearchOutlined,
  ReloadOutlined,
  StarOutlined,
  StarFilled,
  ExportOutlined,
  FilterOutlined,
  BookOutlined,
  CalendarOutlined,
  UserOutlined,
  TagOutlined,
} from '@ant-design/icons';

const { Search } = Input;
const { Option } = Select;
const { Text } = Typography;

// 论文分类列表
const CATEGORIES = [
  { value: 'cs.AI', label: 'cs.AI - 人工智能' },
  { value: 'cs.CL', label: 'cs.CL - 计算语言学' },
  { value: 'cs.CV', label: 'cs.CV - 计算机视觉' },
  { value: 'cs.LG', label: 'cs.LG - 机器学习' },
  { value: 'cs.IR', label: 'cs.IR - 信息检索' },
  { value: 'cs.SE', label: 'cs.SE - 软件工程' },
  { value: 'stat.ML', label: 'stat.ML - 机器学习(统计)' },
  { value: 'math.OC', label: 'math.OC - 优化与控制' },
];

// 排序选项
const SORT_OPTIONS = [
  { value: 'date_desc', label: '发布日期(最新)' },
  { value: 'date_asc', label: '发布日期(最早)' },
  { value: 'title_asc', label: '标题(A-Z)' },
  { value: 'title_desc', label: '标题(Z-A)' },
];

// 模拟论文数据
const generateMockPapers = () => [
  {
    id: '2401.00001',
    title: 'Attention Is All You Need: Revisited',
    authors: ['Wei Zhang', 'Yuki Tanaka', 'Maria Garcia'],
    abstract: 'We revisit the foundational transformer architecture and propose several improvements to the self-attention mechanism. Our modifications reduce computational complexity from O(n²) to O(n log n) while maintaining model quality. We demonstrate through extensive experiments on language modeling and translation tasks that our approach achieves comparable performance with significantly less computation.',
    categories: ['cs.CL', 'cs.LG'],
    publishedDate: '2024-12-15',
    updatedDate: '2024-12-20',
    link: 'https://arxiv.org/abs/2401.00001',
    pdfLink: 'https://arxiv.org/pdf/2401.00001',
    isFavorite: false,
    isRead: true,
  },
  {
    id: '2401.00002',
    title: 'Efficient Fine-Tuning of Large Language Models with Adaptive LoRA',
    authors: ['Jun Li', 'Sarah Chen', 'Raj Patel'],
    abstract: 'Large language models have demonstrated remarkable capabilities but are expensive to fine-tune. We propose Adaptive LoRA (AdaLoRA), a parameter-efficient fine-tuning method that dynamically adjusts the rank of low-rank decomposition during training. AdaLoRA allocates higher ranks to important weight matrices and prunes less important ones, achieving better performance than standard LoRA with fewer trainable parameters.',
    categories: ['cs.CL', 'cs.AI'],
    publishedDate: '2024-12-10',
    updatedDate: '2024-12-10',
    link: 'https://arxiv.org/abs/2401.00002',
    pdfLink: 'https://arxiv.org/pdf/2401.00002',
    isFavorite: true,
    isRead: true,
  },
  {
    id: '2401.00003',
    title: 'Vision-Language Pre-training at Scale with Contrastive Learning',
    authors: ['Emily Wang', 'Thomas Müller', 'Priya Sharma', 'David Kim'],
    abstract: 'We present a comprehensive study on vision-language pre-training at scale. By leveraging a novel contrastive learning objective and a curated dataset of 500 million image-text pairs, we train models that achieve state-of-the-art performance on zero-shot image classification, visual question answering, and image-text retrieval benchmarks.',
    categories: ['cs.CV', 'cs.CL'],
    publishedDate: '2024-12-08',
    updatedDate: '2024-12-12',
    link: 'https://arxiv.org/abs/2401.00003',
    pdfLink: 'https://arxiv.org/pdf/2401.00003',
    isFavorite: false,
    isRead: false,
  },
  {
    id: '2401.00004',
    title: 'Graph Neural Networks for Molecular Property Prediction: A Survey',
    authors: ['Alex Johnson', 'Mei Lin'],
    abstract: 'Graph neural networks (GNNs) have emerged as powerful tools for molecular property prediction. This survey provides a comprehensive overview of recent advances in GNN-based molecular modeling, covering message-passing frameworks, equivariant architectures, and 3D-aware representations. We categorize existing methods, analyze their strengths and limitations, and identify promising directions for future research.',
    categories: ['cs.LG', 'cs.AI'],
    publishedDate: '2024-12-05',
    updatedDate: '2024-12-05',
    link: 'https://arxiv.org/abs/2401.00004',
    pdfLink: 'https://arxiv.org/pdf/2401.00004',
    isFavorite: true,
    isRead: false,
  },
  {
    id: '2401.00005',
    title: 'Retrieval-Augmented Generation with Knowledge Graphs for Fact-Checking',
    authors: ['Oliver Brown', 'Yuna Park', 'Carlos Rodriguez'],
    abstract: 'We propose KG-RAG, a retrieval-augmented generation framework that integrates structured knowledge from knowledge graphs with unstructured text retrieval for automated fact-checking. Our system first retrieves relevant claims from both KG triples and text corpora, then uses a large language model to synthesize evidence and produce verifiable judgments.',
    categories: ['cs.IR', 'cs.AI', 'cs.CL'],
    publishedDate: '2024-12-01',
    updatedDate: '2024-12-03',
    link: 'https://arxiv.org/abs/2401.00005',
    pdfLink: 'https://arxiv.org/pdf/2401.00005',
    isFavorite: false,
    isRead: true,
  },
  {
    id: '2401.00006',
    title: 'Scalable Distributed Training of Foundation Models with Pipeline Parallelism',
    authors: ['Hao Chen', 'Lisa Anderson', 'Kenji Yamamoto'],
    abstract: 'Training foundation models requires efficient distributed computing strategies. We introduce PipeDream-2D, a novel pipeline parallelism approach that combines micro-batch scheduling with 2D mesh communication. Our system achieves near-linear scaling efficiency on clusters with thousands of GPUs, reducing training time by 40% compared to existing approaches.',
    categories: ['cs.LG', 'cs.SE'],
    publishedDate: '2024-11-28',
    updatedDate: '2024-11-28',
    link: 'https://arxiv.org/abs/2401.00006',
    pdfLink: 'https://arxiv.org/pdf/2401.00006',
    isFavorite: false,
    isRead: false,
  },
  {
    id: '2401.00007',
    title: 'Self-Supervised Learning for Code Understanding and Generation',
    authors: ['Rui Xu', 'Anna Kowalski'],
    abstract: 'We present CodeSSL, a self-supervised learning framework for code understanding that combines masked token prediction with contrastive learning over code semantics. Pre-trained on 100GB of open-source code, CodeSSL achieves strong performance on code completion, bug detection, and code summarization tasks with minimal fine-tuning data.',
    categories: ['cs.SE', 'cs.CL'],
    publishedDate: '2024-11-25',
    updatedDate: '2024-11-30',
    link: 'https://arxiv.org/abs/2401.00007',
    pdfLink: 'https://arxiv.org/pdf/2401.00007',
    isFavorite: false,
    isRead: false,
  },
  {
    id: '2401.00008',
    title: 'Robust Optimization for Fair Machine Learning Under Distribution Shift',
    authors: ['Fatima Al-Hassan', 'James Wilson', 'Sophie Laurent'],
    abstract: 'Distribution shift poses significant challenges for fair machine learning. We propose a robust optimization framework that simultaneously minimizes worst-case risk across demographic groups while maintaining overall performance. Our theoretical analysis provides convergence guarantees, and experiments on real-world datasets demonstrate substantial improvements in fairness metrics.',
    categories: ['cs.LG', 'stat.ML'],
    publishedDate: '2024-11-20',
    updatedDate: '2024-11-20',
    link: 'https://arxiv.org/abs/2401.00008',
    pdfLink: 'https://arxiv.org/pdf/2401.00008',
    isFavorite: false,
    isRead: true,
  },
  {
    id: '2401.00009',
    title: 'Multi-Agent Reinforcement Learning for Autonomous Vehicle Coordination',
    authors: ['Marco Rossi', 'Xin Huang', 'Rachel Green'],
    abstract: 'We study the problem of coordinating multiple autonomous vehicles at urban intersections using multi-agent reinforcement learning (MARL). Our proposed method, IntersectionMARL, learns cooperative policies that optimize traffic flow while ensuring safety. Simulations show a 35% reduction in average waiting time and 20% reduction in fuel consumption compared to traffic-light-based control.',
    categories: ['cs.AI', 'cs.LG'],
    publishedDate: '2024-11-15',
    updatedDate: '2024-11-18',
    link: 'https://arxiv.org/abs/2401.00009',
    pdfLink: 'https://arxiv.org/pdf/2401.00009',
    isFavorite: false,
    isRead: false,
  },
  {
    id: '2401.00010',
    title: 'Neural Architecture Search with Hardware-Aware Constraints for Edge Deployment',
    authors: ['Liang Wei', 'Diana Popov', 'Arjun Mehta'],
    abstract: 'Deploying neural networks on edge devices requires balancing accuracy with hardware constraints. We propose HW-NAS, a hardware-aware neural architecture search method that jointly optimizes model accuracy, latency, and energy consumption. HW-NAS uses a differentiable search strategy with a hardware cost model, producing architectures that run 3x faster on mobile GPUs with less than 1% accuracy drop.',
    categories: ['cs.CV', 'cs.LG'],
    publishedDate: '2024-11-10',
    updatedDate: '2024-11-10',
    link: 'https://arxiv.org/abs/2401.00010',
    pdfLink: 'https://arxiv.org/pdf/2401.00010',
    isFavorite: true,
    isRead: false,
  },
];

export default function PaperList() {
  const navigate = useNavigate();

  // 状态
  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [selectedCategory, setSelectedCategory] = useState(undefined);
  const [sortBy, setSortBy] = useState('date_desc');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10 });

  // 加载数据（模拟）
  useEffect(() => {
    setLoading(true);
    const timer = setTimeout(() => {
      setPapers(generateMockPapers());
      setLoading(false);
    }, 600);
    return () => clearTimeout(timer);
  }, []);

  // 切换收藏
  const toggleFavorite = useCallback((paperId, e) => {
    e.stopPropagation();
    setPapers((prev) =>
      prev.map((p) =>
        p.id === paperId ? { ...p, isFavorite: !p.isFavorite } : p
      )
    );
  }, []);

  // 过滤 + 排序
  const filteredPapers = papers
    .filter((paper) => {
      const keyword = searchText.trim().toLowerCase();
      if (keyword) {
        const matchTitle = paper.title.toLowerCase().includes(keyword);
        const matchAuthors = paper.authors.some((a) =>
          a.toLowerCase().includes(keyword)
        );
        const matchAbstract = paper.abstract.toLowerCase().includes(keyword);
        const matchId = paper.id.toLowerCase().includes(keyword);
        if (!matchTitle && !matchAuthors && !matchAbstract && !matchId) {
          return false;
        }
      }
      if (selectedCategory && !paper.categories.includes(selectedCategory)) {
        return false;
      }
      return true;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'date_asc':
          return a.publishedDate.localeCompare(b.publishedDate);
        case 'title_asc':
          return a.title.localeCompare(b.title);
        case 'title_desc':
          return b.title.localeCompare(a.title);
        case 'date_desc':
        default:
          return b.publishedDate.localeCompare(a.publishedDate);
      }
    });

  // 跳转到论文详情页
  const goToDetail = (paperId, e) => {
    if (e) e.stopPropagation();
    navigate(`/papers/${paperId}`);
  };

  // 表格列定义
  const columns = [
    {
      title: '',
      key: 'favorite',
      width: 40,
      render: (_, record) => (
        <Tooltip title={record.isFavorite ? '取消收藏' : '收藏'}>
          <Button
            type="text"
            size="small"
            icon={
              record.isFavorite ? (
                <StarFilled style={{ color: '#faad14' }} />
              ) : (
                <StarOutlined style={{ color: '#d9d9d9' }} />
              )
            }
            onClick={(e) => toggleFavorite(record.id, e)}
          />
        </Tooltip>
      ),
    },
    {
      title: '论文',
      key: 'paper',
      ellipsis: true,
      render: (_, record) => (
        <div className="paper-cell">
          <div
            className="paper-cell-title"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/papers/${record.id}`);
            }}
          >
            {record.title}
          </div>
          <div className="paper-cell-meta">
            <UserOutlined /> {record.authors.join(', ')}
          </div>
        </div>
      ),
    },
    {
      title: '分类',
      key: 'categories',
      width: 200,
      render: (_, record) => (
        <Space size={[0, 4]} wrap>
          {record.categories.map((cat) => (
            <Tag key={cat} color="blue">
              {cat}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '发布日期',
      dataIndex: 'publishedDate',
      key: 'publishedDate',
      width: 120,
      sorter: (a, b) => a.publishedDate.localeCompare(b.publishedDate),
      render: (date) => (
        <Space>
          <CalendarOutlined style={{ color: '#8c8c8c' }} />
          {date}
        </Space>
      ),
    },
    {
      title: '状态',
      key: 'status',
      width: 80,
      render: (_, record) => (
        <Badge
          status={record.isRead ? 'default' : 'processing'}
          text={record.isRead ? '已读' : '未读'}
        />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_, record) => (
        <Space>
          <Tooltip title="查看详情">
            <Button
              type="link"
              size="small"
              icon={<BookOutlined />}
              onClick={(e) => goToDetail(record.id, e)}
            />
          </Tooltip>
          <Tooltip title="在 arXiv 中打开">
            <Button
              type="link"
              size="small"
              icon={<ExportOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                window.open(record.link, '_blank');
              }}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div className="page">
      {/* 页面标题 */}
      <div className="paper-list-header">
        <div>
          <h2>论文列表</h2>
          <p>浏览与检索 ArXiv 论文</p>
        </div>
        <Button
          type="primary"
          icon={<ReloadOutlined />}
          onClick={() => {
            setLoading(true);
            setTimeout(() => {
              setPapers(generateMockPapers());
              setLoading(false);
              message.success('论文列表已刷新');
            }, 500);
          }}
        >
          刷新
        </Button>
      </div>

      {/* 搜索与筛选 */}
      <Card className="paper-filter-card" size="small">
        <Row gutter={[16, 12]} align="middle">
          <Col flex="auto">
            <Search
              placeholder="搜索论文标题、作者、摘要或 arXiv ID..."
              prefix={<SearchOutlined />}
              allowClear
              size="large"
              value={searchText}
              onChange={(e) => {
                setSearchText(e.target.value);
                setPagination((prev) => ({ ...prev, current: 1 }));
              }}
              onSearch={() => {}}
            />
          </Col>
          <Col>
            <Select
              placeholder="选择分类"
              allowClear
              style={{ width: 200 }}
              value={selectedCategory}
              onChange={(val) => {
                setSelectedCategory(val);
                setPagination((prev) => ({ ...prev, current: 1 }));
              }}
              suffixIcon={<FilterOutlined />}
            >
              {CATEGORIES.map((cat) => (
                <Option key={cat.value} value={cat.value}>
                  {cat.label}
                </Option>
              ))}
            </Select>
          </Col>
          <Col>
            <Select
              value={sortBy}
              style={{ width: 180 }}
              onChange={(val) => setSortBy(val)}
            >
              {SORT_OPTIONS.map((opt) => (
                <Option key={opt.value} value={opt.value}>
                  {opt.label}
                </Option>
              ))}
            </Select>
          </Col>
        </Row>
      </Card>

      {/* 统计信息 */}
      <div className="paper-list-stats">
        <Text type="secondary">
          共 <Text strong>{filteredPapers.length}</Text> 篇论文
          {searchText && (
            <span>
              {' '}
              | 关键词: <Text code>{searchText}</Text>
            </span>
          )}
          {selectedCategory && (
            <span>
              {' '}
              | 分类: <Tag color="blue">{selectedCategory}</Tag>
            </span>
          )}
        </Text>
      </div>

      {/* 论文表格 */}
      <Table
        columns={columns}
        dataSource={filteredPapers}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          total: filteredPapers.length,
          showSizeChanger: true,
          showQuickJumper: true,
          pageSizeOptions: ['5', '10', '20', '50'],
          showTotal: (total, range) =>
            `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
          onChange: (page, pageSize) =>
            setPagination({ current: page, pageSize }),
        }}
        locale={{
          emptyText: (
            <Empty
              description="暂无匹配的论文"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          ),
        }}
        onRow={(record) => ({
          onClick: () => navigate(`/papers/${record.id}`),
          style: { cursor: 'pointer' },
        })}
      />

    </div>
  );
}
