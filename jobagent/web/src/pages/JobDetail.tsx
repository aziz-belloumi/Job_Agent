import React, { useState } from 'react';
import { JobDetailData } from '../types';
import { api } from '../api';

interface JobDetailProps {
  job: JobDetailData;
  onBack: () => void;
  onRefresh: () => void;
  onError: (msg: string) => void;
}

export const JobDetail: React.FC<JobDetailProps> = ({ job, onBack, onRefresh, onError }) => {
  const [loading, setLoading] = useState(false);
  const [letterDraft, setLetterDraft] = useState(job.application?.cover_letter || '');
  const [saved, setSaved] = useState(false);

  const runAction = async (fn: () => Promise<unknown>, errMsg: string, onSuccess?: () => void) => {
    setLoading(true);
    try {
      await fn();
      if (onSuccess) onSuccess();
      onRefresh();
    } catch (err: unknown) {
      onError(err instanceof Error ? err.message : errMsg);
    } finally {
      setLoading(false);
    }
  };

  const app = job.application;
  const isNoLetter = app?.letter_status === 'skipped' || app?.letter_status === 'no_letter_needed';
  const isGenerated = app?.letter_status === 'generated' || app?.letter_status === 'generated_with_warnings';
  const isFailed = app?.letter_status === 'failed' || app?.letter_status === 'generation_failed';

  return (
    <div>
      <div style={{ marginBottom: '1rem' }}>
        <button className="btn btn-secondary" onClick={onBack}>← Back to Shortlist</button>
      </div>

      <div className="detail-card">
        <div className="detail-header">
          <div>
            <h2 style={{ fontSize: '1.4rem', marginBottom: '0.3rem' }}>{job.title}</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
              <strong>{job.company}</strong> • {job.location} •{' '}
              <a href={job.source_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>
                Posting Link ↗
              </a>
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span className={`verdict-badge ${job.verdict === 'high_priority' ? 'badge-high' : job.verdict === 'worth_reviewing' ? 'badge-worth' : 'badge-unsuitable'}`}>
              {job.verdict.replace('_', ' ')}
            </span>
            <div className="score-badge">{job.score}</div>
          </div>
        </div>

        <div className="two-col-grid">
          <div className="panel-box">
            <h3>Match Reasons</h3>
            {job.reasons.length ? (
              <ul>{job.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
            ) : <p style={{ color: 'var(--text-muted)' }}>None recorded.</p>}
          </div>
          <div className="panel-box">
            <h3>Missing Skills</h3>
            {job.missing.length ? (
              <ul>{job.missing.map((m, i) => <li key={i} style={{ color: '#f87171' }}>{m}</li>)}</ul>
            ) : <p style={{ color: 'var(--success)' }}>No key required skills missing.</p>}
          </div>
        </div>

        <div className="panel-box" style={{ background: 'rgba(0,0,0,0.3)' }}>
          <h3 style={{ marginBottom: '1rem', color: 'var(--accent)' }}>Application Packet</h3>
          {!app ? (
            <div>
              <p style={{ marginBottom: '1rem', color: 'var(--text-muted)' }}>No application prepared yet.</p>
              <button className="btn btn-primary" disabled={loading} onClick={() => runAction(() => api.prepareJob(job.id), 'Failed to prepare application')}>
                {loading && <span className="spinner" />} Prepare Application
              </button>
            </div>
          ) : (
            <div>
              <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '1rem', flexWrap: 'wrap', fontSize: '0.85rem' }}>
                <div><strong>Status:</strong> {app.status === 'approved' ? '✓ Approved' : '• Prepared'}</div>
                <div><strong>Letter Status:</strong> {app.letter_status}</div>
                <div><strong>CV:</strong> {app.cv_path || 'None'}</div>
                <div><strong>Prepared:</strong> {app.prepared_at ? new Date(app.prepared_at).toLocaleString() : '—'}</div>
                {app.approved_at && <div><strong>Approved:</strong> {new Date(app.approved_at).toLocaleString()}</div>}
              </div>

              {isGenerated && (
                <div>
                  <textarea
                    className="textarea-letter"
                    value={letterDraft}
                    onChange={(e) => setLetterDraft(e.target.value)}
                    placeholder="Cover letter..."
                  />
                  <div className="char-counter">
                    {letterDraft.length} chars | {letterDraft.trim().split(/\s+/).filter(Boolean).length} words
                  </div>
                  <div className="action-row">
                    <button className="btn btn-secondary" disabled={loading} onClick={() => runAction(() => api.updateLetter(job.id, letterDraft), 'Failed to save letter', () => { setSaved(true); setTimeout(() => setSaved(false), 2000); })}>
                      {saved ? '✓ Saved' : 'Save Letter'}
                    </button>
                    {app.status !== 'approved' ? (
                      <button className="btn btn-success" disabled={loading} onClick={() => runAction(() => api.approveApplication(job.id), 'Failed to approve application')}>
                        Approve Application
                      </button>
                    ) : (
                      <button className="btn btn-warning" disabled={loading} onClick={() => runAction(() => api.resetApplication(job.id), 'Failed to reset application')}>
                        Reset to Prepared
                      </button>
                    )}
                  </div>
                </div>
              )}

              {isNoLetter && (
                <div>
                  <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>No cover letter required for this job posting.</p>
                  <div className="action-row">
                    {app.status !== 'approved' ? (
                      <button className="btn btn-success" disabled={loading} onClick={() => runAction(() => api.approveApplication(job.id), 'Failed to approve application')}>
                        Approve Application
                      </button>
                    ) : (
                      <button className="btn btn-warning" disabled={loading} onClick={() => runAction(() => api.resetApplication(job.id), 'Failed to reset application')}>
                        Reset to Prepared
                      </button>
                    )}
                  </div>
                </div>
              )}

              {isFailed && (
                <div>
                  <p style={{ color: 'var(--danger)', marginBottom: '0.5rem' }}>Cover letter generation or validation failed.</p>
                  <button className="btn btn-primary" disabled={loading} onClick={() => runAction(() => api.prepareJob(job.id), 'Failed to retry prepare')}>
                    Retry Prepare
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
