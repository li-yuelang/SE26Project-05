import { mockTasks, taskStatusMeta, taskTypeMeta } from '../data/taskData';
import { ApiError, cloneMockData, createEndpoint, request } from './apiClient';

const defaultTaskMeta = {
  taskTypes: [
    { value: 'keyword', label: '关键词检索' },
    { value: 'category', label: '分类检索' },
  ],
  statuses: taskStatusMeta,
  lookbackDays: [1, 3, 7, 30],
  keywordMatchModes: [
    { value: 'or', label: '匹配任一（OR）' },
    { value: 'and', label: '匹配全部（AND）' },
  ],
  scheduleKinds: [
    { value: 'manual', label: '手动' },
    { value: 'daily', label: '每日' },
    { value: 'weekly', label: '每周' },
  ],
  categories: [
    { value: 'cs.AI', label: '人工智能' },
    { value: 'cs.CL', label: '计算语言学' },
    { value: 'cs.CV', label: '计算机视觉' },
    { value: 'cs.IR', label: '信息检索' },
    { value: 'cs.LG', label: '机器学习' },
    { value: 'cs.SE', label: '软件工程' },
    { value: 'cs.HC', label: '人机交互' },
    { value: 'cs.RO', label: '机器人' },
    { value: 'cs.DS', label: '数据结构与算法' },
    { value: 'stat.ML', label: '统计机器学习' },
  ],
  timezone: 'Asia/Shanghai',
  maxResults: { min: 10, max: 200, default: 50 },
};

function parseKeywords(raw) {
  if (Array.isArray(raw.keywords)) return raw.keywords;
  return String(raw.query || '')
    .split(/\s+(?:OR|AND)\s+/i)
    .map((item) => item.replace(/^all:/i, '').replace(/^"|"$/g, '').trim())
    .filter(Boolean);
}

function inferScheduleKind(raw) {
  if (raw.schedule_kind) return raw.schedule_kind;
  if (raw.schedule?.includes('每天')) return 'daily';
  if (raw.schedule?.includes('每周')) return 'weekly';
  return 'manual';
}

function toTask(raw = {}) {
  const taskType = raw.task_type || raw.taskType || raw.type || 'keyword';
  const categories = raw.categories || [];
  const keywords = parseKeywords(raw);
  const scheduleKind = inferScheduleKind(raw);
  return {
    ...raw,
    id: String(raw.id),
    name: raw.name || '未命名抓取任务',
    description: raw.description || '',
    taskType,
    type: taskType,
    status: raw.status || 'scheduled',
    keywords,
    keywordMatchMode: raw.keyword_match_mode || raw.keywordMatchMode || 'or',
    categories,
    scheduleKind,
    scheduleTime: raw.schedule_time || raw.scheduleTime || null,
    scheduleWeekday: raw.schedule_weekday || raw.scheduleWeekday || null,
    timezone: raw.timezone || 'Asia/Shanghai',
    isEnabled: raw.is_enabled ?? raw.isEnabled ?? raw.status !== 'paused',
    nextRunAt: raw.next_run_at || raw.nextRunAt || null,
    initialLookbackDays: raw.initial_lookback_days || raw.initialLookbackDays || 7,
    maxResults: raw.max_results || raw.maxResults || 50,
    autoAnalyze: raw.auto_analyze ?? raw.autoAnalyze ?? raw.config?.autoSummarize ?? false,
    lastSuccessAt: raw.last_success_at || raw.lastSuccessAt || null,
    candidateCount: raw.candidate_count ?? raw.candidateCount ?? raw.totalFound ?? 0,
    newCount: raw.new_count ?? raw.newCount ?? raw.newPapers ?? 0,
    duplicateCount: raw.duplicate_count ?? raw.duplicateCount ?? raw.duplicates ?? 0,
    analysisQueuedCount: raw.analysis_queued_count ?? raw.analysisQueuedCount ?? 0,
    analysisEnqueueFailedCount:
      raw.analysis_enqueue_failed_count ?? raw.analysisEnqueueFailedCount ?? raw.failedItems ?? 0,
    pageCount: raw.page_count ?? raw.pageCount ?? 0,
    newPapers: raw.new_count ?? raw.newCount ?? raw.newPapers ?? 0,
    duplicates: raw.duplicate_count ?? raw.duplicateCount ?? raw.duplicates ?? 0,
    totalFound: raw.candidate_count ?? raw.candidateCount ?? raw.totalFound ?? 0,
    nextRun: raw.next_run_at || raw.nextRunAt || raw.nextRun || (raw.status === 'paused' ? '已暂停' : '待计算'),
    lastRun: raw.finished_at || raw.finishedAt || raw.lastRun || '暂无运行',
    query: raw.query || (keywords.length ? keywords.join(` ${raw.keyword_match_mode === 'and' ? 'AND' : 'OR'} `) : categories.map((item) => `cat:${item}`).join(' OR ')),
    config: raw.config || {
      dateRange: `近 ${raw.initial_lookback_days || raw.initialLookbackDays || 7} 天`,
      maxResults: raw.max_results || raw.maxResults || 50,
      autoSummarize: raw.auto_analyze ?? raw.autoAnalyze ?? false,
    },
  };
}

