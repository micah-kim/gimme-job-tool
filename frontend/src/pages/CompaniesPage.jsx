import { useEffect, useState } from 'react';
import { getCompanies, addCompany, deleteCompany } from '../api/client';

export default function CompaniesPage() {
  const [companies, setCompanies] = useState([]);
  const [form, setForm] = useState({ name: '', ats_type: 'greenhouse', board_token: '' });
  const [error, setError] = useState('');

  const load = async () => {
    try {
      setCompanies(await getCompanies());
      setError('');
    } catch (e) {
      console.error('Failed to load companies:', e);
      setError(e.message);
    }
  };
  useEffect(() => { load(); }, []);

  const handleAdd = async (e) => {
    e.preventDefault();
    try {
      await addCompany(form);
      setForm({ name: '', ats_type: 'greenhouse', board_token: '' });
      await load();
    } catch (e) {
      console.error('Failed to add company:', e);
      setError(e.message);
    }
  };

  const handleDelete = async (id) => {
    if (confirm('Remove this company?')) {
      try {
        await deleteCompany(id);
        await load();
      } catch (e) {
        console.error('Failed to delete company:', e);
        setError(e.message);
      }
    }
  };

  return (
    <div>
      <h2 className="mb-2">Tracked Companies</h2>

      {error && <div className="card mb-2" style={{ borderColor: '#da3633', color: '#f85149' }}>⚠️ {error}</div>}

      <div className="card mb-2">
        <h3 className="mb-1">Add Company</h3>
        <form onSubmit={handleAdd} className="flex gap-1 items-center" style={{ flexWrap: 'wrap' }}>
          <div className="form-group" style={{ flex: 1, minWidth: 150 }}>
            <label>Company Name</label>
            <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
          </div>
          <div className="form-group" style={{ width: 160 }}>
            <label>ATS Type</label>
            <select value={form.ats_type} onChange={e => setForm({ ...form, ats_type: e.target.value })}>
              <option value="greenhouse">Greenhouse</option>
              <option value="ashby">AshbyHQ</option>
              <option value="lever">Lever</option>
            </select>
          </div>
          <div className="form-group" style={{ flex: 1, minWidth: 150 }}>
            <label>Board Token</label>
            <input value={form.board_token} onChange={e => setForm({ ...form, board_token: e.target.value })} placeholder="e.g. airbnb" required />
          </div>
          <button type="submit" style={{ alignSelf: 'flex-end' }}>Add</button>
        </form>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>ATS</th>
              <th>Board Token</th>
              <th>Last Fetched</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {companies.map(c => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.ats_type}</td>
                <td><code>{c.board_token}</code></td>
                <td className="text-sm text-muted">
                  {c.last_scraped_at ? new Date(c.last_scraped_at).toLocaleString() : 'Never'}
                </td>
                <td><button className="danger" onClick={() => handleDelete(c.id)}>Remove</button></td>
              </tr>
            ))}
            {companies.length === 0 && (
              <tr><td colSpan={5} className="text-muted" style={{ textAlign: 'center', padding: '2rem' }}>No companies tracked yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
