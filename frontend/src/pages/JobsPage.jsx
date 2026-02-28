import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { getJobs, triggerFetch } from '../api/client';

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
            </tr>
          </thead>
          <tbody>
            {jobs.map(job => (
              <tr key={job.id}>
                <td>
                  <a href={job.url} target="_blank" rel="noopener noreferrer">{job.title}</a>
                </td>
                <td>{job.location}</td>
                <td>{job.department}</td>
                <td><span className={`badge badge-${job.status}`}>{job.status}</span></td>
                <td className="text-sm text-muted">{new Date(job.fetched_at).toLocaleDateString()}</td>
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr><td colSpan={5} className="text-muted" style={{ textAlign: 'center', padding: '2rem' }}>No jobs found. Add companies and fetch jobs to get started.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
