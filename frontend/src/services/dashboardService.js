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

function normalizePaper(paper) {
  return {
    ...paper,
    arxivUrl: paper.arxiv_url,
    category: paper.primary_category || paper.categories?.[0] || '未分类',
    publishedAt: paper.published_at?.slice(0, 10) || '',
    summary: paper.abstract || '',
    tags: paper.categories || [],
  };
}

function normalizeTask(task) {
  const keywords = task.keywords || [];
  const categories = task.categories || [];
  return {
    color: statusColor[task.status] || 'default',
    description: [...keywords, ...categories].join('、') || task.schedule || '暂无检索条件',
    name: `${task.task_type || '抓取'}任务`,
    status: task.status,
  };
}

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
  http: async () => {
    const [paperResult, taskResult, trendResult, wikiResult] = await Promise.all([
      request('/papers', { query: { page: 1, page_size: 5 } }),
      request('/tasks'),
      request('/trends'),
      request('/wiki'),
    ]);
    const topics = trendResult.topics?.length ? trendResult.topics : trendResult.signals || [];
    return {
      papers: (paperResult.items || []).map(normalizePaper),
      recentTasks: (taskResult.tasks || []).slice(0, 3).map(normalizeTask),
      stats: {
        concepts: wikiResult.stats?.concepts || 0,
        papers: paperResult.total || 0,
        runningTasks: (taskResult.tasks || []).filter((task) => task.status === 'running').length,
        topics: topics.length,
      },
      topics: topics.slice(0, 4).map((topic) => ({
        count: topic.paper_count || 0,
        name: topic.name,
        percent: topic.hotness || 0,
      })),
    };
  },
});
