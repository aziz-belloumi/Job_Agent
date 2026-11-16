export type Page = 'shortlist' | 'detail' | 'applications';

export interface ShortlistedJob {
  id: number;
  title: string;
  company: string;
  location: string;
  source: string;
  source_url: string;
  score: number;
  verdict: 'high_priority' | 'worth_reviewing' | 'unsuitable' | string;
  reasons: string[];
  missing: string[];
  fetched_at: string;
  posted_at: string;
  has_application: boolean;
}

export interface ApplicationRecord {
  id?: number;
  job_id: number;
  cv_path: string | null;
  cover_letter: string | null;
  letter_status: 'no_letter_needed' | 'skipped' | 'generated' | 'failed' | string;
  violations_json?: string;
  status: 'prepared' | 'approved' | string;
  prepared_at: string;
  approved_at: string | null;
  submitted_at: string | null;
  notes: string | null;
}

export interface JobDetailData {
  id: number;
  source: string;
  source_url: string;
  title: string;
  company: string;
  location: string;
  employment_type: string;
  description: string;
  posted_at: string;
  fetched_at: string;
  score: number;
  verdict: string;
  reasons: string[];
  missing: string[];
  eligibility_flags: string[];
  parsed: Record<string, unknown>;
  application: ApplicationRecord | null;
}

export interface ApplicationListItem {
  id: number;
  title: string;
  company: string;
  location: string;
  source_url: string;
  status: string;
  letter_status: string;
  prepared_at: string;
  approved_at: string | null;
  score: number;
  verdict: string;
}

export interface HealthResponse {
  status: string;
  ollama: boolean;
  db: boolean;
}

export interface PrepareResponse {
  letter_status: 'generated' | 'skipped' | 'failed';
  letter: string | null;
  warnings: string[];
  errors: string[];
}

export interface ShortlistResponse {
  jobs: ShortlistedJob[];
  total: number;
}
