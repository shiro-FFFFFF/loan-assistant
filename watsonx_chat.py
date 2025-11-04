import streamlit as st
import requests
import os
import json
import hashlib
import tempfile
import base64
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import concurrent.futures
from PIL import Image
import fitz  # PyMuPDF for PDF handling
import sqlite3
import uuid
from dotenv import load_dotenv, find_dotenv

# Load environment variables from .env when available
dotenv_loaded = False
dotenv_path = find_dotenv()
if dotenv_path:
    dotenv_loaded = load_dotenv(dotenv_path)
else:
    fallback_dotenv = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(fallback_dotenv):
        dotenv_loaded = load_dotenv(fallback_dotenv)

DEFAULT_CONFIG = {
    "WATSONX_PROJECT_ID": "6344e97c-4a5a-4585-af06-e379c55b855b",
    "WATSONX_MODEL_ID": "meta-llama/llama-3-3-70b-instruct",
    "WATSONX_VISION_MODEL_ID": "meta-llama/llama-3-2-90b-vision-instruct",
    "WATSONX_IAM_URL": "https://iam.cloud.ibm.com/identity/token",
    "WATSONX_API_URL": "https://us-south.ml.cloud.ibm.com/ml/v1/text/chat?version=2023-03-29",
    "WATSONX_VISION_API_URL": "https://us-south.ml.cloud.ibm.com/ml/v1/text/chat?version=2023-03-29",
}


def resolve_config_value(key: str, *, default: Optional[str] = None, required: bool = False) -> str:
    env_value = os.getenv(key)
    value = env_value

    if not value and not dotenv_loaded:
        try:
            value = st.secrets[key]
        except KeyError:
            value = None
        except Exception:
            value = None

    if not value:
        value = default

    if value and not env_value:
        os.environ[key] = value

    if required and not value:
        raise RuntimeError(
            f"{key} is not configured. Provide it via a .env file or Streamlit secrets (see https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)."
        )

    return value or ""


# Watsonx.ai configuration
API_KEY = resolve_config_value("WATSONX_API_KEY", required=True)
PROJECT_ID = resolve_config_value("WATSONX_PROJECT_ID", default=DEFAULT_CONFIG["WATSONX_PROJECT_ID"])
MODEL_ID = resolve_config_value("WATSONX_MODEL_ID", default=DEFAULT_CONFIG["WATSONX_MODEL_ID"])
VISION_MODEL_ID = resolve_config_value("WATSONX_VISION_MODEL_ID", default=DEFAULT_CONFIG["WATSONX_VISION_MODEL_ID"])
IAM_URL = resolve_config_value("WATSONX_IAM_URL", default=DEFAULT_CONFIG["WATSONX_IAM_URL"])
WATSONX_API_URL = resolve_config_value("WATSONX_API_URL", default=DEFAULT_CONFIG["WATSONX_API_URL"])
VISION_API_URL = resolve_config_value("WATSONX_VISION_API_URL", default=DEFAULT_CONFIG["WATSONX_VISION_API_URL"])

# Setup for Streamlit app
st.set_page_config(page_title="Professional Loan Assistant", layout="centered")
st.title("💼 Professional Loan Assistant")
st.markdown("*Your comprehensive loan guidance powered by AI and document analysis*")

# Create directories for file storage
UPLOAD_DIR = "uploads"
INDEX_DIR = "document_index"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(INDEX_DIR, exist_ok=True)

# Database for document index
DB_PATH = os.path.join(INDEX_DIR, "documents.db")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "uploaded_files_queue" not in st.session_state:
    st.session_state.uploaded_files_queue = []

if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()

if "document_index" not in st.session_state:
    st.session_state.document_index = {}

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "document_uploader_key" not in st.session_state:
    st.session_state.document_uploader_key = 0

if "document_uploader_reset" not in st.session_state:
    st.session_state.document_uploader_reset = False

