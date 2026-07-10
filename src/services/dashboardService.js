import { learningPapers } from '../data/learningData';
import { mockTasks } from '../data/taskData';
import { trendTopics } from '../data/trendData';
import { createEndpoint, request } from './apiClient';

const statusColor = {
  completed: 'green',
  failed: 'red',
  paused: 'gold',
  running: 'blue',
  scheduled: 'gold',
};

export const getDashboard = createEndpoint({
  mock: () => ({
    papers: learningPapers.slice(0, 5).map((paper) => ({
      ...paper,
      category: paper.categories[0],
    })),
    recentTasks: mockTasks.slice(0, 3).map((task) => ({
      color: statusColor[task.status] || 'default',
      description: task.description,
      name: task.name,
      status: task.status,
    })),
    topics: trendTopics.slice(0, 4).map((topic) => ({
      count: topic.paperCount,
      name: topic.name,
      percent: topic.trend,
    })),
  }),
  http: () => request('/dashboard'),
});
