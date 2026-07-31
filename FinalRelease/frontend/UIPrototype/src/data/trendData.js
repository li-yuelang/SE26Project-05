import { wikiConcepts } from './wikiData';

const trendSeriesByTopic = {
  transformer: [44, 48, 53, 59, 66, 74, 86],
  'self-attention': [50, 52, 56, 60, 67, 74, 82],
  'multi-head-attention': [38, 41, 45, 49, 54, 61, 68],
  rag: [36, 43, 52, 61, 72, 81, 88],
  'concept-graph': [28, 34, 42, 51, 60, 68, 74],
  'topic-aware-embedding': [22, 28, 34, 42, 48, 55, 61],
  bert: [58, 57, 58, 60, 61, 63, 64],
  'knowledge-graph': [45, 48, 51, 56, 61, 66, 70],
};

export const trendMonthLabels = [
  '2026-01',
  '2026-02',
  '2026-03',
  '2026-04',
  '2026-05',
  '2026-06',
  '2026-07',
];

export const trendRangeOptions = [
  { label: '近 3 月', value: 3 },
  { label: '近 6 月', value: 6 },
  { label: '全部', value: 7 },
];

export const trendSortOptions = [
  { label: '增长最快', value: 'momentum' },
  { label: '热度最高', value: 'trend' },
  { label: '论文最多', value: 'paperCount' },
  { label: '最近更新', value: 'updatedAt' },
];

export const trendSignals = [
  {
    id: 'rag-kg',
    title: 'RAG 与知识图谱关联增强',
    description: 'RAG、Knowledge Graph、Concept Graph 的强关联边集中增加，适合作为知识增强生成方向追踪。',
    time: '2026-07-07 18:20',
    impact: 92,
    color: 'blue',
    topicIds: ['rag', 'knowledge-graph', 'concept-graph'],
  },
  {
    id: 'attention-efficiency',
    title: '长上下文注意力优化升温',
    description: 'Self-Attention 与 Multi-Head Attention 的新增论文更关注计算成本、稀疏化和长序列扩展。',
    time: '2026-07-06 14:35',
    impact: 84,
    color: 'green',
    topicIds: ['self-attention', 'multi-head-attention', 'transformer'],
  },
  {
    id: 'topic-embedding',
    title: '主题感知表示用于论文组织',
    description: 'Topic-Aware Embedding 与 Concept Graph 的关系更紧密，主要服务于论文聚类、推荐和语义检索。',
    time: '2026-07-05 11:10',
    impact: 76,
    color: 'gold',
    topicIds: ['topic-aware-embedding', 'concept-graph'],
  },
];

function buildFallbackSeries(concept) {
  const start = Math.max(18, concept.trend - 30);
  const step = Math.max(3, Math.round((concept.trend - start) / 6));

  return trendMonthLabels.map((_, index) =>
    Math.min(100, start + step * index),
  );
}

function toSeries(concept) {
  const values = trendSeriesByTopic[concept.id] || buildFallbackSeries(concept);

  return values.map((value, index) => ({
    label: trendMonthLabels[index],
    value,
  }));
}

function getTopicStage(concept) {
  if (concept.trend >= 85) return '爆发期';
  if (concept.trend >= 72) return '扩展期';
  if (concept.paperCount >= 14) return '成熟期';
  return '探索期';
}

export const trendTopics = wikiConcepts.map((concept) => {
  const series = toSeries(concept);
  const latest = series[series.length - 1].value;
  const previous = series[series.length - 2]?.value ?? latest;
  const baseline = series[Math.max(0, series.length - 3)].value;

  return {
    ...concept,
    series,
    velocity: latest - previous,
    momentum: latest - baseline,
    stage: getTopicStage(concept),
  };
});

export function getTrendTopicById(topicId) {
  return trendTopics.find((topic) => topic.id === topicId);
}

export function getSeriesForRange(topic, range) {
  return topic.series.slice(-range);
}

export function getTrendStatus(topic) {
  if (topic.momentum >= 14) {
    return { label: '快速升温', color: 'red' };
  }
  if (topic.momentum >= 8) {
    return { label: '持续走强', color: 'orange' };
  }
  if (topic.momentum >= 4) {
    return { label: '稳步增长', color: 'green' };
  }
  return { label: '平稳演进', color: 'blue' };
}

export function getTrendStats(topics = trendTopics) {
  const paperIds = new Set();

  topics.forEach((topic) => {
    topic.papers.forEach((paper) => paperIds.add(paper.id));
  });

  return {
    topics: topics.length,
    papers: paperIds.size,
    averageTrend: topics.length
      ? Math.round(
          topics.reduce((total, topic) => total + topic.trend, 0) /
            topics.length,
        )
      : 0,
    risingTopics: topics.filter((topic) => topic.momentum >= 8).length,
  };
}

export function getTrendMilestones(topic) {
  const paperMilestones = [...topic.papers]
    .sort((left, right) => left.year - right.year)
    .map((paper, index) => ({
      id: `${topic.id}-${paper.id}`,
      year: paper.year,
      title: paper.title,
      description: paper.role,
      paperId: paper.id,
      color: index === 0 ? 'blue' : paper.year >= 2024 ? 'green' : 'gray',
    }));

  return [
    ...paperMilestones,
    {
      id: `${topic.id}-focus`,
      year: '当前',
      title: '当前研究焦点',
      description: topic.summaryPoints[0],
      color: 'gold',
    },
  ];
}

export function getTrendStages(topic) {
  const strongRelationCount = topic.related.filter(
    (relation) => relation.strength >= 80,
  ).length;

  return [
    {
      key: 'foundation',
      label: '问题基础',
      value: topic.summaryPoints[0] || topic.description,
      metric: `${topic.paperCount} 篇来源论文`,
      color: '#4f6ef7',
    },
    {
      key: 'method',
      label: '方法扩展',
      value: topic.summaryPoints[1] || topic.description,
      metric: `${topic.related.length} 条概念关联`,
      color: '#16a085',
    },
    {
      key: 'application',
      label: '应用迁移',
      value: topic.summaryPoints[2] || topic.description,
      metric: `${strongRelationCount} 条强关联`,
      color: '#faad14',
    },
  ];
}