function toRunPaper(raw = {}) {
  return {
    ...raw,
    id: String(raw.id),
    paperId: String(raw.paper_id || raw.paperId || raw.paper?.id || raw.id),
    arxivId: raw.arxiv_id || raw.arxivId || raw.id,
    title: raw.title || raw.paper?.title || raw.arxiv_id || raw.arxivId || '未命名论文',
    category: raw.primary_category || raw.primaryCategory || raw.category || raw.paper?.primary_category,
    published: raw.published_at || raw.publishedAt || raw.published || null,
    resultKind: raw.result_kind || raw.resultKind || 'inserted',
    parsedStatus: raw.parsed_status || raw.parsedStatus || raw.status || 'pending',
  };
}

function toRun(raw = {}) {
  return {
    ...raw,
    id: String(raw.id),
    taskId: String(raw.task_id || raw.taskId),
    triggerKind: raw.trigger_kind || raw.triggerKind || 'manual',
    configSnapshot: raw.config_snapshot || raw.configSnapshot || {},
    windowStart: raw.window_start || raw.windowStart || null,
    windowEnd: raw.window_end || raw.windowEnd || null,
    celeryTaskId: raw.celery_task_id || raw.celeryTaskId || null,
    status: raw.status || 'queued',
    candidateCount: raw.candidate_count ?? raw.candidateCount ?? 0,
    newCount: raw.new_count ?? raw.newCount ?? 0,
    duplicateCount: raw.duplicate_count ?? raw.duplicateCount ?? 0,
    analysisQueuedCount: raw.analysis_queued_count ?? raw.analysisQueuedCount ?? 0,
    analysisEnqueueFailedCount: raw.analysis_enqueue_failed_count ?? raw.analysisEnqueueFailedCount ?? 0,
    pageCount: raw.page_count ?? raw.pageCount ?? 0,
    executionLog: raw.execution_log || raw.executionLog || [],
    errorMessage: raw.error_message || raw.errorMessage || null,
    startedAt: raw.started_at || raw.startedAt || null,
    finishedAt: raw.finished_at || raw.finishedAt || null,
    createdAt: raw.created_at || raw.createdAt || null,
    papers: (raw.papers || []).map(toRunPaper),
  };
}

function normalizeMeta(raw = {}) {
  return {
    ...defaultTaskMeta,
    ...raw,
    taskTypes: raw.task_types || raw.taskTypes || defaultTaskMeta.taskTypes,
    statuses: raw.statuses || raw.statusMeta || defaultTaskMeta.statuses,
    lookbackDays: raw.lookback_days || raw.lookbackDays || defaultTaskMeta.lookbackDays,
    keywordMatchModes: raw.keyword_match_modes || raw.keywordMatchModes || defaultTaskMeta.keywordMatchModes,
    scheduleKinds: raw.schedule_kinds || raw.scheduleKinds || defaultTaskMeta.scheduleKinds,
    categories: raw.categories || defaultTaskMeta.categories,
  };
}

function normalizeCatalog(raw = {}) {
  const items = (raw.items || raw.tasks || []).map(toTask);
  return {
    ...raw,
    items,
    tasks: items,
    total: raw.total ?? items.length,
    page: raw.page || 1,
    pageSize: raw.page_size || raw.pageSize || 20,
    statusMeta: raw.status_meta || raw.statusMeta || taskStatusMeta,
    typeMeta: raw.type_meta || raw.typeMeta || taskTypeMeta,
    summary: {
      ...(raw.summary || {}),
      newPapers: raw.summary?.new_papers ?? raw.summary?.newPapers ?? items.reduce((sum, task) => sum + task.newPapers, 0),
    },
  };
}

