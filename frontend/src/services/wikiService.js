import {
  getConceptById,
  getRelatedConcepts,
  getWikiStats,
  wikiActivity,
  wikiCategoryOptions,
  wikiConcepts,
} from '../data/wikiData';
import { createEndpoint, request } from './apiClient';
import { getMockUserScope, cloneMockData } from './apiClient';

const wikiStores = new Map();

function getWikiState() {
  const scope = getMockUserScope();
  if (!wikiStores.has(scope)) {
    wikiStores.set(scope, {
      concepts: cloneMockData(wikiConcepts),
      activity: cloneMockData(wikiActivity),
      stats: cloneMockData(getWikiStats()),
    });
  }
  return wikiStores.get(scope);
}

export const getWikiOverview = createEndpoint({
  mock: () => ({
    activity: getWikiState().activity,
    categoryOptions: wikiCategoryOptions,
    concepts: getWikiState().concepts,
    relatedConceptsById: Object.fromEntries(
      getWikiState().concepts.map((concept) => [concept.id, getRelatedConcepts(concept)]),
    ),
    stats: getWikiState().stats,
  }),
  http: (query) => request('/wiki', { query }),
});

export const getConceptDetail = createEndpoint({
  mock: (conceptId) => {
    const concept = getWikiState().concepts.find((item) => item.id === conceptId)
      || getConceptById(conceptId);
    return {
      concept,
      relatedConcepts: concept ? getRelatedConcepts(concept) : [],
    };
  },
  http: (conceptId) => request(`/wiki/concepts/${conceptId}`),
});

export function findRelatedConcepts(concept, concepts = wikiConcepts) {
  if (!concept) return [];
  const relationIds = concept.relations.map((relation) => relation.targetId);
  return concepts.filter((item) => relationIds.includes(item.id));
}
