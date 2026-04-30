import { useContext } from 'react';
import { LanguageContext } from './index';
import type { TranslationKeys } from './locales/zh';

export function useT(): TranslationKeys {
  return useContext(LanguageContext).t;
}

export function useLang() {
  return useContext(LanguageContext);
}
