import streamlit as st
import requests

# Watsonx.ai configuration - using the working credentials from test.py
API_KEY         = "NJLshxQ69XRcK_BpAIQHKiWllkZtGUK3eh2uUt16q-Rd"
PROJECT_ID      = "6344e97c-4a5a-4585-af06-e379c55b855b"
MODEL_ID        = "meta-llama/llama-3-2-90b-vision-instruct"
IAM_URL         = "https://iam.cloud.ibm.com/identity/token"
WATSONX_API_URL = "https://us-south.ml.cloud.ibm.com/ml/v1/text/chat?version=2023-03-29"

# Setup for Streamlit app
st.set_page_config(page_title="Watsonx.ai Chat", layout="centered")
st.title("🤖 Watsonx.ai Chat Interface")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

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

# Function to send message to Watsonx.ai
def chat_with_watsonx(message: str, history: list) -> str:
    # Prepare messages for the API
    messages = history + [{"role": "user", "content": message}]
    
    try:
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

# Chat input
if prompt := st.chat_input("Ask me anything..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.write(prompt)
    
    # Get Watsonx.ai response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = chat_with_watsonx(prompt, st.session_state.messages[:-1])
            st.write(response)
    
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})

# Sidebar with clear chat button
with st.sidebar:
    st.header("Chat Controls")
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    st.markdown("**Model Info:**")
    st.markdown(f"- Model: {MODEL_ID}")
    st.markdown(f"- Project: {PROJECT_ID[:8]}...")
    
    if st.session_state.messages:
        st.markdown(f"- Messages: {len(st.session_state.messages)}")