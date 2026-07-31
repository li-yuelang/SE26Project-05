import {
  getTaskById,
  mockTasks,
  taskStatusMeta,
  taskTypeMeta,
} from '../data/taskData';
import { cloneMockData, createEndpoint, request } from './apiClient';

let taskStore = cloneMockData(mockTasks);

export const getTaskCatalog = createEndpoint({
  mock: () => ({
    statusMeta: taskStatusMeta,
    tasks: taskStore,
    typeMeta: taskTypeMeta,
  }),
  http: (query) => request('/tasks', { query }),
});

export const getTaskDetail = createEndpoint({
  mock: (taskId) => ({
    statusMeta: taskStatusMeta,
    task: taskStore.find((task) => task.id === taskId) || getTaskById(taskId),
    typeMeta: taskTypeMeta,
  }),
  http: (taskId) => request(`/tasks/${taskId}`),
});

export const updateTask = createEndpoint({
  mock: (taskId, changes) => {
    taskStore = taskStore.map((task) => (
      task.id === taskId ? { ...task, ...changes } : task
    ));
    return taskStore.find((task) => task.id === taskId);
  },
  http: (taskId, changes) => request(`/tasks/${taskId}`, {
    body: changes,
    method: 'PATCH',
  }),
});

export const resetTasks = createEndpoint({
  mock: () => {
    taskStore = cloneMockData(mockTasks);
    return taskStore;
  },
  http: () => request('/tasks/reset', { method: 'POST' }),
});
