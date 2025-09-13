import {
  UploadResponse,
  BooksResponse,
  MergeResponse,
  ResultResponse,
  MergeGroup,
} from '../types';
import { apiBasePath } from '../config/deployment';

// Use the flexible deployment configuration for API base URL
// This automatically handles all deployment scenarios:
// - Root domain: /api
// - Subfolder: /ko-merge/api (or any custom subfolder)
// - Development: /api
// - Custom domains and ports
const API_BASE = apiBasePath;

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      errorData.detail || `HTTP ${response.status}: ${response.statusText}`
    );
  }
  return response.json();
}

export const api = {
  async uploadFile(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/upload`, {
      method: 'POST',
      body: formData,
    });

    return handleResponse<UploadResponse>(response);
  },

  async getBooks(sessionId: string): Promise<BooksResponse> {
    const response = await fetch(`${API_BASE}/books/${sessionId}`);
    return handleResponse<BooksResponse>(response);
  },

  async addMergeGroup(sessionId: string, mergeGroup: MergeGroup): Promise<{ message: string }> {
    const response = await fetch(`${API_BASE}/merge-groups/${sessionId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(mergeGroup),
    });

    return handleResponse<{ message: string }>(response);
  },

  async removeLastMergeGroup(sessionId: string): Promise<{ message: string }> {
    const response = await fetch(`${API_BASE}/merge-groups/${sessionId}`, {
      method: 'DELETE',
    });

    return handleResponse<{ message: string }>(response);
  },

  async clearMergeGroups(sessionId: string): Promise<{ message: string }> {
    const response = await fetch(`${API_BASE}/merge-groups/${sessionId}/all`, {
      method: 'DELETE',
    });

    return handleResponse<{ message: string }>(response);
  },

  async executeMerge(sessionId: string): Promise<MergeResponse> {
    const response = await fetch(`${API_BASE}/execute-merge/${sessionId}`, {
      method: 'POST',
    });

    return handleResponse<MergeResponse>(response);
  },

  async getResult(sessionId: string): Promise<ResultResponse> {
    const response = await fetch(`${API_BASE}/result/${sessionId}`);
    return handleResponse<ResultResponse>(response);
  },

  getDownloadUrl(sessionId: string): string {
    return `${API_BASE}/download/${sessionId}`;
  },

  async getDownloadCount(): Promise<{ download_count: number }> {
    const response = await fetch(`${API_BASE}/download-count`);
    return handleResponse<{ download_count: number }>(response);
  },

  async cleanupSession(sessionId: string): Promise<{ message: string }> {
    const response = await fetch(`${API_BASE}/cleanup/${sessionId}`, {
      method: 'DELETE',
    });

    return handleResponse<{ message: string }>(response);
  },
};

export { ApiError };
