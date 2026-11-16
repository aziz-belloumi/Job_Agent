import React, { useState, useMemo } from 'react';
import { ApplicationListItem } from '../types';

interface ApplicationsProps {
  applications: ApplicationListItem[];
  loading: boolean;
  onSelectJob: (jobId: number) => void;
}

type SortField = 'approved_at' | 'score';

export const Applications: React.FC<ApplicationsProps> = ({
  applications,
  loading,
  onSelectJob,
}) => {
  const [sortField, setSortField] = useState<SortField>('approved_at');
  const [sortAsc, setSortAsc] = useState<boolean>(false);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  const sortedList = useMemo(() => {
    return [...applications].sort((a, b) => {
      let comparison = 0;
      if (sortField === 'score') {
        comparison = a.score - b.score;
      } else if (sortField === 'approved_at') {
        const timeA = a.approved_at ? new Date(a.approved_at).getTime() : 0;
        const timeB = b.approved_at ? new Date(b.approved_at).getTime() : 0;
        comparison = timeA - timeB;
      }
      return sortAsc ? comparison : -comparison;
    });
  }, [applications, sortField, sortAsc]);

  return (
    <div>
      <div className="page-header">
        <h2>Applications ({applications.length})</h2>
      </div>

      {loading ? (
        <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          <span className="spinner" /> Loading applications...
        </div>
      ) : sortedList.length === 0 ? (
        <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          No applications prepared yet. Navigate to Shortlist to prepare one.
        </div>
      ) : (
        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Job</th>
                <th>Company</th>
                <th>Status</th>
                <th className="col-collapse">Letter</th>
                <th onClick={() => handleSort('score')}>
                  Score {sortField === 'score' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
                <th className="col-collapse">Prepared</th>
                <th onClick={() => handleSort('approved_at')}>
                  Approved {sortField === 'approved_at' ? (sortAsc ? '▲' : '▼') : ''}
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedList.map((app) => (
                <tr
                  key={app.id}
                  className="clickable"
                  onClick={() => onSelectJob(app.id)}
                >
                  <td style={{ fontWeight: 600 }}>{app.title}</td>
                  <td>{app.company}</td>
                  <td>
                    <span
                      style={{
                        padding: '0.2rem 0.5rem',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        background:
                          app.status === 'approved'
                            ? 'rgba(16, 185, 129, 0.2)'
                            : 'rgba(245, 158, 11, 0.2)',
                        color:
                          app.status === 'approved' ? 'var(--success)' : 'var(--warning)',
                      }}
                    >
                      {app.status === 'approved' ? 'Approved' : 'Prepared'}
                    </span>
                  </td>
                  <td className="col-collapse" style={{ color: 'var(--text-muted)' }}>
                    {app.letter_status}
                  </td>
                  <td style={{ fontWeight: 700, color: 'var(--accent)' }}>{app.score}</td>
                  <td className="col-collapse" style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    {app.prepared_at ? new Date(app.prepared_at).toLocaleDateString() : '—'}
                  </td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    {app.approved_at ? (
                      <span style={{ color: 'var(--success)', fontWeight: 600 }}>
                        ✓ {new Date(app.approved_at).toLocaleDateString()}
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
