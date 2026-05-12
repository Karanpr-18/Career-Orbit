import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';

const STATUS_PATH = path.join(process.cwd(), 'agent_status.json');
const TRACKER_PATH = path.join(process.cwd(), 'tracker.csv');
const AGENT_DIR = process.cwd();
const VENV_PYTHON = path.join(AGENT_DIR, 'venv', 'bin', 'python3');

export const dynamic = 'force-dynamic';

function getMailedCount() {
  if (!fs.existsSync(TRACKER_PATH)) return 0;
  try {
    const content = fs.readFileSync(TRACKER_PATH, 'utf-8');
    const lines = content.split('\n').filter(line => line.trim());
    if (lines.length <= 1) return 0; // Only header or empty
    
    let count = 0;
    // Simple count based on successful statuses
    const successKeywords = ['mailed', 'applied', 'drafted'];
    for (let i = 1; i < lines.length; i++) {
      const lineLower = lines[i].toLowerCase();
      if (successKeywords.some(kw => lineLower.includes(kw))) {
        count++;
      }
    }
    return count;
  } catch (e) {
    console.error('Error reading tracker:', e);
    return 0;
  }
}

export async function GET() {
  try {
    const mailedCount = getMailedCount();
    if (!fs.existsSync(STATUS_PATH)) {
      return NextResponse.json({ 
        success: true, 
        data: { status: 'idle', step: 'Ready', progress: { done: mailedCount, total: 50 } } 
      });
    }

    const data = JSON.parse(fs.readFileSync(STATUS_PATH, 'utf-8'));
    
    // Check if the running process is actually alive
    if (data.status === 'running' && data.pid) {
      try {
        process.kill(data.pid, 0); 
      } catch (e) {
        // PID doesn't exist, reset to idle
        data.status = 'idle';
        data.step = 'Process interrupted';
        fs.writeFileSync(STATUS_PATH, JSON.stringify(data), 'utf-8');
      }
    }

    // Ensure we use the latest mailed count even if the file is old
    if (data.status === 'idle') {
      data.progress.done = mailedCount;
    }
    return NextResponse.json({ success: true, data });
  } catch (error) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function POST() {
  try {
    // Check if already running
    if (fs.existsSync(STATUS_PATH)) {
      try {
        const data = JSON.parse(fs.readFileSync(STATUS_PATH, 'utf-8'));
        if (data.status === 'running' && data.pid) {
          try {
            process.kill(data.pid, 0); // Check if process exists
            console.log(`--- AGENT START BLOCKED: Process ${data.pid} is still active.`);
            return NextResponse.json({ success: false, error: 'Agent is already running' }, { status: 400 });
          } catch (e) {
            console.log(`--- STALE PID DETECTED: ${data.pid}. Clearing and proceeding...`);
          }
        }
      } catch (e) {
        console.log('--- ERROR PARSING STATUS FILE:', e.message);
      }
    }

    console.log('--- STARTING AGENT...');
    console.log('--- DIR:', AGENT_DIR);
    console.log('--- PYTHON:', VENV_PYTHON);

    // Start agent as detached process
    const child = spawn(VENV_PYTHON, ['job_hunter.py', '--force'], {
      cwd: AGENT_DIR,
      detached: true,
      stdio: 'ignore'
    });

    const pid = child.pid;
    child.unref();

    // Initial status
    const mailedCount = getMailedCount();
    const initialStatus = { 
      status: 'running', 
      step: 'Starting...', 
      progress: { done: mailedCount, total: 50 },
      pid: pid,
      last_update: new Date().toLocaleTimeString()
    };
    fs.writeFileSync(STATUS_PATH, JSON.stringify(initialStatus), 'utf-8');

    return NextResponse.json({ success: true, message: 'Agent started', pid });
  } catch (error) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function DELETE() {
  try {
    if (!fs.existsSync(STATUS_PATH)) {
      return NextResponse.json({ success: false, error: 'Agent not running' }, { status: 400 });
    }

    const data = JSON.parse(fs.readFileSync(STATUS_PATH, 'utf-8'));
    if (data.pid) {
      try {
        // Kill the entire process group (negative PID on Unix)
        process.kill(-data.pid, 'SIGKILL'); 
      } catch (e) {
        // Fallback to single PID if group kill fails
        try { process.kill(data.pid, 'SIGKILL'); } catch(e2) {}
        console.log('Process kill failed:', e.message);
      }
    } else {
      // Emergency fallback if PID is missing: kill any job_hunter.py process
      try {
        const { exec } = require('child_process');
        exec('pkill -f job_hunter.py');
        console.log('--- EMERGENCY PKILL EXECUTED (PID was missing)');
      } catch (e) {
        console.error('Emergency pkill failed:', e);
      }
    }

    // Update status to idle
    const mailedCount = getMailedCount();
    const finalStatus = { 
      status: 'idle', 
      step: 'Stopped by user', 
      progress: { done: mailedCount, total: 50 },
      last_update: new Date().toLocaleTimeString() 
    };
    fs.writeFileSync(STATUS_PATH, JSON.stringify(finalStatus), 'utf-8');

    return NextResponse.json({ success: true, message: 'Agent stopped' });
  } catch (error) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
