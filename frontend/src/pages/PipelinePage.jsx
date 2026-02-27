import { useState } from 'react';
import { runPipeline, triggerFetch, triggerAnalyze, triggerTailor, applyAll } from '../api/client';

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
        <h3 className="mb-1">Full Pipeline</h3>
        <p className="text-muted text-sm mb-1">Runs all steps: Fetch → Analyze → Tailor → Apply</p>
        <div className="flex gap-1">
          <button onClick={() => run('pipeline', () => runPipeline({ dry_run: true }))} disabled={!!loading}>
            {loading === 'pipeline' ? 'Running...' : '🧪 Dry Run'}
          </button>
          <button className="danger" onClick={() => run('pipeline-live', () => runPipeline({ dry_run: false }))} disabled={!!loading}>
            {loading === 'pipeline-live' ? 'Running...' : '🚀 Run Live'}
          </button>
        </div>
      </div>

      <div className="card mb-2">
        <h3 className="mb-1">Individual Steps</h3>
        <div className="flex gap-1" style={{ flexWrap: 'wrap' }}>
          <button className="secondary" onClick={() => run('fetch', triggerFetch)} disabled={!!loading}>
            {loading === 'fetch' ? '...' : '1. Fetch Jobs'}
          </button>
          <button className="secondary" onClick={() => run('analyze', triggerAnalyze)} disabled={!!loading}>
            {loading === 'analyze' ? '...' : '2. Analyze Jobs'}
          </button>
          <button className="secondary" onClick={() => run('tailor', triggerTailor)} disabled={!!loading}>
            {loading === 'tailor' ? '...' : '3. Tailor Resumes'}
          </button>
          <button className="secondary" onClick={() => run('apply', applyAll)} disabled={!!loading}>
            {loading === 'apply' ? '...' : '4. Apply All'}
          </button>
        </div>
      </div>

      {result && (
        <div className="card">
          <h3 className="mb-1">Result</h3>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.85rem', color: '#8b949e' }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
