import { learningPapers } from '../data/learningData';
import { wikiConcepts } from '../data/wikiData';
import { ApiError, cloneMockData, createEndpoint, request } from './apiClient';

function toListPaper(paper) {
  return {
    ...paper,
    abstract: paper.summary,
    isFavorite: paper.favorite,
    isRead: paper.status === 'done',
    link: paper.arxivUrl,
    pdfLink: paper.pdfUrl,
    publishedDate: paper.publishedAt,
    updatedDate: paper.updatedAt,
  };
}

function toPaperDetail(paper) {
  if (!paper) return null;
  return {
    ...toListPaper(paper),
    arxivId: paper.id,
    isStarred: paper.favorite,
    keywords: paper.tags,
    published: paper.publishedAt,
    relatedConcepts: wikiConcepts.slice(0, 3).map((concept) => ({
      id: concept.id,
      name: concept.name,
      description: concept.description,
    })),
    relatedPapers: learningPapers
      .filter((item) => item.id !== paper.id)
      .slice(0, 3)
      .map((item) => ({ id: item.id, title: item.title })),
    structuredContent: {
      concept: `### 核心概念\n\n${paper.tags.map((tag) => `- **${tag}**`).join('\n')}`,
      methods: `### 方法\n\n${paper.methods.map((method, index) => `${index + 1}. ${method}`).join('\n')}`,
      summary: paper.summary,
    },
    updated: paper.updatedAt,
  };
}

let paperStore = cloneMockData(learningPapers.map(toListPaper));

export const listPapers = createEndpoint({
  mock: () => ({ items: paperStore, total: paperStore.length }),
  http: (query) => request('/papers', { query }),
});

export const getPaperDetail = createEndpoint({
  mock: (paperId) => {
    const paper = learningPapers.find((item) => item.id === paperId);
    if (!paper) {
      throw new ApiError('论文不存在', {
        code: 'PAPER_NOT_FOUND',
        status: 404,
      });
    }
    return toPaperDetail(paper);
  },
  http: (paperId) => request(`/papers/${paperId}`),
});

export const updatePaper = createEndpoint({
  mock: (paperId, changes) => {
    paperStore = paperStore.map((paper) => (
      paper.id === paperId ? { ...paper, ...changes } : paper
    ));
    return paperStore.find((paper) => paper.id === paperId);
  },
  http: (paperId, changes) => request(`/papers/${paperId}`, {
    body: changes,
    method: 'PATCH',
  }),
});
