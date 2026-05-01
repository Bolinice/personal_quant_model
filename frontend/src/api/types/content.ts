export interface ContentSection {
  title: string;
  subtitle?: string;
  body?: string;
  extra?: any;
}

export interface PageContent {
  page: string;
  sections: Record<string, ContentSection>;
}
