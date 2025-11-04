# Loan Assistant

Minimal steps to run the Streamlit loan assistant locally.

## 1. Create and activate a virtual environment
```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux
```

## 2. Install dependencies inside the venv
```bash
pip install -r requirements.txt
```

## 3. Configure Watsonx credentials
Copy the example file and fill in your API key (keep the real `.env` out of version control):
```bash
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
```
Edit `.env` to set `WATSONX_API_KEY` (and adjust other values if needed).

## 4. Load reference documents (optional but recommended)
This populates the shared loan guides into `document_index/documents.db`:
```bash
python load_reference_documents.py
```

## 5. Start the Streamlit app
```bash
streamlit run watsonx_chat.py
```

The app will create any missing folders (`uploads/`, `document_index/`) automatically.
