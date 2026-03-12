"""
Invoice Generator Database Models
Defines all SQLite table schemas per SRS requirements.
Tables: contractors, customers, invoices, invoice_items, dataset_items, sync_logs
"""

# SQL statements for table creation

CREATE_CONTRACTORS_TABLE = """
CREATE TABLE IF NOT EXISTS contractors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    email TEXT UNIQUE,
    phone TEXT,
    address TEXT,
    logo_path TEXT,
    business_license TEXT,
    specialty TEXT,
    role TEXT NOT NULL DEFAULT 'contractor_admin',
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_CUSTOMERS_TABLE = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contractor_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    zip_code TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced INTEGER DEFAULT 0,
    FOREIGN KEY (contractor_id) REFERENCES contractors(id)
);
"""

CREATE_INVOICES_TABLE = """
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    contractor_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    project_location TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    subtotal REAL DEFAULT 0.0,
    tax_rate REAL DEFAULT 0.0,
    tax_amount REAL DEFAULT 0.0,
    total REAL DEFAULT 0.0,
    payment_terms TEXT DEFAULT 'Due on Receipt',
    notes TEXT,
    pdf_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced INTEGER DEFAULT 0,
    FOREIGN KEY (contractor_id) REFERENCES contractors(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);
"""

CREATE_INVOICE_ITEMS_TABLE = """
CREATE TABLE IF NOT EXISTS invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    dataset_item_id INTEGER,
    item_name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    unit TEXT,
    quantity REAL NOT NULL DEFAULT 1,
    unit_price REAL NOT NULL DEFAULT 0.0,
    material_cost REAL DEFAULT 0.0,
    labor_cost REAL DEFAULT 0.0,
    total_price REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_item_id) REFERENCES dataset_items(item_id)
);
"""

CREATE_DATASET_ITEMS_TABLE = """
CREATE TABLE IF NOT EXISTS dataset_items (
    item_id INTEGER PRIMARY KEY,
    category TEXT NOT NULL,
    item_name TEXT NOT NULL,
    unit TEXT NOT NULL,
    material_cost REAL NOT NULL DEFAULT 0.0,
    labor_cost REAL NOT NULL DEFAULT 0.0,
    total_price REAL NOT NULL DEFAULT 0.0,
    csi_code TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_CONTRACTOR_PRICING_TABLE = """
CREATE TABLE IF NOT EXISTS contractor_pricing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contractor_id INTEGER NOT NULL,
    dataset_item_id INTEGER NOT NULL,
    custom_material_cost REAL,
    custom_labor_cost REAL,
    custom_total_price REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (contractor_id) REFERENCES contractors(id),
    FOREIGN KEY (dataset_item_id) REFERENCES dataset_items(item_id),
    UNIQUE(contractor_id, dataset_item_id)
);
"""

CREATE_SYNC_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS sync_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP
);
"""

ALL_TABLES = [
    CREATE_CONTRACTORS_TABLE,
    CREATE_CUSTOMERS_TABLE,
    CREATE_INVOICES_TABLE,
    CREATE_INVOICE_ITEMS_TABLE,
    CREATE_DATASET_ITEMS_TABLE,
    CREATE_CONTRACTOR_PRICING_TABLE,
    CREATE_SYNC_LOGS_TABLE,
]
