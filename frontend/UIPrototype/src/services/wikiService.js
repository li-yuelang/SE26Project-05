import {
  getConceptById,
  getRelatedConcepts,
  getWikiStats,
  wikiActivity,
  wikiCategoryOptions,
  wikiConcepts,
} from '../data/wikiData';
import { createEndpoint, request } from './apiClient';

export const getWikiOverview = createEndpoint({
  mock: () => ({
    activity: wikiActivity,
    categoryOptions: wikiCategoryOptions,
    concepts: wikiConcepts,
    relatedConceptsById: Object.fromEntries(
      wikiConcepts.map((concept) => [concept.id, getRelatedConcepts(concept)]),
    ),
    stats: getWikiStats(),
  }),
  http: (query) => request('/wiki', { query }),
});

export const getConceptDetail = createEndpoint({
  mock: (conceptId) => {
    const concept = getConceptById(conceptId);
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
