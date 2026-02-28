import { useState } from 'react';
import { runPipeline, triggerFetch, applyAll, retryFailed } from '../api/client';

export default function PipelinePage() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState('');

  const run = async (label, fn) => {
    setLoading(label);
    setResult(null);
    try {
      const res = await fn();
      setResult(res);
    } catch (e) {
      setResult({ error: e.message });
    } finally {
      setLoading('');
    }
  };

  return (
    <div>
      <h2 className="mb-2">Pipeline Controls</h2>

      <div className="card mb-2">
        <h3 className="mb-1">🚀 Full Pipeline</h3>
        <p className="text-muted text-sm mb-1">
          Runs the entire workflow in order: fetches new job listings from all your tracked companies,
          filters them by your title/location preferences, then automatically fills out and submits
          applications using your uploaded resume and profile info.
        </p>
        <div className="flex gap-1" style={{ marginTop: '0.75rem' }}>
          <button onClick={() => run('pipeline-dry', () => runPipeline({ dry_run: true }))} disabled={!!loading}>
            {loading === 'pipeline-dry' ? 'Running...' : '🧪 Dry Run'}
          </button>
          <button className="danger" onClick={() => run('pipeline-live', () => runPipeline({ dry_run: false }))} disabled={!!loading}>
            {loading === 'pipeline-live' ? 'Running...' : '🚀 Run Live'}
          </button>
        </div>
        <div style={{ marginTop: '0.75rem', padding: '0.75rem', background: '#0d1117', borderRadius: 6 }}>
          <p className="text-sm" style={{ color: '#e1e4e8' }}><strong>🧪 Dry Run</strong> — Fetches jobs and opens application pages, fills in forms, but does <strong>not</strong> click Submit. Use this to verify everything looks correct before going live. A screenshot is taken of each filled form.</p>
          <p className="text-sm" style={{ color: '#e1e4e8', marginTop: '0.5rem' }}><strong>🚀 Run Live</strong> — Does everything a Dry Run does, but actually <strong>submits the applications</strong>. Only use when you're confident your profile and resume are ready.</p>
        </div>
      </div>

      <div className="card mb-2">
        <h3 className="mb-1">⚡ Individual Steps</h3>
        <p className="text-muted text-sm mb-1">Run each step separately if you want more control.</p>
        <div style={{ display: 'grid', gap: '0.75rem', marginTop: '0.75rem' }}>
          <div className="flex gap-1 items-center">
            <button className="secondary" onClick={() => run('fetch', triggerFetch)} disabled={!!loading} style={{ minWidth: 160 }}>
              {loading === 'fetch' ? 'Fetching...' : '1. Fetch Jobs'}
            </button>
            <span className="text-sm text-muted">Pulls new listings from all tracked companies, filtered by your title and location preferences.</span>
          </div>
          <div className="flex gap-1 items-center">
            <button className="secondary" onClick={() => run('apply', applyAll)} disabled={!!loading} style={{ minWidth: 160 }}>
              {loading === 'apply' ? 'Applying...' : '2. Apply to All'}
            </button>
            <span className="text-sm text-muted">Submits applications to all eligible jobs (skips ones already applied to or previously failed).</span>
          </div>
          <div className="flex gap-1 items-center">
            <button className="secondary" onClick={() => run('retry', retryFailed)} disabled={!!loading} style={{ minWidth: 160 }}>
              {loading === 'retry' ? 'Resetting...' : '↩ Retry Failed'}
            </button>
            <span className="text-sm text-muted">Resets all failed jobs back to "New" so the pipeline can try applying to them again.</span>
          </div>
        </div>
      </div>

      <div className="card mb-2" style={{ background: '#1c1e26', borderColor: '#30363d' }}>
        <h3 className="mb-1" style={{ color: '#8b949e' }}>ℹ️ How it works</h3>
        <ul className="text-sm text-muted" style={{ paddingLeft: '1.2rem', lineHeight: 1.8 }}>
          <li>Jobs are fetched from Greenhouse, AshbyHQ, and Lever APIs based on your tracked companies.</li>
          <li>Only jobs matching your <strong>Target Job Titles</strong> and <strong>Locations</strong> are kept. Jobs containing your <strong>Exclude Titles</strong> words are filtered out.</li>
          <li>Your uploaded <strong>PDF resume</strong> is attached to each application.</li>
          <li>Profile info (name, email, phone, etc.) and application answers (education, work auth, demographics) are auto-filled.</li>
          <li>Jobs with status <strong>Applied</strong> or <strong>Failed</strong> are automatically skipped — no duplicate applications.</li>
        </ul>
      </div>

      {result && (
        <div className="card">
          <h3 className="mb-1">📊 Result</h3>
          {result.error ? (
            <p style={{ color: '#f85149' }}>{result.error}</p>
          ) : (
            <div className="text-sm" style={{ lineHeight: 2 }}>
              {result.dry_run && (
                <p style={{ color: '#d29922', fontWeight: 600, marginBottom: '0.5rem' }}>
                  🧪 DRY RUN — No applications were actually submitted.
                </p>
              )}
              <p>📥 Jobs fetched: <strong>{result.jobs_fetched ?? '—'}</strong></p>
              <p>{result.dry_run ? '📝 Forms previewed' : '✅ Applications submitted'}: <strong>{result.forms_filled ?? '—'}</strong></p>
              <p>❌ Failed: <strong>{result.applications_failed ?? '—'}</strong></p>
              <p>⏭️ Skipped (already applied/failed): <strong>{result.applications_skipped ?? '—'}</strong></p>
              {result.errors?.length > 0 && (
                <div style={{ marginTop: '0.5rem', color: '#f85149' }}>
                  <strong>Errors:</strong>
                  <ul style={{ paddingLeft: '1.2rem' }}>
                    {result.errors.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
