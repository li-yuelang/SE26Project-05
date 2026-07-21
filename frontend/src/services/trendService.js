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
  http: (query) => request('/trends', { query }),
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
  http: (topicId) => request(`/trends/${topicId}`),
});

export {
  getSeriesForRange,
  getTrendMilestones,
  getTrendStages,
  getTrendStats,
  getTrendStatus,
};
