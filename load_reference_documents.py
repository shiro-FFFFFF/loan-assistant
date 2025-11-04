#!/usr/bin/env python3
"""
Load all loan documents from the /documents directory into the RAG database
"""
import os
import sqlite3
import json
import uuid
import hashlib

# Database configuration
DB_PATH = "document_index/documents.db"
DOCUMENTS_DIR = "documents"

def chunk_text_content(text: str, chunk_size: int = 500, overlap: int = 50):
    """Simple text chunking with overlap"""
    chunks = []
    words = text.split()
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        chunk_text = " ".join(chunk_words)
        chunks.append((chunk_text, i // chunk_size))
    
    return chunks

def compute_content_hash(content: str) -> str:
    """Compute hash of content for duplicate detection"""
    return hashlib.md5(content.encode()).hexdigest()

def load_documents():
    """Load all documents from the /documents directory"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    loaded_count = 0
    processed_files = []
    
    # Get list of .txt files in documents directory
    for filename in os.listdir(DOCUMENTS_DIR):
        if filename.endswith('.txt'):
            file_path = os.path.join(DOCUMENTS_DIR, filename)
            
            try:
                # Read file content
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                if not content.strip():
                    continue
                
                # Generate document ID
                doc_id = f"ref_{filename.replace('.txt', '')}"
                
                # Read metadata if available
                metadata = {"source": "reference_library", "file_type": "loan_guide"}
                
                # Store document
                file_hash = compute_content_hash(content)
                metadata_json = json.dumps(metadata)
                
                cursor.execute('''
                    INSERT OR REPLACE INTO documents 
                    (id, filename, content, content_type, file_hash, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (doc_id, filename, content, 'text', file_hash, metadata_json))
                
                # Chunk and store content
                chunks = chunk_text_content(content)
                for chunk_text, chunk_index in chunks:
                    chunk_id = f"{doc_id}_chunk_{chunk_index}"
                    cursor.execute('''
                        INSERT OR REPLACE INTO chunks 
                        (id, document_id, chunk_text, chunk_index)
                        VALUES (?, ?, ?, ?)
                    ''', (chunk_id, doc_id, chunk_text, chunk_index))
                
                processed_files.append(filename)
                loaded_count += 1
                
                print(f"OK Loaded: {filename} ({len(content)} characters, {len(chunks)} chunks)")
                
            except Exception as e:
                print(f"ERROR Error loading {filename}: {str(e)}")
                continue
    
    conn.commit()
    conn.close()
    
    print(f"\n[SUCCESS] Successfully loaded {loaded_count} documents into the reference library")
    return processed_files

if __name__ == "__main__":
    print("Loading loan reference documents...")
    files = load_documents()
    print(f"\nTotal files processed: {len(files)}")
    for file in files:
        print(f"  - {file}")