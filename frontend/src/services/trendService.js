import {
  getSeriesForRange,
  getTrendMilestones,
  getTrendStages,
  getTrendStats,
  getTrendStatus,
  getTrendTopicById,
  trendRangeOptions,
  trendSignals,
  trendSortOptions,
  trendTopics,
} from '../data/trendData';
import { wikiCategoryOptions } from '../data/wikiData';
import { getRelatedConcepts } from '../data/wikiData';
import { cloneMockData, createEndpoint, getMockUserScope, request } from './apiClient';

const trendStores = new Map();

function getTrendStore() {
  const scope = getMockUserScope();
  if (!trendStores.has(scope)) {
    trendStores.set(scope, {
      signals: cloneMockData(trendSignals),
      topics: cloneMockData(trendTopics),
    });
  }
  return trendStores.get(scope);
}

const httpRangeOptions = [
  { label: '近 3 月', value: 3 },
  { label: '近 6 月', value: 6 },
  { label: '近 12 月', value: 12 },
];

const httpSortOptions = [
  { label: '增长最快', value: 'momentum' },
  { label: '热度最高', value: 'trend' },
  { label: '论文最多', value: 'paperCount' },
  { label: '最近更新', value: 'updatedAt' },
];

const phaseMeta = {
  emerging: { label: '探索期', color: '#4f6ef7' },
  growing: { label: '增长期', color: '#16a085' },
  mature: { label: '成熟期', color: '#faad14' },
  declining: { label: '调整期', color: '#8c8c8c' },
};

function normalizePaper(paper) {
  return {
    arxivId: paper.arxiv_id,
    arxivUrl: paper.arxiv_url,
    citationCount: paper.citation_count || 0,
    id: paper.paper_id,
    publishedAt: paper.published_at,
    relevance: paper.relevance || 0,
    role: paper.role || '该主题的代表性研究',
    title: paper.title,
    year: paper.year,
  };
}

function normalizeSeries(points = []) {
  const maxCount = Math.max(1, ...points.map((point) => point.count || 0));
  return points.map((point) => ({
    count: point.count || 0,
    label: point.month,
    value: Math.round(((point.count || 0) / maxCount) * 100),
  }));
}

function getTopicStage(topic) {
  if (topic.trend_direction === 'rising') return '增长期';
  if (topic.trend_direction === 'declining') return '调整期';
  if ((topic.paper_count || 0) >= 10) return '成熟期';
  return '探索期';
}

function normalizeTopic(topic) {
  const series = normalizeSeries(topic.monthly_trend);
  const latest = series.at(-1)?.count || 0;
  const previous = series.at(-2)?.count || 0;
  return {
    aliases: topic.aliases || [],
    category: topic.category || '未分类',
    description: topic.description || '暂无主题说明',
    id: topic.id,
    keywords: topic.keywords || [],
    mentions: topic.mentions || topic.paper_count || 0,
    momentum: topic.momentum || 0,
    paperCount: topic.paper_count || 0,
    papers: (topic.representative_papers || []).map(normalizePaper),
    series,
    stage: getTopicStage(topic),
    summaryPoints: topic.summary_points || [topic.description || '暂无趋势说明'],
    trend: topic.hotness || 0,
    trendDirection: topic.trend_direction || 'stable',
    updatedAt: topic.updated_at || '',
    velocity: latest - previous,
  };
}

function normalizeSignal(signal) {
  return {
    color: signal.color || 'blue',
    description: signal.description || '',
    id: signal.id,
    impact: signal.impact || 0,
    time: signal.time || '',
    title: signal.title,
    topicIds: signal.topic_ids || [],
  };
}

function normalizeOverview(payload) {
  return {
    categoryOptions: payload.category_options || ['全部'],
    rangeOptions: httpRangeOptions,
    relatedConceptsByTopicId: payload.related_concepts_by_topic_id || {},
    signals: (payload.signals || []).map(normalizeSignal),
    sortOptions: httpSortOptions,
    topics: (payload.topics || []).map(normalizeTopic),
  };
}

function normalizeMilestone(milestone, index, total) {
  return {
    color: index === 0 ? 'blue' : index === total - 1 ? 'green' : 'gray',
    description: milestone.role || milestone.significance,
    id: `${milestone.paper_id}-${milestone.significance}`,
    paperId: milestone.paper_id,
    title: milestone.title,
    year: milestone.year,
  };
}

function normalizeStage(phase, index) {
  const meta = phaseMeta[phase.phase] || phaseMeta.emerging;
  return {
    color: meta.color,
    key: `${phase.phase}-${index}`,
    label: meta.label,
    metric: `${phase.start_month} 至 ${phase.end_month}`,
    value: phase.description,
  };
}

function normalizeDetail(payload) {
  const topic = normalizeTopic({
    ...payload.topic,
    monthly_trend: payload.monthly_trend || payload.topic?.monthly_trend,
    representative_papers:
      payload.representative_papers || payload.topic?.representative_papers,
  });
  const milestones = payload.milestones || [];
  return {
    milestones: milestones.map((item, index) => (
      normalizeMilestone(item, index, milestones.length)
    )),
    relatedConcepts: payload.related_concepts || [],
    signals: (payload.signals || []).map(normalizeSignal),
    stages: (payload.phases || []).map(normalizeStage),
    topic,
    topicRank: payload.topic_rank || null,
    topics: (payload.topics || []).map(normalizeTopic),
  };
}

export const getTrendOverview = createEndpoint({
  mock: () => ({
    categoryOptions: wikiCategoryOptions,
    rangeOptions: trendRangeOptions,
    signals: getTrendStore().signals,
    sortOptions: trendSortOptions,
    topics: getTrendStore().topics,
    relatedConceptsByTopicId: Object.fromEntries(
      getTrendStore().topics.map((topic) => [topic.id, getRelatedConcepts(topic)]),
    ),
  }),
  http: async (query) => normalizeOverview(await request('/trends', { query })),
});

export const getTrendDetail = createEndpoint({
  mock: (topicId) => {
    const store = getTrendStore();
    const topic = store.topics.find((item) => item.id === topicId) || getTrendTopicById(topicId);
    return topic
      ? {
          milestones: getTrendMilestones(topic),
          relatedConcepts: getRelatedConcepts(topic),
          signals: store.signals.filter((signal) => signal.topicIds.includes(topic.id)),
          stages: getTrendStages(topic),
          topic,
          topics: store.topics,
        }
      : {
          milestones: [],
          relatedConcepts: [],
          signals: [],
          stages: [],
          topic: null,
          topics: store.topics,
        };
  },
  http: async (topicId) => normalizeDetail(await request(`/trends/${topicId}`)),
});

export {
  getSeriesForRange,
  getTrendMilestones,
  getTrendStages,
  getTrendStats,
  getTrendStatus,
};
