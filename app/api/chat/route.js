import { NextResponse } from 'next/server';

const GROQ_API_KEY = process.env.GROQ_API_KEY;
const MODELS = [
  'llama-3.3-70b-versatile',
  'qwen-2.5-32b',
  'llama-3.1-8b-instant'
];

async function callGroq(model, messages) {
  const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${GROQ_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      model,
      messages,
      temperature: 0.7,
      max_tokens: 1024,
    }),
  });

  if (!response.ok) {
    throw new Error(`Groq API error: ${response.statusText}`);
  }

  return response.json();
}

export async function POST(request) {
  try {
    const { messages } = await request.json();

    let lastError = null;
    for (const model of MODELS) {
      try {
        const result = await callGroq(model, messages);
        return NextResponse.json({ 
          success: true, 
          content: result.choices[0].message.content,
          model: model 
        });
      } catch (error) {
        console.error(`Model ${model} failed:`, error);
        lastError = error;
        continue; // Try next model
      }
    }

    throw new Error(`All models failed. Last error: ${lastError?.message}`);
  } catch (error) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
