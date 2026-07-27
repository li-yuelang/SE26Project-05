/**
 * taskService Mock 单元测试
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

let taskService;
beforeEach(async () => {
  vi.resetModules();
  window.localStorage.clear();
  vi.stubEnv('VITE_API_MODE', 'mock');
  taskService = await import('../services/taskService.js');
});

describe('taskService - getTaskMeta', () => {
  it('应返回元数据（taskTypes、statuses、categories 等）', async () => {
    const meta = await taskService.getTaskMeta();
    expect(meta).toHaveProperty('taskTypes');
    expect(meta).toHaveProperty('statuses');
    expect(meta).toHaveProperty('categories');
    expect(meta).toHaveProperty('lookbackDays');
    expect(meta).toHaveProperty('scheduleKinds');
    expect(meta.categories.length).toBeGreaterThan(0);
  });
});

describe('taskService - getTaskCatalog', () => {
  it('应返回任务列表及分页信息', async () => {
    const catalog = await taskService.getTaskCatalog();
    expect(catalog).toHaveProperty('items');
    expect(catalog).toHaveProperty('total');
    expect(Array.isArray(catalog.items)).toBe(true);
  });

  it('关键词筛选', async () => {
    const catalog = await taskService.getTaskCatalog({ q: 'LLM' });
    catalog.items.forEach((t) => {
      const text = `${t.name} ${t.query} ${t.description}`.toLowerCase();
      expect(text).toContain('llm');
    });
  });

  it('状态筛选', async () => {
    const catalog = await taskService.getTaskCatalog({ status: 'running' });
    catalog.items.forEach((t) => {
      expect(t.status).toBe('running');
    });
  });

  it('分页', async () => {
    const all = await taskService.getTaskCatalog();
    if (all.total <= 2) return;
    const page1 = await taskService.getTaskCatalog({ page: 1, pageSize: 2 });
    const page2 = await taskService.getTaskCatalog({ page: 2, pageSize: 2 });
    expect(page1.items.length).toBeLessThanOrEqual(2);
    if (page2.items.length > 0) {
      expect(page2.items[0].id).not.toBe(page1.items[0].id);
    }
  });
});

describe('taskService - getTaskDetail', () => {
  it('应返回任务详情', async () => {
    const detail = await taskService.getTaskDetail('task-1001');
    expect(detail).toHaveProperty('task');
    expect(detail.task.id).toBe('task-1001');
    expect(detail).toHaveProperty('recentRuns');
  });

  it('不存在任务应返回 task: null', async () => {
    const detail = await taskService.getTaskDetail('not-exist');
    expect(detail.task).toBeNull();
  });
});

describe('taskService - createTask', () => {
  it('应创建任务', async () => {
    const result = await taskService.createTask({
      name: '新任务',
      taskType: 'keyword',
      keywords: ['transformer'],
      scheduleKind: 'daily',
    });
    expect(result).toHaveProperty('task');
    expect(result.task.name).toBe('新任务');
  });

  it('runNow=true 时应触发运行', async () => {
    const result = await taskService.createTask({
      name: '立即运行',
      taskType: 'keyword',
      keywords: ['testing'],
      runNow: true,
    });
    expect(result.run).not.toBeNull();
  });
});

describe('taskService - updateTask', () => {
  it('应更新任务属性', async () => {
    const result = await taskService.updateTask('task-1001', { name: '改名任务' });
    expect(result.task.name).toBe('改名任务');
  });

  it('不存在的任务应抛错', async () => {
    await expect(
      taskService.updateTask('no-such', { name: 'x' })
    ).rejects.toThrow('任务不存在');
  });
});

describe('taskService - pauseTask / resumeTask', () => {
  it('pause 后 isEnabled 应为 false', async () => {
    const result = await taskService.pauseTask('task-1001');
    expect(result.task.isEnabled).toBe(false);
    expect(result.task.status).toBe('paused');
  });

  it('resume 后 isEnabled 应为 true', async () => {
    await taskService.pauseTask('task-1001');
    const result = await taskService.resumeTask('task-1001');
    expect(result.task.isEnabled).toBe(true);
  });
});

describe('taskService - deleteTask', () => {
  it('应删除无活跃运行的任务', async () => {
    const result = await taskService.deleteTask('task-1004');
    expect(result).toBeNull();
  });

  it('不存在的任务应正常返回 null（mock 删除实现为幂等）', async () => {
    const result = await taskService.deleteTask('no-such');
    expect(result).toBeNull();
  });
});

describe('taskService - runTask / listTaskRuns / getTaskRun', () => {
  it('runTask 应创建运行记录', async () => {
    const result = await taskService.runTask('task-1004');
    expect(result).toHaveProperty('run');
    expect(result.run.status).toBe('queued');
  });

  it('已有活跃运行的任务再次运行应抛错', async () => {
    await taskService.runTask('task-1004');
    await expect(taskService.runTask('task-1004')).rejects.toThrow('任务已有运行中的执行记录');
  });

  it('listTaskRuns 应返回运行历史', async () => {
    const runs = await taskService.listTaskRuns('task-1001');
    expect(runs).toHaveProperty('items');
    expect(Array.isArray(runs.items)).toBe(true);
  });

  it('getTaskRun 应返回单条运行记录', async () => {
    const runs = await taskService.listTaskRuns('task-1001');
    if (runs.items.length === 0) return;
    const run = await taskService.getTaskRun('task-1001', runs.items[0].id);
    expect(run.id).toBe(runs.items[0].id);
  });

  it('不存在的运行记录应抛错', async () => {
    await expect(taskService.getTaskRun('task-1001', 'no-run')).rejects.toThrow('运行记录不存在');
  });
});

describe('taskService - retryTaskRun', () => {
  it('retry 失败的运行应创建新运行', async () => {
    const runs = await taskService.listTaskRuns('task-1003');
    if (runs.items.length === 0) return;
    const result = await taskService.retryTaskRun('task-1003', runs.items[0].id);
    expect(result).toHaveProperty('run');
    expect(result.run.status).toBe('queued');
  });
});
