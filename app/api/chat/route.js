import { NextResponse } from 'next/server';

const GROQ_API_KEY = process.env.GROQ_API_KEY;
const CEREBRAS_API_KEY = process.env.CEREBRAS_API_KEY;

const MODELS = [
  { id: 'llama-3.1-8b-instant', provider: 'groq' },
  { id: 'zai-glm-4.7', provider: 'cerebras' },
  { id: 'qwen-3-235b-a22b-instruct-2507', provider: 'cerebras' },
  { id: 'gpt-oss-120b', provider: 'cerebras' }
];

async function callLLM(modelConfig, messages) {
  const isCerebras = modelConfig.provider === 'cerebras';
  const baseUrl = isCerebras ? 'https://api.cerebras.ai/v1/chat/completions' : 'https://api.groq.com/openai/v1/chat/completions';
  const apiKey = isCerebras ? CEREBRAS_API_KEY : GROQ_API_KEY;

  const response = await fetch(baseUrl, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model: modelConfig.id,
      messages,
      temperature: 0.7,
      max_tokens: 1024,
    }),
  });

  if (!response.ok) {
    throw new Error(`${modelConfig.provider} API error: ${response.statusText}`);
  }

  return response.json();
}

export async function POST(request) {
  try {
    const { messages } = await request.json();

    let lastError = null;
    for (const modelConfig of MODELS) {
      try {
        const result = await callLLM(modelConfig, messages);
        return NextResponse.json({
          success: true,
          content: result.choices[0].message.content,
          model: modelConfig.id
        });
      } catch (error) {
        console.error(`Model ${modelConfig.id} (${modelConfig.provider}) failed:`, error);
        lastError = error;
        continue; // Try next model
      }
    }

    throw new Error(`All models failed. Last error: ${lastError?.message}`);
  } catch (error) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
