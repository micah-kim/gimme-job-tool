import { useEffect, useState } from 'react';
import { getProfile, saveProfile, uploadResume } from '../api/client';

const emptyPrefs = { titles: '', excluded_titles: '', locations: '', min_yoe: 0, max_yoe: 99, keywords: '', deal_breakers: '' };

const emptyAnswers = {
  authorized_to_work: '', sponsorship_needed: '',
  school_name: '', degree: '', field_of_study: '', graduation_year: '',
  years_of_experience: '', current_company: '', current_title: '',
  desired_salary: '', salary_currency: 'USD', willing_to_relocate: '',
  available_start_date: '', website_url: '', github_url: '', portfolio_url: '',
  gender: '', race_ethnicity: '', veteran_status: '', disability_status: '',
  over_18: '', how_did_you_hear: '', requires_accommodation: '',
  non_compete: '', previously_worked_here: '', location_city: '',
};

// Convert arrays to comma strings for editing, and back for saving
const arrToStr = (arr) => (Array.isArray(arr) ? arr.join(', ') : arr || '');
const strToArr = (str) => (str || '').split(',').map(s => s.trim()).filter(Boolean);

function SelectField({ label, value, onChange, options, placeholder }) {
  return (
    <div className="form-group">
      <label>{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)}>
        <option value="">{placeholder || '— Select —'}</option>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}

