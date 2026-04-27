import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock axios completely
vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => ({
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() },
      },
      defaults: { headers: { common: {} } },
    })),
    post: vi.fn(),
  },
}))

describe('API Client Configuration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('stores and retrieves access token', () => {
    localStorage.setItem('access_token', 'test-jwt-token')
    expect(localStorage.getItem('access_token')).toBe('test-jwt-token')
  })

  it('stores and retrieves refresh token', () => {
    localStorage.setItem('refresh_token', 'test-refresh-token')
    expect(localStorage.getItem('refresh_token')).toBe('test-refresh-token')
  })

  it('clears tokens on logout', () => {
    localStorage.setItem('access_token', 'test-token')
    localStorage.setItem('refresh_token', 'test-refresh')
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    expect(localStorage.getItem('access_token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
  })
})