# Invoice Generator – AI-Powered Smart Invoice System for Construction

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview
Invoice Generator is an AI-powered voice invoicing platform designed for construction professionals. It converts spoken instructions into professional invoices by understanding construction terminology and mapping it to a standardized dataset.

> **Note:** This project runs locally with offline-first capabilities. You'll need to set up your own API keys (see setup instructions below).

## Features
- **Voice Invoice Creation** – Create invoices using natural speech
- **AI-Powered NLP** – Intent recognition & entity extraction for construction terms
- **100-Item Dataset** – CSI MasterFormat construction materials database
- **Offline-First** – Full functionality without internet using SQLite
- **PDF Export** – Professional invoice generation
- **Web Dashboard** – Customer, invoice, and dataset management
- **Multi-Tenant** – Isolated contractor data with role-based access
- **Cloud-Ready** – Sync to PostgreSQL when online

## Tech Stack
| Component | Technology |
|-----------|-----------|
| Backend | Python 3.10+ / FastAPI |
| AI/NLP | spaCy, rule-based intent/NER |
| Speech-to-Text | Vosk (offline) |
| Database | SQLite (local) / PostgreSQL (cloud) |
| Frontend | HTML/CSS/JS + Jinja2 templates |
| PDF Generation | ReportLab |

## Project Structure
```
Invoice-Generator/
├── backend/          # Core application configuration
├── frontend/         # Web dashboard (HTML/CSS/JS)
├── ai_engine/        # Voice processing, NLP, intent, NER
├── dataset/          # Master dataset (CSV)
├── database/         # SQLite database & models
├── services/         # Business logic services
├── api/              # FastAPI routes
├── invoices/         # Invoice generation & PDF output
├── tests/            # Test suite
├── scripts/          # Utility scripts
├── docs/             # Documentation
├── .env.example      # Environment template (copy to .env)
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

## Getting Started

### Prerequisites
- Python 3.10+
- A free [Groq API key](https://console.groq.com) (for AI-powered parsing)

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/Invoice-Generator.git
cd Invoice-Generator
```

### 2. Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate     # Windows
source venv/bin/activate  # Linux/Mac
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 4. Configure Environment
```bash
cp .env.example .env     # Linux/Mac
copy .env.example .env   # Windows
```
Then edit `.env` and add your API keys.

### 5. Initialize Database & Dataset
```bash
python scripts/init_db.py
python scripts/load_dataset.py
```

### 6. Download Vosk Model (for offline STT)
```bash
python scripts/download_vosk_model.py
```

### 7. Run the Application
```bash
python -m uvicorn api.main:app --reload --port 8000
```

### 8. Open Dashboard
Navigate to `http://localhost:8000` in your browser.

## API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/voice-input | Process voice audio |
| POST | /api/create-invoice | Create new invoice |
| POST | /api/add-item | Add item to invoice |
| POST | /api/remove-item | Remove item from invoice |
| POST | /api/finalize-invoice | Finalize and generate PDF |
| GET | /api/customers | List customers |
| POST | /api/customers | Create customer |
| GET | /api/invoices | List invoices |
| GET | /api/invoices/{id} | Get invoice details |
| GET | /api/dataset | Browse dataset |

## License
MIT License – For educational / portfolio purposes.
