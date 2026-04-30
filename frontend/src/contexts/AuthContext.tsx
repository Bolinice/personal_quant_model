import { createContext, useState, useEffect, useCallback, type ReactNode } from 'react';
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

export const AuthContext = createContext<AuthContextType | null>(null);

function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}

export function AuthProvider({ children }: { children: ReactNode }) {
  // Initialize state based on stored token
  const getInitialState = (): AuthState => {
    const token = localStorage.getItem('access_token');
    return {
      user: null,
      isAuthenticated: false,
      loading: !!token, // Only show loading if we have a token to validate
    };
  };

  const [state, setState] = useState<AuthState>(getInitialState);

  // Validate stored token on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    authApi
      .me()
      .then((res) => {
        setState({ user: res.data, isAuthenticated: true, loading: false });
      })
      .catch(() => {
        clearTokens();
        setState({ user: null, isAuthenticated: false, loading: false });
      });
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await authApi.login({ email, password });
    const data = res.data as { access_token: string; refresh_token: string };

    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);

    const userRes = await authApi.me();
    setState({ user: userRes.data, isAuthenticated: true, loading: false });
  }, []);

  const register = useCallback(async (email: string, username: string, password: string) => {
    const res = await authApi.register({ email, username, password });
    const data = res.data as { access_token: string; refresh_token: string };

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
      const data = res.data as { access_token: string; refresh_token: string };
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

export { useAuth } from './hooks';
