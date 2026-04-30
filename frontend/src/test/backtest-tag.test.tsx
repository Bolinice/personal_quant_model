import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import BacktestTag from '@/components/compliance/BacktestTag';

describe('BacktestTag', () => {
  it('renders with default props', () => {
    render(<BacktestTag />);
    expect(screen.getByText('回测')).toBeInTheDocument();
  });

  it('renders with small size', () => {
    const { container } = render(<BacktestTag size="small" />);
    const chip = container.querySelector('.MuiChip-root');
    expect(chip).toBeInTheDocument();
  });

  it('renders with default size', () => {
    const { container } = render(<BacktestTag size="default" />);
    const chip = container.querySelector('.MuiChip-root');
    expect(chip).toBeInTheDocument();
  });

  it('renders without tooltip when showTooltip is false', () => {
    render(<BacktestTag showTooltip={false} />);
    expect(screen.getByText('回测')).toBeInTheDocument();
  });
});
