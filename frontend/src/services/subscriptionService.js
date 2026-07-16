import { dailyDigest, historyBasedRecommendations } from '../data/subscriptionData';
import { createEndpoint, request } from './apiClient';

function normalizePaper(paper) {
  return {
    ...paper,
    abstract: paper.abstract || '',
    authors: paper.authors || [],
    categories: paper.primary_category ? [paper.primary_category] : [],
    id: paper.paper_id,
    matchScore: Math.round((paper.relevance_score || 0) * 100),
    reason: paper.reason || '与你的研究兴趣相关',
  };
}

export const getSubscriptionFeed = createEndpoint({
  mock: () => ({ dailyDigest, historyBasedRecommendations }),
  http: async () => {
    const [digest, recommendations] = await Promise.all([
      request('/subscriptions/digest'),
      request('/subscriptions/recommendations'),
    ]);
    const topics = (digest.topic_groups || []).map((group, index) => ({
      highlights: (group.papers || []).map(normalizePaper),
      newCount: group.papers?.length || 0,
      topicId: `${group.topic}-${index}`,
      topicName: group.topic,
    }));
    const recommendationItems = [
      ...(recommendations.history_based || []),
      ...(recommendations.content_based || []),
      ...(recommendations.collaborative || []),
    ].map(normalizePaper);
    const paperCount = topics.reduce((total, topic) => total + topic.newCount, 0);
    return {
      dailyDigest: {
        date: digest.date,
        summary: `今日订阅主题共匹配到 ${paperCount} 篇论文。`,
        topics,
      },
      historyBasedRecommendations: recommendationItems,
    };
  },
});

export const saveSubscriptionPreferences = createEndpoint({
  mock: (preferences) => preferences,
  http: (preferences) => request('/settings/notifications', {
    body: {
      email_digest: preferences.digestEnabled ?? true,
      frequency: preferences.digestEnabled === false ? 'none' : 'daily',
      push_new_paper: false,
      push_recommendation: true,
    },
    method: 'PUT',
  }),
});
