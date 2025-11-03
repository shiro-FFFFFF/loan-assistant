require('dotenv').config();
const express = require('express');
const cors = require('cors');
const axios = require('axios');

const app = express();
const PORT = process.env.PORT || 3001;

// IBM Cloud IAM token cache
let cachedToken = null;
let tokenExpiryTime = null;

// Function to get IBM Cloud IAM access token
async function getIamAccessToken(apiKey) {
  try {
    // Check if we have a valid cached token
    if (cachedToken && tokenExpiryTime && Date.now() < tokenExpiryTime) {
      return cachedToken;
    }

    console.log('Getting new IBM Cloud IAM access token...');
    
    const response = await axios.post(
      'https://iam.cloud.ibm.com/identity/token',
      new URLSearchParams({
        grant_type: 'urn:ibm:params:oauth:grant-type:apikey',
        apikey: apiKey
      }),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        timeout: 10000
      }
    );

    const { access_token, expires_in } = response.data;
    
    // Cache the token for 50 minutes (token expires in 60 minutes)
    cachedToken = access_token;
    tokenExpiryTime = Date.now() + (expires_in - 600) * 1000; // Subtract 10 minutes for safety
    
    console.log('IBM Cloud IAM token obtained successfully');
    return access_token;
    
  } catch (error) {
    console.error('Error getting IBM Cloud IAM token:', error.message);
    throw new Error('Failed to authenticate with IBM Cloud IAM');
  }
}

// Middleware
app.use(cors());
app.use(express.json());

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ 
    status: 'healthy', 
    timestamp: new Date().toISOString(),
    watson_configured: !!(process.env.WATSON_API_KEY && process.env.WATSON_PROJECT_ID)
  });
});

// Watsonx.ai query endpoint
app.post('/api/query', async (req, res) => {
  try {
    const { query } = req.body;
    
    // Validate input
    if (!query || typeof query !== 'string') {
      return res.status(400).json({
        error: 'Query parameter is required and must be a string'
      });
    }

    // Check if Watsonx.ai configuration is available
    if (!process.env.WATSON_API_KEY || !process.env.WATSON_PROJECT_ID) {
      return res.status(500).json({
        error: 'Watsonx.ai configuration is missing. Please check environment variables.'
      });
    }

    console.log('Sending request to Watsonx.ai...');
    
    // Get IBM Cloud IAM access token
    const accessToken = await getIamAccessToken(process.env.WATSON_API_KEY);
    
    // Make request to Watsonx.ai API
    const watsonResponse = await axios.post(
      `${process.env.WATSON_API_URL}/ml/v1/text/generation`,
      {
        input: query,
        parameters: {
          max_new_tokens: 500,
          temperature: 0.7,
          top_p: 0.9,
          stop_sequences: []
        },
        model_id: 'meta-llama/llama-3-1-70b-instruct',
        project_id: process.env.WATSON_PROJECT_ID
      },
      {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`
        },
        timeout: 30000 // 30 second timeout
      }
    );

    console.log('Watsonx.ai response received');

    // Extract and format the response
    const aiResponse = watsonResponse.data.results?.[0]?.generated_text || 
                      'No response generated from Watsonx.ai';

    res.json({
      success: true,
      query: query,
      response: aiResponse,
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Error calling Watsonx.ai:', error.message);
    
    // Handle specific error types
    if (error.code === 'ECONNABORTED') {
      return res.status(504).json({
        error: 'Request timeout - Watsonx.ai took too long to respond'
      });
    }
    
    if (error.response) {
      // API returned an error response
      const status = error.response.status;
      const message = error.response.data?.message || error.response.statusText;
      
      return res.status(status).json({
        error: `Watsonx.ai API error: ${message}`,
        details: error.response.data
      });
    }
    
    // Network or other errors
    res.status(500).json({
      error: 'Failed to connect to Watsonx.ai service',
      details: error.message
    });
  }
});

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    message: 'Watsonx.ai Backend Server',
    version: '1.0.0',
    endpoints: {
      health: 'GET /health',
      query: 'POST /api/query'
    },
    usage: {
      query: {
        method: 'POST',
        url: '/api/query',
        body: { query: 'Your question here' }
      }
    }
  });
});

// Global error handler
app.use((err, req, res, next) => {
  console.error('Unhandled error:', err);
  res.status(500).json({
    error: 'Internal server error',
    message: err.message
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`\n🚀 Watsonx.ai Backend Server is running!`);
  console.log(`📡 Server URL: http://localhost:${PORT}`);
  console.log(`🏥 Health check: http://localhost:${PORT}/health`);
  console.log(`📝 API endpoint: http://localhost:${PORT}/api/query`);
  console.log(`\n📋 Environment Status:`);
  console.log(`   Watson API URL: ${process.env.WATSON_API_URL || 'Not configured'}`);
  console.log(`   Watson Project ID: ${process.env.WATSON_PROJECT_ID || 'Not configured'}`);
  console.log(`   Watson API Key: ${process.env.WATSON_API_KEY ? '✅ Configured' : '❌ Missing'}\n`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('\n🛑 Received SIGTERM, shutting down gracefully...');
  process.exit(0);
});

process.on('SIGINT', () => {
  console.log('\n🛑 Received SIGINT, shutting down gracefully...');
  process.exit(0);
});