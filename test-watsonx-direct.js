const axios = require('axios');

async function testWatsonxDirect() {
  console.log('Testing Watsonx.ai direct API...');
  
  try {
    const response = await axios.post(
      'https://us-south.ml.cloud.ibm.com/ml/v1/text/generation',
      {
        input: 'What is a loan?',
        parameters: {
          max_new_tokens: 100,
          temperature: 0.7,
          top_p: 0.9,
          stop_sequences: []
        },
        model_id: 'meta-llama/llama-3-1-70b-instruct',
        project_id: '6344e97c-4a5a-4585-af06-e379c55b855b'
      },
      {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer NJLshxQ69XRcK_BpAIQHKiWllkZtGUK3eh2uUt16q-Rd'
        },
        timeout: 30000
      }
    );
    
    console.log('Success!');
    console.log('Response:', JSON.stringify(response.data, null, 2));
    
  } catch (error) {
    console.error('Error:', error.response?.data || error.message);
    if (error.response) {
      console.error('Status:', error.response.status);
      console.error('Headers:', error.response.headers);
    }
  }
}

testWatsonxDirect();