function normalizeDetail(raw = {}) {
  const detail = raw.task ? raw : { task: raw };
  return {
    ...detail,
    task: toTask(detail.task),
    summary: detail.summary || {},
    recentRuns: (detail.recent_runs || detail.recentRuns || []).map(toRun),
    statusMeta: detail.status_meta || detail.statusMeta || taskStatusMeta,
    typeMeta: detail.type_meta || detail.typeMeta || taskTypeMeta,
  };
}

function normalizeRunList(raw = {}) {
  return {
    ...raw,
    items: (raw.items || []).map(toRun),
    total: raw.total ?? 0,
    page: raw.page || 1,
    pageSize: raw.page_size || raw.pageSize || 20,
  };
}

function formatTimeValue(value) {
  if (!value) return null;
  if (typeof value === 'string') return value.length > 5 ? value.slice(0, 5) : value;
  if (typeof value.format === 'function') return value.format('HH:mm');
  return value;
}

function toApiPayload(body = {}) {
  const result = {};
  const fieldMap = {
    taskType: 'task_type',
    keywordMatchMode: 'keyword_match_mode',
    scheduleKind: 'schedule_kind',
    scheduleTime: 'schedule_time',
    scheduleWeekday: 'schedule_weekday',
    isEnabled: 'is_enabled',
    nextRunAt: 'next_run_at',
    initialLookbackDays: 'initial_lookback_days',
    maxResults: 'max_results',
    autoAnalyze: 'auto_analyze',
    runNow: 'run_now',
  };
  Object.entries(body).forEach(([key, value]) => {
    const apiKey = fieldMap[key] || key;
    if (value !== undefined) result[apiKey] = value;
  });
  if (Object.prototype.hasOwnProperty.call(result, 'schedule_time')) {
    result.schedule_time = formatTimeValue(result.schedule_time);
  }
  return result;
}

let taskStore = cloneMockData(mockTasks).map(toTask);
const runStore = new Map();

