import { useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Descriptions, Tag, Tabs, Card, Row, Col, Typography,
  Divider, Space, Button, Rate, List, Alert, Skeleton, Empty,
  Table, Collapse, Tooltip, message,
} from 'antd';
import {
  StarOutlined, StarFilled, EditOutlined, LinkOutlined,
  ArrowLeftOutlined, BookOutlined, ExperimentOutlined,
  FileTextOutlined, BranchesOutlined, TagsOutlined,
  DownloadOutlined, ShareAltOutlined,
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;

// =====================================================
// 模拟数据（TODO: 对接后端 API 后删除）
// =====================================================
const MOCK_PAPER = {
  id: '1234',
  title: 'Attention Is All You Need',
  authors: ['Ashish Vaswani', 'Noam Shazeer', 'Niki Parmar', 'Jakob Uszkoreit'],
  categories: ['cs.CL', 'cs.LG', 'cs.AI'],
  published: '2017-06-12',
  updated: '2023-08-02',
  arxivId: '1706.03762',
  arxivUrl: 'https://arxiv.org/abs/1706.03762',
  pdfUrl: 'https://arxiv.org/pdf/1706.03762.pdf',
  abstract:
    'The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely. Experiments on two machine translation tasks show that these models are superior in quality while being more parallelizable and requiring significantly less time to train.',
  keywords: ['Transformer', 'attention mechanism', 'sequence transduction', 'machine translation'],
  relatedPapers: [
    { id: '5678', title: 'BERT: Pre-training of Deep Bidirectional Transformers' },
    { id: '9012', title: 'GPT-3: Language Models are Few-Shot Learners' },
    { id: '3456', title: 'Vision Transformer (ViT)' },
  ],
  relatedConcepts: [
    { id: 'c1', name: 'Transformer', description: '一种基于自注意力机制的神经网络架构' },
    { id: 'c2', name: 'Self-Attention', description: '自注意力机制，计算序列内部各位置的关联权重' },
    { id: 'c3', name: 'Multi-Head Attention', description: '多头注意力，并行计算多个注意力表示' },
  ],
  isStarred: false,
  userNote: '',
};

const MOCK_MARKDOWN = {
  summary:
    '该论文提出了一种全新的神经网络架构——Transformer，完全基于注意力机制，摒弃了传统的循环和卷积结构。在机器翻译任务上，Transformer 在训练速度和翻译质量上都达到了当时最优水平。',
  concept:
    '### 核心概念\n\n- **Transformer**：一种基于自注意力机制的编码器-解码器架构\n- **Self-Attention**：计算序列中每个位置与其他位置的相关性\n- **Multi-Head Attention**：并行计算多组注意力，捕捉不同子空间的表示\n- **Positional Encoding**：为模型提供序列中 token 的位置信息',
  methods:
    '### 方法\n\n1. **Scaled Dot-Product Attention**：\n   $$\\text{Attention}(Q,K,V) = \\text{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right)V$$\n\n2. **Multi-Head Attention**：并行执行 h 个注意力函数，拼接后线性投影\n\n3. **Position-wise Feed-Forward Network**：每个位置独立的两层线性变换 + ReLU',
};

export default function PaperDetail() {
  const { paperId } = useParams();
  const [paper] = useState(MOCK_PAPER);
  const [starred, setStarred] = useState(paper.isStarred);
  const [noteVisible, setNoteVisible] = useState(false);
  const [note, setNote] = useState(paper.userNote || '');
  const [readingProgress, setReadingProgress] = useState(0);

  // ===================== 操作回调 =====================
  const handleToggleStar = () => {
    setStarred(!starred);
    message.success(starred ? '已取消收藏' : '已收藏');
  };

  const handleSaveNote = () => {
    setNoteVisible(false);
    message.success('笔记已保存');
  };

  const handleRate = (value) => {
    message.success(`评分: ${value} 分`);
  };

  // ===================== 结构化内容 Tab =====================
  const structureTabs = [
    {
      key: 'summary',
      label: (
        <span><FileTextOutlined /> 摘要总结</span>
      ),
      children: (
        <Card>
          <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: 15 }}>
            {MOCK_MARKDOWN.summary}
          </Paragraph>
        </Card>
      ),
    },
    {
      key: 'concept',
      label: (
        <span><TagsOutlined /> 核心概念</span>
      ),
      children: (
        <Card>
          <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: 15 }}>
            {MOCK_MARKDOWN.concept}
          </Paragraph>
        </Card>
      ),
    },
    {
      key: 'methods',
      label: (
        <span><ExperimentOutlined /> 研究方法</span>
      ),
      children: (
        <Card>
          <Paragraph style={{ whiteSpace: 'pre-wrap', fontSize: 15 }}>
            {MOCK_MARKDOWN.methods}
          </Paragraph>
        </Card>
      ),
    },
  ];

  // ===================== 论文引用信息 =====================
  const citationColumns = [
    { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Button type="link" size="small" icon={<LinkOutlined />}
          onClick={() => message.info('跳转到论文: ' + record.title)}>
          查看
        </Button>
      ),
    },
  ];

  // ===================== 概念关联 =====================
  const conceptColumns = [
    { title: '概念名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Button type="link" size="small"
          onClick={() => message.info('跳转到概念: ' + record.name)}>
          详情
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      {/* ===== 顶部导航 & 操作栏 ===== */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={() => window.history.back()}>
              返回
            </Button>
          </Space>
        </Col>
        <Col>
          <Space>
            <Tooltip title={starred ? '取消收藏' : '收藏论文'}>
              <Button
                icon={starred ? <StarFilled style={{ color: '#faad14' }} /> : <StarOutlined />}
                onClick={handleToggleStar}
              >
                {starred ? '已收藏' : '收藏'}
              </Button>
            </Tooltip>
            <Button icon={<EditOutlined />} onClick={() => setNoteVisible(true)}>
              笔记
            </Button>
            <Button icon={<DownloadOutlined />}>导出</Button>
            <Button icon={<ShareAltOutlined />}>分享</Button>
            <Button type="primary" icon={<LinkOutlined />} href={paper.pdfUrl} target="_blank">
              查看 PDF
            </Button>
          </Space>
        </Col>
      </Row>

      {/* ===== 论文标题 & 元信息 ===== */}
      <Title level={3} style={{ marginBottom: 8 }}>{paper.title}</Title>

      <Space wrap style={{ marginBottom: 12 }}>
        <Tag color="blue" icon={<BookOutlined />}>arXiv: {paper.arxivId}</Tag>
        <Text type="secondary">发布于 {paper.published}</Text>
        <Text type="secondary">| 更新于 {paper.updated}</Text>
        <Rate count={5} onChange={handleRate} style={{ fontSize: 16 }} />
      </Space>

      <Paragraph style={{ marginBottom: 4 }}>
        <Text strong>作者：</Text>
        {paper.authors.join('、')}
      </Paragraph>

      <Space wrap style={{ marginBottom: 16 }}>
        {paper.categories.map((cat) => (
          <Tag key={cat} color="geekblue">{cat}</Tag>
        ))}
      </Space>

      {/* ===== 关键词 ===== */}
      <Space wrap style={{ marginBottom: 20 }}>
        <Text strong>关键词：</Text>
        {paper.keywords.map((kw) => (
          <Tag key={kw} color="purple">{kw}</Tag>
        ))}
      </Space>

      <Divider />

      {/* ===== 摘要 ===== */}
      <Card title="摘要" size="small" style={{ marginBottom: 24 }}>
        <Paragraph style={{ fontSize: 14, lineHeight: 1.8 }}>
          {paper.abstract}
        </Paragraph>
      </Card>

      {/* ===== 结构化内容（Tabs） ===== */}
      <Card title="结构化解析内容" style={{ marginBottom: 24 }} variant="outlined">
        <Tabs items={structureTabs} />
      </Card>

      <Divider />

      {/* ===== 关联信息：网格布局 ===== */}
      <Row gutter={24}>
        {/* 引用/关联论文 */}
        <Col xs={24} lg={12}>
          <Card
            title={<span><BranchesOutlined /> 引用与关联论文</span>}
            size="small"
            style={{ marginBottom: 24 }}
          >
            <Table
              columns={citationColumns}
              dataSource={paper.relatedPapers}
              rowKey="id"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>

        {/* 关联概念 */}
        <Col xs={24} lg={12}>
          <Card
            title={<span><TagsOutlined /> 关联概念</span>}
            size="small"
            style={{ marginBottom: 24 }}
          >
            <Table
              columns={conceptColumns}
              dataSource={paper.relatedConcepts}
              rowKey="id"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>

      {/* ===== 阅读进度 ===== */}
      <Card title="阅读进度" size="small" style={{ marginBottom: 24 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Text>已读进度：{readingProgress}%</Text>
          {/* Antd v6 Progress 用法 */}
          <div
            style={{
              height: 8,
              width: '100%',
              background: '#f0f0f0',
              borderRadius: 4,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${readingProgress}%`,
                background: '#1677ff',
                borderRadius: 4,
                transition: 'width 0.3s',
              }}
            />
          </div>
          <Space>
            <Button size="small" onClick={() => setReadingProgress(Math.min(100, readingProgress + 10))}>
              进度 +10%
            </Button>
            <Button size="small" onClick={() => setReadingProgress(0)}>
              重置
            </Button>
          </Space>
        </Space>
      </Card>

      {/* ===== 笔记弹窗 ===== */}
      {/* 用 antd 的 Modal */}
      {noteVisible && (
        <div
          style={{
            position: 'fixed',
            top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0,0,0,0.45)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          onClick={() => setNoteVisible(false)}
        >
          <div
            style={{
              background: '#fff',
              borderRadius: 8,
              padding: 24,
              width: 500,
              maxWidth: '90vw',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <Title level={4}>论文笔记</Title>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="写下你对这篇论文的笔记..."
              rows={6}
              style={{
                width: '100%',
                border: '1px solid #d9d9d9',
                borderRadius: 6,
                padding: 8,
                fontSize: 14,
                resize: 'vertical',
              }}
            />
            <Space style={{ marginTop: 12, justifyContent: 'flex-end', display: 'flex' }}>
              <Button onClick={() => setNoteVisible(false)}>取消</Button>
              <Button type="primary" onClick={handleSaveNote}>保存</Button>
            </Space>
          </div>
        </div>
      )}
    </div>
  );
}
