import client from '../client';

export const contentApi = {
  getPages: (lang: string = 'zh') => client.get('/content/pages', { params: { lang } }),

  getPage: (page: string, lang: string = 'zh') => client.get(`/content/pages/${page}`, { params: { lang } }),

  getSection: (page: string, section: string, lang: string = 'zh') =>
    client.get(`/content/pages/${page}/sections/${section}`, { params: { lang } }),
};
