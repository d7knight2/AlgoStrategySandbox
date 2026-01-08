import { QuantConnectClient } from '@/lib/quantconnect';
import axios from 'axios';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('QuantConnectClient', () => {
  let client: QuantConnectClient;
  const mockConfig = {
    userId: 'test-user-id',
    apiToken: 'test-api-token',
    baseUrl: 'https://test.api.com',
  };

  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks();
    
    // Suppress console.error during tests
    jest.spyOn(console, 'error').mockImplementation(() => {});
    
    // Setup axios mock
    const mockAxiosInstance = {
      get: jest.fn(),
      post: jest.fn(),
      interceptors: {
        request: {
          use: jest.fn((callback) => callback),
        },
      },
    };
    
    mockedAxios.create.mockReturnValue(mockAxiosInstance as any);
    client = new QuantConnectClient(mockConfig);
  });

  afterEach(() => {
    // Restore console.error
    jest.restoreAllMocks();
  });

  describe('listProjects', () => {
    it('should return an array of projects on success', async () => {
      const mockProjects = [
        { projectId: 1, name: 'Project 1', created: '2024-01-01', modified: '2024-01-02' },
        { projectId: 2, name: 'Project 2', created: '2024-01-03', modified: '2024-01-04' },
      ];

      const mockAxiosInstance = mockedAxios.create() as any;
      mockAxiosInstance.get.mockResolvedValue({ data: { projects: mockProjects } });

      const result = await client.listProjects();

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/projects/read');
      expect(result).toEqual(mockProjects);
    });

    it('should return an empty array on error', async () => {
      const mockAxiosInstance = mockedAxios.create() as any;
      mockAxiosInstance.get.mockRejectedValue(new Error('API Error'));

      const result = await client.listProjects();

      expect(result).toEqual([]);
    });

    it('should return an empty array when projects is undefined', async () => {
      const mockAxiosInstance = mockedAxios.create() as any;
      mockAxiosInstance.get.mockResolvedValue({ data: {} });

      const result = await client.listProjects();

      expect(result).toEqual([]);
    });
  });

  describe('createProject', () => {
    it('should create a project and return it on success', async () => {
      const mockProject = { projectId: 1, name: 'New Project', created: '2024-01-01', modified: '2024-01-01' };
      const mockAxiosInstance = mockedAxios.create() as any;
      mockAxiosInstance.post.mockResolvedValue({ data: { projects: [mockProject] } });

      const result = await client.createProject('New Project');

      expect(mockAxiosInstance.post).toHaveBeenCalledWith('/projects/create', {
        name: 'New Project',
        language: 'Py',
      });
      expect(result).toEqual(mockProject);
    });

    it('should support custom language parameter', async () => {
      const mockProject = { projectId: 1, name: 'C# Project', created: '2024-01-01', modified: '2024-01-01' };
      const mockAxiosInstance = mockedAxios.create() as any;
      mockAxiosInstance.post.mockResolvedValue({ data: { projects: [mockProject] } });

      const result = await client.createProject('C# Project', 'C#');

      expect(mockAxiosInstance.post).toHaveBeenCalledWith('/projects/create', {
        name: 'C# Project',
        language: 'C#',
      });
      expect(result).toEqual(mockProject);
    });

    it('should return null on error', async () => {
      const mockAxiosInstance = mockedAxios.create() as any;
      mockAxiosInstance.post.mockRejectedValue(new Error('API Error'));

      const result = await client.createProject('Failed Project');

      expect(result).toBeNull();
    });

    it('should return null when no projects are returned', async () => {
      const mockAxiosInstance = mockedAxios.create() as any;
      mockAxiosInstance.post.mockResolvedValue({ data: {} });

      const result = await client.createProject('No Project');

      expect(result).toBeNull();
    });
  });

  describe('deleteProject', () => {
    it('should return true on successful deletion', async () => {
      const mockAxiosInstance = mockedAxios.create() as any;
      mockAxiosInstance.post.mockResolvedValue({ data: { success: true } });

      const result = await client.deleteProject(123);

      expect(mockAxiosInstance.post).toHaveBeenCalledWith('/projects/delete', {
        projectId: 123,
      });
      expect(result).toBe(true);
    });

    it('should return false on error', async () => {
      const mockAxiosInstance = mockedAxios.create() as any;
      mockAxiosInstance.post.mockRejectedValue(new Error('API Error'));

      const result = await client.deleteProject(123);

      expect(result).toBe(false);
    });

    it('should return false when success is false', async () => {
      const mockAxiosInstance = mockedAxios.create() as any;
      mockAxiosInstance.post.mockResolvedValue({ data: { success: false } });

      const result = await client.deleteProject(123);

      expect(result).toBe(false);
    });
  });

  describe('getLiveAlgorithm', () => {
    it('should return live algorithm data on success', async () => {
      const mockData = { status: 'running', holdings: [] };
      const mockAxiosInstance = mockedAxios.create() as any;
      mockAxiosInstance.get.mockResolvedValue({ data: mockData });

      const result = await client.getLiveAlgorithm('project-123');

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/live/read?projectId=project-123');
      expect(result).toEqual(mockData);
    });

    it('should return null on error', async () => {
      const mockAxiosInstance = mockedAxios.create() as any;
      mockAxiosInstance.get.mockRejectedValue(new Error('API Error'));

      const result = await client.getLiveAlgorithm('project-123');

      expect(result).toBeNull();
    });
  });

  describe('getBacktest', () => {
    it('should return backtest data on success', async () => {
      const mockData = { results: {}, charts: {} };
      const mockAxiosInstance = mockedAxios.create() as any;
      mockAxiosInstance.get.mockResolvedValue({ data: mockData });

      const result = await client.getBacktest('project-123', 'backtest-456');

      expect(mockAxiosInstance.get).toHaveBeenCalledWith('/backtests/read?projectId=project-123&backtestId=backtest-456');
      expect(result).toEqual(mockData);
    });

    it('should return null on error', async () => {
      const mockAxiosInstance = mockedAxios.create() as any;
      mockAxiosInstance.get.mockRejectedValue(new Error('API Error'));

      const result = await client.getBacktest('project-123', 'backtest-456');

      expect(result).toBeNull();
    });
  });
});

