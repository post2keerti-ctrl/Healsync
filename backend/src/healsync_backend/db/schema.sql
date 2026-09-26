PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    firebase_uid TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('patient', 'doctor', 'supplier')),
    device_token TEXT NOT NULL DEFAULT '',
    location_lat REAL,
    location_lng REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS doctor_profiles (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    specialty TEXT NOT NULL DEFAULT '',
    license_verified INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS supplier_profiles (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    business_name TEXT NOT NULL,
    location_lat REAL NOT NULL,
    location_lng REAL NOT NULL,
    avg_item_cost REAL NOT NULL DEFAULT 6.0,
    avg_dispatch_hours REAL NOT NULL DEFAULT 4.0
);

CREATE TABLE IF NOT EXISTS patient_profiles (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    doctor_id TEXT REFERENCES doctor_profiles(id),
    surgery_type TEXT NOT NULL DEFAULT '',
    recovery_day INTEGER NOT NULL DEFAULT 1 CHECK (recovery_day > 0),
    recovery_total_days INTEGER NOT NULL DEFAULT 14 CHECK (recovery_total_days > 0),
    confidence_score INTEGER NOT NULL DEFAULT 90 CHECK (confidence_score BETWEEN 0 AND 100),
    location_lat REAL NOT NULL,
    location_lng REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS recovery_plan_items (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patient_profiles(id) ON DELETE CASCADE,
    day INTEGER NOT NULL CHECK (day > 0),
    time TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    doctor_adjusted INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patient_profiles(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    storage_path TEXT,
    ocr_text TEXT NOT NULL DEFAULT '',
    nlp_pipeline_mode TEXT NOT NULL,
    extracted_medicines_json TEXT NOT NULL DEFAULT '[]',
    generated_plan_items INTEGER NOT NULL DEFAULT 0,
    uploaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory_items (
    id TEXT PRIMARY KEY,
    supplier_id TEXT NOT NULL REFERENCES supplier_profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    stock_pct INTEGER NOT NULL CHECK (stock_pct BETWEEN 0 AND 100),
    unit_price REAL NOT NULL CHECK (unit_price >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    reference TEXT NOT NULL UNIQUE,
    patient_id TEXT NOT NULL REFERENCES patient_profiles(id),
    supplier_id TEXT REFERENCES supplier_profiles(id),
    items_json TEXT NOT NULL,
    total_amount REAL NOT NULL CHECK (total_amount >= 0),
    status TEXT NOT NULL,
    match_score REAL NOT NULL,
    distance_km REAL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patient_profiles(id) ON DELETE CASCADE,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    resolved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    sent_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_patient_plan_day ON recovery_plan_items(patient_id, day);
CREATE INDEX IF NOT EXISTS idx_orders_patient_created ON orders(patient_id, created_at);
CREATE INDEX IF NOT EXISTS idx_orders_supplier_status ON orders(supplier_id, status);
CREATE INDEX IF NOT EXISTS idx_alerts_patient_created ON alerts(patient_id, created_at);
