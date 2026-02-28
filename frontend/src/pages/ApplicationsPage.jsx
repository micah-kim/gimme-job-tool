import { useEffect, useState } from 'react';
import { getApplications } from '../api/client';

function screenshotUrl(path) {
  if (!path) return null;
  const filename = path.split(/[/\\]/).pop();
  return `/screenshots/${filename}`;
}

export default function ApplicationsPage() {
  const [apps, setApps] = useState([]);
  const [preview, setPreview] = useState(null);
  const [filter, setFilter] = useState('all');

  useEffect(() => { getApplications().then(setApps).catch(e => console.error('Failed to load applications:', e)); }, []);

  const filtered = filter === 'all' ? apps : apps.filter(a => a.status === filter);

  return (
    <div>
      <h2 className="mb-2">Application Log</h2>

      <div className="flex gap-1 mb-2">
        {['all', 'failed', 'submitted', 'pending'].map(f => (
          <button key={f} className={filter === f ? '' : 'secondary'} style={{ padding: '0.3rem 0.8rem', fontSize: '0.85rem' }}
            onClick={() => setFilter(f)}>
            {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
            {f !== 'all' && ` (${apps.filter(a => a.status === f).length})`}
          </button>
        ))}
      </div>

      {preview && (
        <div className="card mb-2" style={{ position: 'relative' }}>
          <button className="secondary" onClick={() => setPreview(null)} style={{ position: 'absolute', top: 8, right: 8 }}>✕ Close</button>
          <h3 className="mb-1">Screenshot Preview</h3>
          <img src={preview} alt="Application screenshot" style={{ maxWidth: '100%', borderRadius: 6, border: '1px solid #30363d' }} />
        </div>
      )}

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Job</th>
              <th>Company</th>
              <th>Status</th>
              <th>Applied At</th>
              <th>Error / Details</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(a => (
              <tr key={a.id}>
                <td className="text-sm">
                  {a.job_url
                    ? <a href={a.job_url} target="_blank" rel="noopener noreferrer" style={{ color: '#58a6ff' }}>{a.job_title || `Job #${a.job_id}`}</a>
                    : (a.job_title || `Job #${a.job_id}`)}
                </td>
                <td className="text-sm">{a.company_name || '—'}</td>
                <td><span className={`badge badge-${a.status}`}>{a.status}</span></td>
                <td className="text-sm">{a.applied_at ? new Date(a.applied_at).toLocaleString() : '—'}</td>
                <td className="text-sm text-muted" style={{ maxWidth: 300, wordBreak: 'break-word' }}>{a.error_message || '—'}</td>
                <td className="text-sm">
                  <div className="flex gap-1">
                    {a.screenshot_path && (
                      <button className="secondary" style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem' }}
                        onClick={() => setPreview(screenshotUrl(a.screenshot_path))}>📸</button>
                    )}
                    {a.status === 'failed' && a.job_url && (
                      <a href={a.job_url} target="_blank" rel="noopener noreferrer"
                        className="secondary" style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem', textDecoration: 'none', display: 'inline-block', borderRadius: 4, border: '1px solid #30363d', color: '#c9d1d9' }}>
                        🔗 Apply Manually
                      </a>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={6} className="text-muted" style={{ textAlign: 'center', padding: '2rem' }}>No applications {filter !== 'all' ? `with status "${filter}"` : 'yet'}.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
