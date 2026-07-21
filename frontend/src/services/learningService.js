import {
  followedTopics,
  learningNotes,
  learningPapers,
  readingHistory,
  statusMeta,
} from '../data/learningData';
import { cloneMockData, createEndpoint, request } from './apiClient';

let paperStore = cloneMockData(learningPapers);
let noteStore = cloneMockData(learningNotes);
let topicStore = cloneMockData(followedTopics);
let httpPaperStore = new Map();
let httpTopicStore = new Map();

const PAPER_PAGE_SIZE = 1000;
const LEARNING_PAGE_SIZE = 100;

const httpStatusMeta = {
  todo: { color: 'default', text: '待读' },
  reading: { color: 'processing', text: '阅读中' },
  done: { color: 'success', text: '已读' },
};

function normalizeNote(note) {
  return {
    ...note,
    content: note.content,
    paperId: note.paper_id,
    tags: note.anchor?.tags || [],
    title: note.anchor?.title || '学习笔记',
    updatedAt: note.updated_at?.slice(0, 16).replace('T', ' ') || '',
  };
}

function normalizeHistory(item) {
  return {
    action: item.progress >= 100 ? '完成阅读' : '更新阅读进度',
    detail: `阅读进度 ${item.progress}%`,
    paperId: item.paper_id,
    time: item.last_read_at?.slice(0, 16).replace('T', ' ') || '',
  };
}

function normalizeTopic(topic) {
  return {
    ...topic,
    digestTime: '每日 09:00',
    followed: true,
    matchRate: 0,
    name: topic.topic,
    newToday: 0,
    paperCount: 0,
  };
}

function normalizePaper(paper, bookmarks, histories, notes) {
  const bookmark = bookmarks.get(paper.id);
  const history = histories.get(paper.id);
  const paperNotes = notes.get(paper.id) || [];
  const progress = history?.progress || 0;
  const normalized = {
    ...paper,
    arxivUrl: paper.arxiv_url,
    bestFor: '',
    categories: paper.categories || [],
    commentsCount: 0,
    conclusion: paper.abstract || '',
    datasets: [],
    direction: paper.primary_category || paper.categories?.[0] || '未分类',
    experiment: '',
    favorite: Boolean(bookmark),
    lastReadAt: history?.last_read_at?.slice(0, 16).replace('T', ' ') || '尚未阅读',
    limitations: '',
    methods: [],
    noteId: paperNotes[0]?.id || null,
    notesCount: paperNotes.length,
    pdfUrl: paper.pdf_url,
    priority: bookmark ? '高' : '中',
    progress,
    publishedAt: paper.published_at?.slice(0, 10) || '',
    rating: 0,
    readMinutes: 0,
    researchQuestion: '',
    status: progress >= 100 ? 'done' : progress > 0 ? 'reading' : 'todo',
    summary: paper.abstract || '',
    tags: paper.categories || [],
    updatedAt: paper.updated_at_source?.slice(0, 10) || '',
    userNote: paperNotes[0]?.content || '',
  };
  httpPaperStore.set(normalized.id, normalized);
  return normalized;
}

async function getAllLearningItems(path) {
  const items = [];
  let page = 1;
  let total = 0;

  do {
    const result = await request(path, {
      query: { page, pageSize: LEARNING_PAGE_SIZE },
    });
    items.push(...(result.items || []));
    total = result.total || 0;
    page += 1;
  } while (items.length < total);

  return items;
}

async function getHttpLearningCenter() {
  const [paperResult, bookmarksResult, notesResult, historiesResult, topicResult] = await Promise.all([
    request('/papers', { query: { page: 1, page_size: PAPER_PAGE_SIZE } }),
    getAllLearningItems('/learning/bookmarks'),
    getAllLearningItems('/learning/notes'),
    getAllLearningItems('/learning/history'),
    request('/learning/topics'),
  ]);
  const bookmarks = new Map(
    bookmarksResult.map((bookmark) => [bookmark.paper_id, bookmark]),
  );
  const histories = new Map(
    historiesResult.map((history) => [history.paper_id, history]),
  );
  const notesByPaper = new Map();
  notesResult.forEach((note) => {
    notesByPaper.set(note.paper_id, [...(notesByPaper.get(note.paper_id) || []), note]);
  });
  const topics = (topicResult.items || []).map(normalizeTopic);
  httpTopicStore = new Map(topics.map((topic) => [topic.id, topic]));
  httpPaperStore = new Map();
  return {
    notes: notesResult.map(normalizeNote),
    papers: (paperResult.items || []).map((paper) => (
      normalizePaper(paper, bookmarks, histories, notesByPaper)
    )),
    readingHistory: historiesResult.map(normalizeHistory),
    statusMeta: httpStatusMeta,
    topics,
  };
}

export const getLearningCenter = createEndpoint({
  mock: () => ({
    notes: noteStore,
    papers: paperStore,
    readingHistory,
    statusMeta,
    topics: topicStore,
  }),
  http: getHttpLearningCenter,
});

async function getHttpPaperNote(paperId) {
  const result = await request('/learning/notes', {
    query: { paper_id: paperId, page: 1, pageSize: 1 },
  });
  return result.items?.[0] || null;
}

export const getPaperNote = createEndpoint({
  mock: (paperId) => noteStore.find((note) => note.paperId === paperId) || null,
  http: getHttpPaperNote,
});

