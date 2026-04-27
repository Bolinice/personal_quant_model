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

// 响应拦截器：统一解包 + 401自动刷新（仅一次，防死循环）
// 并发401场景：多个请求同时收到401时，isRefreshing保证只发起一次token刷新，
// 其余请求await同一个refreshPromise，避免刷新接口被并发调用导致token失效
let isRefreshing = false;
let refreshPromise: Promise<string | null> | null = null;

client.interceptors.response.use(
  (response) => {
    // 后端统一响应格式 {code, message, data}，code=0表示成功，直接解包取出data
    // 非零code视为业务错误，抛出message
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
  async (error) => {
    const originalRequest = error.config;
    const status = error.response?.status;

    // 401 且未重试过 → 尝试刷新token
    if (status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      // 登录/注册/刷新本身的401不需要重试
      const url = originalRequest.url || '';
      if (url.includes('/auth/login') || url.includes('/auth/register') || url.includes('/auth/refresh')) {
        return Promise.reject(new Error(error.response?.data?.detail || '认证失败'));
      }

      // 并发请求只刷新一次
      if (!isRefreshing) {
        isRefreshing = true;
        refreshPromise = (async () => {
          const rt = localStorage.getItem('refresh_token');
          if (!rt) return null;
          try {
            const res = await axios.post(
              `${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/auth/refresh`,
              { refresh_token: rt }
            );
            const respData = res.data?.data || res.data;
            localStorage.setItem('access_token', respData.access_token);
            localStorage.setItem('refresh_token', respData.refresh_token);
            return respData.access_token as string;
          } catch {
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            return null;
          } finally {
            isRefreshing = false;
          }
        })();
      }

      const newToken = await refreshPromise;
      if (newToken) {
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return client(originalRequest);
      }
    }

    const message = error.response?.data?.detail || error.response?.data?.message || error.message || '请求失败';
    console.error(`API Error [${status}]:`, message);
    return Promise.reject(new Error(message));
  }
);

export default client;
