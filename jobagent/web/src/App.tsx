import React, { useState, useEffect, useCallback } from 'react';
import { Page, ShortlistedJob, JobDetailData, ApplicationListItem, HealthResponse } from './types';
import { api } from './api';
import { Shortlist } from './pages/Shortlist';
import { JobDetail } from './pages/JobDetail';
import { Applications } from './pages/Applications';

export const App: React.FC = () => {
  const [page, setPage] = useState<Page>('shortlist');
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [shortlistJobs, setShortlistJobs] = useState<ShortlistedJob[]>([]);
  const [jobDetail, setJobDetail] = useState<JobDetailData | null>(null);
  const [applications, setApplications] = useState<ApplicationListItem[]>([]);

  const [verdictFilter, setVerdictFilter] = useState<string>('all');
  const [loadingList, setLoadingList] = useState<boolean>(false);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [loadingApps, setLoadingApps] = useState<boolean>(false);
  const [refreshingPipeline, setRefreshingPipeline] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadHealth = useCallback(async () => {
    try {
      const res = await api.getHealth();
      setHealth(res);
    } catch {
      setHealth({ status: 'error', ollama: false, db: false });
    }
  }, []);

  const loadShortlist = useCallback(async (filter = verdictFilter) => {
    setLoadingList(true);
    try {
      const res = await api.getShortlist(50, 0, filter);
      setShortlistJobs(res.jobs);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to fetch shortlist');
    } finally {
      setLoadingList(false);
    }
  }, [verdictFilter]);

  const loadJobDetail = useCallback(async (id: number) => {
    setLoadingDetail(true);
    try {
      const res = await api.getJob(id);
      setJobDetail(res);
      setSelectedJobId(id);
      setPage('detail');
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to fetch job details');
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  const loadApplications = useCallback(async () => {
    setLoadingApps(true);
    try {
      const res = await api.getApplications();
      setApplications(res);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to fetch applications');
    } finally {
      setLoadingApps(false);
    }
  }, []);

  useEffect(() => {
    loadHealth();
    loadShortlist('all');
    const interval = setInterval(loadHealth, 30000);
    return () => clearInterval(interval);
  }, [loadHealth, loadShortlist]);

  const handleFullRefresh = async () => {
    setRefreshingPipeline(true);
    setErrorMsg(null);
    try {
      await api.discoverJobs();
      await api.scoreJobs();
      await loadShortlist();
      await loadHealth();
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to refresh discover/score pipeline');
    } finally {
      setRefreshingPipeline(false);
    }
  };

  const handleFilterChange = (verdict: string) => {
    setVerdictFilter(verdict);
    loadShortlist(verdict);
  };

  return (
    <div className="app-container">
      <header className="topbar">
        <div className="brand">
          <h1>JobAgent</h1>
          <nav className="nav-links">
            <button
              className={`nav-btn ${page === 'shortlist' ? 'active' : ''}`}
              onClick={() => { setPage('shortlist'); loadShortlist(); }}
            >
              Shortlist
            </button>
            <button
              className={`nav-btn ${page === 'applications' ? 'active' : ''}`}
              onClick={() => { setPage('applications'); loadApplications(); }}
            >
              Applications
            </button>
          </nav>
        </div>

        <div className="topbar-actions">
          <div className="health-pill" title={health ? `DB: ${health.db ? 'OK' : 'ERR'} | Ollama: ${health.ollama ? 'OK' : 'OFFLINE'}` : 'Checking...'}>
            <span className={`health-dot ${health?.ollama ? 'dot-green' : 'dot-red'}`} />
            <span>Ollama {health?.ollama ? 'Ready' : 'Offline'}</span>
          </div>

          <button
            className="btn btn-secondary"
            onClick={() => loadShortlist()}
            disabled={loadingList}
          >
            Refresh list
          </button>

          <button
            className="btn btn-primary"
            onClick={handleFullRefresh}
            disabled={refreshingPipeline}
          >
            {refreshingPipeline ? <span className="spinner" /> : null}
            Refresh (discover + score)
          </button>
        </div>
      </header>

      {errorMsg && (
        <div className="error-banner">
          <span>{errorMsg}</span>
          <button className="close-btn" onClick={() => setErrorMsg(null)}>✕</button>
        </div>
      )}

      <main className="main-content">
        {page === 'shortlist' && (
          <Shortlist
            jobs={shortlistJobs}
            loading={loadingList}
            verdictFilter={verdictFilter}
            onFilterChange={handleFilterChange}
            onSelectJob={loadJobDetail}
          />
        )}

        {page === 'detail' && jobDetail && (
          loadingDetail ? (
            <div style={{ textAlign: 'center', padding: '3rem' }}>
              <span className="spinner" /> Loading job details...
            </div>
          ) : (
            <JobDetail
              job={jobDetail}
              onBack={() => setPage('shortlist')}
              onRefresh={() => selectedJobId && loadJobDetail(selectedJobId)}
              onError={(msg) => setErrorMsg(msg)}
            />
          )
        )}

        {page === 'applications' && (
          <Applications
            applications={applications}
            loading={loadingApps}
            onSelectJob={loadJobDetail}
          />
        )}
      </main>
    </div>
  );
};

export default App;
