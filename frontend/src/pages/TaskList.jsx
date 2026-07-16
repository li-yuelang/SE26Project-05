import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Input,
  Modal,
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
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import AsyncPageState from '../components/AsyncPageState';
import TaskFormDrawer from '../components/TaskFormDrawer';
import useAsyncResource from '../hooks/useAsyncResource';
import {
  createTask,
  deleteTask,
  getTaskCatalog,
  getTaskMeta,
  pauseTask,
  resumeTask,
  runTask,
  updateTask,
} from '../services/taskService';

const { Search } = Input;
const { Text } = Typography;

function progressForTask(task) {
  if (task.status === 'completed' || task.status === 'scheduled') return 100;
  if (task.status === 'failed' || task.status === 'succeeded_with_warnings') return 70;
  if (task.status === 'queued') return 12;
  if (task.status === 'running') return 48;
  return 0;
}

export default function TaskList() {
  const navigate = useNavigate();
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [typeFilter, setTypeFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(8);
  const [drawer, setDrawer] = useState({ open: false, mode: 'create', task: null });
  const [formLoading, setFormLoading] = useState(false);
  const [meta, setMeta] = useState(null);

  const catalogLoader = useCallback(
    () => getTaskCatalog({ q: searchText, status: statusFilter, taskType: typeFilter, page, pageSize }),
    [page, pageSize, searchText, statusFilter, typeFilter],
  );
  const resource = useAsyncResource(catalogLoader, [catalogLoader]);
  const catalog = resource.data || { items: [], total: 0, summary: {}, statusMeta: {}, typeMeta: {} };
  const tasks = catalog.items || catalog.tasks || [];
  const taskStatusMeta = catalog.statusMeta || {};
  const taskTypeMeta = catalog.typeMeta || {};

  useEffect(() => {
    getTaskMeta().then(setMeta).catch(() => setMeta(null));
  }, []);

  const totals = useMemo(() => ({
    running: catalog.summary?.running ?? tasks.filter((task) => ['running', 'queued'].includes(task.status)).length,
    newPapers: catalog.summary?.newPapers ?? tasks.reduce((sum, task) => sum + (task.newPapers || 0), 0),
    failed: catalog.summary?.failed ?? tasks.filter((task) => task.status === 'failed').length,
    scheduled: catalog.summary?.scheduled ?? tasks.filter((task) => task.status === 'scheduled').length,
  }), [catalog.summary, tasks]);

  const refresh = async () => {
    await resource.reload();
    message.success('任务列表已刷新');
  };

  const openCreate = () => setDrawer({ open: true, mode: 'create', task: null });
  const openEdit = (task) => setDrawer({ open: true, mode: 'edit', task });

  const handleFormSubmit = async (body) => {
    setFormLoading(true);
    try {
      if (drawer.mode === 'edit') {
        await updateTask(drawer.task.id, body);
        message.success('任务配置已保存');
      } else {
        const result = await createTask(body);
        message.success(body.runNow ? '任务已保存并开始运行' : '任务已创建');
        if (body.runNow && result?.task?.id) navigate(`/tasks/${result.task.id}`);
      }
      setDrawer({ open: false, mode: 'create', task: null });
      await resource.reload();
    } catch (error) {
      message.error(error.message || '任务保存失败');
    } finally {
      setFormLoading(false);
    }
  };

  const handleRun = async (task) => {
    try {
      await runTask(task.id);
      message.success('任务已加入运行队列');
      await resource.reload();
    } catch (error) {
      message.error(error.message || '任务运行失败');
    }
  };

  const handleToggle = async (task) => {
    try {
      if (task.isEnabled) await pauseTask(task.id);
      else await resumeTask(task.id);
      message.success(task.isEnabled ? '任务已停用，当前运行会继续完成' : '任务已恢复调度');
      await resource.reload();
    } catch (error) {
      message.error(error.message || '任务状态更新失败');
    }
  };

  const handleDelete = (task) => {
    Modal.confirm({
      title: '删除抓取任务？',
      content: '运行历史会一并删除，但全局论文库中的论文不会删除。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteTask(task.id);
          message.success('任务已删除');
          await resource.reload();
        } catch (error) {
          message.error(error.message || '任务删除失败');
        }
      },
    });
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
            {record.query || record.description || '未设置查询条件'}
          </Text>
        </div>
      ),
    },
    {
      title: '类型',
      dataIndex: 'taskType',
      key: 'taskType',
      width: 120,
      render: (type) => <Tag>{taskTypeMeta[type] || type}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 132,
      render: (status) => {
        const metaItem = taskStatusMeta[status] || { color: 'default', label: status };
        return <Badge status={metaItem.color} text={metaItem.label} />;
      },
    },
    {
      title: '进度',
      key: 'progress',
      width: 150,
      render: (_, record) => (
        <Progress
          percent={progressForTask(record)}
          size="small"
          status={record.status === 'failed' ? 'exception' : undefined}
          showInfo={false}
        />
      ),
    },
    {
      title: '最近新增',
      dataIndex: 'newCount',
      key: 'newCount',
      width: 100,
      sorter: (a, b) => a.newCount - b.newCount,
      render: (count) => <Text strong>{count || 0}</Text>,
    },
    {
      title: '调度',
      dataIndex: 'schedule',
      key: 'schedule',
      width: 140,
      render: (schedule) => (
        <Space size={6}>
          <ClockCircleOutlined />
          <span>{schedule || '手动运行'}</span>
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 178,
      render: (_, record) => (
        <Space size={0}>
          <Tooltip title="查看详情">
            <Button type="link" size="small" icon={<EyeOutlined />} onClick={(event) => {
              event.stopPropagation();
              navigate(`/tasks/${record.id}`);
            }} />
          </Tooltip>
          <Tooltip title="立即运行">
            <Button type="link" size="small" icon={<SyncOutlined />} disabled={['queued', 'running'].includes(record.status)} onClick={(event) => {
              event.stopPropagation();
              handleRun(record);
            }} />
          </Tooltip>
          <Tooltip title={record.isEnabled ? '停用调度' : '恢复调度'}>
            <Button type="link" size="small" icon={record.isEnabled ? <PauseCircleOutlined /> : <PlayCircleOutlined />} onClick={(event) => {
              event.stopPropagation();
              handleToggle(record);
            }} />
          </Tooltip>
          <Tooltip title="编辑">
            <Button type="link" size="small" icon={<EditOutlined />} onClick={(event) => {
              event.stopPropagation();
              openEdit(record);
            }} />
          </Tooltip>
          <Tooltip title="删除">
            <Button type="link" danger size="small" icon={<DeleteOutlined />} disabled={['queued', 'running'].includes(record.status)} onClick={(event) => {
              event.stopPropagation();
              handleDelete(record);
            }} />
          </Tooltip>
        </Space>
      ),
    },
  ];

  if (resource.loading && !resource.data) {
    return <div className="page task-page"><AsyncPageState loading error={null} onRetry={resource.reload} /></div>;
  }
  if (resource.error && !resource.data) {
    return <div className="page task-page"><AsyncPageState loading={false} error={resource.error} onRetry={resource.reload} /></div>;
  }

  return (
    <div className="page task-page">
      <div className="task-page-header">
        <div>
          <h2>抓取任务管理</h2>
          <p>管理 arXiv 自动抓取、去重、解析和入库任务。</p>
        </div>
        <Space wrap>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建抓取任务</Button>
          <Button icon={<ReloadOutlined />} loading={resource.loading} onClick={refresh}>刷新</Button>
        </Space>
      </div>

      <Row gutter={[16, 16]} className="task-stat-row">
        <Col xs={12} lg={6}><Card><Statistic title="运行中" value={totals.running} prefix={<SyncOutlined />} /></Card></Col>
        <Col xs={12} lg={6}><Card><Statistic title="累计新增" value={totals.newPapers} /></Card></Col>
        <Col xs={12} lg={6}><Card><Statistic title="最近失败" value={totals.failed} styles={{ content: { color: '#cf1322' } }} /></Card></Col>
        <Col xs={12} lg={6}><Card><Statistic title="已计划" value={totals.scheduled} /></Card></Col>
      </Row>

      <Card className="task-filter-card" size="small">
        <Row gutter={[16, 12]} align="middle">
          <Col flex="auto">
            <Search
              allowClear
              prefix={<SearchOutlined />}
              placeholder="搜索任务名称、关键词或说明..."
              size="large"
              value={searchText}
              onChange={(event) => {
                setPage(1);
                setSearchText(event.target.value);
              }}
            />
          </Col>
          <Col><Select value={statusFilter} style={{ width: 150 }} onChange={(value) => { setPage(1); setStatusFilter(value); }} options={[{ value: 'all', label: '全部状态' }, ...Object.entries(taskStatusMeta).map(([value, item]) => ({ value, label: item.label }))]} /></Col>
          <Col><Select value={typeFilter} style={{ width: 150 }} onChange={(value) => { setPage(1); setTypeFilter(value); }} options={[{ value: 'all', label: '全部类型' }, ...Object.entries(taskTypeMeta).map(([value, label]) => ({ value, label }))]} /></Col>
        </Row>
      </Card>

      <Table
        columns={columns}
        dataSource={tasks}
        rowKey="id"
        scroll={{ x: 980 }}
        pagination={{
          current: page,
          pageSize,
          total: catalog.total,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 个任务`,
          onChange: (nextPage, nextPageSize) => {
            setPage(nextPageSize !== pageSize ? 1 : nextPage);
            setPageSize(nextPageSize);
          },
        }}
        locale={{ emptyText: <Empty description="暂无匹配任务" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
        onRow={(record) => ({ onClick: () => navigate(`/tasks/${record.id}`), style: { cursor: 'pointer' } })}
      />

      <TaskFormDrawer
        open={drawer.open}
        mode={drawer.mode}
        initialValues={drawer.task}
        meta={meta}
        loading={formLoading}
        onClose={() => setDrawer({ open: false, mode: 'create', task: null })}
        onSubmit={handleFormSubmit}
      />
    </div>
  );
}
