export type Role = 'patient' | 'doctor' | 'supplier';

export type User = {
  id: string;
  firebase_uid: string;
  name: string;
  email: string;
  role: Role;
};

export type RecoveryPlanItem = {
  id: string;
  day: number;
  time: string;
  title: string;
  description: string;
  category: 'medicine' | 'meal' | 'exercise' | 'checkup';
  doctor_adjusted: boolean;
};

export type CareAlert = {
  id: string;
  patient_id: string;
  severity: string;
  message: string;
  resolved: boolean;
  created_at: string;
};

export type DoctorAlert = CareAlert & {
  patient_name: string;
};

export type PatientDashboardData = {
  patient_name: string;
  recovery_day: number;
  recovery_total_days: number;
  confidence_score: number;
  doctor_name: string | null;
  today_items: RecoveryPlanItem[];
  active_order_reference: string | null;
};

export type PatientOrder = {
  id: string;
  reference: string;
  items: Array<{ name?: string; quantity?: number; [key: string]: unknown }>;
  total_amount: number;
  status: string;
  match_score: number;
  distance_km: number;
  created_at: string;
};

export type SupplierOrder = PatientOrder & { patient_id: string };

export type InventoryItem = {
  id: string;
  name: string;
  stock_pct: number;
  unit_price: number;
};

export type ExtractedMedicine = {
  name: string;
  dosage: string;
  frequency: string;
  days: number;
};

export type PatientDocument = {
  id: string;
  filename: string;
  ocr_text: string;
  extraction_mode: string;
  medicines: string[];
  generated_plan_items: number;
  uploaded_at: string;
};

export type SuggestedItem = {
  name: string;
  category: string;
  reason: string;
  price: number;
  triggered_by: string;
};

export type DoctorPatient = {
  id: string;
  name: string;
  email: string;
  surgery_type: string;
  recovery_day: number;
  recovery_total_days: number;
  recovery_percent: number;
  fully_recovered: boolean;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8002';

function normalisePath(path: string): string {
  return path.startsWith('/') ? path : `/${path}`;
}

export async function apiRequest<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(`${API_BASE_URL}${normalisePath(path)}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.text();
    let message = body;
    try {
      const parsed = JSON.parse(body) as { detail?: string };
      if (parsed.detail) message = parsed.detail;
    } catch {
      // Keep non-JSON response bodies as the error message.
    }
    throw new Error(message || `Request failed with status ${response.status}`);
  }
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    return response.json() as Promise<T>;
  }
  return response.text() as unknown as Promise<T>;
}

export const api = {
  currentUser: (token: string) => apiRequest<User>('/me', {}, token),
  dashboard: (token: string) => apiRequest<PatientDashboardData>('/patients/me/dashboard', {}, token),
  patientOrders: (token: string) => apiRequest<PatientOrder[]>('/patients/me/orders', {}, token),
  recoveryPlan: (token: string) => apiRequest<RecoveryPlanItem[]>('/patients/me/recovery-plan', {}, token),
  alerts: (token: string) => apiRequest<CareAlert[]>('/patients/me/alerts', {}, token),
  documents: (token: string) => apiRequest<PatientDocument[]>('/patients/me/documents', {}, token),
  doctorPatients: (token: string) => apiRequest<DoctorPatient[]>('/doctors/me/patients', {}, token),
  doctorAlerts: (token: string) => apiRequest<DoctorAlert[]>('/doctors/me/alerts', {}, token),
  supplierOrders: (token: string) => apiRequest<SupplierOrder[]>('/suppliers/me/orders', {}, token),
  supplierInventory: (token: string) => apiRequest<InventoryItem[]>('/suppliers/me/inventory', {}, token),
  uploadDocument: (file: File, token: string) => {
    const body = new FormData();
    body.append('file', file);
    return apiRequest<PatientDocument>('/patients/me/documents', { method: 'POST', body }, token);
  },
  addPrescriptionItems: (documentId: string, token: string) => apiRequest<{ added: string[] }>(`/patients/me/documents/${encodeURIComponent(documentId)}/add-prescription-items`, { method: 'POST' }, token),
  documentSuggestions: (documentId: string, token: string) => apiRequest<SuggestedItem[]>(`/patients/me/documents/${encodeURIComponent(documentId)}/suggestions`, {}, token),
};
