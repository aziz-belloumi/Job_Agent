import React, { useState, useMemo } from 'react';
import { ShortlistedJob } from '../types';

interface ShortlistProps {
  jobs: ShortlistedJob[];
  loading: boolean;
  verdictFilter: string;
  onFilterChange: (verdict: string) => void;
  onSelectJob: (jobId: number) => void;
}

type SortField = 'score' | 'title' | 'company';

export const Shortlist: React.FC<ShortlistProps> = ({
  jobs,
  loading,
  verdictFilter,
  onFilterChange,
  onSelectJob,
}) => {
  const [sortField, setSortField] = useState<SortField>('score');
  const [sortAsc, setSortAsc] = useState<boolean>(false);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(field !== 'score');
    }
  };

  const sortedJobs = useMemo(() => {
    return [...jobs].sort((a, b) => {
      let comparison = 0;
      if (sortField === 'score') {
        comparison = a.score - b.score;
      } else if (sortField === 'title') {
        comparison = a.title.localeCompare(b.title);
      } else if (sortField === 'company') {
        comparison = a.company.localeCompare(b.company);
      }
      return sortAsc ? comparison : -comparison;
    });
  }, [jobs, sortField, sortAsc]);

  const renderStatus = (job: ShortlistedJob) => {
    if (!job.has_application) return '—';
    return '•'; // Details page has exact prepared/approved state
  };

  return (
    <div>
      <div className="page-header">
        <h2>Shortlisted Jobs ({jobs.length})</h2>
        <div className="filter-pills">
          <button
            className={`pill ${verdictFilter === 'all' ? 'active' : ''}`}
            onClick={() => onFilterChange('all')}
          >
            All
          </button>
          <button
            className={`pill ${verdictFilter === 'high_priority' ? 'active' : ''}`}
            onClick={() => onFilterChange('high_priority')}
          >
            High Priority
          </button>
          <button
            className={`pill ${verdictFilter === 'worth_reviewing' ? 'active' : ''}`}
            onClick={() => onFilterChange('worth_reviewing')}
          >
            Worth Reviewing
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          <span className="spinner" /> Loading shortlist...
        </div>
      ) : sortedJobs.length === 0 ? (
        <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          No jobs found for this filter.
        </div>
      ) : (
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th onClick={() => handleSort('score')}>
                  Score {sortField === 'score' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th onClick={() => handleSort('title')}>
                  Title {sortField === 'title' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th onClick={() => handleSort('company')}>
                  Company {sortField === 'company' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th className="col-collapse">Location</th>
                <th>Verdict</th>
                <th className="col-collapse">Reasons</th>
                <th title="Application status">Status</th>
              </tr>
            </thead>
            <tbody>
              {sortedJobs.map((job) => {
                const firstReason = job.reasons.length > 0 ? job.reasons[0] : '—';
                const truncatedReason =
                  firstReason.length > 40 ? `${firstReason.substring(0, 40)}...` : firstReason;
                return (
                  <tr
                    key={job.id}
                    className="clickable"
                    onClick={() => onSelectJob(job.id)}
                  >
                    <td style={{ fontWeight: 700, color: 'var(--accent)' }}>{job.score}</td>
                    <td style={{ fontWeight: 600 }}>{job.title}</td>
                    <td>{job.company}</td>
                    <td className="col-collapse" style={{ color: 'var(--text-muted)' }}>
                      {job.location}
                    </td>
                    <td>
                      <span
                        className={`verdict-badge ${
                          job.verdict === 'high_priority'
                            ? 'badge-high'
                            : job.verdict === 'worth_reviewing'
                            ? 'badge-worth'
                            : 'badge-unsuitable'
                        }`}
                      >
                        {job.verdict.replace('_', ' ')}
                      </span>
                    </td>
                    <td
                      className="col-collapse"
                      title={job.reasons.join('\n')}
                      style={{ color: 'var(--text-muted)' }}
                    >
                      {truncatedReason}
                    </td>
                    <td style={{ textAlign: 'center', fontWeight: 700 }}>
                      {renderStatus(job)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
