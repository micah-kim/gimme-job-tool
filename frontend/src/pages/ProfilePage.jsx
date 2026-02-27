import { useEffect, useState } from 'react';
import { getProfile, saveProfile, uploadResume } from '../api/client';

const emptyPrefs = { titles: [], locations: [], min_yoe: 0, max_yoe: 99, keywords: [], deal_breakers: [] };

export default function ProfilePage() {
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState({
    first_name: '', last_name: '', email: '', phone: '', linkedin_url: '',
    preferences: { ...emptyPrefs },
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getProfile().then(p => {
      if (p) {
        setProfile(p);
        setForm({
          first_name: p.first_name, last_name: p.last_name,
          email: p.email, phone: p.phone || '', linkedin_url: p.linkedin_url || '',
          preferences: p.preferences || { ...emptyPrefs },
        });
      }
    });
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    const result = await saveProfile(form);
    setProfile(result);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleResume = async (e) => {
    const file = e.target.files[0];
    if (file) {
      const res = await uploadResume(file);
      alert(`Resume uploaded: ${res.filename}`);
    }
  };

  const updatePref = (key, value) => {
    setForm({ ...form, preferences: { ...form.preferences, [key]: value } });
  };

  const parseList = (str) => str.split(',').map(s => s.trim()).filter(Boolean);

  return (
    <div>
      <h2 className="mb-2">Profile & Preferences</h2>
      <form onSubmit={handleSave}>
        <div className="card mb-2">
          <h3 className="mb-1">Personal Info</h3>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            <div className="form-group" style={{ flex: 1, minWidth: 200 }}>
              <label>First Name</label>
              <input value={form.first_name} onChange={e => setForm({ ...form, first_name: e.target.value })} required />
            </div>
            <div className="form-group" style={{ flex: 1, minWidth: 200 }}>
              <label>Last Name</label>
              <input value={form.last_name} onChange={e => setForm({ ...form, last_name: e.target.value })} required />
            </div>
          </div>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            <div className="form-group" style={{ flex: 1, minWidth: 200 }}>
              <label>Email</label>
              <input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} required />
            </div>
            <div className="form-group" style={{ flex: 1, minWidth: 200 }}>
              <label>Phone</label>
              <input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} />
            </div>
          </div>
          <div className="form-group">
            <label>LinkedIn URL</label>
            <input value={form.linkedin_url} onChange={e => setForm({ ...form, linkedin_url: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Base Resume (DOCX or TXT)</label>
            <input type="file" accept=".docx,.txt,.pdf" onChange={handleResume} />
            {profile?.base_resume_path && <span className="text-sm text-muted">Current: {profile.base_resume_path}</span>}
          </div>
        </div>

        <div className="card mb-2">
          <h3 className="mb-1">Job Preferences</h3>
          <div className="form-group">
            <label>Target Job Titles (comma-separated)</label>
            <input
              value={(form.preferences.titles || []).join(', ')}
              onChange={e => updatePref('titles', parseList(e.target.value))}
              placeholder="Software Engineer, Backend Developer, Full Stack"
            />
          </div>
          <div className="form-group">
            <label>Preferred Locations (comma-separated)</label>
            <input
              value={(form.preferences.locations || []).join(', ')}
              onChange={e => updatePref('locations', parseList(e.target.value))}
              placeholder="Remote, San Francisco, New York"
            />
          </div>
          <div className="flex gap-2">
            <div className="form-group" style={{ flex: 1 }}>
              <label>Min Years of Experience</label>
              <input type="number" value={form.preferences.min_yoe || 0} onChange={e => updatePref('min_yoe', +e.target.value)} />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label>Max Years of Experience</label>
              <input type="number" value={form.preferences.max_yoe || 99} onChange={e => updatePref('max_yoe', +e.target.value)} />
            </div>
          </div>
          <div className="form-group">
            <label>Keywords to Match (comma-separated)</label>
            <input
              value={(form.preferences.keywords || []).join(', ')}
              onChange={e => updatePref('keywords', parseList(e.target.value))}
              placeholder="Python, React, distributed systems"
            />
          </div>
          <div className="form-group">
            <label>Deal-Breakers (comma-separated)</label>
            <input
              value={(form.preferences.deal_breakers || []).join(', ')}
              onChange={e => updatePref('deal_breakers', parseList(e.target.value))}
              placeholder="security clearance, PHP, unpaid"
            />
          </div>
        </div>

        <button type="submit">{saved ? '✓ Saved!' : 'Save Profile'}</button>
      </form>
    </div>
  );
}
