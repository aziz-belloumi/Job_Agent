import {
  HealthResponse,
  ShortlistResponse,
  JobDetailData,
  PrepareResponse,
  ApplicationRecord,
  ApplicationListItem,
} from './types';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    let errMsg = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      errMsg = data.detail || data.error || errMsg;
    } catch {
      // Ignore json parse error and keep status message
    }
    throw new ApiError(response.status, errMsg);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getHealth: () => request<HealthResponse>('/api/health'),

  getShortlist: (limit = 50, offset = 0, verdict = 'all') =>
    request<ShortlistResponse>(
      `/api/jobs/shortlist?limit=${limit}&offset=${offset}&verdict=${encodeURIComponent(verdict)}`
    ),

  getJob: (jobId: number) => request<JobDetailData>(`/api/jobs/${jobId}`),

  prepareJob: (jobId: number) =>
    request<PrepareResponse>(`/api/jobs/${jobId}/prepare`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  updateLetter: (jobId: number, letter: string) =>
    request<ApplicationRecord>(`/api/applications/${jobId}/letter`, {
      method: 'PATCH',
      body: JSON.stringify({ letter }),
    }),

  approveApplication: (jobId: number) =>
    request<ApplicationRecord>(`/api/applications/${jobId}/approve`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  resetApplication: (jobId: number) =>
    request<ApplicationRecord>(`/api/applications/${jobId}/reset`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  getApplications: () => request<ApplicationListItem[]>('/api/applications'),

  discoverJobs: () =>
    request<{ fetched: number; new: number; duplicates: number }>('/api/admin/discover', {
      method: 'POST',
    }),

  scoreJobs: () =>
    request<{ scored: number; high_priority: number; worth_reviewing: number; unsuitable: number }>(
      '/api/admin/score',
      { method: 'POST' }
    ),
};
