import { useState, useEffect } from 'react';
import { runPipeline, triggerFetch, applyAll, retryFailed, getScanStatus, scanJobs } from '../api/client';
import { useNavigate } from 'react-router-dom';

export default function PipelinePage() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState('');
  const [scanStatus, setScanStatus] = useState(null);
  const navigate = useNavigate();

  useEffect(() => { loadStatus(); }, []);

  async function loadStatus() {
    try {
      setScanStatus(await getScanStatus());
    } catch (e) { /* ignore */ }
  }

  const run = async (label, fn) => {
    setLoading(label);
    setResult(null);
    try {
      const res = await fn();
      setResult(res);
      loadStatus();
    } catch (e) {
      setResult({ error: e.message });
    } finally {
      setLoading('');
    }
  };

  return (
    <div>
      <h2 className="mb-2">Pipeline Controls</h2>

      {/* Scan status banner */}
      {scanStatus && (
        <div className="card mb-1" style={{
          display: 'flex', gap: '1.5rem', alignItems: 'center', flexWrap: 'wrap',
          borderLeft: `4px solid ${scanStatus.ready_to_apply ? '#27ae60' : scanStatus.unanswered_questions > 0 ? '#e74c3c' : '#888'}`,
        }}>
          <div className="text-sm">
            <strong>{scanStatus.eligible_jobs}</strong> eligible jobs
          </div>
          <div className="text-sm">
            <strong>{scanStatus.scanned_jobs}</strong> scanned
          </div>
          <div className="text-sm">
            <strong>{scanStatus.total_questions}</strong> questions
          </div>
          <div className="text-sm" style={{ fontWeight: 'bold', color: scanStatus.unanswered_questions > 0 ? '#e74c3c' : '#27ae60' }}>
            {scanStatus.unanswered_questions > 0
              ? `⚠️ ${scanStatus.unanswered_questions} unanswered`
              : '✅ Ready to apply'
            }
          </div>
          {scanStatus.unanswered_questions > 0 && (
            <button className="secondary" style={{ marginLeft: 'auto', fontSize: '0.85rem' }} onClick={() => navigate('/questions')}>
              Review Questions →
            </button>
          )}
        </div>
      )}

      <div className="card mb-2">
        <h3 className="mb-1">🚀 Full Pipeline</h3>
        <p className="text-muted text-sm mb-1">
          Runs the complete workflow: <strong>Fetch</strong> new listings → <strong>Scan</strong> forms for questions →
          <strong> Apply</strong> (only if all questions are answered). If new questions are found, the pipeline pauses and directs you to the Questions page.
        </p>
        <div className="flex gap-1" style={{ marginTop: '0.75rem' }}>
          <button onClick={() => run('pipeline-dry', () => runPipeline({ dry_run: true }))} disabled={!!loading}>
            {loading === 'pipeline-dry' ? 'Running...' : '🧪 Dry Run'}
          </button>
          <button className="danger" onClick={() => run('pipeline-live', () => runPipeline({ dry_run: false }))} disabled={!!loading}>
            {loading === 'pipeline-live' ? 'Running...' : '🚀 Run Live'}
          </button>
        </div>
      </div>

      <div className="card mb-2">
        <h3 className="mb-1">⚡ Individual Steps</h3>
        <p className="text-muted text-sm mb-1">Run each step separately for more control.</p>
        <div style={{ display: 'grid', gap: '0.75rem', marginTop: '0.75rem' }}>
          <div className="flex gap-1 items-center">
            <button className="secondary" onClick={() => run('fetch', triggerFetch)} disabled={!!loading} style={{ minWidth: 160 }}>
              {loading === 'fetch' ? 'Fetching...' : '1. Fetch Jobs'}
            </button>
            <span className="text-sm text-muted">Pull new listings from tracked companies.</span>
          </div>
          <div className="flex gap-1 items-center">
            <button className="secondary" onClick={() => run('scan', () => scanJobs())} disabled={!!loading} style={{ minWidth: 160 }}>
              {loading === 'scan' ? 'Scanning...' : '2. Scan Forms'}
            </button>
            <span className="text-sm text-muted">Open each job's application form and discover all questions.</span>
          </div>
          <div className="flex gap-1 items-center">
            <button className="secondary" onClick={() => navigate('/questions')} disabled={!!loading} style={{ minWidth: 160 }}>
              3. Review Questions
            </button>
            <span className="text-sm text-muted">Answer any new questions discovered during scanning.</span>
          </div>
          <div className="flex gap-1 items-center">
            <button className="secondary" onClick={() => run('apply', applyAll)} disabled={!!loading || (scanStatus && scanStatus.unanswered_questions > 0)} style={{ minWidth: 160 }}>
              {loading === 'apply' ? 'Applying...' : '4. Apply to All'}
            </button>
            <span className="text-sm text-muted">
              {scanStatus && scanStatus.unanswered_questions > 0
                ? `Blocked — ${scanStatus.unanswered_questions} questions need answers first.`
                : 'Submit applications to all eligible jobs.'}
            </span>
          </div>
          <div className="flex gap-1 items-center">
            <button className="secondary" onClick={() => run('retry', retryFailed)} disabled={!!loading} style={{ minWidth: 160 }}>
              {loading === 'retry' ? 'Resetting...' : '↩ Retry Failed'}
            </button>
            <span className="text-sm text-muted">Reset failed jobs back to "New" for re-attempt.</span>
          </div>
        </div>
      </div>

      <div className="card mb-2" style={{ background: '#1c1e26', borderColor: '#30363d' }}>
        <h3 className="mb-1" style={{ color: '#8b949e' }}>ℹ️ How it works</h3>
        <ul className="text-sm text-muted" style={{ paddingLeft: '1.2rem', lineHeight: 1.8 }}>
          <li><strong>Fetch</strong> — Pulls jobs from Greenhouse, AshbyHQ, Lever APIs filtered by your preferences.</li>
          <li><strong>Scan</strong> — Opens each application form (headless browser), extracts every question and dropdown option.</li>
          <li><strong>Review</strong> — New questions are shown on the Questions page. You answer them once, and they're reused for all future jobs asking the same thing.</li>
          <li><strong>Apply</strong> — Only runs when ALL questions have answers. Fills forms with 100% coverage and submits.</li>
          <li>The Q&A bank grows over time — after a few runs, most questions are already answered.</li>
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
              {result.needs_review && (
                <p style={{ color: '#e74c3c', fontWeight: 600, marginBottom: '0.5rem' }}>
                  ⚠️ Pipeline paused — {result.questions_unanswered} questions need answers before applying.
                  <button className="secondary" style={{ marginLeft: '0.5rem', fontSize: '0.8rem' }} onClick={() => navigate('/questions')}>
                    Review Questions →
                  </button>
                </p>
              )}
              <p>📥 Jobs fetched: <strong>{result.jobs_fetched ?? '—'}</strong></p>
              <p>🔍 Jobs scanned: <strong>{result.jobs_scanned ?? '—'}</strong></p>
              <p>❓ Questions found: <strong>{result.questions_found ?? '—'}</strong></p>
              {result.questions_unanswered > 0 && (
                <p>🔴 Unanswered: <strong>{result.questions_unanswered}</strong></p>
              )}
              {!result.needs_review && (
                <>
                  <p>{result.dry_run ? '📝 Forms previewed' : '✅ Applications submitted'}: <strong>{result.forms_filled ?? '—'}</strong></p>
                  <p>❌ Failed: <strong>{result.applications_failed ?? '—'}</strong></p>
                  <p>⏭️ Skipped: <strong>{result.applications_skipped ?? '—'}</strong></p>
                </>
              )}
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
