#!/usr/bin/env python3
"""
Test script to verify the RAG database functionality
"""
import sqlite3
import os
import json
from watsonx_chat import *

def test_database():
    """Test if the database and functions work correctly"""
    print("Testing database functionality...")
    
    # Test database initialization
    init_database()
    print("✅ Database initialized")
    
    # Test document storage
    test_doc_id = "test-123"
    test_filename = "test_document.txt"
    test_content = "This is a test document with information about loan interest rates. The interest rate is 5.5% annually."
    test_content_type = "text"
    test_metadata = {"test": True}
    
    store_document(test_doc_id, test_filename, test_content, test_content_type, test_metadata)
    print("✅ Document stored")
    
    # Test content retrieval
    relevant_content = retrieve_relevant_content("What is the interest rate?")
    print(f"✅ Retrieved {len(relevant_content)} relevant content items")
    
    if relevant_content:
        for i, content in enumerate(relevant_content):
            print(f"Content {i+1}: {content['text'][:100]}...")
    
    # Test database query directly
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM documents")
    documents = cursor.fetchall()
    print(f"✅ Found {len(documents)} documents in database")
    
    cursor.execute("SELECT * FROM chunks")
    chunks = cursor.fetchall()
    print(f"✅ Found {len(chunks)} chunks in database")
    
    conn.close()

if __name__ == "__main__":
    test_database()