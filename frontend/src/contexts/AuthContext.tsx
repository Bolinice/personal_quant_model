import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { authApi } from '@/api';
import type { UserResponse } from '@/api';

interface AuthState {
  user: UserResponse | null;
  isAuthenticated: boolean;
  loading: boolean;
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshToken: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    loading: true,
  });

  // Initialize: validate stored token
  // 拦截器会自动处理401 refresh，这里只需调一次 /me
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      setState({ user: null, isAuthenticated: false, loading: false });
      return;
    }

    authApi.me()
      .then((res) => {
        setState({ user: res.data, isAuthenticated: true, loading: false });
      })
      .catch(() => {
        // 拦截器已尝试refresh，仍然失败说明token彻底无效
        clearTokens();
        setState({ user: null, isAuthenticated: false, loading: false });
      });
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await authApi.login({ email, password });
    const data = res.data as any;

    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);

    const userRes = await authApi.me();
    setState({ user: userRes.data, isAuthenticated: true, loading: false });
  }, []);

  const register = useCallback(async (email: string, username: string, password: string) => {
    const res = await authApi.register({ email, username, password });
    const data = res.data as any;

    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);

    const userRes = await authApi.me();
    setState({ user: userRes.data, isAuthenticated: true, loading: false });
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    setState({ user: null, isAuthenticated: false, loading: false });
  }, []);

  const refreshToken = useCallback(async () => {
    const rt = localStorage.getItem('refresh_token');
    if (!rt) {
      logout();
      return;
    }

    try {
      const res = await authApi.refresh(rt);
      const data = res.data as any;
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      const userRes = await authApi.me();
      setState({ user: userRes.data, isAuthenticated: true, loading: false });
    } catch {
      logout();
    }
  }, [logout]);

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout, refreshToken }}>
      {children}
    </AuthContext.Provider>
  );
}
