#!/usr/bin/env python3
"""
Test script to verify the RAG database functionality
"""
import sqlite3
import os
import json

# Import the database functions directly
DB_PATH = "document_index/documents.db"

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
            metadata TEXT
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
    conn.commit()
    conn.close()

def compute_content_hash(content):
    import hashlib
    return hashlib.md5(content.encode()).hexdigest()

def chunk_text_content(text, chunk_size=500, overlap=50):
    """Fixed function to avoid variable name conflict"""
    chunks = []
    words = text.split()
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        chunk_text = " ".join(chunk_words)
        chunks.append((chunk_text, i // chunk_size))
    
    return chunks

def store_document(document_id, filename, content, content_type, metadata=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    file_hash = compute_content_hash(content)
    metadata_json = json.dumps(metadata or {})
    
    try:
        # Store document
        cursor.execute('''
            INSERT OR REPLACE INTO documents 
            (id, filename, content, content_type, file_hash, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (document_id, filename, content, content_type, file_hash, metadata_json))
        
        # Chunk and store text content
        if content_type in ['text', 'pdf', 'image']:
            chunks = chunk_text_content(content)
            for chunk_text, chunk_index in chunks:  # Fixed variable name
                chunk_id = f"{document_id}_chunk_{chunk_index}"
                cursor.execute('''
                    INSERT OR REPLACE INTO chunks 
                    (id, document_id, chunk_text, chunk_index)
                    VALUES (?, ?, ?, ?)
                ''', (chunk_id, document_id, chunk_text, chunk_index))
        
        conn.commit()
        
    except Exception as e:
        print(f"Error storing document: {str(e)}")
    finally:
        conn.close()

def simple_rerank(query, chunks, top_k=3):
    query_words = set(query.lower().split())
    chunk_scores = []
    
    for chunk_text, index in chunks:
        chunk_words = set(chunk_text.lower().split())
        score = len(query_words.intersection(chunk_words))
        chunk_scores.append((chunk_text, index, score))
    
    chunk_scores.sort(key=lambda x: x[2], reverse=True)
    return [(text, idx) for text, idx, score in chunk_scores[:top_k]]

def retrieve_relevant_content(query, top_k=3):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get all chunks
        cursor.execute('''
            SELECT c.chunk_text, d.filename, d.content_type, d.metadata
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
        ''')
        
        chunks = []
        for row in cursor.fetchall():
            chunks.append({
                'text': row[0],
                'filename': row[1],
                'content_type': row[2],
                'metadata': json.loads(row[3]) if row[3] else {}
            })
        
        conn.close()
        
        # Simple reranking
        chunk_texts = [(chunk['text'], 0) for chunk in chunks]
        top_chunks = simple_rerank(query, chunk_texts, top_k)
        
        # Get metadata for top chunks
        relevant_content = []
        for chunk_text, _ in top_chunks:
            for chunk in chunks:
                if chunk['text'] == chunk_text:
                    relevant_content.append(chunk)
                    break
        
        return relevant_content
        
    except Exception as e:
        print(f"Error retrieving content: {str(e)}")
        return []
    finally:
        conn.close()

def test_database():
    """Test if the database and functions work correctly"""
    print("Testing database functionality...")
    
    # Test database initialization
    init_database()
    print("Database initialized")
    
    # Test document storage
    test_doc_id = "test-123"
    test_filename = "test_document.txt"
    test_content = "This is a test document with information about loan interest rates. The interest rate is 5.5% annually. The loan agreement states that the borrower agrees to pay interest at a rate of 5.5% per year."
    test_content_type = "text"
    test_metadata = {"test": True}
    
    store_document(test_doc_id, test_filename, test_content, test_content_type, test_metadata)
    print("Document stored")
    
    # Test content retrieval
    relevant_content = retrieve_relevant_content("What is the interest rate?")
    print(f"Retrieved {len(relevant_content)} relevant content items")
    
    if relevant_content:
        for i, content in enumerate(relevant_content):
            print(f"Content {i+1}: {content['text']}")
    
    # Test database query directly
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM documents")
    documents = cursor.fetchall()
    print(f"Found {len(documents)} documents in database")
    
    cursor.execute("SELECT * FROM chunks")
    chunks = cursor.fetchall()
    print(f"Found {len(chunks)} chunks in database")
    
    if documents:
        print("Sample document:")
        print(f"  ID: {documents[0][0]}")
        print(f"  Filename: {documents[0][1]}")
        print(f"  Content length: {len(documents[0][2])}")
        print(f"  Content preview: {documents[0][2][:100]}...")
    
    conn.close()

if __name__ == "__main__":
    test_database()