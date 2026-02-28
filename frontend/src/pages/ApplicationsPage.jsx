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

  useEffect(() => { getApplications().then(setApps).catch(e => console.error('Failed to load applications:', e)); }, []);

  return (
    <div>
      <h2 className="mb-2">Application Log</h2>

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
              <th>Job ID</th>
              <th>Status</th>
              <th>Applied At</th>
              <th>Error</th>
              <th>Screenshot</th>
            </tr>
          </thead>
          <tbody>
            {apps.map(a => (
              <tr key={a.id}>
                <td>{a.job_id}</td>
                <td><span className={`badge badge-${a.status}`}>{a.status}</span></td>
                <td className="text-sm">{a.applied_at ? new Date(a.applied_at).toLocaleString() : '—'}</td>
                <td className="text-sm text-muted">{a.error_message || '—'}</td>
                <td className="text-sm">
                  {a.screenshot_path
                    ? <button className="secondary" style={{ padding: '0.2rem 0.5rem', fontSize: '0.8rem' }} onClick={() => setPreview(screenshotUrl(a.screenshot_path))}>📸 View</button>
                    : '—'}
                </td>
              </tr>
            ))}
            {apps.length === 0 && (
              <tr><td colSpan={5} className="text-muted" style={{ textAlign: 'center', padding: '2rem' }}>No applications yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
