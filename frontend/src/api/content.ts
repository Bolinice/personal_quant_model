import { defaultContent } from './defaultContent';
import { defaultContentEn } from './defaultContentEn';
import type { Lang } from '@/i18n';

type ContentMap = Record<
  string,
  Record<string, { title: string; subtitle?: string; body?: string; extra?: unknown }>
>;

const contentByLang: Record<Lang, ContentMap> = {
  zh: defaultContent,
  en: defaultContentEn,
};

export function getContent(lang: Lang): ContentMap {
  return contentByLang[lang];
}

export { defaultContent, defaultContentEn };
