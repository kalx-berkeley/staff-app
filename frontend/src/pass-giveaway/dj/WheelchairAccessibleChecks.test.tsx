import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import WheelchairAccessibleChecks from './WheelchairAccessibleChecks';

describe('WheelchairAccessibleChecks', () => {
  it('checks Yes for an accessible venue', () => {
    const { container } = render(<WheelchairAccessibleChecks value="yes" />);
    expect(container.textContent).toBe('Yes ☑   No ☐');
  });

  it('checks No for an inaccessible venue', () => {
    const { container } = render(<WheelchairAccessibleChecks value="no" />);
    expect(container.textContent).toBe('Yes ☐   No ☑');
  });

  it('says Unknown instead of showing check boxes', () => {
    const { container } = render(<WheelchairAccessibleChecks value="unknown" />);
    expect(container.textContent).toBe('Unknown');
  });
});
