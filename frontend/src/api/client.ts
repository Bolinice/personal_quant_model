import axios from 'axios';

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：自动附加JWT token
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器：统一错误处理
client.interceptors.response.use(
  (response) => {
    // 如果后端返回 {code, message, data} 格式，自动解包
    const data = response.data;
    if (data && typeof data === 'object' && 'code' in data && 'data' in data) {
      if (data.code === 0) {
        response.data = data.data;
      } else {
        return Promise.reject(new Error(data.message || '请求失败'));
      }
    }
    return response;
  },
  (error) => {
    const status = error.response?.status;
    const message = error.response?.data?.detail || error.response?.data?.message || error.message || '请求失败';

    // 401 未授权：清除token并跳转登录
    if (status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }

    console.error(`API Error [${status}]:`, message);
    return Promise.reject(new Error(message));
  }
);

export default client;