# Initialize database
def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            content_type TEXT NOT NULL,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_hash TEXT UNIQUE,
            metadata TEXT,
            session_id TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT,
            chunk_text TEXT,
            chunk_index INTEGER,
            FOREIGN KEY (document_id) REFERENCES documents (id)
        )
    ''')

    cursor.execute("PRAGMA table_info(documents)")
    columns = [row[1] for row in cursor.fetchall()]
    if "session_id" not in columns:
        cursor.execute("ALTER TABLE documents ADD COLUMN session_id TEXT")

    conn.commit()
    conn.close()

init_database()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Get IAM token function (from test.py)
@st.cache_data
def get_iam_token(apikey: str) -> str:
    r = requests.post(
        IAM_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": apikey},
    )
    if r.status_code != 200:
        raise Exception("IAM token error: " + r.text)
    return r.json()["access_token"]

def encode_image_to_base64(image_path: str) -> str:
    """Convert image to base64 string for vision API"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def pdf_to_images(pdf_path: str) -> List[str]:
    """Convert PDF pages to images"""
    image_paths = []
    pdf_document = fitz.open(pdf_path)
    
    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))  # 2x zoom for better quality
        
        image_path = os.path.join(tempfile.gettempdir(), f"page_{page_num + 1}.png")
        pix.save(image_path)
        image_paths.append(image_path)
    
    pdf_document.close()
    return image_paths

def process_single_image(image_path: str, session_id: str) -> str:
    """Process a single image with vision model"""
    try:
        token = get_iam_token(API_KEY)
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        # Encode image
        image_b64 = encode_image_to_base64(image_path)
        
        # Prepare vision message
        body = {
            "model_id": VISION_MODEL_ID,
            "project_id": PROJECT_ID,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract and summarize all text content from this image. If it's a document page, provide a structured summary."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1000
        }
        
        resp = requests.post(VISION_API_URL, headers=headers, json=body)
        
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            return f"Error processing image: {resp.status_code} - {resp.text}"
            
    except Exception as e:
        return f"Error processing image: {str(e)}"

def process_images_parallel(image_paths: List[str], session_id: str) -> List[str]:
    """Process multiple images in parallel"""
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_path = {
            executor.submit(process_single_image, path, session_id): path 
            for path in image_paths
        }
        
        for future in concurrent.futures.as_completed(future_to_path):
            result = future.result()
            results.append(result)
    
    return results

def merge_vision_results(results: List[str], document_name: str) -> str:
    """Use Watsonx to merge and summarize vision results"""
    try:
        token = get_iam_token(API_KEY)
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        combined_text = "\n\n".join([f"Page {i+1}: {result}" for i, result in enumerate(results)])
        
        body = {
            "model_id": MODEL_ID,
            "project_id": PROJECT_ID,
            "messages": [
                {
                    "role": "user",
                    "content": f"""Please analyze and organize the following extracted text from a document called '{document_name}'. 
                    
Provide a coherent, well-structured summary that combines all the content in logical sections. 
Remove any duplicate information and organize it in a clear, readable format.

Extracted content:
{combined_text}"""
                }
            ],
            "temperature": 0.3,
            "max_tokens": 2000
        }
        
        resp = requests.post(WATSONX_API_URL, headers=headers, json=body)
        
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        else:
            return combined_text  # Fallback to combined raw results
            
    except Exception as e:
        return f"Error merging results: {str(e)}"

def compute_content_hash(content: str) -> str:
    """Compute hash of content for duplicate detection"""
    return hashlib.md5(content.encode()).hexdigest()

def chunk_text_content(text: str, chunk_size: int = 500, overlap: int = 50) -> List[Tuple[str, int]]:
    """Simple text chunking with overlap"""
    chunks = []
    words = text.split()
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        chunk_text = " ".join(chunk_words)
        chunks.append((chunk_text, i // chunk_size))
    
    return chunks

def simple_rerank(query: str, chunks: List[Tuple[str, int]], top_k: int = 3) -> List[Tuple[str, int]]:
    """Simple keyword-based reranking"""
    query_words = set(query.lower().split())
    chunk_scores = []
    
    for chunk_text, index in chunks:
        chunk_words = set(chunk_text.lower().split())
        # Simple overlap scoring
        score = len(query_words.intersection(chunk_words))
        chunk_scores.append((chunk_text, index, score))
    
    # Sort by score and return top_k
    chunk_scores.sort(key=lambda x: x[2], reverse=True)
    return [(text, idx) for text, idx, score in chunk_scores[:top_k]]

def store_document(document_id: str, filename: str, content: str, content_type: str, metadata: Dict = None, session_id: Optional[str] = None):
    """Store document in database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    file_hash = compute_content_hash(content)
    metadata_json = json.dumps(metadata or {})
    session_id = session_id or st.session_state.get("session_id")
    
    try:
        # Store document
        cursor.execute('''
            INSERT OR REPLACE INTO documents 
            (id, filename, content, content_type, file_hash, metadata, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (document_id, filename, content, content_type, file_hash, metadata_json, session_id))
        
        # Chunk and store text content
        if content_type in ['text', 'pdf', 'image']:
            chunks = chunk_text_content(content)
            for chunk_text, chunk_index in chunks:
                chunk_id = f"{document_id}_chunk_{chunk_index}"
                cursor.execute('''
                    INSERT OR REPLACE INTO chunks
                    (id, document_id, chunk_text, chunk_index)
                    VALUES (?, ?, ?, ?)
                ''', (chunk_id, document_id, chunk_text, chunk_index))
        
        conn.commit()
        
        # Update session state
        if session_id == st.session_state.get("session_id") or not metadata or metadata.get("source") == "reference_library":
            st.session_state.document_index[document_id] = {
                'filename': filename,
                'content_type': content_type,
                'content': content,
                'metadata': metadata,
                'upload_time': datetime.now().isoformat(),
                'session_id': session_id
            }
        
    except Exception as e:
        st.error(f"Error storing document: {str(e)}")
    finally:
        conn.close()

