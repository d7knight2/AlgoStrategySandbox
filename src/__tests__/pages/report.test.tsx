import { render, screen } from '@testing-library/react';
import ReportPage from '@/pages/report';

describe('Report page', () => {
  it('renders the report title and sections', () => {
    render(<ReportPage />);

    expect(screen.getByText('Lumibot + Alpaca Integration Report')).toBeInTheDocument();
    expect(screen.getByText('Proposed Strategies')).toBeInTheDocument();
    expect(screen.getByText('Integration Roadmap')).toBeInTheDocument();
    expect(screen.getByText('Vercel Deployment Notes')).toBeInTheDocument();
    expect(screen.getByText('Research Sources')).toBeInTheDocument();
  });

  it('renders all three strategy cards', () => {
    render(<ReportPage />);

    expect(screen.getByText('Opening Range Breakout (ORB)')).toBeInTheDocument();
    expect(screen.getByText('SMA Regime Rotation')).toBeInTheDocument();
    expect(screen.getByText('RSI Mean Reversion Basket')).toBeInTheDocument();
  });

  it('contains a navigation link back to home', () => {
    render(<ReportPage />);

    const backLink = screen.getByText('Back to Home');
    expect(backLink.closest('a')).toHaveAttribute('href', '/');
  });
});
