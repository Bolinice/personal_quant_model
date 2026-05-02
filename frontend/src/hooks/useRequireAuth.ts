import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';

/**
 * Hook for features that require authentication
 * Returns a function that checks auth and redirects to login if needed
 */
export function useRequireAuth() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  /**
   * Check if user is authenticated before performing an action
   * @param action - The action to perform if authenticated
   * @returns true if authenticated and action was performed, false otherwise
   */
  const requireAuth = (action?: () => void): boolean => {
    if (!isAuthenticated) {
      // Redirect to login with return path
      navigate('/login', { state: { from: location } });
      return false;
    }

    // User is authenticated, perform the action
    if (action) {
      action();
    }
    return true;
  };

  return { requireAuth, isAuthenticated };
}
