import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  formatConversationDate,
  getDateDaysAgo,
  getLocalDateString,
} from './date';

describe('date utilities', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('formats a local date with zero-padded month and day', () => {
    expect(getLocalDateString(new Date(2026, 0, 5, 23, 30))).toBe('2026-01-05');
  });

  it('uses the current local date when no date is supplied', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 6, 30, 8, 0));

    expect(getLocalDateString()).toBe('2026-07-30');
  });

  it('calculates dates in the past from local noon', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 2, 1, 1, 30));

    expect(getDateDaysAgo(1)).toBe('2026-02-28');
  });

  it.each([
    [null, ''],
    ['', ''],
    ['2026-07-09', '2026-07-09'],
    ['2026-07-09T23:00:00', '2026-07-09'],
    ['not-a-date', 'not-a-date'],
  ])('formats conversation date %j as %j', (value, expected) => {
    expect(formatConversationDate(value)).toBe(expected);
  });
});
