import { dailyDigest } from '../data/subscriptionData';
import { createEndpoint, request } from './apiClient';

let subscriptionStore = dailyDigest.topics.map((topic) => ({
  categories: [...new Set(topic.highlights.flatMap((paper) => paper.categories || []))],
  created_at: new Date().toISOString(),
  enabled: true,
  frequency: 'daily',
  id: topic.topicId,
  topic_keywords: [topic.topicName],
}));

function normalizeSubscription(subscription) {
  const keywords = subscription.topic_keywords || [];
  const categories = subscription.categories || [];
  return {
    ...subscription,
    categories,
    enabled: subscription.enabled ?? true,
    frequency: subscription.frequency || 'daily',
    keywords,
    name: keywords[0] || categories[0] || '未命名订阅',
  };
}

function toSubscriptionPayload(subscription) {
  return {
    categories: subscription.categories || [],
    enabled: subscription.enabled ?? true,
    frequency: subscription.frequency || 'daily',
    topic_keywords: subscription.keywords || [],
  };
}

function toSubscriptionUpdatePayload(changes) {
  const payload = {};
  if (changes.keywords !== undefined) payload.topic_keywords = changes.keywords;
  if (changes.categories !== undefined) payload.categories = changes.categories;
  if (changes.frequency !== undefined) payload.frequency = changes.frequency;
  if (changes.enabled !== undefined) payload.enabled = changes.enabled;
  return payload;
}

function normalizePaper(paper) {
  const arxivId = paper.arxiv_id || null;
  return {
    ...paper,
    abstract: paper.abstract || '',
    arxivId,
    arxivUrl: paper.arxiv_url || (arxivId ? `https://arxiv.org/abs/${arxivId}` : null),
    authors: paper.authors || [],
    categories: paper.primary_category ? [paper.primary_category] : [],
    id: paper.paper_id,
    inLibrary: Boolean(paper.in_library),
    matchScore: Math.round((paper.relevance_score || 0) * 100),
    reason: paper.reason || '与你的研究兴趣相关',
  };
}

export const getSubscriptionFeed = createEndpoint({
  mock: () => ({
    dailyDigest: {
      date: new Date().toISOString().slice(0, 10),
      summary: 'Mock 模式不展示真实论文推送，请连接后端获取数据库中的论文。',
      topics: [],
    },
    historyBasedRecommendations: [],
  }),
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

export const listSubscriptions = createEndpoint({
  mock: () => subscriptionStore.map(normalizeSubscription),
  http: async () => {
    const result = await request('/subscriptions');
    return (result.items || []).map(normalizeSubscription);
  },
});

export const createSubscription = createEndpoint({
  mock: (subscription) => {
    const created = {
      ...toSubscriptionPayload(subscription),
      created_at: new Date().toISOString(),
      id: `subscription-${Date.now()}`,
    };
    subscriptionStore = [created, ...subscriptionStore];
    return normalizeSubscription(created);
  },
  http: async (subscription) => normalizeSubscription(await request('/subscriptions', {
    body: toSubscriptionPayload(subscription),
    method: 'POST',
  })),
});

export const updateSubscription = createEndpoint({
  mock: (subscriptionId, changes) => {
    subscriptionStore = subscriptionStore.map((subscription) => (
      subscription.id === subscriptionId
        ? { ...subscription, ...toSubscriptionUpdatePayload(changes) }
        : subscription
    ));
    return normalizeSubscription(
      subscriptionStore.find((subscription) => subscription.id === subscriptionId),
    );
  },
  http: async (subscriptionId, changes) => normalizeSubscription(
    await request(`/subscriptions/${subscriptionId}`, {
      body: toSubscriptionUpdatePayload(changes),
      method: 'PUT',
    }),
  ),
});

export const deleteSubscription = createEndpoint({
  mock: (subscriptionId) => {
    subscriptionStore = subscriptionStore.filter((subscription) => subscription.id !== subscriptionId);
    return null;
  },
  http: (subscriptionId) => request(`/subscriptions/${subscriptionId}`, { method: 'DELETE' }),
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
