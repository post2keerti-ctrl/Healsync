import { useEffect, useState, type FormEvent } from 'react';
import { sendPasswordResetEmail, signInWithEmailAndPassword } from 'firebase/auth';
import {
  Activity,
  Bell,
  ChevronRight,
  ClipboardList,
  FileText,
  HeartPulse,
  LayoutDashboard,
  Menu,
  PackageCheck,
  Search,
  ShieldCheck,
  ShoppingCart,
  Truck,
  UserRound,
} from 'lucide-react';
import { api, apiRequest, type PatientDashboardData } from './lib/api';
import { firebaseAuth } from './lib/firebase';
import { NotificationsPanel, WorkspacePage } from './WorkspacePage';

type Role = 'patient' | 'doctor' | 'supplier';
type Page = 'dashboard' | 'documents' | 'recovery' | 'orders' | 'patients' | 'inventory' | 'alerts';

const demoAccounts: Record<Role, { name: string; email: string }> = {
  patient: { name: 'Karthik Subramanian', email: 'karthik@healsync.com' },
  doctor: { name: 'Dr. Meera Rao', email: 'doctor@healsync.com' },
  supplier: { name: 'Apollo MedSupply', email: 'supplier@healsync.com' },
};

const roleConfig: Record<Role, { label: string; accent: string; nav: { id: Page; label: string; icon: typeof LayoutDashboard }[] }> = {
  patient: {
    label: 'Patient companion',
    accent: 'coral',
    nav: [
      { id: 'dashboard', label: 'Overview', icon: LayoutDashboard },
      { id: 'documents', label: 'Documents', icon: FileText },
      { id: 'recovery', label: 'Recovery plan', icon: HeartPulse },
      { id: 'orders', label: 'Orders', icon: ShoppingCart },
      { id: 'alerts', label: 'Alerts', icon: Bell },
    ],
  },
  doctor: {
    label: 'Clinical console',
    accent: 'navy',
    nav: [
      { id: 'dashboard', label: 'Overview', icon: LayoutDashboard },
      { id: 'patients', label: 'Patients', icon: UserRound },
      { id: 'alerts', label: 'Care alerts', icon: Bell },
    ],
  },
  supplier: {
    label: 'Fulfilment portal',
    accent: 'teal',
    nav: [
      { id: 'dashboard', label: 'Overview', icon: LayoutDashboard },
      { id: 'orders', label: 'Orders', icon: PackageCheck },
      { id: 'inventory', label: 'Inventory', icon: ClipboardList },
    ],
  },
};

