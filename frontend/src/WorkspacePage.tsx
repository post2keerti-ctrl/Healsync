import { useEffect, useState, type ChangeEvent } from 'react';
import { Bell, ChevronRight, Clock3, FileText, HeartPulse, PackageCheck, Upload, UserRound, X } from 'lucide-react';
import { api, type CareAlert, type DoctorAlert, type DoctorPatient, type InventoryItem, type PatientDocument, type PatientOrder, type RecoveryPlanItem, type SuggestedItem, type SupplierOrder } from './lib/api';
import './workspace.css';

type Role = 'patient' | 'doctor' | 'supplier';
type Page = 'dashboard' | 'documents' | 'recovery' | 'orders' | 'patients' | 'inventory' | 'alerts';

export function WorkspacePage({ role, page }: { role: Role; page: Page }) {
  const [plan, setPlan] = useState<RecoveryPlanItem[]>([]);
  const [alerts, setAlerts] = useState<CareAlert[]>([]);
  const [doctorAlerts, setDoctorAlerts] = useState<DoctorAlert[]>([]);
  const [documents, setDocuments] = useState<PatientDocument[]>([]);
  const [patients, setPatients] = useState<DoctorPatient[]>([]);
  const [orders, setOrders] = useState<PatientOrder[]>([]);
  const [suggestions, setSuggestions] = useState<SuggestedItem[]>([]);
  const [supplierOrders, setSupplierOrders] = useState<SupplierOrder[]>([]);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [selectedDocumentId, setSelectedDocumentId] = useState('');
  const [expandedPatientId, setExpandedPatientId] = useState('');

  useEffect(() => {
    const token = localStorage.getItem('healsync_token');
    if (!token) return;
    const patientRequest = role === 'patient' && ['recovery', 'alerts', 'documents', 'orders'].includes(page);
    const doctorRequest = role === 'doctor' && ['patients', 'alerts'].includes(page);
    const supplierRequest = role === 'supplier' && ['orders', 'inventory'].includes(page);
    if (!patientRequest && !doctorRequest && !supplierRequest) return;

    let active = true;
    setLoading(true);
    setError('');
    const request = role === 'supplier'
      ? page === 'orders'
        ? api.supplierOrders(token).then((data) => { if (active) setSupplierOrders(data); })
        : api.supplierInventory(token).then((data) => { if (active) setInventory(data); })
      : role === 'doctor'
      ? page === 'alerts'
        ? api.doctorAlerts(token).then((data) => { if (active) setDoctorAlerts(data); })
        : api.doctorPatients(token).then((data) => { if (active) setPatients(data); })
      : page === 'orders'
        ? api.patientOrders(token).then((data) => { if (active) setOrders(data); })
        : page === 'recovery'
        ? api.recoveryPlan(token).then((data) => { if (active) setPlan(data); })
        : page === 'alerts'
          ? api.alerts(token).then((data) => { if (active) setAlerts(data); })
          : api.documents(token).then((data) => {
            if (active) {
              setDocuments(data);
              setSelectedDocumentId((current) => current || data[0]?.id || '');
            }
          });
    request.catch((requestError: unknown) => {
      if (active) setError(requestError instanceof Error ? requestError.message : 'Could not load this information.');
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [page, role]);

  useEffect(() => {
    if (role !== 'patient' || page !== 'documents' || !selectedDocumentId) {
      setSuggestions([]);
      return;
    }
    const token = localStorage.getItem('healsync_token');
    if (!token) return;
    let active = true;
    api.documentSuggestions(selectedDocumentId, token).then((data) => {
      if (active) setSuggestions(data);
    }).catch(() => {
      if (active) setSuggestions([]);
    });
    return () => { active = false; };
  }, [page, role, selectedDocumentId]);

  const uploadDocument = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const token = localStorage.getItem('healsync_token');
    if (!token) {
      setError('Sign in again before uploading a prescription.');
      return;
    }
    setLoading(true);
    setError('');
    setNotice('Uploading and reading the prescription...');
    try {
      const document = await api.uploadDocument(file, token);
      setDocuments((current) => [document, ...current.filter((item) => item.id !== document.id)]);
      setSelectedDocumentId(document.id);
      setNotice(document.ocr_text ? 'Prescription text read successfully. The document writing is shown below.' : 'Document saved, but no readable text was found.');
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Could not upload this document.');
      setNotice('');
    } finally {
      setLoading(false);
      event.target.value = '';
    }
  };

  if (page === 'recovery' && role === 'patient') return <section className="panel workspace-panel">
    <div className="panel-heading"><h2><HeartPulse size={19} /> Recovery plan</h2><span>{loading ? 'Loading...' : `${plan.length} items`}</span></div>
    <p className="workspace-intro">Your schedule from the patient record.</p>
    {error && <p className="workspace-notice error-notice" role="alert">{error}</p>}
    {plan.length ? <div className="workspace-list">{plan.map((item) => <div className="workspace-row" key={item.id}><time><Clock3 size={15} />{item.time}</time><div><strong>{item.title}</strong><small>{item.description}</small></div><span className="status-pill active">Day {item.day}</span></div>)}</div> : !loading && !error && <div className="workspace-empty">No recovery items are recorded.</div>}
  </section>;

  if (page === 'documents' && role === 'patient') {
    const selectedDocument = documents.find((document) => document.id === selectedDocumentId);
    const detectedMedicines = selectedDocument
      ? selectedDocument.medicines.length
        ? selectedDocument.medicines
        : selectedDocument.ocr_text.split(/\r?\n/).map((line) => line.trim()).filter((line) => /\b(?:parah|paracetamol|amoxicillin|ibuprofen|tablet|tab|capsule|cap|syrup|ointment|cream|drops?)\b/i.test(line)).map((line) => line.replace(/\bparah\b/gi, 'Paracetamol'))
      : [];
    return <section className="panel workspace-panel">
      <div className="panel-heading"><h2><FileText size={19} /> Documents & prescriptions</h2><label className="secondary-button upload-control"><Upload size={16} /> Add document<input type="file" accept=".pdf,.txt,.text,.png,.jpg,.jpeg,.tif,.tiff" onChange={uploadDocument} /></label></div>
      <p className="workspace-intro">Upload a PDF, text prescription, or clear photo. Detected prescription items appear below for review before you add them to your plan.</p>
      {notice && <p className="workspace-notice" role="status">{notice}</p>}
      {error && <p className="workspace-notice error-notice" role="alert">{error}</p>}
      {loading && <p className="workspace-empty">Working on your document...</p>}
      {documents.length ? <div className="document-layout">
        <div className="workspace-list document-list">{documents.map((document) => <button className={`document-link ${document.id === selectedDocumentId ? 'selected' : ''}`} key={document.id} onClick={() => setSelectedDocumentId(document.id)}><FileText size={17} /><span><strong>{document.filename}</strong><small>{new Date(document.uploaded_at).toLocaleDateString()}</small></span><ChevronRight size={15} /></button>)}</div>
        {selectedDocument && <article className="prescription-reader"><div className="panel-heading"><h3>Prescription writing</h3><span className="status-pill done">{selectedDocument.extraction_mode}</span></div>{detectedMedicines.length > 0 && <section className="prescription-medicine-section"><h4>Medicines found</h4><ul className="prescription-items">{detectedMedicines.map((medicine) => <li key={medicine}>{medicine}</li>)}</ul></section>}{suggestions.length > 0 && <section className="purchase-suggestions"><h4>Useful items to buy together</h4><div className="suggestion-list">{suggestions.map((item) => <div className="suggestion-card" key={item.name}><div><strong>{item.name}</strong><small>{item.reason}</small></div><span>₹{item.price.toFixed(2)}</span></div>)}</div></section>}{selectedDocument.ocr_text ? <><h4>Document text</h4><pre aria-label="Extracted prescription text">{selectedDocument.ocr_text}</pre></> : <p className="workspace-empty">No readable writing was found in this document. Try a clearer scan or photo.</p>}</article>}
      </div> : !loading && <div className="workspace-empty">No documents yet. Add a PDF, text file, or prescription image.</div>}
    </section>;
  }

  if (page === 'alerts' && role === 'patient') return <section className="panel workspace-panel">
    <div className="panel-heading"><h2>Care alerts</h2><span>{loading ? 'Loading...' : `${alerts.filter((item) => !item.resolved).length} open`}</span></div>
    <p className="workspace-intro">Reminders recorded for your patient profile.</p>
    {error && <p className="workspace-notice error-notice" role="alert">{error}</p>}
    {alerts.length ? <div className="workspace-list">{alerts.map((alert) => <div className="workspace-row alert-row" key={alert.id}><span className={`alert-mark ${alert.severity}`} /><div><strong>{alert.message}</strong><small>{new Date(alert.created_at).toLocaleString()}</small></div><span className={`status-pill ${alert.resolved ? 'done' : 'active'}`}>{alert.resolved ? 'Resolved' : 'Open'}</span></div>)}</div> : !loading && !error && <div className="workspace-empty">No alerts are recorded.</div>}
  </section>;

  if (page === 'patients' && role === 'doctor') return <section className="panel workspace-panel">
    <div className="panel-heading"><h2><UserRound size={19} /> Patient roster</h2><span>{loading ? 'Loading...' : `${patients.length} assigned`}</span></div>
    <p className="workspace-intro">Recovery status for patients assigned to your clinical profile.</p>
    {error && <p className="workspace-notice error-notice" role="alert">{error}</p>}
    {patients.length ? <div className="workspace-list">{patients.map((patient) => <article className="patient-roster-row" key={patient.id}><div className="patient-roster-main"><div className="large-avatar navy">{patient.name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</div><div><strong>{patient.name}</strong><small>{patient.surgery_type} · Day {patient.recovery_day} of {patient.recovery_total_days}</small></div><strong className="patient-score">{patient.recovery_percent}%</strong>{patient.fully_recovered && <span className="status-pill done">Fully recovered</span>}<button className="ghost-button" onClick={() => setExpandedPatientId(expandedPatientId === patient.id ? '' : patient.id)}>{expandedPatientId === patient.id ? 'Close' : 'Details'}</button></div>{expandedPatientId === patient.id && <div className="patient-recovery-detail"><div className="recovery-meter"><i style={{ width: `${patient.recovery_percent}%` }} /></div><p>{patient.fully_recovered ? 'Recovery plan completed. 100% recovery milestone reached.' : `${patient.recovery_percent}% recovery confidence recorded.`}</p></div>}</article>)}</div> : !loading && !error && <div className="workspace-empty">No patients are assigned to your account.</div>}
  </section>;

  if (page === 'alerts' && role === 'doctor') return <section className="panel workspace-panel">
    <div className="panel-heading"><h2><Bell size={19} /> Care alerts</h2><span>{loading ? 'Loading...' : `${doctorAlerts.filter((item) => !item.resolved).length} open`}</span></div>
    <p className="workspace-intro">Recovery changes and care items for your assigned patients.</p>
    {error && <p className="workspace-notice error-notice" role="alert">{error}</p>}
    {doctorAlerts.length ? <div className="workspace-list">{doctorAlerts.map((alert) => <article className="workspace-row alert-row" key={alert.id}><span className={`alert-mark ${alert.severity}`} /><div><strong>{alert.patient_name}</strong><small>{alert.message}</small><small>{new Date(alert.created_at).toLocaleString()}</small></div><span className={`status-pill ${alert.resolved ? 'done' : 'active'}`}>{alert.resolved ? 'Resolved' : 'Open'}</span></article>)}</div> : !loading && !error && <div className="workspace-empty">No care alerts are recorded for your patients.</div>}
  </section>;
  if (page === 'alerts') return <section className="panel workspace-empty"><h2>Clinical alert feed is not connected</h2><p>Alerts for this account type are not available from the backend yet.</p></section>;
  if (page === 'orders' && role === 'patient') return <section className="panel workspace-panel">
    <div className="panel-heading"><h2><PackageCheck size={19} /> Your orders</h2><span>{loading ? 'Loading...' : `${orders.length} orders`}</span></div>
    <p className="workspace-intro">Orders linked to your patient record.</p>
    {error && <p className="workspace-notice error-notice" role="alert">{error}</p>}
    {orders.length ? <div className="workspace-list">{orders.map((order) => <article className="order-detail" key={order.id}><div className="order-summary"><small>ORDER</small><strong>{order.reference}</strong><span>{order.items.map((item) => item.name ?? 'Medical item').join(', ') || 'Medical supplies'} · ₹{order.total_amount.toFixed(2)}</span></div><div className="order-actions"><span className="status-pill active">{order.status}</span><button className="secondary-button" onClick={() => setSelectedOrderId(selectedOrderId === order.id ? '' : order.id)}>{selectedOrderId === order.id ? 'Hide details' : 'View details'} <ChevronRight size={15} /></button></div>{selectedOrderId === order.id && <div className="order-expanded"><strong>Order details</strong><span>Items: {order.items.map((item) => `${item.name ?? 'Medical item'}${item.quantity ? ` × ${item.quantity}` : ''}`).join(', ') || 'Medical supplies'}</span><span>Status: {order.status} · Match score: {Math.round(order.match_score * 100)}%</span><span>Delivery distance: {order.distance_km} km · Placed {new Date(order.created_at).toLocaleString()}</span></div>}</article>)}</div> : !loading && !error && <div className="workspace-empty">No orders are linked to your account yet.</div>}
  </section>;
  if (page === 'orders' && role === 'supplier') return <section className="panel workspace-panel">
    <div className="panel-heading"><h2><PackageCheck size={19} /> Supplier orders</h2><span>{loading ? 'Loading...' : `${supplierOrders.length} orders`}</span></div>
    <p className="workspace-intro">Orders waiting for fulfilment from your supply account.</p>
    {error && <p className="workspace-notice error-notice" role="alert">{error}</p>}
    {supplierOrders.length ? <div className="workspace-list">{supplierOrders.map((order) => <article className="order-detail" key={order.id}><div className="order-summary"><small>ORDER</small><strong>{order.reference}</strong><span>{order.items.map((item) => item.name ?? 'Medical item').join(', ')} · ₹{order.total_amount.toFixed(2)}</span></div><div className="order-actions"><span className="status-pill active">{order.status}</span><span className="delivery-state">{Math.round(order.match_score * 100)}% match</span></div></article>)}</div> : !loading && !error && <div className="workspace-empty">No supplier orders are available.</div>}
  </section>;
  if (page === 'orders') return <section className="panel workspace-empty"><h2>Order data is not connected</h2><p>No live order records are available for this account yet.</p></section>;
  if (page === 'inventory' && role === 'supplier') return <section className="panel workspace-panel">
    <div className="panel-heading"><h2><PackageCheck size={19} /> Inventory</h2><span>{loading ? 'Loading...' : `${inventory.length} items`}</span></div>
    <p className="workspace-intro">Current stock and unit prices for your catalogue.</p>
    {error && <p className="workspace-notice error-notice" role="alert">{error}</p>}
    {inventory.length ? <div className="workspace-list">{inventory.map((item) => <div className="workspace-row inventory-control" key={item.id}><div><strong>{item.name}</strong><div className="inventory-meter"><i style={{ width: `${item.stock_pct}%` }} /></div></div><span>{item.stock_pct}%</span><strong>₹{item.unit_price.toFixed(2)}</strong></div>)}</div> : !loading && !error && <div className="workspace-empty">No inventory items are available.</div>}
  </section>;
  if (page === 'inventory') return <section className="panel workspace-empty"><h2>Inventory is not connected</h2><p>No live supplier stock endpoint is available yet.</p></section>;
  return <section className="panel workspace-empty">This page is not available for this account type.</section>;
}

export function NotificationsPanel({ role, onNavigate, onClose }: { role: Role; onNavigate: (page: Page) => void; onClose: () => void }) {
  const [alerts, setAlerts] = useState<CareAlert[]>([]);
  const [loading, setLoading] = useState(role === 'patient');
  const [error, setError] = useState('');

  useEffect(() => {
    if (role !== 'patient') return;
    const token = localStorage.getItem('healsync_token');
    if (!token) {
      setError('Sign in to load notifications.');
      setLoading(false);
      return;
    }
    let active = true;
    api.alerts(token).then((data) => { if (active) setAlerts(data); }).catch((requestError: unknown) => {
      if (active) setError(requestError instanceof Error ? requestError.message : 'Could not load notifications.');
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [role]);

  return <section className="notification-panel" aria-label="Notifications">
    <div className="panel-heading"><h2><Bell size={17} /> Notifications</h2><button className="icon-button notification-close" aria-label="Close notifications" onClick={onClose}><X size={16} /></button></div>
    {role !== 'patient' ? <p className="workspace-empty">Notifications are not connected for this workspace yet.</p> : loading ? <p className="workspace-empty">Loading notifications...</p> : error ? <p className="workspace-empty" role="alert">{error}</p> : alerts.length ? <div className="notification-list">{alerts.map((alert) => <article className="notification-item" key={alert.id}><span className={`alert-mark ${alert.severity}`} /><div><strong>{alert.message}</strong><small>{new Date(alert.created_at).toLocaleString()}</small></div></article>)}</div> : <p className="workspace-empty">No notifications right now.</p>}
    {role === 'patient' && <button className="text-button notification-link" onClick={() => onNavigate('alerts')}>Open care alerts <ChevronRight size={15} /></button>}
  </section>;
}