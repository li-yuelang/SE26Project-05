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

function fromHttpPaper(paper) {
  return {
    ...paper,
    arxivId: paper.arxiv_id,
    id: paper.id,
    isFavorite: false,
    isRead: paper.parsed_status === 'done',
    link: paper.arxiv_url,
    pdfLink: paper.pdf_url,
    pdfUrl: paper.pdf_url,
    publishedDate: paper.published_at?.slice(0, 10) || '',
    updatedDate: paper.updated_at_source?.slice(0, 10) || '',
  };
}

function fromHttpPaperDetail(paper) {
  const normalized = fromHttpPaper(paper);
  const structured = paper.structured_content || {};
  return {
    ...normalized,
    isStarred: false,
    keywords: paper.metadata_extra?.keywords || paper.categories || [],
    published: normalized.publishedDate,
    updated: normalized.updatedDate || paper.updated_at?.slice(0, 10) || '',
    relatedConcepts: paper.relatedConcepts || [],
    relatedPapers: paper.relatedPapers || [],
    structuredContent: {
      summary: structured.summary || paper.abstract,
      concept: structured.concept || structured.concepts || '暂无结构化概念内容',
      methods: structured.methods || '暂无结构化方法内容',
    },
  };
}

let paperStore = cloneMockData(learningPapers.map(toListPaper));

export const listPapers = createEndpoint({
  mock: () => ({ items: paperStore, total: paperStore.length }),
  http: async (query) => {
    const result = await request('/papers', { query });
    return { ...result, items: result.items.map(fromHttpPaper) };
  },
});

export const getPaperDetail = createEndpoint({
  mock: (paperId) => {
    const paper = paperStore.find((item) => item.id === paperId);
    if (!paper) {
      throw new ApiError('论文不存在', {
        code: 'PAPER_NOT_FOUND',
        status: 404,
      });
    }
    return toPaperDetail(paper);
  },
  http: async (paperId) => fromHttpPaperDetail(await request(`/papers/${paperId}`)),
});

export const getPaperBookmarkStatus = createEndpoint({
  mock: (paperId) => {
    const paper = paperStore.find((item) => item.id === paperId);
    return Boolean(paper?.favorite || paper?.isFavorite);
  },
  http: async (paperId) => {
    const pageSize = 100;
    let page = 1;
    let total = 0;

    do {
      const result = await request('/learning/bookmarks', {
        query: { page, pageSize },
      });
      if ((result.items || []).some((bookmark) => bookmark.paper_id === paperId)) {
        return true;
      }
      total = result.total || 0;
      page += 1;
    } while ((page - 1) * pageSize < total);

    return false;
  },
});

export const setPaperBookmark = createEndpoint({
  mock: (paperId, bookmarked) => {
    paperStore = paperStore.map((paper) => (
      paper.id === paperId
        ? { ...paper, favorite: bookmarked, isFavorite: bookmarked }
        : paper
    ));
    return bookmarked;
  },
  http: async (paperId, bookmarked) => {
    await request(`/learning/bookmarks${bookmarked ? '' : `/${paperId}`}`, {
      ...(bookmarked ? { body: { folder: null, paper_id: paperId } } : {}),
      method: bookmarked ? 'POST' : 'DELETE',
    });
    return bookmarked;
  },
});

export const setPaperBookmarks = createEndpoint({
  mock: (paperIds, bookmarked) => {
    const selectedIds = new Set(paperIds);
    paperStore = paperStore.map((paper) => (
      selectedIds.has(paper.id)
        ? { ...paper, favorite: bookmarked, isFavorite: bookmarked }
        : paper
    ));
    return {
      paperIds,
      bookmarked,
      processedCount: paperIds.length,
    };
  },
  http: (paperIds, bookmarked) => request('/learning/bookmarks/batch', {
    body: { paper_ids: paperIds, bookmarked },
    method: 'PUT',
  }),
});

export const getPaperChunk = createEndpoint({
  mock: (paperId, chunkIndex) => ({
    paperId,
    chunkIndex,
    sectionTitle: '引用原文',
    content: '该引用定位到论文解析后的原文片段。切换到真实后端后，此处会展示入库的完整片段内容。',
  }),
  http: (paperId, chunkIndex) => request(`/papers/${paperId}/chunks/${chunkIndex}`),
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

export const deletePaper = createEndpoint({
  mock: (paperId) => {
    const exists = paperStore.some((paper) => paper.id === paperId);
    if (!exists) {
      throw new ApiError('论文不存在', {
        code: 'PAPER_NOT_FOUND',
        status: 404,
      });
    }
    paperStore = paperStore.filter((paper) => paper.id !== paperId);
    return null;
  },
  http: (paperId) => request(`/papers/${paperId}`, { method: 'DELETE' }),
});

export const deletePapers = createEndpoint({
  mock: (paperIds) => {
    const selectedIds = new Set(paperIds);
    const deletedIds = paperStore
      .filter((paper) => selectedIds.has(paper.id))
      .map((paper) => paper.id);
    paperStore = paperStore.filter((paper) => !selectedIds.has(paper.id));
    return { deletedIds, deletedCount: deletedIds.length };
  },
  http: (paperIds) => request('/papers/batch', {
    body: { paper_ids: paperIds },
    method: 'DELETE',
  }),
});
