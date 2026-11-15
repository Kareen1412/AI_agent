# MACOT — AI Clothing Store Assistant

MACOT is an AI-powered assistant for an online clothing store. It answers customer questions about products, sizes, colors, prices, and availability; collects order details; prepares backend-validated quotes; and confirms orders after the customer explicitly approves the quote. The backend updates inventory in Firebase Firestore, while a separate owner dashboard displays orders and stock.

## Tech stack

Python · Google Gemini API · FastAPI · Streamlit · Firebase Cloud Firestore · Firebase Admin SDK · HTTPX · Pandas

## Project structure

```text
AI_agent/
├── agent/                         # Gemini-powered shopping agent
├── backend/
│   ├── main.py                    # FastAPI backend
│   ├── firebase_client.py         # Firebase connection
│   ├── requirements.txt
│   ├── seed_db.py                 # Optional database initialization
│   └── set_delivery_fee.py        # Optional delivery-fee configuration
├── macot_integration/
│   ├── customer/customer_chat.py  # Customer Streamlit interface
│   ├── dashboard/app.py           # Owner Streamlit interface
│   ├── .env                       # Local configuration (not committed)
│   └── requirements.txt
├── .env                           # Local configuration (not committed)
├── .gitignore
└── requirements.txt
```

Other folders may contain experiments, tests, or integration code; they are not required to start the three services below.

## Prerequisites

- Python installed (prefer a version supported by the dependencies in `requirements.txt`)
- Git
- Internet access for the Gemini API and Firebase
- A valid Gemini API key
- Authorized Firebase project credentials and an initialized Firestore database

> **Security:** Never commit `.env` files, `backend/serviceAccountKey.json`, or other private keys. If a key was previously exposed or committed, revoke it and replace it; adding it to `.gitignore` does not remove it from Git history.

## 1. Clone and install

Clone the repository and enter its root directory (`AI_agent` in the commands below):

```bash
git clone <YOUR_REPOSITORY_URL>
cd <YOUR_REPOSITORY_DIRECTORY>
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r backend/requirements.txt
python -m pip install -r macot_integration/requirements.txt
```

### Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r backend/requirements.txt
python -m pip install -r macot_integration/requirements.txt
```

If PowerShell blocks virtual-environment activation, use `\.venv\Scripts\python.exe` instead of `python` in subsequent commands, or change the execution policy for the current process according to your organization's rules.

## 2. Configure the two `.env` files

This repository uses **two separate `.env` files**:

1. `AI_agent/.env`
2. `AI_agent/macot_integration/.env`

Create both files locally after cloning. They are excluded from Git and therefore will not be downloaded with the repository.

**`AI_agent/.env`**

```dotenv
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
BACKEND_URL=http://127.0.0.1:8000
ADMIN_API_TOKEN=CHOOSE_A_LONG_RANDOM_ADMIN_TOKEN
```

**`AI_agent/macot_integration/.env`**

```dotenv
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
BACKEND_URL=http://127.0.0.1:8000
ADMIN_API_TOKEN=CHOOSE_A_LONG_RANDOM_ADMIN_TOKEN
```

Use the **same** `ADMIN_API_TOKEN` in both files. These are example variable names; if your local code reads additional variables, include those too. Some modules load `.env` relative to their own file or current working directory, so check the `load_dotenv(...)` paths if configuration is not detected.

### Firebase credentials

The backend uses `backend/firebase_client.py` to connect to Firestore. Configure it with an authorized Firebase service-account credential. If the current implementation reads `backend/serviceAccountKey.json`, place a **private, securely provided** credential file there locally; do not commit it. Alternatively, adapt `firebase_client.py` to use Google Application Default Credentials.

The Firestore database must already contain the necessary shop configuration and product data. The repository includes `backend/seed_db.py` and `backend/set_delivery_fee.py` for initial setup; review their behavior before running them because they may write to Firestore.

## 3. Run MACOT locally

Open **three separate terminals**. Keep all three running. Start each terminal in the repository root (`AI_agent`) and activate the same virtual environment.

### Terminal 1 — FastAPI backend

**macOS / Linux**

```bash
source .venv/bin/activate
cd backend
python -m uvicorn main:app --reload --port 8000
```

**Windows (PowerShell)**

```powershell
.\.venv\Scripts\Activate.ps1
cd backend
python -m uvicorn main:app --reload --port 8000
```

Backend: http://127.0.0.1:8000  
API documentation: http://127.0.0.1:8000/docs

### Terminal 2 — Customer chatbot

**macOS / Linux**

```bash
source .venv/bin/activate
python -m streamlit run macot_integration/customer/customer_chat.py --server.port 8501
```

**Windows (PowerShell)**

```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run macot_integration/customer/customer_chat.py --server.port 8501
```

Customer chatbot: http://localhost:8501

Enter a customer's phone number to open a conversation. The phone number is passed to the AI agent as the customer ID. The Streamlit interface holds its displayed chat list in session memory; this is not a verified phone-number login system, and the agent may maintain its own state separately.

### Terminal 3 — Owner dashboard

**macOS / Linux**

```bash
source .venv/bin/activate
python -m streamlit run macot_integration/dashboard/app.py --server.port 8502
```

**Windows (PowerShell)**

```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run macot_integration/dashboard/app.py --server.port 8502
```

Owner dashboard: http://localhost:8502

The dashboard reads backend data for its overview, orders, and inventory views. The admin API token must match the backend configuration.

## 4. Quick verification

1. Visit http://127.0.0.1:8000/docs to check that FastAPI started.
2. Visit http://localhost:8501 and ask about a product.
3. Visit http://localhost:8502 and check that the dashboard connects to the backend.
4. For order testing, use a demo Firebase project and test products; successful order confirmation may change inventory.

## Troubleshooting

| Problem | What to check |
|---|---|
| `ModuleNotFoundError` | Activate `.venv` and install all three requirements files. |
| Backend connection refused | Start Terminal 1 first; check that `BACKEND_URL` is `http://127.0.0.1:8000`. |
| Dashboard shows `401` or `503` | Check that `ADMIN_API_TOKEN` is configured consistently in both `.env` files and that the backend has restarted. |
| Firebase credentials error | Confirm `firebase_client.py` points to a valid, authorized credential and the correct Firebase project. |
| Gemini API error | Check `GEMINI_API_KEY`, API access, quotas, and network connectivity. |
| Port already in use | Stop the existing process or choose another port, then update URLs accordingly. |

## Notes

- This is a local development/demo setup, **not** a production deployment.
- The customer chat and owner dashboard run as separate Streamlit applications.
- The backend must be running for product and order operations.
- Do not expose the owner dashboard publicly without proper authentication and authorization.
- Never share real customer data or production credentials with repository recipients unless they are explicitly authorized.
