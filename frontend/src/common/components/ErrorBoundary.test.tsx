import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ErrorBoundary from './ErrorBoundary';

const Broken = (): never => {
  throw new Error('an API field went missing');
};

describe('ErrorBoundary', () => {
  it('shows its children when nothing is wrong', () => {
    render(<ErrorBoundary><p>The page</p></ErrorBoundary>);

    expect(screen.getByText('The page')).toBeInTheDocument();
  });

  it('offers a reload instead of leaving a blank page', () => {
    render(<ErrorBoundary><Broken /></ErrorBoundary>);

    expect(screen.getByText(/Something went wrong/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  });
});
