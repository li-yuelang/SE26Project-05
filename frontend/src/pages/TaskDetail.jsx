import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Badge,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Modal,
  Progress,
  Row,
  Select,
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
  DeleteOutlined,
  EditOutlined,
  FileSearchOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import AsyncPageState from '../components/AsyncPageState';
import TaskFormDrawer from '../components/TaskFormDrawer';
import useAsyncResource from '../hooks/useAsyncResource';
import {
  deleteTask,
  getTaskDetail,
  getTaskMeta,
  getTaskRun,
  listTaskRuns,
  pauseTask,
  retryTaskRun,
  resumeTask,
  runTask,
  updateTask,
} from '../services/taskService';

const { Paragraph, Text, Title } = Typography;

const runStatusMeta = {
  queued: { label: '排队中', color: 'blue' },
  running: { label: '运行中', color: 'processing' },
  succeeded: { label: '成功', color: 'green' },
  succeeded_with_warnings: { label: '成功但有警告', color: 'orange' },
  failed: { label: '失败', color: 'red' },
};

function formatDate(value, fallback = '暂无') {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('zh-CN', { hour12: false });
}

function statusTag(status, meta = {}) {
  const item = meta[status] || runStatusMeta[status] || { label: status, tagColor: 'default', color: 'default' };
  return <Tag color={item.tagColor || item.color}>{item.label || status}</Tag>;
}

