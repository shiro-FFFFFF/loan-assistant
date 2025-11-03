# Watsonx.ai Backend Server

A simple Node.js/Express server for testing Watsonx.ai integration. This backend server provides a REST API interface to interact with IBM Watsonx.ai language models.

## Features

- 🚀 **Express.js REST API** - Clean, RESTful API endpoints
- 🤖 **Watsonx.ai Integration** - Direct integration with IBM Watsonx.ai
- 🛡️ **Error Handling** - Comprehensive error handling for API failures
- 📊 **Health Monitoring** - Health check endpoint for monitoring
- 🔒 **Environment Configuration** - Secure environment variable configuration
- ⚡ **CORS Support** - Cross-origin resource sharing enabled
- 📝 **Comprehensive Logging** - Detailed console logging for debugging

## Prerequisites

- Node.js (v14 or higher)
- npm or yarn
- IBM Watsonx.ai account with API access

## Installation

1. **Clone or download the project files**
2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Configure environment variables:**
   The server automatically loads from the existing `.env` file:
   ```env
   WATSON_API_KEY=your_api_key_here
   WATSON_API_URL=https://us-south.ml.cloud.ibm.com
   WATSON_PROJECT_ID=your_project_id_here
   ```

## Running the Server

### Development Mode (with auto-restart)
```bash
npm run dev
```

### Production Mode
```bash
npm start
```

The server will start on `http://localhost:3001` by default.

## API Endpoints

### Root Endpoint
**GET** `/`

Returns server information and available endpoints.

**Response:**
```json
{
  "message": "Watsonx.ai Backend Server",
  "version": "1.0.0",
  "endpoints": {
    "health": "GET /health",
    "query": "POST /api/query"
  },
  "usage": {
    "query": {
      "method": "POST",
      "url": "/api/query",
      "body": { "query": "Your question here" }
    }
  }
}
```

### Health Check
**GET** `/health`

Returns server health status and Watsonx.ai configuration status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2023-11-03T17:50:43.349Z",
  "watson_configured": true
}
```

### Query Watsonx.ai
**POST** `/api/query`

Send a query to Watsonx.ai and receive AI-generated response.

**Request:**
```json
{
  "query": "What are the benefits of refinancing a loan?"
}
```

**Success Response (200):**
```json
{
  "success": true,
  "query": "What are the benefits of refinancing a loan?",
  "response": "Loan refinancing can offer several benefits including...",
  "timestamp": "2023-11-03T17:50:43.349Z"
}
```

**Error Response (400):**
```json
{
  "error": "Query parameter is required and must be a string"
}
```

**Error Response (500):**
```json
{
  "error": "Watsonx.ai configuration is missing. Please check environment variables."
}
```

## Testing the Server

### 1. Basic Health Check
```bash
curl http://localhost:3001/health
```

### 2. Test Watsonx.ai Query
```bash
curl -X POST http://localhost:3001/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain the basics of loan interest rates"}'
```

### 3. Using JavaScript (Node.js)
```javascript
const axios = require('axios');

async function testWatsonx() {
  try {
    const response = await axios.post('http://localhost:3001/api/query', {
      query: 'What is debt consolidation?'
    });
    console.log('AI Response:', response.data.response);
  } catch (error) {
    console.error('Error:', error.response.data);
  }
}

testWatsonx();
```

### 4. Using Frontend JavaScript
```javascript
// Example for integrating with frontend
async function queryWatsonx(question) {
  try {
    const response = await fetch('http://localhost:3001/api/query', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query: question })
    });
    
    const data = await response.json();
    return data.response;
  } catch (error) {
    console.error('Query failed:', error);
    return 'Sorry, I encountered an error processing your question.';
  }
}
```

## Environment Variables

The server uses the following environment variables from your `.env` file:

- `WATSON_API_KEY` - Your IBM Watsonx.ai API key
- `WATSON_API_URL` - Watsonx.ai API base URL
- `WATSON_PROJECT_ID` - Your Watsonx.ai project ID

Optional:
- `PORT` - Server port (default: 3001)

## Error Handling

The server includes comprehensive error handling:

- **Input Validation** - Validates query parameter presence and type
- **API Timeouts** - 30-second timeout for Watsonx.ai requests
- **Network Errors** - Handles connection failures gracefully
- **API Errors** - Properly handles Watsonx.ai API error responses
- **Timeout Errors** - Special handling for request timeouts

## Model Configuration

The server is configured to use the `meta-llama/llama-3-1-70b-instruct` model with these parameters:

- **Max New Tokens**: 500
- **Temperature**: 0.7
- **Top P**: 0.9

You can modify these parameters in the `server.js` file under the POST `/api/query` endpoint.

## Troubleshooting

### Common Issues

1. **"Watsonx.ai configuration is missing"**
   - Check that your `.env` file contains all required variables
   - Ensure the API key and project ID are correct

2. **Connection timeout**
   - Verify your internet connection
   - Check that the Watsonx.ai API URL is accessible
   - Increase timeout value if needed

3. **Authentication errors**
   - Verify your API key is valid and has not expired
   - Check that your project ID is correct

4. **Port already in use**
   - Change the PORT environment variable
   - Kill any process using port 3001

### Debug Mode

Enable detailed logging by adding debug output:
```javascript
// Add to server.js for debugging
console.log('Environment variables:', {
  WATSON_API_KEY: process.env.WATSON_API_KEY ? 'Set' : 'Missing',
  WATSON_PROJECT_ID: process.env.WATSON_PROJECT_ID ? 'Set' : 'Missing',
  WATSON_API_URL: process.env.WATSON_API_URL || 'Not set'
});
```

## Security Notes

- Never commit your `.env` file to version control
- Keep your API keys secure and rotate them regularly
- The server currently allows CORS from all origins (configure for production)
- Consider adding rate limiting for production use

## Development

### Project Structure
```
├── package.json       # Dependencies and scripts
├── server.js          # Main server file
├── .env              # Environment variables (not in repo)
└── README.md         # This file
```

### Adding Features

To extend the server functionality:

1. Add new routes in `server.js`
2. Create additional API endpoints
3. Add authentication middleware if needed
4. Implement rate limiting for production

## License

MIT License - feel free to modify and use for your projects.

## Support

For issues with:
- **Watsonx.ai API**: Check IBM Cloud documentation
- **Server functionality**: Review the error messages and logs
- **Integration**: Test with the provided examples first