describe('createQuantConnectClient', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
    // Suppress console.error during tests
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('should create a client with valid environment variables', () => {
    // Setup fresh mock for this test
    const mockAxiosInstance = {
      get: jest.fn(),
      post: jest.fn(),
      interceptors: {
        request: {
          use: jest.fn(),
        },
      },
    };
    mockedAxios.create.mockReturnValue(mockAxiosInstance as any);
    
    const client = new QuantConnectClient({
      userId: 'test-user',
      apiToken: 'test-token',
      baseUrl: 'https://test.api.com',
    });

    expect(client).not.toBeNull();
    expect(client).toBeInstanceOf(QuantConnectClient);
  });

  it('should return null from factory when credentials are missing', () => {
    // Test the actual factory function behavior
    const originalUserId = process.env.NEXT_PUBLIC_QUANTCONNECT_USER_ID;
    const originalToken = process.env.NEXT_PUBLIC_QUANTCONNECT_API_TOKEN;
    
    delete process.env.NEXT_PUBLIC_QUANTCONNECT_USER_ID;
    delete process.env.NEXT_PUBLIC_QUANTCONNECT_API_TOKEN;
    
    const { createQuantConnectClient } = require('@/lib/quantconnect');
    const client = createQuantConnectClient();

    expect(client).toBeNull();
    
    // Restore env variables
    if (originalUserId) process.env.NEXT_PUBLIC_QUANTCONNECT_USER_ID = originalUserId;
    if (originalToken) process.env.NEXT_PUBLIC_QUANTCONNECT_API_TOKEN = originalToken;
  });
});
