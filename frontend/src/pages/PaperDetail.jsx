import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  Descriptions, Tag, Tabs, Card, Row, Col, Typography,
  Divider, Space, Button, Rate, List, Alert, Skeleton, Empty,
  Table, Collapse, Tooltip, message, Modal,
} from 'antd';
import {
  StarOutlined, StarFilled, EditOutlined, LinkOutlined,
  ArrowLeftOutlined, BookOutlined, ExperimentOutlined,
  FileTextOutlined, BranchesOutlined, TagsOutlined,
  DownloadOutlined, ShareAltOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import AsyncPageState from '../components/AsyncPageState';
import useAsyncResource from '../hooks/useAsyncResource';
import { deletePaper, getPaperChunk, getPaperDetail, updatePaper } from '../services/paperService';

const { Title, Text, Paragraph } = Typography;

export default function PaperDetail() {
  const navigate = useNavigate();
  const { paperId } = useParams();
  const [searchParams] = useSearchParams();
  const citedChunkIndex = searchParams.get('chunk');
  const resource = useAsyncResource(() => getPaperDetail(paperId), [paperId]);
  const citedChunk = useAsyncResource(
    () => citedChunkIndex == null ? Promise.resolve(null) : getPaperChunk(paperId, citedChunkIndex),
    [paperId, citedChunkIndex],
  );
  const paper = resource.data;
  const [starred, setStarred] = useState(false);
  const [noteVisible, setNoteVisible] = useState(false);
  const [note, setNote] = useState('');
  const [readingProgress, setReadingProgress] = useState(0);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!paper) return;
    setStarred(paper.isStarred);
    setNote(paper.userNote || '');
    setReadingProgress(paper.progress || 0);
  }, [paper]);

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

  // ===================== 操作回调 =====================
  const handleToggleStar = async () => {
    try {
      await updatePaper(paper.id, { isStarred: !starred, isFavorite: !starred });
      setStarred(!starred);
      message.success(starred ? '已取消收藏' : '已收藏');
    } catch (error) {
      message.error(error.message || '收藏状态更新失败');
    }
  };

  const handleSaveNote = async () => {
    try {
      await updatePaper(paper.id, { userNote: note });
      setNoteVisible(false);
      message.success('笔记已保存');
    } catch (error) {
      message.error(error.message || '笔记保存失败');
    }
  };

  const handleRate = (value) => {
    message.success(`评分: ${value} 分`);
  };

  const handleDelete = () => {
    Modal.confirm({
      title: '删除论文？',
      content: '该论文及相关解析内容、收藏、笔记和引用记录将被永久删除。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        setDeleting(true);
        try {
          await deletePaper(paper.id);
          message.success('论文已删除');
          navigate('/papers', { replace: true });
        } catch (error) {
          message.error(error.message || '论文删除失败');
          throw error;
        } finally {
          setDeleting(false);
        }
      },
    });
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
            {paper.structuredContent.summary}
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
            {paper.structuredContent.concept}
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
            {paper.structuredContent.methods}
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
            <Button danger icon={<DeleteOutlined />} loading={deleting} onClick={handleDelete}>
              删除
            </Button>
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

      {citedChunkIndex != null && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 24 }}
          message={`问答引用定位 · 片段 ${citedChunkIndex}${citedChunk.data?.sectionTitle ? ` · ${citedChunk.data.sectionTitle}` : ''}`}
          description={
            citedChunk.loading
              ? '正在加载引用原文…'
              : citedChunk.error
                ? citedChunk.error.message
                : citedChunk.data?.content
          }
        />
      )}

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
        <Space orientation="vertical" style={{ width: '100%' }}>
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
