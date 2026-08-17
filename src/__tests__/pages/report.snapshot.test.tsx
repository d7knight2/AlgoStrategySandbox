import { render } from '@testing-library/react';
import ReportPage from '@/pages/report';

describe('Report page snapshots', () => {
  it('matches the rendered report page snapshot', () => {
    const { container } = render(<ReportPage />);
    expect(container).toMatchSnapshot();
  });
});
