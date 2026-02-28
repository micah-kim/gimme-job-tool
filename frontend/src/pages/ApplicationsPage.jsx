import { useEffect, useState } from 'react';
import { getApplications } from '../api/client';

export default function ApplicationsPage() {
  const [apps, setApps] = useState([]);

  useEffect(() => { getApplications().then(setApps).catch(e => console.error('Failed to load applications:', e)); }, []);

  return (
    <div>
      <h2 className="mb-2">Application Log</h2>
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
                <td className="text-sm">{a.screenshot_path ? '📸' : '—'}</td>
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
