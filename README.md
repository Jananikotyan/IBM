# Sehat Saathi 🏥
### Multilingual AI Healthcare Awareness Assistant for Rural & Underserved Communities

Powered by **IBM watsonx.ai (Granite models)** + **LangChain** + **RAG**

---

## Overview

Sehat Saathi ("Health Companion" in Hindi) is an AI-powered healthcare awareness assistant designed for rural and underserved communities in India and beyond. It helps users:

- **Triage symptoms** into actionable care tiers (self-care / see a doctor / urgent care)
- **Find nearby healthcare facilities** (PHCs, hospitals, clinics)
- **Track vaccination schedules** for children and pregnant women
- **Get preventive health guidance** grounded in WHO/MoHFW documents
- **Communicate in their native language** — Hindi, Tamil, Bengali, Telugu, and more

> ⚠️ Sehat Saathi is an awareness tool — not a diagnostic system. Always consult a qualified healthcare professional for diagnosis and treatment.

---

## Architecture

```
User Input (Text/Voice)
        │
        ▼
Watson Language Translator (detect & translate to English)
        │
        ▼
Deterministic Safety Layer (keyword-intercept guardrail)
   ├── RED FLAG detected → emergency_escalation_tool → Return helplines
   └── Safe → LangChain Agent
                    │
          ┌─────────┴──────────┐
          │   RAG Retrieval    │
          │ (Chroma/FAISS +    │
          │  WHO/MoHFW docs)   │
          └─────────┬──────────┘
                    │
         ┌──────────┴───────────┐
         │   Tool Router        │
         ├── symptom_triage_tool
         ├── facility_locator_tool
         ├── vaccination_schedule_tool
         └── emergency_escalation_tool
                    │
                    ▼
         IBM watsonx.ai Granite LLM
                    │
                    ▼
         Watson Language Translator (translate back to user's language)
                    │
                    ▼
              User Response
```

## Tech Stack

| Layer | Technology |
|---|---|
| Core LLM | IBM watsonx.ai (Granite-13b-chat) |
| Orchestration | LangChain Agents + Router Chain |
| Memory | ConversationBufferMemory |
| RAG | Chroma / FAISS + sentence-transformers |
| Multilingual | IBM Watson Language Translator |
| Voice (optional) | IBM Watson Speech-to-Text |
| Facility Locator | Google Places API / OpenStreetMap |
| Backend | Python + FastAPI |
| Frontend | Streamlit |

---

## Project Structure

```
sehat-saathi/
├── app/
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── sehat_agent.py          # Main LangChain agent
│   │   ├── safety_layer.py         # Deterministic keyword guardrail
│   │   └── memory.py               # Conversation memory management
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── symptom_triage.py       # Symptom risk scoring tool
│   │   ├── facility_locator.py     # Nearby PHC/hospital finder
│   │   ├── vaccination_schedule.py # Immunization due date calculator
│   │   └── emergency_escalation.py # Emergency helplines tool
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── vector_store.py         # Chroma/FAISS vector DB setup
│   │   └── document_loader.py      # WHO/MoHFW document ingestion
│   ├── multilingual/
│   │   ├── __init__.py
│   │   └── translator.py           # Watson Language Translator wrapper
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py               # FastAPI route definitions
│   │   └── schemas.py              # Pydantic request/response models
│   └── config.py                   # App configuration
├── frontend/
│   └── streamlit_app.py            # Streamlit chat UI
├── data/
│   ├── knowledge_base/             # WHO/MoHFW PDF/text documents
│   └── vector_store/               # Persisted Chroma vector DB
├── scripts/
│   └── ingest_documents.py         # One-time document ingestion script
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

### 1. Clone and Install

```bash
git clone https://github.com/your-org/sehat-saathi.git
cd sehat-saathi
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Ingest Knowledge Base Documents

Place WHO guidelines and MoHFW documents (PDF or TXT) in `data/knowledge_base/`, then run:

```bash
python scripts/ingest_documents.py
```

### 4. Run the Backend

```bash
uvicorn app.api.routes:app --reload --port 8000
```

### 5. Run the Frontend

```bash
streamlit run frontend/streamlit_app.py
```

---

## Usage Examples

**Symptom Query (Hindi):**
> "Mujhe 2 din se bukhaar hai aur sar dard ho raha hai"
> *(I've had fever for 2 days and a headache)*

**Vaccination Query:**
> "My baby is 6 weeks old. What vaccines are due?"

**Facility Locator:**
> "Where is the nearest government hospital? My pincode is 110001"

**Emergency (Red-flag - auto-escalated):**
> "I'm having severe chest pain and can't breathe"
> → Immediately returns: **Call 108 (Ambulance) NOW**

---

## Safety & Disclaimer

- Sehat Saathi is NOT a medical diagnostic tool.
- All symptom triage is for awareness only — always confirm with a doctor.
- Emergency red-flag queries bypass the LLM entirely and return hardcoded helplines.
- Drug names, dosages, and prescriptions are never provided.

---

## License

MIT License — built for public health awareness.