def retrieve_relevant_content(query: str, top_k: int = 3) -> List[Dict]:
    """Retrieve and rerank relevant content from stored documents with priority for user uploads"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get all chunks with source priority
        current_session = st.session_state.get('session_id')
        cursor.execute('''
            SELECT c.chunk_text, d.filename, d.content_type, d.metadata, d.session_id,
                   CASE
                       WHEN d.metadata LIKE '%"source": "reference_library"%' THEN 1
                       ELSE 0
                   END as is_user_upload
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.session_id IS NULL OR d.session_id = ?
        ''', (current_session,))
        
        chunks = []
        for row in cursor.fetchall():
            chunks.append({
                'text': row[0],
                'filename': row[1],
                'content_type': row[2],
                'metadata': json.loads(row[3]) if row[3] else {},
                'session_id': row[4],
                'is_user_upload': row[5] == 0  # True for user uploads, False for reference documents
            })
        
        conn.close()
        
        # Prioritize user uploads first, then reference documents
        user_uploads = [chunk for chunk in chunks if chunk['is_user_upload']]
        reference_docs = [chunk for chunk in chunks if not chunk['is_user_upload']]
        
        # Get top results from each category
        top_user_uploads = simple_rerank(query, [(chunk['text'], 0) for chunk in user_uploads], min(top_k, len(user_uploads)))
        remaining_slots = top_k - len(top_user_uploads)
        top_reference = simple_rerank(query, [(chunk['text'], 0) for chunk in reference_docs], remaining_slots) if remaining_slots > 0 else []
        
        # Combine results with user uploads first
        all_top_chunks = top_user_uploads + top_reference
        
        # Get metadata for top chunks
        relevant_content = []
        for chunk_text, _ in all_top_chunks:
            for chunk in chunks:
                if chunk['text'] == chunk_text:
                    relevant_content.append(chunk)
                    break
        
        return relevant_content
        
    except Exception as e:
        st.error(f"Error retrieving content: {str(e)}")
        return []
    finally:
        conn.close()

def process_uploaded_file(uploaded_file) -> str:
    """Process uploaded file based on its type"""
    file_id = str(uuid.uuid4())
    filename = uploaded_file.name
    
    try:
        if filename.lower().endswith('.pdf'):
            # Process PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(uploaded_file.getbuffer())
                tmp_path = tmp_file.name
            
            # Convert PDF to images
            image_paths = pdf_to_images(tmp_path)
            
            # Process images in parallel
            st.info("Processing PDF pages with vision model...")
            vision_results = process_images_parallel(image_paths, st.session_state.get('session_id', 'default'))
            
            # Merge results
            merged_content = merge_vision_results(vision_results, filename)
            
            # Store document
            store_document(file_id, filename, merged_content, 'pdf', {
                'pages': len(image_paths),
                'original_filename': filename
            })
            
            # Clean up temporary files
            for path in image_paths:
                try:
                    os.remove(path)
                except:
                    pass
            os.remove(tmp_path)
            
            return f"✅ Successfully processed PDF: {filename}\n\nExtracted Content:\n{merged_content}"
            
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
            # Process single image
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_file:
                tmp_file.write(uploaded_file.getbuffer())
                tmp_path = tmp_file.name
            
            st.info("Processing image with vision model...")
            vision_result = process_single_image(tmp_path, st.session_state.get('session_id', 'default'))
            
            # Store document
            store_document(file_id, filename, vision_result, 'image', {
                'original_filename': filename,
                'file_size': len(uploaded_file.getbuffer())
            })
            
            # Clean up
            os.remove(tmp_path)
            
            return f"✅ Successfully processed image: {filename}\n\nExtracted Content:\n{vision_result}"
            
        else:
            # Process as text file
            content = uploaded_file.read().decode('utf-8', errors='ignore')
            
            # Store document
            store_document(file_id, filename, content, 'text', {
                'original_filename': filename,
                'file_size': len(content)
            })
            
            return f"✅ Successfully processed text file: {filename}\n\nContent Preview:\n{content}"
            
    except Exception as e:
        return f"❌ Error processing file {filename}: {str(e)}"

# Function to send message to Watsonx.ai with RAG context
def chat_with_watsonx_rag(message: str, history: list) -> str:
    # Prepare messages for the API
    messages = history + [{"role": "user", "content": message}]
    
    try:
        # Get relevant content from document index
        relevant_content = retrieve_relevant_content(message)
        
        if relevant_content:
            # Add context to the message
            context_text = "Relevant information from uploaded documents:\n\n"
            for i, content in enumerate(relevant_content):
                context_text += f"Document {i+1} ({content['filename']}):\n{content['text']}\n\n"
            
            messages[-1]["content"] = f"{context_text}\n\nUser question: {message}\n\nPlease answer the user's question based on the provided context when relevant."
        
        # Get IAM token
        token = get_iam_token(API_KEY)
        
        # Prepare request headers
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        # Prepare request body
        body = {
            "model_id": MODEL_ID,
            "project_id": PROJECT_ID,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        # Send request to Watsonx.ai
        resp = requests.post(WATSONX_API_URL, headers=headers, json=body)
        
        if resp.status_code != 200:
            return f"Error {resp.status_code}: {resp.text}"
        
        # Extract response
        response = resp.json()["choices"][0]["message"]["content"]
        return response
        
    except Exception as e:
        return f"Error: {str(e)}"

# Enhanced professional sidebar with loan expertise
with st.sidebar:
    st.header("🏦 Professional Loan Services")
    
    # File upload section
    st.subheader("📄 Document Analysis")
    st.write("Upload your loan documents for personalized analysis:")
    if st.session_state.get("document_uploader_reset"):
        st.session_state.document_uploader_key += 1
        st.session_state.document_uploader_reset = False
    new_uploaded_files = st.file_uploader(
        "Upload loan documents (PDF, Images, Text files)",
        type=['pdf', 'png', 'jpg', 'jpeg', 'gif', 'bmp', 'txt', 'md'],
        accept_multiple_files=True,
        key=f"document_uploader_{st.session_state.document_uploader_key}"
    )
    
    # Process new files and add to queue (no auto-analysis to prevent loops)
    files_to_add = []
    if new_uploaded_files:
        for new_file in new_uploaded_files:
            # Only add files that haven't been processed before
            if (new_file.name not in st.session_state.processed_files and
                not any(existing_file.name == new_file.name for existing_file in st.session_state.uploaded_files_queue)):
                files_to_add.append(new_file)
        
        # Add new files to queue
        if files_to_add:
            st.session_state.uploaded_files_queue.extend(files_to_add)
            
            # Auto-start analysis for each new file
            for new_file in files_to_add:
                try:
                    with st.spinner(f"Auto-analyzing {new_file.name}..."):
                        result = process_uploaded_file(new_file)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": result
                        })
                        
                        # Mark file as processed and remove from queue
                        st.session_state.processed_files.add(new_file.name)
                        st.session_state.uploaded_files_queue = [
                            f for f in st.session_state.uploaded_files_queue
                            if f.name != new_file.name
                        ]
                        
                        st.success(f"✅ {new_file.name} analyzed successfully!")
                        st.session_state.document_uploader_reset = True
                        
                except Exception as e:
                    st.error(f"❌ Error analyzing {new_file.name}: {str(e)}")
                    # Mark file as processed to prevent re-analysis even if it failed
                    st.session_state.processed_files.add(new_file.name)
                    # Remove failed file from queue
                    st.session_state.uploaded_files_queue = [
                        f for f in st.session_state.uploaded_files_queue
                        if f.name != new_file.name
                    ]
                    st.session_state.document_uploader_reset = True
            if st.session_state.document_uploader_reset:
                st.rerun()
    
    # Display files in queue with individual remove buttons
    if st.session_state.uploaded_files_queue:
        st.markdown("---")
        st.subheader("📋 Documents in Queue")
        
        # Create a copy of the queue to iterate over
        queue_copy = st.session_state.uploaded_files_queue.copy()
        
        for uploaded_file in queue_copy:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"📄 **{uploaded_file.name}**")
                st.caption(f"Size: {uploaded_file.size} bytes")
            
            with col2:
                if st.button("🗑️ Remove", key=f"remove_{uploaded_file.name}"):
                    # Remove this specific file from queue
                    st.session_state.uploaded_files_queue = [
                        f for f in st.session_state.uploaded_files_queue
                        if f.name != uploaded_file.name
                    ]
                    st.rerun()
            
            st.markdown("---")
        
        # Clear all files button
        if st.button("🗑️ Clear All Files", type="secondary"):
            st.session_state.uploaded_files_queue = []
            st.rerun()
    else:
        st.info("No documents in queue. Upload files above to get started.")
    
    # Display analyzed documents
    current_session = st.session_state.get("session_id")
    visible_docs = {
        doc_id: doc_info
        for doc_id, doc_info in st.session_state.document_index.items()
        if doc_info.get('session_id') == current_session
        or (doc_info.get('metadata') or {}).get('source') == 'reference_library'
    }

    if visible_docs:
        st.markdown("---")
        st.subheader("📚 Analyzed Documents")
        
        for doc_id, doc_info in visible_docs.items():
            with st.expander(f"{doc_info['filename']} ({doc_info['content_type']})"):
                st.write(f"**Type:** {doc_info['content_type']}")
                st.write(f"**Analyzed:** {doc_info['upload_time']}")
                if doc_info.get('metadata'):
                    st.write(f"**Details:** {doc_info['metadata'].get('pages', doc_info['metadata'].get('file_size', 'N/A'))}")
                st.write(f"**Content:** {doc_info['content']}")
    
    # Assistant settings
    st.markdown("---")
    st.header("⚙️ Assistant Settings")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Clear Chat History", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
    
    with col2:
        if st.button("Clear Analyzed Docs", use_container_width=True):
            st.session_state.document_index = {}
            st.rerun()
    
    st.markdown("---")
    st.markdown("**🔧 System Information:**")
    st.markdown(f"- **Model:** {MODEL_ID.split('/')[-1]}")
    st.markdown(f"- **Vision:** {VISION_MODEL_ID.split('/')[-1]}")
    st.markdown(f"- **Project:** {PROJECT_ID[:8]}...")
    st.markdown(f"- **Reference Docs:** 14 loan guides loaded")
    st.markdown(f"- **Queue Files:** {len(st.session_state.uploaded_files_queue)}")
    st.markdown(f"- **Processed Files:** {len(st.session_state.processed_files)}")
    
    if st.session_state.messages:
        st.markdown(f"- **Session Messages:** {len(st.session_state.messages)}")
        st.markdown(f"- **Analyzed Docs:** {len(st.session_state.document_index)}")

# Professional chat interface
if prompt := st.chat_input("Ask me about loans, interest rates, applications, or analyze your documents..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.write(prompt)
    
    # Get Watsonx.ai response with RAG context and loan expertise
    with st.chat_message("assistant"):
        with st.spinner("Analyzing your loan question..."):
            # Enhance the system prompt for loan expertise
            system_context = """You are a professional loan assistant with expertise in all aspects of lending. You have access to:
            
