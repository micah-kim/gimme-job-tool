import { Routes, Route, NavLink } from 'react-router-dom';
import JobsPage from './pages/JobsPage';
import CompaniesPage from './pages/CompaniesPage';
import ProfilePage from './pages/ProfilePage';
import ApplicationsPage from './pages/ApplicationsPage';
import PipelinePage from './pages/PipelinePage';

export default function App() {
  return (
    <div className="app">
      <nav className="sidebar">
        <h1>🎯 Gimme Job</h1>
        <NavLink to="/" end>Jobs</NavLink>
        <NavLink to="/companies">Companies</NavLink>
        <NavLink to="/profile">Profile</NavLink>
        <NavLink to="/applications">Applications</NavLink>
        <NavLink to="/pipeline">Pipeline</NavLink>
      </nav>
      <main className="main">
        <Routes>
          <Route path="/" element={<JobsPage />} />
          <Route path="/companies" element={<CompaniesPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/applications" element={<ApplicationsPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
        </Routes>
      </main>
    </div>
  );
}
