import Head from 'next/head';
import Link from 'next/link';
import { useState } from 'react';

export default function Home() {
  const [isConfigured, setIsConfigured] = useState(false);

  // Check if API credentials are configured
  useState(() => {
    const userId = process.env.NEXT_PUBLIC_QUANTCONNECT_USER_ID;
    const apiToken = process.env.NEXT_PUBLIC_QUANTCONNECT_API_TOKEN;
    setIsConfigured(!!(userId && apiToken && userId !== 'your_user_id_here'));
  });

  return (
    <>
      <Head>
        <title>AlgoStrategySandbox - QuantConnect Integration</title>
        <meta name="description" content="Build and manage stock portfolios using QuantConnect APIs" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div style={styles.container}>
        <header style={styles.header}>
          <h1 style={styles.title}>AlgoStrategySandbox</h1>
          <p style={styles.subtitle}>QuantConnect Integration Starter Site</p>
        </header>

        <main style={styles.main}>
          <div style={styles.hero}>
            <h2 style={styles.heroTitle}>Build and Manage Stock Portfolios</h2>
            <p style={styles.heroText}>
              Connect to QuantConnect APIs to create, manage, and analyze both paper trading
              and live portfolios. Perfect for algorithmic trading strategies and backtesting.
            </p>
          </div>

          {!isConfigured && (
            <div style={styles.warningBox}>
              <h3 style={styles.warningTitle}>⚠️ Configuration Required</h3>
              <p style={styles.warningText}>
                Please configure your QuantConnect API credentials to get started.
                Copy <code style={styles.code}>.env.example</code> to <code style={styles.code}>.env</code> and
                add your credentials.
              </p>
            </div>
          )}

          <div style={styles.features}>
            <div style={styles.featureCard}>
              <h3 style={styles.featureTitle}>📊 Portfolio Management</h3>
              <p style={styles.featureText}>
                Create and manage multiple portfolios with real-time tracking of holdings,
                performance, and P&L.
              </p>
            </div>

            <div style={styles.featureCard}>
              <h3 style={styles.featureTitle}>📈 Paper Trading</h3>
              <p style={styles.featureText}>
                Test your strategies with paper trading portfolios before risking real capital.
              </p>
            </div>

            <div style={styles.featureCard}>
              <h3 style={styles.featureTitle}>💰 Live Trading</h3>
              <p style={styles.featureText}>
                Deploy your strategies to live markets and manage real portfolios through QuantConnect.
              </p>
            </div>

            <div style={styles.featureCard}>
              <h3 style={styles.featureTitle}>🔍 Stock Search</h3>
              <p style={styles.featureText}>
                Search and analyze stocks to add to your portfolios with comprehensive data.
              </p>
            </div>
          </div>

          <div style={styles.ctaSection}>
            <Link href="/portfolios" style={styles.ctaButton}>
              Go to Portfolios
            </Link>
          </div>

          <div style={styles.infoSection}>
            <h3 style={styles.infoTitle}>Getting Started</h3>
            <ol style={styles.infoList}>
              <li>Sign up for a <a href="https://www.quantconnect.com/" target="_blank" rel="noopener noreferrer" style={styles.link}>QuantConnect account</a></li>
              <li>Get your API credentials from the QuantConnect dashboard</li>
              <li>Configure your <code style={styles.code}>.env</code> file with your credentials</li>
              <li>Start creating and managing your portfolios!</li>
            </ol>
          </div>
        </main>

        <footer style={styles.footer}>
          <p>Built with Next.js and QuantConnect API</p>
        </footer>
      </div>
    </>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: '#0f172a',
    color: '#e2e8f0',
  },
  header: {
    padding: '2rem',
    borderBottom: '1px solid #334155',
    textAlign: 'center',
  },
  title: {
    fontSize: '2.5rem',
    fontWeight: 'bold',
    margin: 0,
    background: 'linear-gradient(to right, #3b82f6, #8b5cf6)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  },
  subtitle: {
    fontSize: '1.2rem',
    color: '#94a3b8',
    margin: '0.5rem 0 0 0',
  },
  main: {
    flex: 1,
    padding: '2rem',
    maxWidth: '1200px',
    margin: '0 auto',
    width: '100%',
  },
  hero: {
    textAlign: 'center',
    marginBottom: '3rem',
  },
  heroTitle: {
    fontSize: '2rem',
    marginBottom: '1rem',
    color: '#f1f5f9',
  },
  heroText: {
    fontSize: '1.1rem',
    color: '#cbd5e1',
    maxWidth: '800px',
    margin: '0 auto',
    lineHeight: '1.6',
  },
  warningBox: {
    backgroundColor: '#7c2d12',
    border: '1px solid #ea580c',
    borderRadius: '8px',
    padding: '1.5rem',
    marginBottom: '2rem',
  },
  warningTitle: {
    margin: '0 0 0.5rem 0',
    color: '#fed7aa',
  },
  warningText: {
    margin: 0,
    color: '#fef3c7',
    lineHeight: '1.6',
  },
  features: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
    gap: '1.5rem',
    marginBottom: '3rem',
  },
  featureCard: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '1.5rem',
  },
  featureTitle: {
    fontSize: '1.3rem',
    marginTop: 0,
    marginBottom: '1rem',
    color: '#f1f5f9',
  },
  featureText: {
    margin: 0,
    color: '#cbd5e1',
    lineHeight: '1.6',
  },
  ctaSection: {
    textAlign: 'center',
    margin: '3rem 0',
  },
  ctaButton: {
    display: 'inline-block',
    backgroundColor: '#3b82f6',
    color: 'white',
    padding: '1rem 2rem',
    borderRadius: '8px',
    textDecoration: 'none',
    fontSize: '1.1rem',
    fontWeight: 'bold',
    transition: 'background-color 0.3s',
  },
  infoSection: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '2rem',
    marginTop: '2rem',
  },
  infoTitle: {
    marginTop: 0,
    color: '#f1f5f9',
  },
  infoList: {
    lineHeight: '2',
    color: '#cbd5e1',
  },
  code: {
    backgroundColor: '#334155',
    padding: '0.2rem 0.4rem',
    borderRadius: '4px',
    fontFamily: 'monospace',
    fontSize: '0.9em',
  },
  link: {
    color: '#60a5fa',
    textDecoration: 'none',
  },
  footer: {
    padding: '2rem',
    borderTop: '1px solid #334155',
    textAlign: 'center',
    color: '#94a3b8',
  },
};