1. **Reference Library**: Comprehensive loan guides covering all loan types including:
   - Personal loans, auto loans, business loans, student loans
   - Mortgage and home equity loans
   - Bad credit loans and credit score requirements
   - Interest rates, APR, and loan calculations
   - Application processes and loan terminology
   
2. **User Documents**: Any loan documents uploaded by the user (these take priority)

Your responses should be:
- Professional and authoritative
- Based on the provided documents when relevant
- Actionable and practical
- Include specific information from the documents
- Acknowledge user-uploaded documents when they contain relevant information

Always cite specific information from the documents when answering questions."""
            
            response = chat_with_watsonx_rag(prompt, st.session_state.messages[:-1])
            st.write(response)
    
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})

# Professional welcome message
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.write("""
        🏦 **Welcome to Your Professional Loan Assistant**
        
        I'm here to help you with comprehensive loan guidance, backed by extensive reference materials and your personal documents.
        
        **💼 My Expertise Areas:**
        • **Loan Types**: Personal, auto, business, student, mortgage, home equity
        • **Credit & Approval**: Credit scores, bad credit options, approval requirements
        • **Financial Details**: Interest rates, APR, loan calculations, repayment terms
        • **Process Guidance**: Application steps, required documents, approval timelines
        • **Document Analysis**: PDF contracts, bank statements, loan agreements
        
        **📄 Document Analysis Features:**
        • **Upload & Process**: PDF, images (PNG, JPG), text files
        • **Vision AI**: Extract content from scanned documents and images
        • **Smart Prioritization**: Your documents are prioritized over reference materials
        • **RAG Integration**: Intelligent content retrieval and contextual answers
        
        **🚀 How I Can Help:**
        1. **Upload your documents** in the sidebar for analysis
        2. **Ask specific questions** about loan terms, rates, or processes
        3. **Get personalized guidance** based on your documents
        4. **Compare options** using our comprehensive loan reference library
        
        **💡 Example Questions:**
        - "What's the interest rate in my loan agreement?"
        - "How do I improve my credit score for better loan terms?"
        - "Compare auto loan vs personal loan for my situation"
        - "Explain the differences between APR and interest rate"
        
        Start by uploading a document or asking a loan question!
        """)