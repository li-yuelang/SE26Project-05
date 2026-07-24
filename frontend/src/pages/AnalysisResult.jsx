import ReactMarkdown from 'react-markdown';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Button,
  Card,
  Divider,
  Space,
  Tag,
  Typography,
} from 'antd';
import {
  ArrowLeftOutlined,
  FileTextOutlined,
  TagsOutlined,
  ExperimentOutlined,
  BookOutlined,
} from '@ant-design/icons';
import AsyncPageState from '../components/AsyncPageState';
import useAsyncResource from '../hooks/useAsyncResource';
import { getPaperDetail } from '../services/paperService';

const { Title, Text, Paragraph } = Typography;

export default function AnalysisResult() {
  const navigate = useNavigate();
  const { paperId } = useParams();
  const resource = useAsyncResource(() => getPaperDetail(paperId), [paperId]);
  const paper = resource.data;

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

  const structured = paper.structuredContent || {};
  const hasContent = structured.summary || structured.concept || structured.methods;

  return (
    <div style={{ padding: 24 }}>
      {/* 顶部导航 */}
      <Space style={{ marginBottom: 20 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate(`/papers/${paperId}`)}
        >
          返回论文详情
        </Button>
      </Space>

      {/* 论文标题 & 元信息 */}
      <Title level={3} style={{ marginBottom: 12 }}>{paper.title}</Title>
      <Space wrap style={{ marginBottom: 8 }}>
        {paper.arxivId && (
          <Tag color="blue" icon={<BookOutlined />}>arXiv: {paper.arxivId}</Tag>
        )}
        {paper.published && <Text type="secondary">发布于 {paper.published}</Text>}
      </Space>
      {paper.authors && paper.authors.length > 0 && (
        <Paragraph style={{ marginBottom: 4 }}>
          <Text strong>作者：</Text>
          {paper.authors.join('、')}
        </Paragraph>
      )}

      <Divider />

      {!hasContent ? (
        <Card>
          <Paragraph type="secondary" style={{ textAlign: 'center', padding: '40px 0' }}>
            该论文尚未完成结构化解析。请先触发解析任务，解析完成后即可在此页面查看结果。
          </Paragraph>
        </Card>
      ) : (
        <>
          {/* 摘要总结 */}
          <Card
            title={
              <span><FileTextOutlined style={{ marginRight: 8 }} />摘要总结</span>
            }
            style={{ marginBottom: 24 }}
          >
            <div className="analysis-markdown-content">
              {structured.summary ? (
                <ReactMarkdown>{structured.summary}</ReactMarkdown>
              ) : (
                <Text type="secondary">暂无摘要总结内容</Text>
              )}
            </div>
          </Card>

          {/* 核心概念 */}
          <Card
            title={
              <span><TagsOutlined style={{ marginRight: 8 }} />核心概念</span>
            }
            style={{ marginBottom: 24 }}
          >
            <div className="analysis-markdown-content">
              {structured.concept ? (
                <ReactMarkdown>{structured.concept}</ReactMarkdown>
              ) : (
                <Text type="secondary">暂无核心概念内容</Text>
              )}
            </div>
          </Card>

          {/* 研究方法 */}
          <Card
            title={
              <span><ExperimentOutlined style={{ marginRight: 8 }} />研究方法</span>
            }
            style={{ marginBottom: 24 }}
          >
            <div className="analysis-markdown-content">
              {structured.methods ? (
                <ReactMarkdown>{structured.methods}</ReactMarkdown>
              ) : (
                <Text type="secondary">暂无研究方法内容</Text>
              )}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
