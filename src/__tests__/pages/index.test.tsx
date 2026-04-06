import { render, screen } from '@testing-library/react';
import Home from '@/pages/index';

describe('Home Page', () => {
  beforeEach(() => {
    // Mock environment variables
    process.env.NEXT_PUBLIC_QUANTCONNECT_USER_ID = undefined;
    process.env.NEXT_PUBLIC_QUANTCONNECT_API_TOKEN = undefined;
  });

  it('should render the page title', () => {
    render(<Home />);
    
    const title = screen.getByText('AlgoStrategySandbox');
    expect(title).toBeInTheDocument();
  });

  it('should render the subtitle', () => {
    render(<Home />);
    
    const subtitle = screen.getByText('QuantConnect Integration Starter Site');
    expect(subtitle).toBeInTheDocument();
  });

  it('should render main heading', () => {
    render(<Home />);
    
    const heading = screen.getByText('Build and Manage Stock Portfolios');
    expect(heading).toBeInTheDocument();
  });

  it('should render the configuration warning when not configured', () => {
    // Set default placeholder values to trigger the warning
    process.env.NEXT_PUBLIC_QUANTCONNECT_USER_ID = 'your_user_id_here';
    process.env.NEXT_PUBLIC_QUANTCONNECT_API_TOKEN = 'test-token';
    
    render(<Home />);
    
    const warningTitle = screen.getByText(/Configuration Required/i);
    expect(warningTitle).toBeInTheDocument();
  });

  it('should not render the configuration warning when properly configured', () => {
    // Set valid credentials
    process.env.NEXT_PUBLIC_QUANTCONNECT_USER_ID = 'real-user-id';
    process.env.NEXT_PUBLIC_QUANTCONNECT_API_TOKEN = 'real-api-token';
    
    render(<Home />);
    
    const warningTitle = screen.queryByText(/Configuration Required/i);
    expect(warningTitle).not.toBeInTheDocument();
  });

  it('should render feature cards', () => {
    render(<Home />);
    
    expect(screen.getByText('📊 Portfolio Management')).toBeInTheDocument();
    expect(screen.getByText('📈 Paper Trading')).toBeInTheDocument();
    expect(screen.getByText('💰 Live Trading')).toBeInTheDocument();
    expect(screen.getByText('🔍 Stock Search')).toBeInTheDocument();
  });

  it('should render the portfolios link', () => {
    render(<Home />);
    
    const link = screen.getByText('Go to Portfolios');
    expect(link).toBeInTheDocument();
    expect(link.closest('a')).toHaveAttribute('href', '/portfolios');
  });


  it('should render the report link', () => {
    render(<Home />);

    const link = screen.getByText('View Lumibot + Alpaca Report');
    expect(link).toBeInTheDocument();
    expect(link.closest('a')).toHaveAttribute('href', '/report');
  });

  it('should render getting started section', () => {
    render(<Home />);
    
    const gettingStarted = screen.getByText('Getting Started');
    expect(gettingStarted).toBeInTheDocument();
  });

  it('should render footer', () => {
    render(<Home />);
    
    const footer = screen.getByText('Built with Next.js and QuantConnect API');
    expect(footer).toBeInTheDocument();
  });
});
