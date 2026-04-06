import Head from 'next/head';
import Link from 'next/link';
import {
  deploymentNotes,
  integrationSteps,
  researchSources,
  strategyCards,
} from '@/lib/research/lumibotAlpacaReport';

export default function ReportPage() {
  return (
    <>
      <Head>
        <title>Lumibot + Alpaca Research Report</title>
        <meta
          name="description"
          content="Implementation report for Lumibot + Alpaca strategy workflow, paper trading validation, and Vercel deployment architecture."
        />
      </Head>

      <main style={styles.container}>
        <header style={styles.header}>
          <h1 style={styles.title}>Lumibot + Alpaca Integration Report</h1>
          <p style={styles.subtitle}>
            Research-backed implementation plan for strategy development, paper trading, and production architecture.
          </p>
          <Link href="/" style={styles.backLink}>Back to Home</Link>
        </header>

        <section style={styles.section}>
          <h2>Proposed Strategies</h2>
          <div style={styles.grid}>
            {strategyCards.map((card) => (
              <article key={card.id} style={styles.card}>
                <h3>{card.name}</h3>
                <p><strong>Market:</strong> {card.market}</p>
                <p><strong>Timeframe:</strong> {card.timeframe}</p>
                <p>{card.summary}</p>
                <p><strong>Lumibot Sketch:</strong> {card.lumibotSketch}</p>
                <ul>
                  {card.riskRules.map((rule) => (
                    <li key={rule}>{rule}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <section style={styles.section}>
          <h2>Integration Roadmap</h2>
          <ol>
            {integrationSteps.map((step) => (
              <li key={step.title} style={styles.listItem}>
                <strong>{step.title}</strong>
                <p>{step.details}</p>
              </li>
            ))}
          </ol>
        </section>

        <section style={styles.section}>
          <h2>Vercel Deployment Notes</h2>
          {deploymentNotes.map((note) => (
            <article key={note.title} style={styles.noteCard}>
              <h3>{note.title}</h3>
              <p>{note.details}</p>
            </article>
          ))}
        </section>

        <section style={styles.section}>
          <h2>Research Sources</h2>
          <ul>
            {researchSources.map((source) => (
              <li key={source}>
                <a href={source.split(' ')[0]} target="_blank" rel="noreferrer noopener" style={styles.link}>
                  {source}
                </a>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    maxWidth: '1100px',
    margin: '0 auto',
    padding: '2rem',
    color: '#e2e8f0',
  },
  header: {
    marginBottom: '2rem',
  },
  title: {
    marginBottom: '0.5rem',
  },
  subtitle: {
    color: '#94a3b8',
  },
  section: {
    marginBottom: '2.5rem',
  },
  grid: {
    display: 'grid',
    gap: '1rem',
    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
  },
  card: {
    background: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '1rem',
  },
  noteCard: {
    background: '#1e293b',
    borderLeft: '3px solid #3b82f6',
    borderRadius: '6px',
    padding: '0.8rem 1rem',
    marginBottom: '0.8rem',
  },
  listItem: {
    marginBottom: '1rem',
  },
  backLink: {
    display: 'inline-block',
    marginTop: '0.8rem',
    color: '#93c5fd',
    textDecoration: 'none',
  },
  link: {
    color: '#93c5fd',
  },
};
