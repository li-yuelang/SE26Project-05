import {
  followedTopics,
  learningNotes,
  learningPapers,
  readingHistory,
  statusMeta,
} from '../data/learningData';
import { cloneMockData, createEndpoint, request } from './apiClient';

let paperStore = cloneMockData(learningPapers);
let topicStore = cloneMockData(followedTopics);

export const getLearningCenter = createEndpoint({
  mock: () => ({
    notes: learningNotes,
    papers: paperStore,
    readingHistory,
    statusMeta,
    topics: topicStore,
  }),
  http: () => request('/learning'),
});

export const listLearningPapers = createEndpoint({
  mock: () => paperStore,
  http: (query) => request('/learning/papers', { query }),
});

export const updateLearningPaper = createEndpoint({
  mock: (paperId, changes) => {
    paperStore = paperStore.map((paper) => (
      paper.id === paperId ? { ...paper, ...changes } : paper
    ));
    return paperStore.find((paper) => paper.id === paperId);
  },
  http: (paperId, changes) => request(`/learning/papers/${paperId}`, {
    body: changes,
    method: 'PATCH',
  }),
});

export const updateFollowedTopic = createEndpoint({
  mock: (topicId, followed) => {
    topicStore = topicStore.map((topic) => (
      topic.id === topicId ? { ...topic, followed } : topic
    ));
    return topicStore.find((topic) => topic.id === topicId);
  },
  http: (topicId, followed) => request(`/learning/topics/${topicId}`, {
    body: { followed },
    method: 'PATCH',
  }),
});

export const exportComparison = createEndpoint({
  mock: (paperIds) => ({ paperIds, status: 'draft' }),
  http: (paperIds) => request('/learning/comparisons/export', {
    body: { paperIds },
    method: 'POST',
  }),
});
