import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { getJobs, triggerFetch, updateJobStatus } from '../api/client';

export default function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const location = useLocation();

  const load = async () => {
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      const data = await getJobs(params);
      setJobs(data);
    } catch (e) {
      console.error('Failed to load jobs:', e);
    }
  };

  useEffect(() => { load(); }, [statusFilter, location.key]);

  const [message, setMessage] = useState('');

  const handleFetch = async () => {
    setLoading(true);
    setMessage('');
    try {
      const res = await triggerFetch();
      setMessage(`✅ Fetched ${res.jobs_fetched} new jobs`);
      await load();
    } catch (e) {
      setMessage(`❌ Fetch failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSkip = async (jobId) => {
    try {
      await updateJobStatus(jobId, 'skipped');
      setJobs(prev => prev.map(j => j.id === jobId ? { ...j, status: 'skipped' } : j));
    } catch (e) {
      setMessage(`❌ Failed to skip: ${e.message}`);
    }
  };

  const handleRestore = async (jobId) => {
    try {
      await updateJobStatus(jobId, 'new');
      setJobs(prev => prev.map(j => j.id === jobId ? { ...j, status: 'new' } : j));
    } catch (e) {
      setMessage(`❌ Failed to restore: ${e.message}`);
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-2">
        <h2>Job Listings</h2>
        <div className="flex gap-1">
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ width: 'auto' }}>
            <option value="">All Statuses</option>
            <option value="new">New</option>
            <option value="matched">Matched</option>
            <option value="rejected">Rejected</option>
            <option value="applied">Applied</option>
            <option value="failed">Failed</option>
            <option value="skipped">Skipped</option>
          </select>
          <button onClick={handleFetch} disabled={loading}>
            {loading ? 'Fetching...' : 'Fetch Jobs'}
          </button>
        </div>
      </div>
      {message && <div className="card mb-2 text-sm" style={{ padding: '0.75rem' }}>{message}</div>}
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Title</th>
              <th>Location</th>
              <th>Department</th>
              <th>Status</th>
              <th>Fetched</th>
              <th style={{ width: 60 }}></th>
            </tr>
          </thead>
          <tbody>
            {jobs.map(job => (
              <tr key={job.id} style={job.status === 'skipped' ? { opacity: 0.5 } : {}}>
                <td>
                  <a href={job.url} target="_blank" rel="noopener noreferrer">{job.title}</a>
                </td>
                <td>{job.location}</td>
                <td>{job.department}</td>
                <td><span className={`badge badge-${job.status}`}>{job.status}</span></td>
                <td className="text-sm text-muted">{new Date(job.fetched_at).toLocaleDateString()}</td>
                <td>
                  {(job.status === 'new' || job.status === 'matched') && (
                    <button
                      onClick={() => handleSkip(job.id)}
                      title="Skip this job"
                      style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem', padding: '0.2rem 0.4rem' }}
                    >✕</button>
                  )}
                  {job.status === 'skipped' && (
                    <button
                      onClick={() => handleRestore(job.id)}
                      title="Restore this job"
                      style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.85rem', padding: '0.2rem 0.4rem' }}
                    >↩</button>
                  )}
                </td>
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr><td colSpan={6} className="text-muted" style={{ textAlign: 'center', padding: '2rem' }}>No jobs found. Add companies and fetch jobs to get started.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
