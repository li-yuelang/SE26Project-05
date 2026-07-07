import { useMemo, useState } from "react";
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
} from "antd";

const { Paragraph, Text, Title } = Typography;
const { Search, TextArea } = Input;

const paperList = [
  {
    id: "2406.01234",
    title: "Retrieval-Augmented Agents for Scientific Literature Review",
    authors: ["Alice Chen", "Bo Wang", "Carol Smith"],
    category: "cs.AI",
    publishedAt: "2026-07-01",
    tags: ["RAG", "Agent", "Literature Review"],
    summary:
      "This paper studies how retrieval-augmented agents can help users read, connect, and summarize large collections of scientific papers.",
    arxivUrl: "https://arxiv.org/abs/2406.01234",
  },
  {
    id: "2406.05678",
    title: "Concept Graph Construction from Research Papers",
    authors: ["David Liu", "Emma Brown"],
    category: "cs.CL",
    publishedAt: "2026-06-28",
    tags: ["Concept Graph", "Information Extraction", "NLP"],
    summary:
      "This paper proposes a pipeline for extracting concepts, methods, research questions, and experimental conclusions from paper text.",
    arxivUrl: "https://arxiv.org/abs/2406.05678",
  },
  {
    id: "2406.09123",
    title: "Automatic Paper Classification with Topic-Aware Embeddings",
    authors: ["Frank Zhang", "Grace Miller"],
    category: "cs.IR",
    publishedAt: "2026-06-20",
    tags: ["Paper Classification", "Embedding", "Search"],
    summary:
      "This work introduces topic-aware embeddings for organizing papers by research area, author, publication time, and concept labels.",
    arxivUrl: "https://arxiv.org/abs/2406.09123",
  },
];

const topicList = [
  { name: "Large Language Models", count: 42, percent: 86 },
  { name: "Retrieval-Augmented Generation", count: 31, percent: 64 },
  { name: "Computer Vision", count: 18, percent: 38 },
  { name: "Graph Neural Networks", count: 15, percent: 32 },
];

const recentTasks = [
  {
    name: "arXiv paper fetching",
    status: "Completed",
    color: "green",
    description: "Fetched 18 new papers from cs.AI and cs.CL.",
  },
  {
    name: "PDF structure parsing",
    status: "Running",
    color: "blue",
    description: "Generating summary.md, concept.md, and methods.md for 6 papers.",
  },
  {
    name: "Knowledge wiki update",
    status: "Pending",
    color: "gold",
    description: "Waiting for concept extraction results.",
  },
];

export default function Dashboard() {
  const [keyword, setKeyword] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");

  const categories = useMemo(() => {
    return ["all", ...new Set(paperList.map((paper) => paper.category))].map(
      (category) => ({
        label: category === "all" ? "全部分类" : category,
        value: category,
      }),
    );
  }, []);

  const filteredPapers = useMemo(() => {
    return paperList.filter((paper) => {
      const matchesCategory =
        selectedCategory === "all" || paper.category === selectedCategory;
      const searchText = [
        paper.title,
        paper.summary,
        paper.category,
        paper.authors.join(" "),
        paper.tags.join(" "),
      ]
        .join(" ")
        .toLowerCase();

      return matchesCategory && searchText.includes(keyword.toLowerCase());
    });
  }, [keyword, selectedCategory]);

  const paperColumns = [
    {
      title: "论文",
      dataIndex: "title",
      render: (_, paper) => (
        <Space direction="vertical" size={2}>
          <a href={paper.arxivUrl} target="_blank" rel="noreferrer">
            {paper.title}
          </a>
          <Text type="secondary">{paper.authors.join(", ")}</Text>
        </Space>
      ),
    },
    {
      title: "分类",
      dataIndex: "category",
      width: 110,
      render: (category) => <Tag color="geekblue">{category}</Tag>,
    },
    {
      title: "发布日期",
      dataIndex: "publishedAt",
      width: 130,
    },
    {
      title: "标签",
      dataIndex: "tags",
      render: (tags) => (
        <Flex gap={6} wrap="wrap">
          {tags.map((tag) => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </Flex>
      ),
    },
  ];

  return (
    <main className="dashboard-page">
      <Card className="dashboard-hero" bordered={false}>
        <Row gutter={[24, 24]} align="middle">
          <Col xs={24} lg={14}>
            <Text className="dashboard-eyebrow">Arxiv Paper Mate</Text>
            <Title level={1}>自动抓取、解析、检索和问答的论文阅读助手</Title>
            <Paragraph>
              定时获取 arXiv 论文，生成结构化笔记，构建论文 Wiki，并基于知识库进行自然语言问答。
            </Paragraph>
            <Space.Compact className="dashboard-search">
              <Search
                allowClear
                placeholder="输入标题、作者、关键词或研究方向"
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                onSearch={setKeyword}
              />
              <Select
                options={categories}
                value={selectedCategory}
                onChange={setSelectedCategory}
              />
            </Space.Compact>
          </Col>
          <Col xs={24} lg={10}>
            <Row gutter={[16, 16]}>
              <Col span={12}>
                <Statistic title="入库论文" value={128} suffix="篇" />
              </Col>
              <Col span={12}>
                <Statistic title="本周新增" value={18} suffix="篇" />
              </Col>
              <Col span={12}>
                <Statistic title="知识概念" value={356} />
              </Col>
              <Col span={12}>
                <Statistic title="运行任务" value={6} />
              </Col>
            </Row>
          </Col>
        </Row>
      </Card>

      <Row gutter={[20, 20]}>
        <Col xs={24} xl={16}>
          <Card title="最新论文" bordered={false}>
            <Table
              rowKey="id"
              columns={paperColumns}
              dataSource={filteredPapers}
              pagination={false}
              locale={{ emptyText: <Empty description="没有找到匹配的论文" /> }}
            />
          </Card>
        </Col>

        <Col xs={24} xl={8}>
          <Card title="热门研究方向" bordered={false}>
            <List
              dataSource={topicList}
              renderItem={(topic) => (
                <List.Item>
                  <Space direction="vertical" className="dashboard-list-item">
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
        </Col>
      </Row>

      <Row gutter={[20, 20]}>
        <Col xs={24} lg={8}>
          <Card title="论文知识 Wiki" bordered={false}>
            <Paragraph type="secondary">
              检索论文之间的引用关系、主题关联和概念关联，快速了解一个方向的研究脉络。
            </Paragraph>
            <Search placeholder="输入概念、方法、论文标题或作者" enterButton="检索 Wiki" />
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="智能问答" bordered={false}>
            <Paragraph type="secondary">
              围绕论文内容、概念解释、研究方法或研究脉络进行提问。
            </Paragraph>
            <Space direction="vertical" className="dashboard-list-item">
              <TextArea rows={4} placeholder="例如：RAG 在论文阅读中通常怎么使用？" />
              <Button type="primary" block>
                开始提问
              </Button>
            </Space>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="最近任务" bordered={false}>
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
        </Col>
      </Row>
    </main>
  );
}
