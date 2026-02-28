import { useState, useEffect } from 'react';
import { getUnansweredQuestions, answerQuestions, getScanStatus, seedQA, getQAEntries } from '../api/client';

const CATEGORY_LABELS = {
  work_auth: '🛂 Work Authorization',
  demographic: '📊 Demographics (EEO)',
  education: '🎓 Education',
  experience: '💼 Experience',
  compensation: '💰 Compensation',
  logistics: '📍 Logistics',
  legal: '⚖️ Legal',
  online: '🔗 Online Presence',
  misc: '📝 Miscellaneous',
  other: '❓ Other',
};

export default function QuestionsPage() {
  const [unanswered, setUnanswered] = useState([]);
  const [allQA, setAllQA] = useState([]);
  const [scanStatus, setScanStatus] = useState(null);
  const [answers, setAnswers] = useState({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [view, setView] = useState('unanswered'); // 'unanswered' | 'all'

  useEffect(() => { load(); }, []);

  async function load() {
    try {
      const [unans, status, all] = await Promise.all([
        getUnansweredQuestions(),
        getScanStatus(),
        getQAEntries(),
      ]);
      setUnanswered(unans);
      setScanStatus(status);
      setAllQA(all);
    } catch (e) {
      setMsg('Error loading: ' + e.message);
    }
  }

  async function handleSeed() {
    try {
      const res = await seedQA();
      setMsg(`Seeded ${res.seeded} entries from profile`);
      load();
    } catch (e) {
      setMsg('Error: ' + e.message);
    }
  }

  function setAnswer(qaId, value) {
    setAnswers(prev => ({ ...prev, [qaId]: value }));
  }

  async function handleSave() {
    const items = Object.entries(answers)
      .filter(([, v]) => v)
      .map(([qaId, answer]) => ({ qa_id: parseInt(qaId), answer }));
    if (!items.length) return;
    setSaving(true);
    try {
      await answerQuestions(items);
      setMsg(`Saved ${items.length} answers`);
      setAnswers({});
      load();
    } catch (e) {
      setMsg('Error saving: ' + e.message);
    }
    setSaving(false);
  }

  // Group unanswered by category
  const grouped = {};
  for (const q of unanswered) {
    const cat = q.category || 'other';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(q);
  }

  // Group all QA by category
  const allGrouped = {};
  for (const q of allQA) {
    const cat = q.category || 'other';
    if (!allGrouped[cat]) allGrouped[cat] = [];
    allGrouped[cat].push(q);
  }

  return (
    <div>
      <h2>❓ Questions Bank</h2>
      <p className="text-sm text-muted mb-1">
        Questions discovered from job application forms. Answer them here so applications can be auto-filled with 100% coverage.
      </p>

      {/* Status banner */}
      {scanStatus && (
        <div className="card mb-1" style={{ display: 'flex', gap: '2rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <div><strong>{scanStatus.scanned_jobs}</strong> jobs scanned</div>
          <div><strong>{scanStatus.total_questions}</strong> total questions</div>
          <div style={{ color: scanStatus.unanswered_questions > 0 ? '#e74c3c' : '#27ae60', fontWeight: 'bold' }}>
            {scanStatus.unanswered_questions > 0
              ? `⚠️ ${scanStatus.unanswered_questions} unanswered`
              : '✅ All answered — ready to apply!'
            }
          </div>
          <button onClick={handleSeed} style={{ marginLeft: 'auto', fontSize: '0.85rem' }}>
            Seed from Profile
          </button>
        </div>
      )}

      {msg && <div className="msg mb-1" style={{ padding: '0.5rem', background: '#f0f0f0', borderRadius: '4px' }}>{msg}</div>}

      {/* View toggle */}
      <div className="flex gap-1 mb-1">
        <button
          onClick={() => setView('unanswered')}
          style={{ fontWeight: view === 'unanswered' ? 'bold' : 'normal', textDecoration: view === 'unanswered' ? 'underline' : 'none' }}
        >
          Unanswered ({unanswered.length})
        </button>
        <button
          onClick={() => setView('all')}
          style={{ fontWeight: view === 'all' ? 'bold' : 'normal', textDecoration: view === 'all' ? 'underline' : 'none' }}
        >
          All Questions ({allQA.length})
        </button>
      </div>

      {view === 'unanswered' && (
        <>
          {unanswered.length === 0 ? (
            <div className="card">
              <p>No unanswered questions! Run the pipeline to scan job forms, or click "Seed from Profile" to pre-populate from your profile answers.</p>
            </div>
          ) : (
            <>
              {Object.entries(grouped)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([category, questions]) => (
                  <div key={category} className="card mb-1">
                    <h3>{CATEGORY_LABELS[category] || category}</h3>
                    {questions.map(q => (
                      <div key={q.qa_id} className="form-group" style={{ marginBottom: '0.75rem', padding: '0.5rem', background: '#fafafa', borderRadius: '4px' }}>
                        <label style={{ fontWeight: '600', marginBottom: '0.25rem', display: 'block' }}>
                          {q.display_question}
                          <span className="text-sm text-muted" style={{ marginLeft: '0.5rem' }}>
                            ({q.job_count} job{q.job_count > 1 ? 's' : ''})
                          </span>
                        </label>
                        {q.field_type === 'select' && q.options.length > 0 ? (
                          <select
                            value={answers[q.qa_id] || ''}
                            onChange={e => setAnswer(q.qa_id, e.target.value)}
                          >
                            <option value="">-- Select --</option>
                            {q.options.map(([text, value]) => (
                              <option key={value} value={text}>{text}</option>
                            ))}
                          </select>
                        ) : q.field_type === 'textarea' ? (
                          <textarea
                            value={answers[q.qa_id] || ''}
                            onChange={e => setAnswer(q.qa_id, e.target.value)}
                            rows={3}
                          />
                        ) : (
                          <input
                            type="text"
                            value={answers[q.qa_id] || ''}
                            onChange={e => setAnswer(q.qa_id, e.target.value)}
                          />
                        )}
                      </div>
                    ))}
                  </div>
                ))}
              <button onClick={handleSave} disabled={saving || Object.keys(answers).length === 0}>
                {saving ? 'Saving...' : `Save ${Object.keys(answers).filter(k => answers[k]).length} Answer(s)`}
              </button>
            </>
          )}
        </>
      )}

      {view === 'all' && (
        <>
          {allQA.length === 0 ? (
            <div className="card"><p>No questions in the bank yet. Run the pipeline to scan job forms.</p></div>
          ) : (
            Object.entries(allGrouped)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([category, questions]) => (
                <div key={category} className="card mb-1">
                  <h3>{CATEGORY_LABELS[category] || category}</h3>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #ddd', textAlign: 'left' }}>
                        <th style={{ padding: '0.4rem' }}>Question</th>
                        <th style={{ padding: '0.4rem' }}>Type</th>
                        <th style={{ padding: '0.4rem' }}>Answer</th>
                      </tr>
                    </thead>
                    <tbody>
                      {questions.map(q => (
                        <tr key={q.id} style={{ borderBottom: '1px solid #eee' }}>
                          <td style={{ padding: '0.4rem' }}>{q.display_question}</td>
                          <td style={{ padding: '0.4rem' }}><code>{q.field_type}</code></td>
                          <td style={{ padding: '0.4rem', color: q.answer ? '#27ae60' : '#e74c3c' }}>
                            {q.answer || '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))
          )}
        </>
      )}
    </div>
  );
}
