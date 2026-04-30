import client from '../client';
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserResponse,
  PasswordChangeRequest,
  ForgotPasswordRequest,
  ResetPasswordRequest,
} from '../types';

export const authApi = {
  login: (data: LoginRequest) => client.post<TokenResponse>('/auth/login', data),

  register: (data: RegisterRequest) =>
    client.post<TokenResponse & { user: UserResponse }>('/auth/register', data),

  me: () => client.get<UserResponse>('/auth/me'),

  refresh: (refreshToken: string) =>
    client.post<TokenResponse>('/auth/refresh', { refresh_token: refreshToken }),

  changePassword: (data: PasswordChangeRequest) =>
    client.post<{ message: string }>('/auth/change-password', data),

  forgotPassword: (data: ForgotPasswordRequest) =>
    client.post<{ message: string }>('/auth/forgot-password', data),

  resetPassword: (data: ResetPasswordRequest) =>
    client.post<{ message: string }>('/auth/reset-password', data),
};
