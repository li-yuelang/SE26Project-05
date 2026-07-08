import { useNavigate, useParams } from 'react-router-dom';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Progress,
  Row,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import {
  ArrowLeftOutlined,
  BookOutlined,
  BranchesOutlined,
  FileTextOutlined,
  TagsOutlined,
} from '@ant-design/icons';
import { getConceptById, getRelatedConcepts } from '../data/wikiData';

const { Paragraph, Text, Title } = Typography;

export default function ConceptDetail() {
  const { conceptId } = useParams();
  const navigate = useNavigate();
  const concept = getConceptById(conceptId);

  if (!concept) {
    return (
      <div className="page">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/wiki')}>
          返回 Wiki
        </Button>
        <Empty
          className="concept-empty"
          description={`没有找到概念：${conceptId}`}
        />
      </div>
    );
  }

  const relatedConcepts = getRelatedConcepts(concept);

  const paperColumns = [
    {
      title: '论文',
      dataIndex: 'title',
      render: (_, paper) => (
        <Space orientation="vertical" size={2}>
          <Button type="link" onClick={() => navigate(`/papers/${paper.id}`)}>
            {paper.title}
          </Button>
          <Text type="secondary">arXiv: {paper.id}</Text>
        </Space>
      ),
    },
    {
      title: '年份',
      dataIndex: 'year',
      width: 100,
    },
    {
      title: '知识作用',
      dataIndex: 'role',
      render: (role) => <Tag color="geekblue">{role}</Tag>,
    },
  ];

  const relationColumns = [
    {
      title: '相关概念',
      dataIndex: ['concept', 'name'],
      render: (_, relation) =>
        relation.exists ? (
          <Button
            type="link"
            onClick={() => navigate(`/wiki/concepts/${relation.concept.id}`)}
          >
            {relation.concept.name}
          </Button>
        ) : (
          <Space>
            <Text>{relation.concept.name}</Text>
            <Tag>整理中</Tag>
          </Space>
        ),
    },
    {
      title: '关系类型',
      dataIndex: 'type',
      width: 140,
      render: (type) => <Tag>{type}</Tag>,
    },
    {
      title: '强度',
      dataIndex: 'strength',
      width: 180,
      render: (strength) => (
        <Progress percent={strength} size="small" />
      ),
    },
  ];

  return (
    <main className="concept-page">
      <Space className="concept-toolbar">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/wiki')}>
          返回 Wiki
        </Button>
      </Space>

      <Card variant="borderless" className="concept-hero">
        <Space orientation="vertical" size={14}>
          <Space wrap>
            <Tag color="blue" icon={<TagsOutlined />}>
              {concept.category}
            </Tag>
            <Text type="secondary">更新于 {concept.updatedAt}</Text>
          </Space>
          <Title level={2}>{concept.name}</Title>
          <Paragraph>{concept.description}</Paragraph>
          <Space size={[8, 8]} wrap>
            {concept.aliases.map((alias) => (
              <Tag key={alias}>{alias}</Tag>
            ))}
          </Space>
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card variant="borderless">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="提及次数">
                {concept.mentions}
              </Descriptions.Item>
              <Descriptions.Item label="来源论文">
                {concept.paperCount} 篇
              </Descriptions.Item>
              <Descriptions.Item label="热度趋势">
                <Progress percent={concept.trend} size="small" />
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} md={16}>
          <Card
            variant="borderless"
            title={
              <Space>
                <FileTextOutlined />
                核心笔记
              </Space>
            }
          >
            <ul className="wiki-note-list concept-note-list">
              {concept.summaryPoints.map((point) => (
                <li key={point} className="wiki-note-item">
                  <Text>{point}</Text>
                </li>
              ))}
            </ul>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card
            variant="borderless"
            title={
              <Space>
                <BookOutlined />
                来源论文
              </Space>
            }
          >
            <Table
              rowKey="id"
              columns={paperColumns}
              dataSource={concept.papers}
              pagination={false}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card
            variant="borderless"
            title={
              <Space>
                <BranchesOutlined />
                相关概念
              </Space>
            }
          >
            <Table
              rowKey="id"
              columns={relationColumns}
              dataSource={relatedConcepts}
              pagination={false}
            />
          </Card>
        </Col>
      </Row>
    </main>
  );
}
