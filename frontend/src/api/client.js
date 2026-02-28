const BASE = '/api';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

// Companies
export const getCompanies = () => request('/companies');
export const addCompany = (data) => request('/companies', { method: 'POST', body: JSON.stringify(data) });
export const deleteCompany = (id) => request(`/companies/${id}`, { method: 'DELETE' });

// Jobs
export const getJobs = (params = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/jobs?${qs}`);
};
export const getMatchedJobs = () => request('/jobs/matched');
export const getJobScore = (id) => request(`/jobs/${id}/score`);

// Profile
export const getProfile = () => request('/profile');
export const saveProfile = (data) => request('/profile', { method: 'POST', body: JSON.stringify(data) });
export const updatePreferences = (prefs) => request('/profile/preferences', { method: 'PUT', body: JSON.stringify(prefs) });

export const uploadResume = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${BASE}/profile/resume`, { method: 'POST', body: formData });
  return res.json();
};

// Pipeline
export const runPipeline = (opts = {}) => request('/pipeline/run', { method: 'POST', body: JSON.stringify(opts) });
export const triggerFetch = () => request('/jobs/fetch', { method: 'POST' });
export const applyToJob = (id) => request(`/jobs/${id}/apply`, { method: 'POST' });
export const applyAll = () => request('/apply/run', { method: 'POST' });

// Applications
export const getApplications = () => request('/applications');
