#!/usr/bin/env python3
"""
Clean up test data from the RAG database
"""
import sqlite3
import os

DB_PATH = "document_index/documents.db"

def cleanup_test_data():
    """Remove all test data from the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Delete all chunks first (foreign key constraint)
        cursor.execute("DELETE FROM chunks")
        
        # Delete all documents
        cursor.execute("DELETE FROM documents")
        
        conn.commit()
        print("Test data cleaned up successfully")
        
        # Verify cleanup
        cursor.execute("SELECT COUNT(*) FROM documents")
        doc_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM chunks")
        chunk_count = cursor.fetchone()[0]
        
        print(f"Documents remaining: {doc_count}")
        print(f"Chunks remaining: {chunk_count}")
        
    except Exception as e:
        print(f"Error cleaning up data: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    cleanup_test_data()