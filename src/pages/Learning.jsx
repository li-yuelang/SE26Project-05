import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Flex,
  Input,
  List,
  Modal,
  Progress,
  Rate,
  Row,
  Segmented,
  Select,
  Slider,
  Space,
  Statistic,
  Table,
  Tag,
  Timeline,
  Typography,
  message,
} from 'antd';
import {
  BookOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CommentOutlined,
  EditOutlined,
  EyeOutlined,
  FileSearchOutlined,
  FireOutlined,
  HistoryOutlined,
  LinkOutlined,
  ReadOutlined,
  StarFilled,
  StarOutlined,
  TagsOutlined,
} from '@ant-design/icons';
import {
  followedTopics,
  learningNotes,
  learningPapers,
  readingHistory,
  statusMeta,
} from '../data/learningData';

const { Search, TextArea } = Input;
const { Paragraph, Text, Title } = Typography;

const priorityColor = {
  高: 'red',
  中: 'gold',
  低: 'blue',
};

export default function Learning() {
  const navigate = useNavigate();
  const [papers, setPapers] = useState(learningPapers);
  const [topics, setTopics] = useState(followedTopics);
  const [activeView, setActiveView] = useState('queue');
  const [keyword, setKeyword] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [directionFilter, setDirectionFilter] = useState('all');
  const [selectedPaperIds, setSelectedPaperIds] = useState([]);
  const [noteModalOpen, setNoteModalOpen] = useState(false);
  const [activePaper, setActivePaper] = useState(null);
  const [draftNote, setDraftNote] = useState('');
  const [draftProgress, setDraftProgress] = useState(0);
  const [draftRating, setDraftRating] = useState(0);

  const directions = useMemo(
    () => ['all', ...Array.from(new Set(papers.map((paper) => paper.direction)))],
    [papers],
  );

  const stats = useMemo(() => {
    const totalMinutes = papers.reduce((sum, paper) => sum + paper.readMinutes, 0);

    return {
      favorites: papers.filter((paper) => paper.favorite).length,
      reading: papers.filter((paper) => paper.status === 'reading').length,
      done: papers.filter((paper) => paper.status === 'done').length,
      notes: papers.reduce((sum, paper) => sum + paper.notesCount, 0),
      hours: Math.round(totalMinutes / 6) / 10,
    };
  }, [papers]);

  const filteredPapers = useMemo(() => {
    const normalizedKeyword = keyword.trim().toLowerCase();

    return papers.filter((paper) => {
      const matchesStatus =
        statusFilter === 'all' ||
        paper.status === statusFilter ||
        (statusFilter === 'favorite' && paper.favorite);
      const matchesDirection =
        directionFilter === 'all' || paper.direction === directionFilter;
      const searchableText = [
        paper.title,
        paper.authors.join(' '),
        paper.categories.join(' '),
        paper.direction,
        paper.tags.join(' '),
        paper.summary,
      ]
        .join(' ')
        .toLowerCase();

      return (
        matchesStatus &&
        matchesDirection &&
        searchableText.includes(normalizedKeyword)
      );
    });
  }, [directionFilter, keyword, papers, statusFilter]);

  const visiblePapers = useMemo(
    () =>
      activeView === 'favorites'
        ? filteredPapers.filter((paper) => paper.favorite)
        : filteredPapers,
    [activeView, filteredPapers],
  );

  const selectedPapers = useMemo(
    () => papers.filter((paper) => selectedPaperIds.includes(paper.id)),
    [papers, selectedPaperIds],
  );

  const openNoteModal = (paper) => {
    setActivePaper(paper);
    setDraftNote(paper.userNote || '');
    setDraftProgress(paper.progress);
    setDraftRating(paper.rating);
    setNoteModalOpen(true);
  };

  const saveNote = () => {
    if (!activePaper) return;

    setPapers((currentPapers) =>
      currentPapers.map((paper) => {
        if (paper.id !== activePaper.id) return paper;

        return {
          ...paper,
          userNote: draftNote,
          progress: draftProgress,
          rating: draftRating,
          notesCount: draftNote && !paper.userNote ? paper.notesCount + 1 : paper.notesCount,
          status: draftProgress >= 100 ? 'done' : draftProgress > 0 ? 'reading' : 'todo',
          lastReadAt: '刚刚',
        };
      }),
    );
    setNoteModalOpen(false);
    message.success('学习记录已更新');
  };

  const toggleFavorite = (paperId) => {
    setPapers((currentPapers) =>
      currentPapers.map((paper) =>
        paper.id === paperId ? { ...paper, favorite: !paper.favorite } : paper,
      ),
    );
  };

  const markDone = (paperId) => {
    setPapers((currentPapers) =>
      currentPapers.map((paper) =>
        paper.id === paperId
          ? { ...paper, status: 'done', progress: 100, lastReadAt: '刚刚' }
          : paper,
      ),
    );
    message.success('已标记为完成阅读');
  };

  const toggleTopic = (topicId) => {
    setTopics((currentTopics) =>
      currentTopics.map((topic) =>
        topic.id === topicId ? { ...topic, followed: !topic.followed } : topic,
      ),
    );
  };

  const startCompare = () => {
    if (selectedPaperIds.length < 2) {
      message.warning('请选择至少 2 篇论文进行对比');
      return;
    }

    navigate('/compare', { state: { paperIds: selectedPaperIds } });
  };

  const paperColumns = [
    {
      title: '论文',
      dataIndex: 'title',
      render: (_, paper) => (
        <Space direction="vertical" size={4} className="learning-paper-cell">
          <Flex align="center" gap={8} wrap="wrap">
            <Button
              type="link"
              className="learning-paper-title"
              onClick={() => navigate(`/papers/${paper.id}`)}
            >
              {paper.title}
            </Button>
            {paper.favorite && <StarFilled className="learning-star" />}
          </Flex>
          <Text type="secondary">{paper.authors.join(', ')}</Text>
          <Space size={[6, 6]} wrap>
            {paper.tags.map((tag) => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </Space>
        </Space>
      ),
    },
    {
      title: '方向',
      dataIndex: 'direction',
      width: 110,
      render: (direction) => <Tag color="geekblue">{direction}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (status) => (
        <Badge status={statusMeta[status].color} text={statusMeta[status].text} />
      ),
    },
    {
      title: '进度',
      dataIndex: 'progress',
      width: 170,
      render: (progress) => <Progress percent={progress} size="small" />,
    },
    {
      title: '学习记录',
      key: 'activity',
      width: 180,
      render: (_, paper) => (
        <Space direction="vertical" size={2}>
          <Text type="secondary">{paper.lastReadAt}</Text>
          <Text type="secondary">
            {paper.notesCount} 条笔记 · {paper.commentsCount} 条评论
          </Text>
        </Space>
      ),
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      width: 90,
      render: (priority) => <Tag color={priorityColor[priority]}>{priority}</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 210,
      render: (_, paper) => (
        <Space>
          <Button
            size="small"
            icon={paper.favorite ? <StarFilled /> : <StarOutlined />}
            onClick={() => toggleFavorite(paper.id)}
          />
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => openNoteModal(paper)}
          >
            笔记
          </Button>
          <Button
            size="small"
            icon={<CheckCircleOutlined />}
            onClick={() => markDone(paper.id)}
          >
            完成
          </Button>
        </Space>
      ),
    },
  ];

  const rowSelection = {
    selectedRowKeys: selectedPaperIds,
    onChange: (keys) => {
      if (keys.length > 4) {
        message.warning('一次最多对比 4 篇论文');
        return;
      }
      setSelectedPaperIds(keys);
    },
  };

  const renderPaperTable = () => (
    <>
      <Card variant="borderless" className="learning-filter-card">
        <Flex align="center" gap={12} wrap="wrap">
          <Search
            allowClear
            className="learning-search"
            placeholder="搜索标题、作者、标签或摘要"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            onSearch={setKeyword}
          />
          <Select
            value={statusFilter}
            className="learning-select"
            onChange={setStatusFilter}
            options={[
              { label: '全部状态', value: 'all' },
              { label: '待读', value: 'todo' },
              { label: '阅读中', value: 'reading' },
              { label: '已读', value: 'done' },
              { label: '已收藏', value: 'favorite' },
            ]}
          />
          <Select
            value={directionFilter}
            className="learning-select"
            onChange={setDirectionFilter}
            options={directions.map((direction) => ({
              label: direction === 'all' ? '全部方向' : direction,
              value: direction,
            }))}
          />
          <Button
            type="primary"
            icon={<FileSearchOutlined />}
            disabled={selectedPaperIds.length < 2}
            onClick={startCompare}
          >
            对比阅读
          </Button>
        </Flex>
      </Card>

      <Table
        rowKey="id"
        columns={paperColumns}
        dataSource={visiblePapers}
        rowSelection={rowSelection}
        pagination={{ pageSize: 5, showTotal: (total) => `共 ${total} 篇论文` }}
        scroll={{ x: 980 }}
        locale={{ emptyText: <Empty description="没有找到匹配的论文" /> }}
      />
    </>
  );

  const renderNotes = () => (
    <Card variant="borderless" title="笔记与评论">
      <List
        dataSource={learningNotes}
        locale={{ emptyText: <Empty description="暂无笔记" /> }}
        renderItem={(note) => {
          const paper = papers.find((item) => item.id === note.paperId);

          return (
            <List.Item
              actions={[
                <Button
                  key="edit"
                  type="link"
                  icon={<EditOutlined />}
                  onClick={() => paper && openNoteModal(paper)}
                >
                  编辑
                </Button>,
                <Button
                  key="paper"
                  type="link"
                  icon={<BookOutlined />}
                  onClick={() => navigate(`/papers/${note.paperId}`)}
                >
                  原文
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={
                  <Space wrap>
                    <Text strong>{note.title}</Text>
                    <Text type="secondary">{paper?.title}</Text>
                  </Space>
                }
                description={
                  <Space direction="vertical" size={8}>
                    <Paragraph className="learning-note-text">{note.content}</Paragraph>
                    <Space size={[6, 6]} wrap>
                      {note.tags.map((tag) => (
                        <Tag key={tag}>{tag}</Tag>
                      ))}
                      <Text type="secondary">{note.updatedAt}</Text>
                    </Space>
                  </Space>
                }
              />
            </List.Item>
          );
        }}
      />
    </Card>
  );

  const renderHistory = () => (
    <Card variant="borderless" title="阅读历史">
      <Timeline
        items={readingHistory.map((item) => {
          const paper = papers.find((currentPaper) => currentPaper.id === item.paperId);

          return {
            color: item.action === '完成阅读' ? 'green' : 'blue',
            content: (
              <Space direction="vertical" size={2}>
                <Text strong>{item.action}</Text>
                <Text>{paper?.title}</Text>
                <Text type="secondary">{item.detail}</Text>
                <Text type="secondary">{item.time}</Text>
              </Space>
            ),
          };
        })}
      />
    </Card>
  );

  const renderTopics = () => (
    <Row gutter={[16, 16]}>
      {topics.map((topic) => (
        <Col xs={24} md={12} xl={8} key={topic.id}>
          <Card
            variant="borderless"
            className="learning-topic-card"
            title={
              <Flex align="center" justify="space-between" gap={12}>
                <Text strong>{topic.name}</Text>
                <Badge count={topic.newToday} color="#4f6ef7" />
              </Flex>
            }
            extra={
              <Button size="small" onClick={() => toggleTopic(topic.id)}>
                {topic.followed ? '取消关注' : '关注'}
              </Button>
            }
          >
            <Space direction="vertical" size={12} className="learning-topic-body">
              <Progress percent={topic.matchRate} size="small" />
              <Text type="secondary">
                已匹配 {topic.paperCount} 篇论文 · {topic.digestTime} 推送
              </Text>
              <Space size={[6, 6]} wrap>
                {topic.keywords.map((keywordItem) => (
                  <Tag key={keywordItem}>{keywordItem}</Tag>
                ))}
              </Space>
            </Space>
          </Card>
        </Col>
      ))}
    </Row>
  );

  return (
    <main className="learning-page">
      <Flex
        className="learning-header"
        align="flex-start"
        justify="space-between"
        gap={16}
        wrap="wrap"
      >
        <div>
          <Title level={2}>学习中心</Title>
          <Paragraph>
            管理收藏、笔记、评论、阅读历史和关注主题，把论文阅读过程沉淀成可复用的学习资产。
          </Paragraph>
        </div>
        <Space wrap>
          <Button icon={<HistoryOutlined />} onClick={() => setActiveView('history')}>
            最近记录
          </Button>
          <Button type="primary" icon={<FileSearchOutlined />} onClick={startCompare}>
            进入对比
          </Button>
        </Space>
      </Flex>

      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic title="收藏论文" value={stats.favorites} suffix="篇" />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic title="阅读中" value={stats.reading} suffix="篇" />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic title="已完成" value={stats.done} suffix="篇" />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card variant="borderless">
            <Statistic title="学习时长" value={stats.hours} suffix="小时" />
          </Card>
        </Col>
      </Row>

      <Card variant="borderless" className="learning-view-card">
        <Flex align="center" justify="space-between" gap={12} wrap="wrap">
          <Segmented
            value={activeView}
            onChange={setActiveView}
            options={[
              { label: '阅读队列', value: 'queue', icon: <ReadOutlined /> },
              { label: '收藏夹', value: 'favorites', icon: <StarOutlined /> },
              { label: '笔记评论', value: 'notes', icon: <CommentOutlined /> },
              { label: '阅读历史', value: 'history', icon: <ClockCircleOutlined /> },
              { label: '关注主题', value: 'topics', icon: <TagsOutlined /> },
            ]}
          />
          {selectedPapers.length > 0 && (
            <Space size={[6, 6]} wrap>
              <Text type="secondary">已选</Text>
              {selectedPapers.map((paper) => (
                <Tag
                  key={paper.id}
                  closable
                  onClose={() =>
                    setSelectedPaperIds((ids) => ids.filter((id) => id !== paper.id))
                  }
                >
                  {paper.id}
                </Tag>
              ))}
            </Space>
          )}
        </Flex>
      </Card>

      {(activeView === 'queue' || activeView === 'favorites') && renderPaperTable()}
      {activeView === 'notes' && renderNotes()}
      {activeView === 'history' && renderHistory()}
      {activeView === 'topics' && renderTopics()}

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card
            variant="borderless"
            title={
              <Space>
                <FireOutlined />
                今日阅读建议
              </Space>
            }
          >
            <List
              dataSource={papers
                .filter((paper) => paper.status !== 'done')
                .sort((a, b) => b.progress - a.progress)
                .slice(0, 3)}
              renderItem={(paper) => (
                <List.Item
                  actions={[
                    <Button key="note" type="link" onClick={() => openNoteModal(paper)}>
                      记录
                    </Button>,
                    <Button key="done" type="link" onClick={() => markDone(paper.id)}>
                      完成
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    avatar={<Progress type="circle" percent={paper.progress} size={44} />}
                    title={paper.title}
                    description={`${paper.direction} · ${paper.priority}优先级 · ${paper.lastReadAt}`}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card
            variant="borderless"
            title={
              <Space>
                <EyeOutlined />
                关注主题概览
              </Space>
            }
          >
            <List
              dataSource={topics.filter((topic) => topic.followed)}
              renderItem={(topic) => (
                <List.Item>
                  <Space direction="vertical" className="learning-topic-summary" size={4}>
                    <Flex justify="space-between" gap={12}>
                      <Text strong>{topic.name}</Text>
                      <Text type="secondary">今日 +{topic.newToday}</Text>
                    </Flex>
                    <Progress percent={topic.matchRate} showInfo={false} size="small" />
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>

      <Modal
        title={activePaper ? `学习记录：${activePaper.title}` : '学习记录'}
        open={noteModalOpen}
        onCancel={() => setNoteModalOpen(false)}
        onOk={saveNote}
        okText="保存"
        cancelText="取消"
        width={720}
      >
        <Space direction="vertical" size={18} className="learning-note-modal">
          <div>
            <Text strong>阅读进度</Text>
            <Slider
              value={draftProgress}
              onChange={setDraftProgress}
              marks={{ 0: '0%', 50: '50%', 100: '100%' }}
            />
          </div>
          <div>
            <Text strong>评分</Text>
            <div>
              <Rate value={draftRating} onChange={setDraftRating} />
            </div>
          </div>
          <div>
            <Text strong>笔记</Text>
            <TextArea
              rows={6}
              value={draftNote}
              onChange={(event) => setDraftNote(event.target.value)}
              placeholder="记录关键问题、方法差异、实验结论或后续待读点"
            />
          </div>
          {activePaper && (
            <Space size={[6, 6]} wrap>
              {activePaper.tags.map((tag) => (
                <Tag key={tag}>{tag}</Tag>
              ))}
              <Button
                type="link"
                icon={<LinkOutlined />}
                href={activePaper.arxivUrl}
                target="_blank"
              >
                arXiv
              </Button>
            </Space>
          )}
        </Space>
      </Modal>
    </main>
  );
}
