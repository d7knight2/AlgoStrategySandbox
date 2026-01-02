import Head from 'next/head';
import Link from 'next/link';
import { useState, useEffect } from 'react';
import { createQuantConnectClient, Project } from '../lib/quantconnect';

export default function Portfolios() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newProjectName, setNewProjectName] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    setLoading(true);
    setError(null);
    
    const client = createQuantConnectClient();
    if (!client) {
      setError('QuantConnect API credentials not configured. Please check your .env file.');
      setLoading(false);
      return;
    }

    try {
      const projectList = await client.listProjects();
      setProjects(projectList);
    } catch (err) {
      setError('Failed to load projects. Please check your API credentials.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!newProjectName.trim()) {
      return;
    }

    setCreating(true);
    const client = createQuantConnectClient();
    
    if (!client) {
      setError('QuantConnect API credentials not configured.');
      setCreating(false);
      return;
    }

    try {
      const newProject = await client.createProject(newProjectName);
      if (newProject) {
        setNewProjectName('');
        await loadProjects();
      } else {
        setError('Failed to create project. Please try again.');
      }
    } catch (err) {
      setError('Failed to create project. Please try again.');
      console.error(err);
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteProject = async (projectId: number, projectName: string) => {
    if (!confirm(`Are you sure you want to delete "${projectName}"?`)) {
      return;
    }

    const client = createQuantConnectClient();
    if (!client) {
      setError('QuantConnect API credentials not configured.');
      return;
    }

    try {
      const success = await client.deleteProject(projectId);
      if (success) {
        await loadProjects();
      } else {
        setError('Failed to delete project. Please try again.');
      }
    } catch (err) {
      setError('Failed to delete project. Please try again.');
      console.error(err);
    }
  };

  return (
    <>
      <Head>
        <title>Portfolios - AlgoStrategySandbox</title>
        <meta name="description" content="Manage your QuantConnect portfolios" />
      </Head>

      <div style={styles.container}>
        <header style={styles.header}>
          <div style={styles.headerContent}>
            <Link href="/" style={styles.homeLink}>← Home</Link>
            <h1 style={styles.title}>Portfolio Management</h1>
          </div>
        </header>

        <main style={styles.main}>
          {error && (
            <div style={styles.errorBox}>
              <p style={styles.errorText}>{error}</p>
            </div>
          )}

          <section style={styles.section}>
            <h2 style={styles.sectionTitle}>Create New Portfolio</h2>
            <form onSubmit={handleCreateProject} style={styles.form}>
              <input
                type="text"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                placeholder="Enter portfolio name..."
                style={styles.input}
                disabled={creating}
              />
              <button
                type="submit"
                style={styles.createButton}
                disabled={creating || !newProjectName.trim()}
              >
                {creating ? 'Creating...' : 'Create Portfolio'}
              </button>
            </form>
          </section>

          <section style={styles.section}>
            <h2 style={styles.sectionTitle}>Your Portfolios</h2>
            
            {loading ? (
              <div style={styles.loadingBox}>
                <p>Loading portfolios...</p>
              </div>
            ) : projects.length === 0 ? (
              <div style={styles.emptyBox}>
                <p>No portfolios yet. Create your first one above!</p>
              </div>
            ) : (
              <div style={styles.projectGrid}>
                {projects.map((project) => (
                  <div key={project.projectId} style={styles.projectCard}>
                    <div style={styles.projectHeader}>
                      <h3 style={styles.projectName}>{project.name}</h3>
                      <span style={styles.projectId}>ID: {project.projectId}</span>
                    </div>
                    <div style={styles.projectDetails}>
                      <p style={styles.projectDetail}>
                        <strong>Created:</strong> {new Date(project.created).toLocaleDateString()}
                      </p>
                      <p style={styles.projectDetail}>
                        <strong>Modified:</strong> {new Date(project.modified).toLocaleDateString()}
                      </p>
                    </div>
                    <div style={styles.projectActions}>
                      <button
                        style={styles.viewButton}
                        onClick={() => alert('View functionality coming soon! This will show detailed portfolio information.')}
                      >
                        View Details
                      </button>
                      <button
                        style={styles.deleteButton}
                        onClick={() => handleDeleteProject(project.projectId, project.name)}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section style={styles.infoSection}>
            <h3 style={styles.infoTitle}>About Portfolios</h3>
            <p style={styles.infoText}>
              Portfolios in AlgoStrategySandbox are powered by QuantConnect projects. Each portfolio can contain:
            </p>
            <ul style={styles.infoList}>
              <li>Algorithmic trading strategies written in Python or C#</li>
              <li>Backtesting results with historical data</li>
              <li>Paper trading simulations for testing strategies</li>
              <li>Live trading connections to real brokerages</li>
            </ul>
            <p style={styles.infoText}>
              Visit the <a href="https://www.quantconnect.com/docs" target="_blank" rel="noopener noreferrer" style={styles.link}>QuantConnect documentation</a> to learn more about creating trading algorithms.
            </p>
          </section>
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
    padding: '1.5rem 2rem',
    borderBottom: '1px solid #334155',
  },
  headerContent: {
    maxWidth: '1200px',
    margin: '0 auto',
    display: 'flex',
    alignItems: 'center',
    gap: '2rem',
  },
  homeLink: {
    color: '#60a5fa',
    textDecoration: 'none',
    fontSize: '1rem',
  },
  title: {
    fontSize: '2rem',
    fontWeight: 'bold',
    margin: 0,
    color: '#f1f5f9',
  },
  main: {
    flex: 1,
    padding: '2rem',
    maxWidth: '1200px',
    margin: '0 auto',
    width: '100%',
  },
  errorBox: {
    backgroundColor: '#7c2d12',
    border: '1px solid #ea580c',
    borderRadius: '8px',
    padding: '1rem',
    marginBottom: '2rem',
  },
  errorText: {
    margin: 0,
    color: '#fef3c7',
  },
  section: {
    marginBottom: '3rem',
  },
  sectionTitle: {
    fontSize: '1.5rem',
    marginBottom: '1.5rem',
    color: '#f1f5f9',
  },
  form: {
    display: 'flex',
    gap: '1rem',
    flexWrap: 'wrap',
  },
  input: {
    flex: 1,
    minWidth: '300px',
    padding: '0.75rem 1rem',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    color: '#e2e8f0',
    fontSize: '1rem',
  },
  createButton: {
    padding: '0.75rem 1.5rem',
    backgroundColor: '#3b82f6',
    color: 'white',
    border: 'none',
    borderRadius: '8px',
    fontSize: '1rem',
    fontWeight: 'bold',
    cursor: 'pointer',
    transition: 'background-color 0.3s',
  },
  loadingBox: {
    textAlign: 'center',
    padding: '3rem',
    color: '#94a3b8',
  },
  emptyBox: {
    textAlign: 'center',
    padding: '3rem',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    color: '#94a3b8',
  },
  projectGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
    gap: '1.5rem',
  },
  projectCard: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '1.5rem',
  },
  projectHeader: {
    marginBottom: '1rem',
  },
  projectName: {
    margin: '0 0 0.5rem 0',
    fontSize: '1.3rem',
    color: '#f1f5f9',
  },
  projectId: {
    fontSize: '0.9rem',
    color: '#94a3b8',
  },
  projectDetails: {
    marginBottom: '1.5rem',
  },
  projectDetail: {
    margin: '0.5rem 0',
    fontSize: '0.9rem',
    color: '#cbd5e1',
  },
  projectActions: {
    display: 'flex',
    gap: '0.5rem',
  },
  viewButton: {
    flex: 1,
    padding: '0.5rem 1rem',
    backgroundColor: '#334155',
    color: '#e2e8f0',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '0.9rem',
  },
  deleteButton: {
    padding: '0.5rem 1rem',
    backgroundColor: '#dc2626',
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '0.9rem',
  },
  infoSection: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '2rem',
  },
  infoTitle: {
    marginTop: 0,
    color: '#f1f5f9',
  },
  infoText: {
    lineHeight: '1.6',
    color: '#cbd5e1',
  },
  infoList: {
    lineHeight: '2',
    color: '#cbd5e1',
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
