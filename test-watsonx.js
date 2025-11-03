const axios = require('axios');

async function testWatsonx() {
  console.log('Testing Watsonx.ai integration...');
  
  try {
    // Test basic query
    const response = await axios.post('http://localhost:3001/api/query', {
      query: 'What are the benefits of refinancing a home loan?'
    });
    
    console.log('Success!');
    console.log('Query:', response.data.query);
    console.log('Response:', response.data.response);
    console.log('Timestamp:', response.data.timestamp);
    
  } catch (error) {
    console.error('Error:', error.response?.data || error.message);
    console.error('Status:', error.response?.status);
  }
}

testWatsonx();