export const savePaperNote = createEndpoint({
  mock: (paperId, rawContent) => {
    const content = rawContent.trim();
    const existing = noteStore.find((note) => note.paperId === paperId);

    if (!content) {
      noteStore = noteStore.filter((note) => note.paperId !== paperId);
      return null;
    }

    if (existing) {
      noteStore = noteStore.map((note) => (
        note.id === existing.id ? { ...note, content, updatedAt: '刚刚' } : note
      ));
      return noteStore.find((note) => note.id === existing.id);
    }

    const note = {
      id: `note-${paperId}`,
      content,
      paperId,
      tags: [],
      title: '论文笔记',
      updatedAt: '刚刚',
    };
    noteStore = [note, ...noteStore];
    return note;
  },
  http: async (paperId, rawContent) => {
    const content = rawContent.trim();
    const existing = await getHttpPaperNote(paperId);

    if (!content) {
      if (existing) {
        await request(`/learning/notes/${existing.id}`, { method: 'DELETE' });
      }
      return null;
    }

    if (existing) {
      return request(`/learning/notes/${existing.id}`, {
        body: { content },
        method: 'PUT',
      });
    }

    return request('/learning/notes', {
      body: {
        anchor: { title: '论文笔记' },
        content,
        is_public: false,
        paper_id: paperId,
      },
      method: 'POST',
    });
  },
});

export const listLearningPapers = createEndpoint({
  mock: () => paperStore,
  http: async (query) => {
    const result = await request('/papers', {
      query: { ...query, page_size: PAPER_PAGE_SIZE },
    });
    return result.items || [];
  },
});

export const updateLearningPaper = createEndpoint({
  mock: (paperId, changes) => {
    paperStore = paperStore.map((paper) => (
      paper.id === paperId ? { ...paper, ...changes } : paper
    ));
    return paperStore.find((paper) => paper.id === paperId);
  },
  http: async (paperId, changes) => {
    const current = httpPaperStore.get(paperId);
    let progressResult = null;
    let nextNoteId = current?.noteId || null;

    if (changes.favorite !== undefined && changes.favorite !== current?.favorite) {
      await request(`/learning/bookmarks${changes.favorite ? '' : `/${paperId}`}`, {
        ...(changes.favorite ? { body: { folder: null, paper_id: paperId } } : {}),
        method: changes.favorite ? 'POST' : 'DELETE',
      });
    }

    if (changes.progress !== undefined || changes.status === 'done') {
      progressResult = await request('/learning/history', {
        body: {
          paper_id: paperId,
          progress: changes.status === 'done' ? 100 : changes.progress,
        },
        method: 'POST',
      });
    }

    if (changes.userNote !== undefined && changes.userNote !== current?.userNote) {
      const content = changes.userNote.trim();
      if (nextNoteId && content) {
        await request(`/learning/notes/${nextNoteId}`, {
          body: { content },
          method: 'PUT',
        });
      } else if (nextNoteId) {
        await request(`/learning/notes/${nextNoteId}`, { method: 'DELETE' });
        nextNoteId = null;
      } else if (content) {
        const note = await request('/learning/notes', {
          body: { content, is_public: false, paper_id: paperId },
          method: 'POST',
        });
        nextNoteId = note.id;
      }
    }

    const progress = progressResult?.progress ?? changes.progress ?? current?.progress ?? 0;
    const updated = {
      ...current,
      ...changes,
      lastReadAt: progressResult?.last_read_at?.slice(0, 16).replace('T', ' ')
        || changes.lastReadAt
        || current?.lastReadAt,
      noteId: nextNoteId,
      progress,
      status: progress >= 100 ? 'done' : progress > 0 ? 'reading' : 'todo',
    };
    httpPaperStore.set(paperId, updated);
    return updated;
  },
});

export const updateFollowedTopic = createEndpoint({
  mock: (topicId, followed) => {
    topicStore = topicStore.map((topic) => (
      topic.id === topicId ? { ...topic, followed } : topic
    ));
    return topicStore.find((topic) => topic.id === topicId);
  },
  http: async (topicId, followed) => {
    const topic = httpTopicStore.get(topicId);
    if (followed) {
      const result = await request('/learning/topics', {
        body: { keywords: topic?.keywords || [], topic: topic?.name || '未命名主题' },
        method: 'POST',
      });
      const updated = normalizeTopic(result);
      httpTopicStore.set(updated.id, updated);
      return updated;
    }
    await request(`/learning/topics/${topicId}`, { method: 'DELETE' });
    const updated = { ...topic, followed: false };
    httpTopicStore.set(topicId, updated);
    return updated;
  },
});

export const exportComparison = createEndpoint({
  mock: (paperIds, comparisonId) => ({
    comparison_id: comparisonId || `mock-comparison-${Date.now()}`,
    paperIds,
    report_content: [
      '# AI 论文对比报告',
      '',
      `已基于所选 ${paperIds.length} 篇论文生成对比分析。`,
      '',
      '> Mock 模式不会请求真实大模型；切换到 HTTP 模式后将展示模型生成的完整报告。',
    ].join('\n'),
  }),
  http: async (paperIds, comparisonId) => {
    let id = comparisonId;
    if (!id) {
      const comparison = await request('/compare', {
        body: { paper_ids: paperIds, title: `论文对比（${paperIds.length} 篇）` },
        method: 'POST',
      });
      id = comparison.id;
    }
    return request(`/compare/export/${id}`);
  },
});
