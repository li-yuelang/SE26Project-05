/**
 * paperService Mock 单元测试
 *
 * 测试目标 —— 验证 paperService 所有 mock 分支的 CRUD 行为
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

let paperService;
beforeEach(async () => {
  vi.resetModules();
  window.localStorage.clear();
  vi.stubEnv('VITE_API_MODE', 'mock');
  paperService = await import('../services/paperService.js');
});

describe('paperService - listPapers', () => {
  it('应该返回论文列表（items + total）', async () => {
    const result = await paperService.listPapers();
    expect(result).toHaveProperty('items');
    expect(result).toHaveProperty('total');
    expect(Array.isArray(result.items)).toBe(true);
    expect(result.total).toBe(result.items.length);
  });

  it('返回的论文应包含 toListPaper 转换字段', async () => {
    const { items } = await paperService.listPapers();
    const paper = items[0];
    expect(paper).toHaveProperty('abstract');
    expect(paper).toHaveProperty('isFavorite');
    expect(paper).toHaveProperty('isRead');
    expect(paper).toHaveProperty('link');
    expect(paper).toHaveProperty('publishedDate');
  });
});

describe('paperService - getPaperDetail', () => {
  it('存在的论文应返回详情', async () => {
    const paper = await paperService.getPaperDetail('2406.01234');
    expect(paper.id).toBe('2406.01234');
    expect(paper).toHaveProperty('structuredContent');
    expect(paper.structuredContent).toHaveProperty('concept');
    expect(paper.structuredContent).toHaveProperty('methods');
    expect(paper).toHaveProperty('relatedConcepts');
    expect(paper).toHaveProperty('relatedPapers');
  });

  it('不存在的论文应抛出 PAPER_NOT_FOUND', async () => {
    await expect(paperService.getPaperDetail('non-existent')).rejects.toThrow('论文不存在');
    try {
      await paperService.getPaperDetail('non-existent');
    } catch (e) {
      expect(e.code).toBe('PAPER_NOT_FOUND');
      expect(e.status).toBe(404);
    }
  });
});

describe('paperService - addPaperToLibrary', () => {
  it('应返回 { added: false, paperId }', async () => {
    const result = await paperService.addPaperToLibrary('2406.01234');
    expect(result).toEqual({ added: false, paperId: '2406.01234' });
  });
});

describe('paperService - 收藏（bookmark）', () => {
  it('默认未收藏', async () => {
    const status = await paperService.getPaperBookmarkStatus('2406.09123');
    expect(status).toBe(false);
  });

  it('收藏后状态为 true', async () => {
    await paperService.setPaperBookmark('2406.09123', true);
    const status = await paperService.getPaperBookmarkStatus('2406.09123');
    expect(status).toBe(true);
  });

  it('取消收藏后状态为 false', async () => {
    await paperService.setPaperBookmark('2406.09123', true);
    await paperService.setPaperBookmark('2406.09123', false);
    const status = await paperService.getPaperBookmarkStatus('2406.09123');
    expect(status).toBe(false);
  });

  it('批量收藏 setPaperBookmarks', async () => {
    const result = await paperService.setPaperBookmarks(['2406.09123', '2405.08777'], true);
    expect(result.processedCount).toBe(2);
    expect(result.bookmarked).toBe(true);
    const s1 = await paperService.getPaperBookmarkStatus('2406.09123');
    expect(s1).toBe(true);
  });
});

describe('paperService - updatePaper', () => {
  it('应更新论文属性', async () => {
    const updated = await paperService.updatePaper('2406.01234', { title: '新标题' });
    expect(updated.title).toBe('新标题');
  });
});

describe('paperService - deletePaper / deletePapers', () => {
  it('deletePaper 应删除并返回 null', async () => {
    const { total: before } = await paperService.listPapers();
    const result = await paperService.deletePaper('2406.01234');
    expect(result).toBeNull();
    const { total: after } = await paperService.listPapers();
    expect(after).toBe(before - 1);
  });

  it('删除不存在的论文应抛错', async () => {
    await expect(paperService.deletePaper('nonexist')).rejects.toThrow('论文不存在');
  });

  it('deletePapers 批量删除', async () => {
    const result = await paperService.deletePapers(['2406.05678', '2405.11890']);
    expect(result.deletedCount).toBe(2);
    expect(result.deletedIds).toContain('2406.05678');
  });
});

describe('paperService - getPaperChunk', () => {
  it('应返回段落内容', async () => {
    const chunk = await paperService.getPaperChunk('2406.01234', 0);
    expect(chunk.paperId).toBe('2406.01234');
    expect(chunk.chunkIndex).toBe(0);
    expect(chunk).toHaveProperty('content');
  });
});

describe('paperService - triggerAnalysis / getAnalysisStatus', () => {
  it('getAnalysisStatus 应返回 completed', async () => {
    const result = await paperService.getAnalysisStatus('2406.01234');
    expect(result.status).toBe('completed');
  });
});