export default function ProfilePage() {
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState({
    first_name: '', last_name: '', email: '', phone: '', linkedin_url: '',
    preferences: { ...emptyPrefs },
    application_answers: { ...emptyAnswers },
  });
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getProfile().then(p => {
      if (p) {
        setProfile(p);
        const prefs = p.preferences || {};
        setForm({
          first_name: p.first_name, last_name: p.last_name,
          email: p.email, phone: p.phone || '', linkedin_url: p.linkedin_url || '',
          preferences: {
            titles: arrToStr(prefs.titles),
            excluded_titles: arrToStr(prefs.excluded_titles),
            locations: arrToStr(prefs.locations),
            min_yoe: prefs.min_yoe || 0,
            max_yoe: prefs.max_yoe || 99,
            keywords: arrToStr(prefs.keywords),
            deal_breakers: arrToStr(prefs.deal_breakers),
          },
          application_answers: { ...emptyAnswers, ...(p.application_answers || {}) },
        });
      }
    }).catch(e => { console.error('Failed to load profile:', e); setError(e.message); });
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    setError('');
    try {
      // Convert comma-separated strings back to arrays for the API
      const payload = {
        ...form,
        preferences: {
          titles: strToArr(form.preferences.titles),
          excluded_titles: strToArr(form.preferences.excluded_titles),
          locations: strToArr(form.preferences.locations),
          min_yoe: form.preferences.min_yoe,
          max_yoe: form.preferences.max_yoe,
          keywords: strToArr(form.preferences.keywords),
          deal_breakers: strToArr(form.preferences.deal_breakers),
        },
      };
      const result = await saveProfile(payload);
      setProfile(result);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      console.error('Failed to save profile:', e);
      setError(e.message);
    }
  };

  const handleResume = async (e) => {
    const file = e.target.files[0];
    if (file) {
      try {
        const res = await uploadResume(file);
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      } catch (err) {
        console.error('Failed to upload resume:', err);
        setError(err.message);
      }
    }
  };

  const updatePref = (key, value) => {
    setForm({ ...form, preferences: { ...form.preferences, [key]: value } });
  };

  const updateAnswer = (key, value) => {
    setForm({ ...form, application_answers: { ...form.application_answers, [key]: value } });
  };

  return (
    <div>
      <h2 className="mb-2">Profile & Preferences</h2>
      {error && <div className="card mb-2" style={{ borderColor: '#da3633', color: '#f85149' }}>⚠️ {error}</div>}
      <form onSubmit={handleSave}>

        {/* ── Personal Info ── */}
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
            <input value={form.linkedin_url} onChange={e => setForm({ ...form, linkedin_url: e.target.value })} placeholder="https://linkedin.com/in/yourname" />
          </div>
          <div className="form-group">
            <label>Resume (PDF only)</label>
            <input type="file" accept=".pdf" onChange={handleResume} />
            {profile?.base_resume_path && <span className="text-sm text-muted">Current: {profile.base_resume_path}</span>}
          </div>
        </div>

        {/* ── Job Preferences ── */}
        <div className="card mb-2">
          <h3 className="mb-1">Job Preferences</h3>
          <p className="text-sm text-muted mb-1">Comma-separated values. These are used by AI to score and filter job listings.</p>
          <div className="form-group">
            <label>Target Job Titles</label>
            <input
              value={form.preferences.titles}
              onChange={e => updatePref('titles', e.target.value)}
              placeholder="Software Engineer, Backend Developer, Full Stack Engineer"
            />
          </div>
          <div className="form-group">
            <label>Exclude Titles Containing</label>
            <input
              value={form.preferences.excluded_titles}
              onChange={e => updatePref('excluded_titles', e.target.value)}
              placeholder="Staff, Senior, Principal, Manager"
            />
          </div>
          <div className="form-group">
            <label>Preferred Locations</label>
            <input
              value={form.preferences.locations}
              onChange={e => updatePref('locations', e.target.value)}
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
            <label>Keywords to Match</label>
            <input
              value={form.preferences.keywords}
              onChange={e => updatePref('keywords', e.target.value)}
              placeholder="Python, React, distributed systems, Kubernetes"
            />
          </div>
          <div className="form-group">
            <label>Deal-Breakers (reject if found)</label>
            <input
              value={form.preferences.deal_breakers}
              onChange={e => updatePref('deal_breakers', e.target.value)}
              placeholder="security clearance required, PHP, unpaid"
            />
          </div>
        </div>

        {/* ── Work Authorization ── */}
        <div className="card mb-2">
          <h3 className="mb-1">Work Authorization</h3>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            <SelectField label="Authorized to work in the U.S.?" value={form.application_answers.authorized_to_work}
              onChange={v => updateAnswer('authorized_to_work', v)} options={['Yes', 'No']} />
            <SelectField label="Will you now or in the future require sponsorship?" value={form.application_answers.sponsorship_needed}
              onChange={v => updateAnswer('sponsorship_needed', v)} options={['Yes', 'No']} />
          </div>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            <SelectField label="Are you over 18 years of age?" value={form.application_answers.over_18}
              onChange={v => updateAnswer('over_18', v)} options={['Yes', 'No']} />
            <SelectField label="Willing to relocate?" value={form.application_answers.willing_to_relocate}
              onChange={v => updateAnswer('willing_to_relocate', v)} options={['Yes', 'No']} />
          </div>
          <div className="form-group">
            <label>Available Start Date</label>
            <input type="date" value={form.application_answers.available_start_date}
              onChange={e => updateAnswer('available_start_date', e.target.value)} />
          </div>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            <SelectField label="Subject to non-compete/non-solicitation agreement?" value={form.application_answers.non_compete}
              onChange={v => updateAnswer('non_compete', v)} options={['Yes', 'No']} />
            <SelectField label="Previously worked at the company?" value={form.application_answers.previously_worked_here}
              onChange={v => updateAnswer('previously_worked_here', v)} options={['Yes', 'No']} />
          </div>
          <div className="form-group">
            <label>Location (City) — used for application forms</label>
            <input value={form.application_answers.location_city}
              onChange={e => updateAnswer('location_city', e.target.value)} placeholder="San Francisco, CA" />
          </div>
        </div>

        {/* ── Education ── */}
        <div className="card mb-2">
          <h3 className="mb-1">Education</h3>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            <div className="form-group" style={{ flex: 2, minWidth: 200 }}>
              <label>School / University</label>
              <input value={form.application_answers.school_name}
                onChange={e => updateAnswer('school_name', e.target.value)} placeholder="University of California, Berkeley" />
            </div>
            <div className="form-group" style={{ flex: 1, minWidth: 120 }}>
              <label>Graduation Year</label>
              <input value={form.application_answers.graduation_year}
                onChange={e => updateAnswer('graduation_year', e.target.value)} placeholder="2022" />
            </div>
          </div>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            <SelectField label="Degree" value={form.application_answers.degree}
              onChange={v => updateAnswer('degree', v)}
              options={["High School Diploma", "Associate's", "Bachelor's", "Master's", "PhD", "Other"]} />
            <div className="form-group" style={{ flex: 1, minWidth: 200 }}>
              <label>Field of Study</label>
              <input value={form.application_answers.field_of_study}
                onChange={e => updateAnswer('field_of_study', e.target.value)} placeholder="Computer Science" />
            </div>
          </div>
        </div>

        {/* ── Work Experience ── */}
        <div className="card mb-2">
          <h3 className="mb-1">Work Experience</h3>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            <div className="form-group" style={{ flex: 1, minWidth: 200 }}>
              <label>Current Company</label>
              <input value={form.application_answers.current_company}
                onChange={e => updateAnswer('current_company', e.target.value)} />
            </div>
            <div className="form-group" style={{ flex: 1, minWidth: 200 }}>
              <label>Current Title</label>
              <input value={form.application_answers.current_title}
                onChange={e => updateAnswer('current_title', e.target.value)} />
            </div>
          </div>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            <div className="form-group" style={{ flex: 1, minWidth: 150 }}>
              <label>Total Years of Experience</label>
              <input value={form.application_answers.years_of_experience}
                onChange={e => updateAnswer('years_of_experience', e.target.value)} placeholder="5" />
            </div>
            <div className="form-group" style={{ flex: 1, minWidth: 150 }}>
              <label>Desired Salary</label>
              <input value={form.application_answers.desired_salary}
                onChange={e => updateAnswer('desired_salary', e.target.value)} placeholder="150000" />
            </div>
            <SelectField label="Currency" value={form.application_answers.salary_currency}
              onChange={v => updateAnswer('salary_currency', v)} options={['USD', 'EUR', 'GBP', 'CAD', 'AUD']} />
          </div>
        </div>

        {/* ── Online Presence ── */}
        <div className="card mb-2">
          <h3 className="mb-1">Online Presence</h3>
          <div className="form-group">
            <label>Website / Portfolio URL</label>
            <input value={form.application_answers.website_url}
              onChange={e => updateAnswer('website_url', e.target.value)} placeholder="https://yoursite.com" />
          </div>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            <div className="form-group" style={{ flex: 1, minWidth: 200 }}>
              <label>GitHub URL</label>
              <input value={form.application_answers.github_url}
                onChange={e => updateAnswer('github_url', e.target.value)} placeholder="https://github.com/yourname" />
            </div>
            <div className="form-group" style={{ flex: 1, minWidth: 200 }}>
              <label>Portfolio URL</label>
              <input value={form.application_answers.portfolio_url}
                onChange={e => updateAnswer('portfolio_url', e.target.value)} placeholder="https://dribbble.com/yourname" />
            </div>
          </div>
          <div className="form-group">
            <label>How did you hear about us? (default answer)</label>
            <input value={form.application_answers.how_did_you_hear}
              onChange={e => updateAnswer('how_did_you_hear', e.target.value)} placeholder="Company website" />
          </div>
        </div>

        {/* ── EEO / Demographics ── */}
        <div className="card mb-2">
          <h3 className="mb-1">EEO / Demographics</h3>
          <p className="text-sm text-muted mb-1">Voluntary self-identification. These are used to auto-fill optional demographic questions on applications.</p>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            <SelectField label="Gender" value={form.application_answers.gender}
              onChange={v => updateAnswer('gender', v)}
              options={['Male', 'Female', 'Non-binary', 'Prefer not to say']} />
            <SelectField label="Race / Ethnicity" value={form.application_answers.race_ethnicity}
              onChange={v => updateAnswer('race_ethnicity', v)}
              options={[
                'White', 'Black or African American', 'Asian',
                'Hispanic or Latino', 'Native American or Alaska Native',
                'Native Hawaiian or Other Pacific Islander', 'Two or More Races',
                'Prefer not to say'
              ]} />
          </div>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            <SelectField label="Veteran Status" value={form.application_answers.veteran_status}
              onChange={v => updateAnswer('veteran_status', v)}
              options={['I am a veteran', 'I am not a veteran', 'Prefer not to say']} />
            <SelectField label="Disability Status" value={form.application_answers.disability_status}
              onChange={v => updateAnswer('disability_status', v)}
              options={['Yes, I have a disability', 'No, I do not have a disability', 'Prefer not to say']} />
          </div>
          <SelectField label="Do you require any accommodations?" value={form.application_answers.requires_accommodation}
            onChange={v => updateAnswer('requires_accommodation', v)} options={['Yes', 'No']} />
        </div>

        <button type="submit">{saved ? '✓ Saved!' : 'Save Profile'}</button>
      </form>
    </div>
  );
}
