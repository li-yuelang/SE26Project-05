import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Input,
  Progress,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import {
  ClockCircleOutlined,
  EyeOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import AsyncPageState from '../components/AsyncPageState';
import useAsyncResource from '../hooks/useAsyncResource';
import {
  getTaskCatalog,
  resetTasks,
  updateTask,
} from '../services/taskService';

const { Search } = Input;
const { Text } = Typography;

export default function TaskList() {
  const navigate = useNavigate();
  const resource = useAsyncResource(getTaskCatalog, []);
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [tasks, setTasks] = useState([]);
  const taskStatusMeta = resource.data?.statusMeta || {};
  const taskTypeMeta = resource.data?.typeMeta || {};

  useEffect(() => {
    if (resource.data) setTasks(resource.data.tasks);
  }, [resource.data]);

  const filteredTasks = useMemo(() => {
    const keyword = searchText.trim().toLowerCase();

    return tasks.filter((task) => {
      const matchKeyword =
        !keyword ||
        task.name.toLowerCase().includes(keyword) ||
        task.query.toLowerCase().includes(keyword) ||
        task.description.toLowerCase().includes(keyword);
      const matchStatus = statusFilter === 'all' || task.status === statusFilter;
      const matchType = typeFilter === 'all' || task.type === typeFilter;

      return matchKeyword && matchStatus && matchType;
    });
  }, [searchText, statusFilter, tasks, typeFilter]);

  const totals = useMemo(
    () => ({
      running: tasks.filter((task) => task.status === 'running').length,
      newPapers: tasks.reduce((sum, task) => sum + task.newPapers, 0),
      failed: tasks.filter((task) => task.status === 'failed').length,
      scheduled: tasks.filter((task) => task.status === 'scheduled').length,
    }),
    [tasks]
  );

  const updateTaskStatus = async (taskId, status) => {
    try {
      const updatedTask = await updateTask(taskId, { status });
      setTasks((currentTasks) => currentTasks.map((task) => (
        task.id === taskId ? updatedTask : task
      )));
      message.success(`任务已${status === 'running' ? '启动' : '暂停'}`);
    } catch (error) {
      message.error(error.message || '任务状态更新失败');
    }
  };

  const columns = [
    {
      title: '任务',
      key: 'task',
      ellipsis: true,
      render: (_, record) => (
        <div className="task-cell">
          <button
            className="task-title-button"
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              navigate(`/tasks/${record.id}`);
            }}
          >
            {record.name}
          </button>
          <Text type="secondary" ellipsis className="task-query">
            {record.query}
          </Text>
        </div>
      ),
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 120,
      render: (type) => <Tag>{taskTypeMeta[type]}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (status) => {
        const meta = taskStatusMeta[status];
        return <Badge status={meta.color} text={meta.label} />;
      },
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      width: 170,
      render: (progress, record) => (
        <Progress
          percent={progress}
          size="small"
          status={record.status === 'failed' ? 'exception' : undefined}
        />
      ),
    },
    {
      title: '新增',
      dataIndex: 'newPapers',
      key: 'newPapers',
      width: 90,
      sorter: (a, b) => a.newPapers - b.newPapers,
      render: (count) => <Text strong>{count}</Text>,
    },
    {
      title: '调度',
      dataIndex: 'schedule',
      key: 'schedule',
      width: 140,
      render: (schedule) => (
        <Space size={6}>
          <ClockCircleOutlined />
          <span>{schedule}</span>
        </Space>
      ),
    },
    {
      title: '最近运行',
      dataIndex: 'lastRun',
      key: 'lastRun',
      width: 150,
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_, record) => (
        <Space>
          <Tooltip title="查看详情">
            <Button
              type="link"
              size="small"
              icon={<EyeOutlined />}
              onClick={(event) => {
                event.stopPropagation();
                navigate(`/tasks/${record.id}`);
              }}
            />
          </Tooltip>
          <Tooltip title={record.status === 'running' ? '暂停' : '启动'}>
            <Button
              type="link"
              size="small"
              icon={
                record.status === 'running' ? (
                  <PauseCircleOutlined />
                ) : (
                  <PlayCircleOutlined />
                )
              }
              onClick={(event) => {
                event.stopPropagation();
                updateTaskStatus(
                  record.id,
                  record.status === 'running' ? 'paused' : 'running'
                );
              }}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  if (resource.loading || resource.error) {
    return (
      <div className="page task-page">
        <AsyncPageState
          loading={resource.loading}
          error={resource.error}
          onRetry={resource.reload}
        />
      </div>
    );
  }

  return (
    <div className="page task-page">
      <div className="task-page-header">
        <div>
          <h2>抓取任务管理</h2>
          <p>管理 ArXiv 自动抓取、去重、解析和入库任务。</p>
        </div>
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => message.info('新建任务功能开发中')}
          >
            新建抓取任务
          </Button>
          <Button
            icon={<ReloadOutlined />}
            onClick={async () => {
              try {
                setTasks(await resetTasks());
                message.success('任务列表已刷新');
              } catch (error) {
                message.error(error.message || '任务列表刷新失败');
              }
            }}
          >
            刷新
          </Button>
        </Space>
      </div>

      <Row gutter={[16, 16]} className="task-stat-row">
        <Col xs={12} lg={6}>
          <Card>
            <Statistic title="运行中" value={totals.running} prefix={<SyncOutlined />} />
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card>
            <Statistic title="新增论文" value={totals.newPapers} />
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card>
            <Statistic title="失败任务" value={totals.failed} styles={{ content: { color: '#cf1322' } }} />
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card>
            <Statistic title="已计划" value={totals.scheduled} />
          </Card>
        </Col>
      </Row>

      <Card className="task-filter-card" size="small">
        <Row gutter={[16, 12]} align="middle">
          <Col flex="auto">
            <Search
              allowClear
              prefix={<SearchOutlined />}
              placeholder="搜索任务名称、查询条件或说明..."
              size="large"
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
            />
          </Col>
          <Col>
            <Select
              value={statusFilter}
              style={{ width: 140 }}
              onChange={setStatusFilter}
              options={[
                { value: 'all', label: '全部状态' },
                ...Object.entries(taskStatusMeta).map(([value, meta]) => ({
                  value,
                  label: meta.label,
                })),
              ]}
            />
          </Col>
          <Col>
            <Select
              value={typeFilter}
              style={{ width: 140 }}
              onChange={setTypeFilter}
              options={[
                { value: 'all', label: '全部类型' },
                ...Object.entries(taskTypeMeta).map(([value, label]) => ({
                  value,
                  label,
                })),
              ]}
            />
          </Col>
        </Row>
      </Card>

      <Table
        columns={columns}
        dataSource={filteredTasks}
        rowKey="id"
        pagination={{
          pageSize: 8,
          showTotal: (total) => `共 ${total} 个任务`,
        }}
        locale={{
          emptyText: (
            <Empty
              description="暂无匹配任务"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          ),
        }}
        onRow={(record) => ({
          onClick: () => navigate(`/tasks/${record.id}`),
          style: { cursor: 'pointer' },
        })}
      />
    </div>
  );
}
