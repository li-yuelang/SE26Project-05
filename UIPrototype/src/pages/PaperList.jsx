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
import { listPapers, updatePaper } from '../services/paperService';

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

export default function PaperList() {
  const navigate = useNavigate();

  // 状态
  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [selectedCategory, setSelectedCategory] = useState(undefined);
  const [sortBy, setSortBy] = useState('date_desc');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10 });

  const loadPapers = useCallback(async ({ showSuccess = false } = {}) => {
    setLoading(true);
    try {
      const result = await listPapers();
      setPapers(result.items);
      if (showSuccess) message.success('论文列表已刷新');
    } catch (error) {
      message.error(error.message || '论文列表加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPapers();
  }, [loadPapers]);

  // 切换收藏
  const toggleFavorite = useCallback(async (paperId, e) => {
    e.stopPropagation();
    const paper = papers.find((item) => item.id === paperId);
    if (!paper) return;
    try {
      const updatedPaper = await updatePaper(paperId, {
        isFavorite: !paper.isFavorite,
      });
      setPapers((currentPapers) => currentPapers.map((item) => (
        item.id === paperId ? updatedPaper : item
      )));
    } catch (error) {
      message.error(error.message || '收藏状态更新失败');
    }
  }, [papers]);

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
          onClick={() => loadPapers({ showSuccess: true })}
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