function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [role, setRole] = useState<Role>('patient');
  const [page, setPage] = useState<Page>('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [notificationsOpen, setNotificationsOpen] = useState(false);

  const config = roleConfig[role];
  if (!authenticated) {
    return <LoginScreen onLogin={(nextRole: Role) => {
      setRole(nextRole);
      setAuthenticated(true);
    }} />;
  }

  return (
    <div className={`app-shell accent-${config.accent}`}>
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><Activity size={20} strokeWidth={2.5} /></div>
          <div><strong>HealSync</strong><span>Recovery, coordinated.</span></div>
        </div>
        <div className="workspace-label">Workspace</div>
        <nav>
          {config.nav.map(({ id, label, icon: Icon }) => (
            <button className={page === id ? 'nav-item active' : 'nav-item'} key={id} onClick={() => { setPage(id); setSidebarOpen(false); }}>
              <Icon size={18} />{label}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="trust-note"><ShieldCheck size={17} /><span><strong>Care team connected</strong><small>Your data stays private.</small></span></div>
          <div className="profile-mini">
            <span className="avatar">{role === 'patient' ? 'KS' : role === 'doctor' ? 'DR' : 'AM'}</span>
            <span><strong>{role === 'patient' ? 'Karthik S.' : role === 'doctor' ? 'Dr. Meera Rao' : 'Apollo MedSupply'}</strong><small>{config.label}</small></span>
          </div>
        </div>
      </aside>

      {sidebarOpen && <button className="scrim" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
      <main className="main-content">
        <header className="topbar">
          <button className="icon-button menu-button" aria-label="Open navigation" onClick={() => setSidebarOpen(true)}><Menu size={20} /></button>
          <div className="breadcrumbs"><span>HealSync</span><ChevronRight size={14} /><strong>{config.nav.find((item) => item.id === page)?.label ?? 'Overview'}</strong></div>
          <div className="top-actions"><button className="icon-button" aria-label="Search" aria-expanded={searchOpen} onClick={() => { setSearchOpen(!searchOpen); setSearchTerm(''); setNotificationsOpen(false); }}><Search size={18} /></button><button className="icon-button" aria-label="Notifications" aria-expanded={notificationsOpen} onClick={() => { setNotificationsOpen(!notificationsOpen); setSearchOpen(false); }}><Bell size={18} /></button><button className="avatar top-avatar" aria-label="Sign out" title="Sign out" onClick={() => { localStorage.removeItem('healsync_token'); localStorage.removeItem('healsync_demo_mode'); setAuthenticated(false); setRole('patient'); setPage('dashboard'); setSearchOpen(false); setSearchTerm(''); setNotificationsOpen(false); setSidebarOpen(false); }}> {role === 'patient' ? 'KS' : role === 'doctor' ? 'DR' : 'AM'}</button></div>
        </header>

        {notificationsOpen && <NotificationsPanel role={role} onNavigate={(targetPage) => { setPage(targetPage); setNotificationsOpen(false); }} onClose={() => setNotificationsOpen(false)} />}
        {searchOpen && <div className="workspace-search"><label htmlFor="workspace-search-input">Find a workspace page</label><input id="workspace-search-input" autoFocus value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="Search pages..." onKeyDown={(event) => { if (event.key === 'Escape') setSearchOpen(false); if (event.key === 'Enter') { const match = config.nav.find((item) => item.label.toLowerCase().includes(searchTerm.toLowerCase())); if (match) { setPage(match.id); setSearchOpen(false); } } }} /><div className="search-results">{config.nav.filter((item) => item.label.toLowerCase().includes(searchTerm.toLowerCase())).map((item) => <button key={item.id} onClick={() => { setPage(item.id); setSearchOpen(false); }}>{item.label}<ChevronRight size={15} /></button>)}</div></div>}

        <div className="content-wrap">
          <PageHeader role={role} page={page} onAction={() => setPage(role === 'patient' ? 'recovery' : role === 'doctor' ? 'alerts' : 'orders')} />
          {page === 'dashboard' ? <Dashboard role={role} onNavigate={setPage} /> : <WorkspacePage role={role} page={page} />}
        </div>
      </main>
    </div>
  );
}

function LoginScreen({ onLogin }: { onLogin: (role: Role) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [selectedRole, setSelectedRole] = useState<Role>('patient');
  const [error, setError] = useState('');

  const resetPassword = async () => {
    if (!email) {
      setError('Enter your email address first.');
      return;
    }
    if (!firebaseAuth || !import.meta.env.VITE_FIREBASE_API_KEY) {
      setError('Password reset is not available for this account.');
      return;
    }
    try {
      await sendPasswordResetEmail(firebaseAuth, email);
      setError('Password reset email sent.');
    } catch (resetError) {
      setError(resetError instanceof Error ? resetError.message : 'Unable to send a reset email.');
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!email || !password) {
      setError('Choose a named account and enter its password.');
      return;
    }
    setError('');
    const loginWithDemoAccount = async () => {
      const payload = await apiRequest<{ id_token: string; role?: Role }>('/auth/dev-login', {
        method: 'POST',
        body: JSON.stringify({ email, password, role: selectedRole }),
      });
      localStorage.setItem('healsync_token', payload.id_token);
      localStorage.setItem('healsync_demo_mode', 'true');
      onLogin(payload.role ?? selectedRole);
    };

    try {
      if (firebaseAuth && import.meta.env.VITE_FIREBASE_API_KEY) {
        try {
          const userCredential = await signInWithEmailAndPassword(firebaseAuth, email, password);
          const idToken = await userCredential.user.getIdToken();
          localStorage.setItem('healsync_token', idToken);

          const profile = await apiRequest<{ role: Role }>('/auth/sync-profile', {
            method: 'POST',
            body: JSON.stringify({ name: demoAccounts[selectedRole].name, role: selectedRole }),
          }, idToken);

          localStorage.removeItem('healsync_demo_mode');
          onLogin(profile.role);
          return;
        } catch (firebaseError) {
          const code = firebaseError && typeof firebaseError === 'object' && 'code' in firebaseError
            ? String(firebaseError.code)
            : '';
          if (!['auth/invalid-credential', 'auth/user-not-found', 'auth/operation-not-allowed'].includes(code)) {
            throw firebaseError;
          }
        }
      }

      await loginWithDemoAccount();
    } catch (authError) {
      setError(authError instanceof Error ? authError.message : 'Unable to sign in. Try again.');
    }
  };

  return <main className="login-page">
    <section className="login-story">
      <div className="brand-lockup login-brand"><div className="brand-mark"><Activity size={20} strokeWidth={2.5} /></div><div><strong>HealSync</strong><span>Recovery, coordinated.</span></div></div>
      <div className="story-copy"><p className="eyebrow">Post-surgical care</p><h1>A clearer path through recovery.</h1><p>One calm workspace for patients, clinicians, and the suppliers who keep care moving.</p></div>
      <div className="story-proof"><ShieldCheck size={17} /><span><strong>Private by design</strong><small>Your care information is protected with Firebase security.</small></span></div>
    </section>
    <section className="login-card-wrap"><form className="login-card" onSubmit={submit}><div><p className="eyebrow">Welcome back</p><h2>Sign in to HealSync</h2><p className="login-muted">Use your secure account to continue to your workspace.</p></div><div className="role-switcher" aria-label="Select login role" style={{ marginBottom: '1rem' }}>
      {(['patient', 'doctor', 'supplier'] as Role[]).map((role) => (
        <button type="button" key={role} className={selectedRole === role ? 'selected' : ''} onClick={() => { setSelectedRole(role); setEmail(demoAccounts[role].email); setPassword('demo'); setError(''); }}>{role}</button>
      ))}
    </div><label>Email address<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="Enter your email address" autoComplete="email" /></label><label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" autoComplete="current-password" /></label>{error && <div className="form-error" role="alert">{error}</div>}<button className="primary-button login-submit" type="submit">Continue securely <ChevronRight size={17} /></button><button className="link-button" type="button" onClick={resetPassword}>Forgot password?</button><p className="login-legal">By continuing, you agree to HealSync's Terms of Service and Privacy Policy.</p></form></section>
  </main>;
}

function PageHeader({ role, page, onAction }: { role: Role; page: Page; onAction: () => void }) {
  const title = page === 'dashboard' ? role === 'patient' ? 'Good morning, Karthik' : role === 'doctor' ? 'Good morning, Dr. Rao' : 'Good morning, Apollo MedSupply' : roleConfig[role].nav.find((item) => item.id === page)?.label ?? 'Workspace';
  const subtitle = page === 'dashboard' ? role === 'patient' ? 'Here is your recovery picture for today.' : role === 'doctor' ? 'A focused view of the patients who need your attention.' : 'Keep every recovery order moving with confidence.' : 'A responsive workspace for the next action.';
  return <div className="page-header"><div><p className="eyebrow">{roleConfig[role].label}</p><h1>{title}</h1><p>{subtitle}</p></div><button className="primary-button" onClick={onAction}><Activity size={17} /> {role === 'patient' ? 'Log an update' : role === 'doctor' ? 'Review alerts' : 'View incoming orders'}</button></div>;
}

function Dashboard({ role, onNavigate }: { role: Role; onNavigate: (page: Page) => void }) {
  if (role === 'doctor') return <WorkspacePage role="doctor" page="patients" />;
  if (role === 'supplier') return <SupplierDashboard onNavigate={onNavigate} />;
  return <PatientDashboard onNavigate={onNavigate} />;
}

function PatientDashboard({ onNavigate }: { onNavigate: (page: Page) => void }) {
  const [dashboard, setDashboard] = useState<PatientDashboardData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('healsync_token');
    if (!token) {
      setError('Sign in to load your recovery information.');
      return;
    }
    let active = true;
    api.dashboard(token).then((data) => {
      if (active) setDashboard(data);
    }).catch((loadError) => {
      if (active) setError(loadError instanceof Error ? loadError.message : 'Unable to load recovery information.');
    });
    return () => { active = false; };
  }, []);

  if (error) return <section className="panel workspace-empty" role="status">{error}</section>;
  if (!dashboard) return <section className="panel workspace-empty" role="status">Loading your recovery information...</section>;

  return <>
    <section className="stat-grid"><article className="stat-card coral"><span>Recovery confidence</span><strong>{dashboard.confidence_score}%</strong><small>Current care-team score</small></article><article className="stat-card sage"><span>Today's plan</span><strong>{dashboard.today_items.length}</strong><small>Scheduled items</small></article><article className="stat-card amber"><span>Active order</span><strong>{dashboard.active_order_reference ?? 'None'}</strong><small>{dashboard.active_order_reference ? 'Order reference' : 'No order linked'}</small></article></section>
    <section className="dashboard-grid">
      <article className="panel plan-panel"><PanelHeading title="Today's recovery plan" action="Open timeline" onClick={() => onNavigate('recovery')} /><div className="progress-meta"><span>Day {dashboard.recovery_day} of {dashboard.recovery_total_days}</span></div>{dashboard.today_items.length ? dashboard.today_items.map((item) => <div className="plan-row" key={item.id}><time>{item.time}</time><span className="timeline-dot next" /><div><strong>{item.title}</strong><small>{item.description}</small></div><span className="status-pill next">Scheduled</span></div>) : <p className="workspace-empty">No recovery items are scheduled for today.</p>}</article>
      <article className="panel order-panel"><PanelHeading title="Recovery order" action="View orders" onClick={() => onNavigate('orders')} /><div className="order-status"><div className="delivery-icon"><Truck size={22} /></div><div><strong>{dashboard.active_order_reference ? dashboard.active_order_reference : 'No order linked'}</strong><span>Order status is not available yet.</span></div></div><button className="secondary-button" onClick={() => onNavigate('orders')}>View orders <ChevronRight size={16} /></button></article>
    </section>
    <section className="panel care-panel"><PanelHeading title="Your care team" action="View alerts" onClick={() => onNavigate('alerts')} /><div className="care-person"><div className="large-avatar navy">{dashboard.doctor_name ? dashboard.doctor_name.slice(0, 2).toUpperCase() : '—'}</div><div><strong>{dashboard.doctor_name ?? 'No clinician linked'}</strong><span>Care-team profile</span></div></div><div className="care-actions"><button className="secondary-button" onClick={() => onNavigate('documents')}><FileText size={16} /> Documents</button><button className="ghost-button" onClick={() => onNavigate('alerts')}><Bell size={16} /> Alerts</button></div></section>
  </>;
}

function DoctorDashboard({ onNavigate }: { onNavigate: (page: Page) => void }) {
  return <section className="panel workspace-empty"><h2>Doctor dashboard data is not connected</h2><p>Patient roster and clinical metrics will appear here when the doctor API is available.</p><button className="secondary-button" onClick={() => onNavigate('patients')}>Open patient roster <ChevronRight size={15} /></button></section>;
}

function SupplierDashboard({ onNavigate }: { onNavigate: (page: Page) => void }) {
  return <section className="panel workspace-empty"><h2>Supplier dashboard data is not connected</h2><p>Live order queue and inventory data are not available from the backend yet.</p><button className="secondary-button" onClick={() => onNavigate('orders')}>Open orders <ChevronRight size={15} /></button></section>;
}

function PanelHeading({ title, action, onClick }: { title: string; action: string; onClick: () => void }) { return <div className="panel-heading"><h2>{title}</h2><button className="text-button" onClick={onClick}>{action}<ChevronRight size={15} /></button></div>; }

export default App;
