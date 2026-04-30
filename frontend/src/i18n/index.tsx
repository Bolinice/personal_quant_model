import { createContext, useState, useCallback, type ReactNode } from 'react';
import zh, { type TranslationKeys } from './locales/zh';
import en from './locales/en';

export type Lang = 'zh' | 'en';

const STORAGE_KEY = 'lang';

const locales: Record<Lang, TranslationKeys> = { zh, en };

function getInitialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'zh' || saved === 'en') return saved;
  } catch {
    // Ignore localStorage errors
  }
  return 'zh';
}

interface LanguageContextValue {
  lang: Lang;
  t: TranslationKeys;
  setLang: (lang: Lang) => void;
  toggleLang: () => void;
}

export const LanguageContext = createContext<LanguageContextValue>({
  lang: 'zh',
  t: zh,
  setLang: () => {
    // Default no-op
  },
  toggleLang: () => {
    // Default no-op
  },
});

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(getInitialLang);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      // Ignore localStorage errors
    }
  }, []);

  const toggleLang = useCallback(() => {
    setLang(lang === 'zh' ? 'en' : 'zh');
  }, [lang, setLang]);

  return (
    <LanguageContext.Provider value={{ lang, t: locales[lang], setLang, toggleLang }}>
      {children}
    </LanguageContext.Provider>
  );
}

export { useT, useLang } from './hooks';
export type { TranslationKeys } from './locales/zh';
