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
import AsyncPageState from "../components/AsyncPageState";
import useAsyncResource from "../hooks/useAsyncResource";
import { getDashboard } from "../services/dashboardService";

const { Paragraph, Text, Title } = Typography;
const { Search, TextArea } = Input;

export default function Dashboard() {
  const resource = useAsyncResource(getDashboard, []);
  const paperList = resource.data?.papers || [];
  const topicList = resource.data?.topics || [];
  const recentTasks = resource.data?.recentTasks || [];
  const stats = resource.data?.stats || {};
  const [keyword, setKeyword] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");

  const categories = useMemo(() => {
    return ["all", ...new Set(paperList.map((paper) => paper.category))].map(
      (category) => ({
        label: category === "all" ? "全部分类" : category,
        value: category,
      }),
    );
  }, [paperList]);

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
  }, [keyword, paperList, selectedCategory]);

  const paperColumns = [
    {
      title: "论文",
      dataIndex: "title",
      render: (_, paper) => (
        <Space orientation="vertical" size={2}>
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
      <Card className="dashboard-hero" variant="borderless">
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
                <Statistic title="入库论文" value={stats.papers || 0} suffix="篇" />
              </Col>
              <Col span={12}>
                <Statistic title="研究主题" value={stats.topics || 0} />
              </Col>
              <Col span={12}>
                <Statistic title="知识概念" value={stats.concepts || 0} />
              </Col>
              <Col span={12}>
                <Statistic title="运行任务" value={stats.runningTasks || 0} />
              </Col>
            </Row>
          </Col>
        </Row>
      </Card>

      <Row gutter={[20, 20]}>
        <Col xs={24} xl={16}>
          <Card title="最新论文" variant="borderless">
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
          <Card title="热门研究方向" variant="borderless">
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
        </Col>
      </Row>

      <Row gutter={[20, 20]}>
        <Col xs={24} lg={8}>
          <Card title="论文知识 Wiki" variant="borderless">
            <Paragraph type="secondary">
              检索论文之间的引用关系、主题关联和概念关联，快速了解一个方向的研究脉络。
            </Paragraph>
            <Search placeholder="输入概念、方法、论文标题或作者" enterButton="检索 Wiki" />
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="智能问答" variant="borderless">
            <Paragraph type="secondary">
              围绕论文内容、概念解释、研究方法或研究脉络进行提问。
            </Paragraph>
            <Space orientation="vertical" className="dashboard-list-item">
              <TextArea rows={4} placeholder="例如：RAG 在论文阅读中通常怎么使用？" />
              <Button type="primary" block>
                开始提问
              </Button>
            </Space>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="最近任务" variant="borderless">
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