function buildMockRun(task, rawPaper = null) {
  return toRun({
    id: `${task.id}-run-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    task_id: task.id,
    trigger_kind: task.scheduleKind === 'manual' ? 'manual' : 'scheduled',
    config_snapshot: toApiPayload(task),
    status: task.status === 'running' ? 'running' : task.status === 'failed' ? 'failed' : 'succeeded',
    candidate_count: task.totalFound,
    new_count: task.newPapers,
    duplicate_count: task.duplicates,
    page_count: task.pageCount || 1,
    execution_log: task.logs || [],
    error_message: task.status === 'failed' ? '模拟抓取运行失败，可重试。' : null,
    started_at: task.lastRun,
    finished_at: task.status === 'running' ? null : task.lastRun,
    papers: rawPaper ? [rawPaper] : task.papers || [],
  });
}

taskStore.forEach((task) => runStore.set(task.id, [buildMockRun(task)]));

function getMockTask(taskId) {
  return taskStore.find((task) => task.id === taskId);
}

function mockSummary() {
  return taskStore.reduce((summary, task) => {
    if (['running', 'queued'].includes(task.status)) summary.running += 1;
    if (task.status === 'scheduled') summary.scheduled += 1;
    if (task.status === 'failed') summary.failed += 1;
    summary.newPapers += task.newPapers;
    return summary;
  }, { running: 0, scheduled: 0, failed: 0, newPapers: 0 });
}

function mockDetail(taskId) {
  const task = getMockTask(taskId);
  if (!task) return { task: null, statusMeta: taskStatusMeta, typeMeta: taskTypeMeta };
  return {
    task,
    summary: {
      candidateCount: task.totalFound,
      newPapers: task.newPapers,
      duplicateCount: task.duplicates,
    },
    recentRuns: (runStore.get(taskId) || []).slice().sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt))),
    statusMeta: taskStatusMeta,
    typeMeta: taskTypeMeta,
  };
}

function scheduleMockRun(taskId, runId) {
  const transition = (status, patch = {}) => {
    const task = getMockTask(taskId);
    const runs = runStore.get(taskId) || [];
    const run = runs.find((item) => item.id === runId);
    if (!task || !run) return;
    Object.assign(run, { status, ...patch });
    if (status === 'running') task.status = 'running';
    if (status === 'succeeded') {
      task.status = !task.isEnabled ? 'paused' : task.scheduleKind !== 'manual' ? 'scheduled' : 'completed';
      task.newPapers += 2;
      task.newCount = task.newPapers;
      task.totalFound += 2;
      task.lastRun = new Date().toISOString();
      run.candidateCount = 2;
      run.newCount = 2;
      run.finishedAt = task.lastRun;
    }
  };
  globalThis.setTimeout(() => transition('running', { startedAt: new Date().toISOString() }), 250);
  globalThis.setTimeout(() => transition('succeeded'), 900);
}

export const getTaskMeta = createEndpoint({
  mock: () => normalizeMeta(defaultTaskMeta),
  http: () => request('/tasks/meta').then(normalizeMeta),
});

export const getTaskCatalog = createEndpoint({
  mock: (query = {}) => {
    const keyword = String(query.q || '').trim().toLowerCase();
    const filtered = taskStore.filter((task) => {
      const matchKeyword = !keyword || `${task.name} ${task.query} ${task.description}`.toLowerCase().includes(keyword);
      const matchStatus = !query.status || query.status === 'all' || task.status === query.status;
      const matchType = !query.taskType || query.taskType === 'all' || task.taskType === query.taskType;
      return matchKeyword && matchStatus && matchType;
    });
    const page = Number(query.page || 1);
    const pageSize = Number(query.pageSize || 20);
    const items = filtered.slice((page - 1) * pageSize, page * pageSize);
    return normalizeCatalog({ items, total: filtered.length, page, page_size: pageSize, summary: mockSummary() });
  },
  http: (query = {}) => request('/tasks', {
    query: {
      q: query.q,
      task_type: query.taskType,
      status: query.status === 'all' ? undefined : query.status,
      page: query.page,
      page_size: query.pageSize,
    },
  }).then(normalizeCatalog),
});

export const getTaskDetail = createEndpoint({
  mock: (taskId) => mockDetail(taskId),
  http: (taskId) => request(`/tasks/${taskId}`).then(normalizeDetail),
});

export const createTask = createEndpoint({
  mock: (body) => {
    const id = `mock-task-${Date.now()}`;
    const task = toTask({ ...body, id, status: body.isEnabled === false ? 'paused' : 'scheduled' });
    taskStore = [task, ...taskStore];
    runStore.set(task.id, []);
    if (body.runNow) {
      const run = createMockRun(task, 'initial');
      runStore.get(task.id).unshift(run);
      scheduleMockRun(task.id, run.id);
      task.status = 'queued';
    }
    return { ...mockDetail(task.id), run: runStore.get(task.id)?.[0] || null };
  },
  http: (body) => request('/tasks', { method: 'POST', body: toApiPayload(body) }).then(normalizeDetail),
});

function createMockRun(task, triggerKind = 'manual', sourceRun = null) {
  const run = toRun({
    id: `${task.id}-run-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    task_id: task.id,
    trigger_kind: triggerKind,
    config_snapshot: sourceRun?.configSnapshot || toApiPayload(task),
    window_start: sourceRun?.windowStart || new Date(Date.now() - 7 * 86400000).toISOString(),
    window_end: sourceRun?.windowEnd || new Date().toISOString(),
    status: 'queued',
    execution_log: [{ time: new Date().toISOString(), level: 'info', content: '运行已排队。' }],
  });
  return run;
}

export const updateTask = createEndpoint({
  mock: (taskId, changes) => {
    const current = getMockTask(taskId);
    if (!current) throw new ApiError('任务不存在', { status: 404, code: 'TASK_NOT_FOUND' });
    const next = toTask({ ...current, ...changes, is_enabled: changes.isEnabled ?? current.isEnabled });
    if (changes.status === 'paused') next.status = 'paused';
    taskStore = taskStore.map((task) => (task.id === taskId ? next : task));
    return mockDetail(taskId);
  },
  http: (taskId, changes) => request(`/tasks/${taskId}`, {
    method: 'PATCH',
    body: toApiPayload(changes),
  }).then(normalizeDetail),
});

