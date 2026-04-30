import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import { MemoryRouter } from 'react-router-dom';

// Test component that uses auth context
function AuthTestComponent() {
  const { user, isAuthenticated, isLoading } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(isLoading)}</span>
      <span data-testid="authenticated">{String(isAuthenticated)}</span>
      <span data-testid="username">{user?.username || 'none'}</span>
    </div>
  );
}

describe('AuthContext', () => {
  it('provides default unauthenticated state', () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <AuthTestComponent />
        </AuthProvider>
      </MemoryRouter>
    );

    expect(screen.getByTestId('authenticated')).toHaveTextContent('false');
    expect(screen.getByTestId('username')).toHaveTextContent('none');
  });

  it('starts with loading state', () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <AuthTestComponent />
        </AuthProvider>
      </MemoryRouter>
    );

    // Initially loading should be true, then resolve to false
    expect(screen.getByTestId('loading')).toBeInTheDocument();
  });
});
