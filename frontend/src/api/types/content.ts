export interface ContentSection {
  title: string;
  subtitle?: string;
  body?: string;
  extra?: Record<string, unknown>;
}

export interface PageContent {
  page: string;
  sections: Record<string, ContentSection>;
}
