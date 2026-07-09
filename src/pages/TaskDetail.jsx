import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Progress,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Timeline,
  Typography,
  message,
} from 'antd';
import {
  ArrowLeftOutlined,
  FileSearchOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { getTaskById, taskStatusMeta, taskTypeMeta } from '../data/taskData';

const { Paragraph, Text, Title } = Typography;

const logColorMap = {
  error: 'red',
  warning: 'orange',
  success: 'green',
  info: 'blue',
};

export default function TaskDetail() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const task = getTaskById(taskId);

  if (!task) {
    return (
      <div className="page task-page">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>
          返回任务列表
        </Button>
        <Empty
          className="task-detail-empty"
          description={`未找到任务：${taskId}`}
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </div>
    );
  }

  const statusMeta = taskStatusMeta[task.status];

  const paperColumns = [
    {
      title: '论文',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (title, record) => (
        <Space orientation="vertical" size={2}>
          <Link to={`/papers/${record.id}`}>{title}</Link>
          <Text type="secondary">arXiv: {record.id}</Text>
        </Space>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 110,
      render: (category) => <Tag color="blue">{category}</Tag>,
    },
    {
      title: '发布日期',
      dataIndex: 'published',
      key: 'published',
      width: 120,
    },
    {
      title: '处理状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (status) => <Tag>{status}</Tag>,
    },
  ];

  return (
    <div className="page task-page">
      <div className="task-detail-toolbar">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>
          返回
        </Button>
        <Space>
          <Button
            icon={task.status === 'running' ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
            onClick={() => message.success(task.status === 'running' ? '任务已暂停' : '任务已启动')}
          >
            {task.status === 'running' ? '暂停任务' : '启动任务'}
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => message.success('任务已加入重试队列')}>
            重试
          </Button>
          <Button type="primary" icon={<SettingOutlined />}>
            编辑配置
          </Button>
        </Space>
      </div>

      <Card className="task-detail-hero">
        <Row gutter={[24, 16]} align="middle">
          <Col xs={24} lg={16}>
            <Space wrap className="task-detail-tags">
              <Tag color={statusMeta.tagColor}>{statusMeta.label}</Tag>
              <Tag>{taskTypeMeta[task.type]}</Tag>
              {task.categories.map((category) => (
                <Tag key={category} color="geekblue">
                  {category}
                </Tag>
              ))}
            </Space>
            <Title level={3}>{task.name}</Title>
            <Paragraph>{task.description}</Paragraph>
            <Text code>{task.query}</Text>
          </Col>
          <Col xs={24} lg={8}>
            <Progress
              type="circle"
              percent={task.progress}
              status={task.status === 'failed' ? 'exception' : undefined}
            />
          </Col>
        </Row>
      </Card>

      {task.status === 'failed' && (
        <Alert
          className="task-alert"
          type="error"
          showIcon
          message="任务执行失败"
          description="摘要解析服务超时，部分论文尚未完成结构化处理，可点击重试重新排队。"
        />
      )}

      <Row gutter={[16, 16]} className="task-stat-row">
        <Col xs={12} md={6}>
          <Card>
            <Statistic title="候选论文" value={task.totalFound} prefix={<FileSearchOutlined />} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic title="新增入库" value={task.newPapers} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic title="重复过滤" value={task.duplicates} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="失败条目"
              value={task.failedItems}
              styles={task.failedItems > 0 ? { content: { color: '#cf1322' } } : undefined}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={15}>
          <Card title="抓取结果">
            <Table
              columns={paperColumns}
              dataSource={task.papers}
              rowKey="id"
              pagination={false}
              locale={{
                emptyText: (
                  <Empty
                    description="本次执行未发现新论文"
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                  />
                ),
              }}
            />
          </Card>
        </Col>

        <Col xs={24} xl={9}>
          <Space orientation="vertical" size={16} className="task-side-stack">
            <Card title="任务信息">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="任务 ID">{task.id}</Descriptions.Item>
                <Descriptions.Item label="负责人">{task.owner}</Descriptions.Item>
                <Descriptions.Item label="调度">{task.schedule}</Descriptions.Item>
                <Descriptions.Item label="最近运行">{task.lastRun}</Descriptions.Item>
                <Descriptions.Item label="下次运行">
                  <Badge status={statusMeta.color} text={task.nextRun} />
                </Descriptions.Item>
                <Descriptions.Item label="创建时间">{task.createdAt}</Descriptions.Item>
                <Descriptions.Item label="更新时间">{task.updatedAt}</Descriptions.Item>
              </Descriptions>
            </Card>

            <Card title="抓取配置">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="时间范围">{task.config.dateRange}</Descriptions.Item>
                <Descriptions.Item label="最大结果">{task.config.maxResults}</Descriptions.Item>
                <Descriptions.Item label="排序方式">{task.config.sortBy}</Descriptions.Item>
                <Descriptions.Item label="语言">{task.config.language}</Descriptions.Item>
                <Descriptions.Item label="自动摘要">
                  {task.config.autoSummarize ? '开启' : '关闭'}
                </Descriptions.Item>
              </Descriptions>
            </Card>
          </Space>
        </Col>
      </Row>

      <Card title="执行日志" className="task-log-card">
        <Timeline
          items={task.logs.map((log) => ({
            color: logColorMap[log.level],
            content: (
              <Space orientation="vertical" size={2}>
                <Text type="secondary">{log.time}</Text>
                <Text>{log.content}</Text>
              </Space>
            ),
          }))}
        />
      </Card>
    </div>
  );
}
