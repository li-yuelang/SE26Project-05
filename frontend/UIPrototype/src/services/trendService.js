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
import { createEndpoint, request } from './apiClient';

export const getTrendOverview = createEndpoint({
  mock: () => ({
    categoryOptions: wikiCategoryOptions,
    rangeOptions: trendRangeOptions,
    signals: trendSignals,
    sortOptions: trendSortOptions,
    topics: trendTopics,
    relatedConceptsByTopicId: Object.fromEntries(
      trendTopics.map((topic) => [topic.id, getRelatedConcepts(topic)]),
    ),
  }),
  http: (query) => request('/trends', { query }),
});

export const getTrendDetail = createEndpoint({
  mock: (topicId) => {
    const topic = getTrendTopicById(topicId);
    return topic
      ? {
          milestones: getTrendMilestones(topic),
          relatedConcepts: getRelatedConcepts(topic),
          signals: trendSignals.filter((signal) => signal.topicIds.includes(topic.id)),
          stages: getTrendStages(topic),
          topic,
          topics: trendTopics,
        }
      : {
          milestones: [],
          relatedConcepts: [],
          signals: [],
          stages: [],
          topic: null,
          topics: trendTopics,
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
