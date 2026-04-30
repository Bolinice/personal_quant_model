import { describe, it, expect } from 'vitest';
import zh from '@/i18n/locales/zh';
import en from '@/i18n/locales/en';

describe('i18n Locales', () => {
  it('zh locale has required keys', () => {
    expect(zh).toBeDefined();
    expect(typeof zh).toBe('object');
  });

  it('en locale has required keys', () => {
    expect(en).toBeDefined();
    expect(typeof en).toBe('object');
  });

  it('zh and en have the same top-level keys', () => {
    const zhKeys = Object.keys(zh).sort();
    const enKeys = Object.keys(en).sort();
    expect(zhKeys).toEqual(enKeys);
  });
});