export default function TaskDetail() {
  const { taskId } = useParams();
  const navigate = useNavigate();
  const [meta, setMeta] = useState(null);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [formLoading, setFormLoading] = useState(false);

  const loader = useCallback(async () => {
    const [detail, runs] = await Promise.all([getTaskDetail(taskId), listTaskRuns(taskId, { page: 1, pageSize: 100 })]);
    return { detail, runs };
  }, [taskId]);
  const resource = useAsyncResource(loader, [loader]);
  const task = resource.data?.detail?.task;
  const runs = resource.data?.runs?.items || resource.data?.detail?.recentRuns || [];
  const statusMeta = resource.data?.detail?.statusMeta || {};
  const typeMeta = resource.data?.detail?.typeMeta || {};
  const selectedRun = useAsyncResource(
    () => (selectedRunId ? getTaskRun(taskId, selectedRunId) : Promise.resolve(null)),
    [taskId, selectedRunId],
  );

  useEffect(() => {
    getTaskMeta().then(setMeta).catch(() => setMeta(null));
  }, []);

  useEffect(() => {
    if (!runs.length) {
      setSelectedRunId(null);
      return;
    }
    if (!selectedRunId || !runs.some((run) => run.id === selectedRunId)) setSelectedRunId(runs[0].id);
  }, [runs, selectedRunId]);

  useEffect(() => {
    if (!task || !['queued', 'running'].includes(task.status)) return undefined;
    const timer = window.setInterval(() => resource.reload(), 4000);
    return () => window.clearInterval(timer);
  }, [resource.reload, task]);

  const activeRun = useMemo(() => runs.find((run) => ['queued', 'running'].includes(run.status)), [runs]);
  const run = selectedRun.data || runs.find((item) => item.id === selectedRunId) || null;
  const taskStatus = statusMeta[task?.status] || runStatusMeta[task?.status] || { label: task?.status, color: 'default', tagColor: 'default' };

  const refresh = async () => {
    await resource.reload();
    if (selectedRunId) await selectedRun.reload();
  };

  const handleToggle = async () => {
    try {
      if (task.isEnabled) await pauseTask(task.id);
      else await resumeTask(task.id);
      message.success(task.isEnabled ? '任务已停用，当前运行会继续完成' : '任务已恢复调度');
      await refresh();
    } catch (error) {
      message.error(error.message || '任务状态更新失败');
    }
  };

  const handleRun = async () => {
    try {
      await runTask(task.id);
      message.success('任务已加入运行队列');
      await refresh();
    } catch (error) {
      message.error(error.message || '任务运行失败');
    }
  };

  const handleRetry = async () => {
    if (!run) return;
    try {
      await retryTaskRun(task.id, run.id);
      message.success('本次运行已重新排队');
      await refresh();
    } catch (error) {
      message.error(error.message || '运行重试失败');
    }
  };

  const handleDelete = () => {
    Modal.confirm({
      title: '删除抓取任务？',
      content: '运行历史会一并删除，但论文库中的论文不会删除。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteTask(task.id);
          message.success('任务已删除');
          navigate('/tasks');
        } catch (error) {
          message.error(error.message || '任务删除失败');
        }
      },
    });
  };

  const handleEdit = async (body) => {
    setFormLoading(true);
    try {
      await updateTask(task.id, body);
      setDrawerOpen(false);
      message.success('任务配置已保存');
      await refresh();
    } catch (error) {
      message.error(error.message || '任务配置保存失败');
    } finally {
      setFormLoading(false);
    }
  };

  const paperColumns = [
    {
      title: '论文',
      key: 'paper',
      ellipsis: true,
      render: (_, paper) => (
        <Space orientation="vertical" size={2}>
          <Link to={`/papers/${paper.paperId}`}>{paper.title}</Link>
          <Text type="secondary">arXiv: {paper.arxivId}</Text>
        </Space>
      ),
    },
    {
      title: '结果',
      dataIndex: 'resultKind',
      key: 'resultKind',
      width: 100,
      render: (kind) => <Tag color={kind === 'inserted' ? 'green' : 'default'}>{kind === 'inserted' ? '新增' : '重复'}</Tag>,
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 110,
      render: (category) => category ? <Tag color="blue">{category}</Tag> : '—',
    },
    {
      title: '发布日期',
      dataIndex: 'published',
      key: 'published',
      width: 150,
      render: (value) => formatDate(value, '—'),
    },
    {
      title: '解析状态',
      dataIndex: 'parsedStatus',
      key: 'parsedStatus',
      width: 100,
      render: (status) => <Tag>{status}</Tag>,
    },
  ];

  if (resource.loading && !resource.data) {
    return <div className="page task-page"><AsyncPageState loading error={null} onRetry={resource.reload} /></div>;
  }
  if (resource.error && !resource.data) {
    return <div className="page task-page"><AsyncPageState loading={false} error={resource.error} onRetry={resource.reload} /></div>;
  }
  if (!task) {
    return (
      <div className="page task-page">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>返回任务列表</Button>
        <Empty className="task-detail-empty" description={`未找到任务：${taskId}`} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </div>
    );
  }

  return (
    <div className="page task-page">
      <div className="task-detail-toolbar">
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>返回</Button>
        <Space wrap>
          <Button icon={<SyncOutlined />} disabled={Boolean(activeRun)} onClick={handleRun}>立即运行</Button>
          <Button icon={task.isEnabled ? <PauseCircleOutlined /> : <PlayCircleOutlined />} onClick={handleToggle}>
            {task.isEnabled ? '停用调度' : '恢复调度'}
          </Button>
          <Button icon={<EditOutlined />} onClick={() => setDrawerOpen(true)}>编辑配置</Button>
          <Button danger icon={<DeleteOutlined />} disabled={Boolean(activeRun)} onClick={handleDelete}>删除</Button>
        </Space>
      </div>

      <Card className="task-detail-hero">
        <Row gutter={[24, 16]} align="middle">
          <Col xs={24} lg={17}>
            <Space wrap className="task-detail-tags">
              {statusTag(task.status, statusMeta)}
              <Tag>{typeMeta[task.taskType] || task.taskType}</Tag>
              {(task.categories || []).map((category) => <Tag key={category} color="geekblue">{category}</Tag>)}
            </Space>
            <Title level={3}>{task.name}</Title>
            <Paragraph>{task.description || '暂无任务说明。'}</Paragraph>
            <Text code>{task.query || (task.keywords || []).join(' OR ') || (task.categories || []).join(', ')}</Text>
          </Col>
          <Col xs={24} lg={7}>
            <Progress type="circle" percent={task.status === 'failed' ? 70 : ['queued', 'running'].includes(task.status) ? 48 : 100} status={task.status === 'failed' ? 'exception' : undefined} />
          </Col>
        </Row>
      </Card>

      {run?.status === 'failed' && (
        <Alert className="task-alert" type="error" showIcon message="本次运行失败" description={run.errorMessage || '抓取服务返回了错误，可重试本次运行。'} action={<Button size="small" onClick={handleRetry}>重试本次运行</Button>} />
      )}
      {run?.status === 'succeeded_with_warnings' && (
        <Alert className="task-alert" type="warning" showIcon message="本次运行成功但有警告" description={run.errorMessage || '部分新增论文未能加入自动解析队列。'} />
      )}

      <Row gutter={[16, 16]} className="task-stat-row">
        <Col xs={12} md={3}><Card><Statistic title="候选论文" value={run?.candidateCount ?? task.candidateCount ?? 0} prefix={<FileSearchOutlined />} /></Card></Col>
        <Col xs={12} md={3}><Card><Statistic title="新增入库" value={run?.newCount ?? task.newCount ?? 0} /></Card></Col>
        <Col xs={12} md={3}><Card><Statistic title="重复过滤" value={run?.duplicateCount ?? task.duplicateCount ?? 0} /></Card></Col>
        <Col xs={12} md={3}><Card><Statistic title="解析入队" value={run?.analysisQueuedCount ?? task.analysisQueuedCount ?? 0} /></Card></Col>
        <Col xs={12} md={3}><Card><Statistic title="分页数" value={run?.pageCount ?? task.pageCount ?? 0} /></Card></Col>
        <Col xs={12} md={3}><Card><Statistic title="当前状态" value={runStatusMeta[run?.status]?.label || taskStatus.label || task.status} /></Card></Col>
      </Row>

      <Card title="运行历史" extra={(
        <Select
          value={selectedRunId}
          onChange={setSelectedRunId}
          loading={resource.loading}
          placeholder="选择运行记录"
          style={{ width: 300, maxWidth: '100%' }}
          options={runs.map((item) => ({ value: item.id, label: `${formatDate(item.createdAt)} · ${runStatusMeta[item.status]?.label || item.status}` }))}
        />
      )}>
        {run ? (
          <Descriptions column={{ xs: 1, sm: 2, lg: 4 }} size="small">
            <Descriptions.Item label="触发方式">{({ initial: '首次运行', manual: '手动运行', scheduled: '定时运行', retry: '失败重试' })[run.triggerKind] || run.triggerKind}</Descriptions.Item>
            <Descriptions.Item label="状态">{statusTag(run.status, runStatusMeta)}</Descriptions.Item>
            <Descriptions.Item label="抓取窗口">{formatDate(run.windowStart)} — {formatDate(run.windowEnd)}</Descriptions.Item>
            <Descriptions.Item label="执行时间">{formatDate(run.startedAt)} — {formatDate(run.finishedAt)}</Descriptions.Item>
          </Descriptions>
        ) : <Empty description="暂无运行历史" image={Empty.PRESENTED_IMAGE_SIMPLE} />}
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={16}>
          <Card title="本次抓取论文">
            <Table columns={paperColumns} dataSource={run?.papers || []} rowKey="id" pagination={{ pageSize: 8, showSizeChanger: false }} scroll={{ x: 760 }} locale={{ emptyText: <Empty description="本次运行暂无论文结果" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }} />
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Space orientation="vertical" size={16} className="task-side-stack">
            <Card title="任务信息">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="任务 ID"><Text copyable={{ text: task.id }}>{task.id}</Text></Descriptions.Item>
                <Descriptions.Item label="调度">{task.schedule || '手动运行'}</Descriptions.Item>
                <Descriptions.Item label="启停状态"><Badge status={task.isEnabled ? 'success' : 'default'} text={task.isEnabled ? '启用' : '停用'} /></Descriptions.Item>
                <Descriptions.Item label="下次运行">{task.nextRunAt ? formatDate(task.nextRunAt) : '不自动调度'}</Descriptions.Item>
                <Descriptions.Item label="最近成功">{formatDate(task.lastSuccessAt)}</Descriptions.Item>
                <Descriptions.Item label="创建时间">{formatDate(task.createdAt)}</Descriptions.Item>
              </Descriptions>
            </Card>
            <Card title="抓取配置">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="关键词匹配">{task.keywordMatchMode === 'and' ? '全部匹配（AND）' : '任一匹配（OR）'}</Descriptions.Item>
                <Descriptions.Item label="首次回溯">近 {task.initialLookbackDays} 天</Descriptions.Item>
                <Descriptions.Item label="单次上限">{task.maxResults}</Descriptions.Item>
                <Descriptions.Item label="自动解析">{task.autoAnalyze ? '开启' : '关闭'}</Descriptions.Item>
                <Descriptions.Item label="时区">{task.timezone}</Descriptions.Item>
              </Descriptions>
            </Card>
          </Space>
        </Col>
      </Row>

      <Card title="执行日志" className="task-log-card">
        <Timeline items={(run?.executionLog || []).slice().reverse().map((log, index) => ({
          key: `${log.time}-${index}`,
          color: log.level === 'error' ? 'red' : log.level === 'warning' ? 'orange' : log.level === 'success' ? 'green' : 'blue',
          children: <Space orientation="vertical" size={2}><Text type="secondary">{formatDate(log.time, log.time)}</Text><Text>{log.content}</Text></Space>,
        }))} />
      </Card>

      <TaskFormDrawer
        open={drawerOpen}
        mode="edit"
        initialValues={task}
        meta={meta}
        loading={formLoading}
        onClose={() => setDrawerOpen(false)}
        onSubmit={handleEdit}
      />
    </div>
  );
}
