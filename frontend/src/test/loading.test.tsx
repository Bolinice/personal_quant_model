import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import Loading from '@/components/ui/Loading';

describe('Loading Component', () => {
  it('renders without crashing', () => {
    const { container } = render(<Loading />);
    expect(container.firstChild).toBeInTheDocument();
  });

  it('contains a Box container', () => {
    const { container } = render(<Loading />);
    // MUI Box renders a div
    expect(container.querySelector('div')).toBeInTheDocument();
  });
});