export const deleteTask = createEndpoint({
  mock: (taskId) => {
    const runs = runStore.get(taskId) || [];
    if (runs.some((run) => ['queued', 'running'].includes(run.status))) {
      throw new ApiError('任务当前有运行中的执行记录', { status: 409, code: 'TASK_RUN_ACTIVE' });
    }
    taskStore = taskStore.filter((task) => task.id !== taskId);
    runStore.delete(taskId);
    return null;
  },
  http: (taskId) => request(`/tasks/${taskId}`, { method: 'DELETE' }),
});

function setMockTaskEnabled(taskId, enabled) {
  const task = getMockTask(taskId);
  if (!task) throw new ApiError('任务不存在', { status: 404, code: 'TASK_NOT_FOUND' });
  task.isEnabled = enabled;
  task.status = enabled ? 'scheduled' : 'paused';
  return mockDetail(taskId);
}

export const pauseTask = createEndpoint({
  mock: (taskId) => setMockTaskEnabled(taskId, false),
  http: (taskId) => request(`/tasks/${taskId}/pause`, { method: 'POST' }).then(normalizeDetail),
});

export const resumeTask = createEndpoint({
  mock: (taskId) => setMockTaskEnabled(taskId, true),
  http: (taskId) => request(`/tasks/${taskId}/resume`, { method: 'POST' }).then(normalizeDetail),
});

export const runTask = createEndpoint({
  mock: (taskId) => {
    const task = getMockTask(taskId);
    if (!task) throw new ApiError('任务不存在', { status: 404, code: 'TASK_NOT_FOUND' });
    const active = (runStore.get(taskId) || []).find((run) => ['queued', 'running'].includes(run.status));
    if (active) throw new ApiError('任务已有运行中的执行记录', { status: 409, code: 'TASK_RUN_ACTIVE' });
    const run = createMockRun(task);
    runStore.set(taskId, [run, ...(runStore.get(taskId) || [])]);
    task.status = 'queued';
    scheduleMockRun(taskId, run.id);
    return { task: mockDetail(taskId), run };
  },
  http: (taskId) => request(`/tasks/${taskId}/runs`, { method: 'POST' }).then((payload) => ({
    ...payload,
    task: normalizeDetail(payload.task),
    run: toRun(payload.run),
  })),
});

export const listTaskRuns = createEndpoint({
  mock: (taskId, query = {}) => {
    const all = runStore.get(taskId) || [];
    const page = Number(query.page || 1);
    const pageSize = Number(query.pageSize || 20);
    return normalizeRunList({ items: all.slice((page - 1) * pageSize, page * pageSize), total: all.length, page, page_size: pageSize });
  },
  http: (taskId, query = {}) => request(`/tasks/${taskId}/runs`, {
    query: { page: query.page, page_size: query.pageSize },
  }).then(normalizeRunList),
});

export const getTaskRun = createEndpoint({
  mock: (taskId, runId) => {
    const run = (runStore.get(taskId) || []).find((item) => item.id === runId);
    if (!run) throw new ApiError('运行记录不存在', { status: 404, code: 'TASK_RUN_NOT_FOUND' });
    return run;
  },
  http: (taskId, runId) => request(`/tasks/${taskId}/runs/${runId}`).then(toRun),
});

export const retryTaskRun = createEndpoint({
  mock: (taskId, runId) => {
    const task = getMockTask(taskId);
    const source = (runStore.get(taskId) || []).find((run) => run.id === runId);
    if (!task || !source) throw new ApiError('运行记录不存在', { status: 404, code: 'TASK_RUN_NOT_FOUND' });
    if (!['failed', 'succeeded_with_warnings'].includes(source.status)) {
      throw new ApiError('该运行暂不可重试', { status: 409, code: 'TASK_RUN_NOT_RETRYABLE' });
    }
    const run = createMockRun(task, 'retry', source);
    runStore.set(taskId, [run, ...(runStore.get(taskId) || [])]);
    task.status = 'queued';
    scheduleMockRun(taskId, run.id);
    return { task: mockDetail(taskId), run };
  },
  http: (taskId, runId) => request(`/tasks/${taskId}/runs/${runId}/retry`, { method: 'POST' }).then((payload) => ({
    ...payload,
    task: normalizeDetail(payload.task),
    run: toRun(payload.run),
  })),
});

const normalizeTask = toTask;
const normalizeRun = toRun;

export { normalizeDetail, normalizeMeta, normalizeRun, normalizeTask };
