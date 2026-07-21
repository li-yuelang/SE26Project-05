import { useEffect, useState } from 'react';
import dayjs from 'dayjs';
import {
  CheckCircleOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Button,
  Drawer,
  Form,
  Input,
  InputNumber,
  Radio,
  Select,
  Space,
  Switch,
  TimePicker,
  Typography,
} from 'antd';

const { Text } = Typography;

const weekdayOptions = [
  { value: 1, label: '星期一' },
  { value: 2, label: '星期二' },
  { value: 3, label: '星期三' },
  { value: 4, label: '星期四' },
  { value: 5, label: '星期五' },
  { value: 6, label: '星期六' },
  { value: 7, label: '星期日' },
];

function asTimeValue(value) {
  if (!value) return null;
  if (typeof value === 'string') return dayjs(`2000-01-01T${value.slice(0, 5)}`);
  return value;
}

export default function TaskFormDrawer({
  open,
  mode = 'create',
  initialValues,
  meta,
  loading = false,
  onClose,
  onSubmit,
}) {
  const [form] = Form.useForm();
  const [submitAction, setSubmitAction] = useState('save');
  const taskType = Form.useWatch('taskType', form) || 'keyword';
  const scheduleKind = Form.useWatch('scheduleKind', form) || 'manual';
  const categories = meta?.categories || [];
  const taskTypes = meta?.taskTypes || [
    { value: 'keyword', label: '关键词检索' },
    { value: 'category', label: '分类检索' },
  ];

  useEffect(() => {
    if (!open) return;
    const task = initialValues || {};
    form.setFieldsValue({
      name: task.name || '',
      description: task.description || '',
      taskType: task.taskType || 'keyword',
      keywords: task.keywords || [],
      keywordMatchMode: task.keywordMatchMode || 'or',
      categories: task.categories || [],
      scheduleKind: task.scheduleKind || 'manual',
      scheduleTime: asTimeValue(task.scheduleTime),
      scheduleWeekday: task.scheduleWeekday || 1,
      initialLookbackDays: task.initialLookbackDays || (meta?.lookbackDays?.includes(7) ? 7 : meta?.lookbackDays?.[0] || 7),
      maxResults: task.maxResults || meta?.maxResults?.default || 50,
      autoAnalyze: true,
      isEnabled: task.isEnabled ?? true,
    });
    setSubmitAction('save');
  }, [form, initialValues, meta, open]);

  useEffect(() => {
    if (!open) return;
    if (scheduleKind === 'manual') {
      form.setFieldsValue({ scheduleTime: null, scheduleWeekday: null });
    } else if (scheduleKind === 'daily') {
      form.setFieldsValue({ scheduleWeekday: null });
    }
  }, [form, open, scheduleKind]);

  const handleFinish = async (values) => {
    await onSubmit({
      ...values,
      autoAnalyze: true,
      runNow: submitAction === 'run',
      scheduleTime: values.scheduleTime ? values.scheduleTime.format('HH:mm') : null,
      scheduleWeekday: values.scheduleKind === 'weekly' ? values.scheduleWeekday : null,
    });
  };

  return (
    <Drawer
      title={mode === 'edit' ? '编辑抓取任务' : '新建抓取任务'}
      open={open}
      width={520}
      destroyOnClose
      onClose={onClose}
      className="task-form-drawer"
      footer={(
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button
            loading={loading && submitAction === 'save'}
            onClick={() => {
              setSubmitAction('save');
              form.submit();
            }}
          >
            保存任务
          </Button>
          {mode === 'create' && (
            <Button
              type="primary"
              loading={loading && submitAction === 'run'}
              onClick={() => {
                setSubmitAction('run');
                form.submit();
              }}
            >
              保存并立即运行
            </Button>
          )}
        </Space>
      )}
    >
      <Alert
        type="info"
        showIcon
        message="抓取任务只保存 arXiv 元数据"
        description="论文去重后进入共享论文库；自动解析只会为本次新增论文排队。所有计划时间使用 Asia/Shanghai。"
        className="task-form-alert"
      />
      <Form form={form} layout="vertical" onFinish={handleFinish} requiredMark="optional">
        <Form.Item name="name" label="任务名称" rules={[{ required: true, message: '请输入任务名称' }]}>
          <Input maxLength={255} placeholder="例如：LLM 与 RAG 每日更新" />
        </Form.Item>
        <Form.Item name="description" label="说明">
          <Input.TextArea rows={3} maxLength={4000} placeholder="描述任务用途，便于后续查找" />
        </Form.Item>
        <Form.Item name="taskType" label="任务类型" rules={[{ required: true }]}>
          <Radio.Group options={taskTypes} optionType="button" buttonStyle="solid" />
        </Form.Item>
        {taskType === 'keyword' && (
          <>
            <Form.Item
              name="keywords"
              label="关键词"
              extra="支持 1–10 个关键词；输入后按回车确认。"
              rules={[{ required: true, type: 'array', min: 1, max: 10, message: '请输入 1–10 个关键词' }]}
            >
              <Select mode="tags" tokenSeparators={[',']} placeholder="例如：retrieval augmented generation" />
            </Form.Item>
            <Form.Item name="keywordMatchMode" label="关键词匹配方式">
              <Radio.Group
                options={meta?.keywordMatchModes || [
                  { value: 'or', label: '匹配任一（OR）' },
                  { value: 'and', label: '匹配全部（AND）' },
                ]}
              />
            </Form.Item>
          </>
        )}
        <Form.Item
          name="categories"
          label={taskType === 'category' ? 'arXiv 分类' : '分类过滤（可选）'}
          rules={taskType === 'category' ? [{ required: true, type: 'array', min: 1, message: '请选择至少一个分类' }] : []}
        >
          <Select
            mode="multiple"
            options={categories}
            placeholder="选择分类"
            optionFilterProp="label"
            maxTagCount="responsive"
          />
        </Form.Item>
        <Form.Item name="scheduleKind" label="调度方式">
          <Select options={meta?.scheduleKinds || [
            { value: 'manual', label: '手动' },
            { value: 'daily', label: '每日' },
            { value: 'weekly', label: '每周' },
          ]} />
        </Form.Item>
        {scheduleKind !== 'manual' && (
          <Space className="task-form-inline" align="start">
            {scheduleKind === 'weekly' && (
              <Form.Item name="scheduleWeekday" label="星期" rules={[{ required: true, message: '请选择星期' }]}>
                <Select options={weekdayOptions} style={{ width: 130 }} />
              </Form.Item>
            )}
            <Form.Item name="scheduleTime" label="时间" rules={[{ required: true, message: '请选择时间' }]}>
              <TimePicker format="HH:mm" minuteStep={5} style={{ width: 130 }} />
            </Form.Item>
          </Space>
        )}
        <Form.Item name="initialLookbackDays" label="首次回溯范围">
          <Select options={(meta?.lookbackDays || [1, 3, 7, 30]).map((value) => ({ value, label: `近 ${value} 天` }))} />
        </Form.Item>
        <Form.Item name="maxResults" label="单次最大结果数">
          <InputNumber min={meta?.maxResults?.min || 10} max={meta?.maxResults?.max || 200} step={10} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="自动解析新增论文" required>
          <Space>
            <CheckCircleOutlined style={{ color: '#52c41a' }} />
            <Text>已启用，新入库论文将自动进入解析队列</Text>
          </Space>
        </Form.Item>
        {mode === 'edit' && (
          <Form.Item name="isEnabled" label="启用后续调度" valuePropName="checked">
            <Switch />
          </Form.Item>
        )}
        <Text type="secondary">当前固定时区：{meta?.timezone || 'Asia/Shanghai'}</Text>
      </Form>
    </Drawer>
  );
}
