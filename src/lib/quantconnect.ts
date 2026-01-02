import axios, { AxiosInstance } from 'axios';

export interface QuantConnectConfig {
  userId: string;
  apiToken: string;
  baseUrl: string;
}

export interface Portfolio {
  id: string;
  name: string;
  type: 'paper' | 'live';
  cash: number;
  holdings: Holding[];
  totalValue: number;
  createdAt: string;
}

export interface Holding {
  symbol: string;
  quantity: number;
  averagePrice: number;
  currentPrice: number;
  totalValue: number;
  profitLoss: number;
  profitLossPercent: number;
}

export interface Project {
  projectId: number;
  name: string;
  created: string;
  modified: string;
}

export class QuantConnectClient {
  private client: AxiosInstance;
  private userId: string;
  private apiToken: string;

  constructor(config: QuantConnectConfig) {
    this.userId = config.userId;
    this.apiToken = config.apiToken;
    
    this.client = axios.create({
      baseURL: config.baseUrl,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add auth to all requests
    this.client.interceptors.request.use((config) => {
      config.auth = {
        username: this.userId,
        password: this.apiToken,
      };
      return config;
    });
  }

  /**
   * List all projects in the user's account
   */
  async listProjects(): Promise<Project[]> {
    try {
      const response = await this.client.get('/projects/read');
      return response.data.projects || [];
    } catch (error) {
      console.error('Error listing projects:', error);
      return [];
    }
  }

  /**
   * Create a new project (portfolio)
   */
  async createProject(name: string, language: string = 'Py'): Promise<Project | null> {
    try {
      const response = await this.client.post('/projects/create', {
        name,
        language,
      });
      return response.data.projects?.[0] || null;
    } catch (error) {
      console.error('Error creating project:', error);
      return null;
    }
  }

  /**
   * Delete a project
   */
  async deleteProject(projectId: number): Promise<boolean> {
    try {
      const response = await this.client.post('/projects/delete', {
        projectId,
      });
      return response.data.success || false;
    } catch (error) {
      console.error('Error deleting project:', error);
      return false;
    }
  }

  /**
   * Get live algorithm status and holdings
   * This is a mock implementation as the actual API requires specific endpoints
   */
  async getLiveAlgorithm(projectId: string): Promise<any> {
    try {
      const response = await this.client.get(`/live/read?projectId=${projectId}`);
      return response.data;
    } catch (error) {
      console.error('Error getting live algorithm:', error);
      return null;
    }
  }

  /**
   * Get backtest results
   */
  async getBacktest(projectId: string, backtestId: string): Promise<any> {
    try {
      const response = await this.client.get(`/backtests/read?projectId=${projectId}&backtestId=${backtestId}`);
      return response.data;
    } catch (error) {
      console.error('Error getting backtest:', error);
      return null;
    }
  }
}

// Factory function to create client from environment variables
export function createQuantConnectClient(): QuantConnectClient | null {
  const userId = process.env.NEXT_PUBLIC_QUANTCONNECT_USER_ID;
  const apiToken = process.env.NEXT_PUBLIC_QUANTCONNECT_API_TOKEN;
  const baseUrl = process.env.QUANTCONNECT_API_BASE_URL || 'https://www.quantconnect.com/api/v2';

  if (!userId || !apiToken) {
    console.error('QuantConnect credentials not found in environment variables');
    return null;
  }

  return new QuantConnectClient({
    userId,
    apiToken,
    baseUrl,
  });
}
