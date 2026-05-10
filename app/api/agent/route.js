import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';

const STATUS_PATH = path.join(process.cwd(), 'agent_status.json');
const AGENT_DIR = process.cwd();
const VENV_PYTHON = path.join(AGENT_DIR, 'venv', 'bin', 'python3');

export async function GET() {
  try {
    if (!fs.existsSync(STATUS_PATH)) {
      return NextResponse.json({ 
        success: true, 
        data: { status: 'idle', step: 'Ready', progress: { done: 0, total: 50 } } 
      });
    }
    const data = JSON.parse(fs.readFileSync(STATUS_PATH, 'utf-8'));
    return NextResponse.json({ success: true, data });
  } catch (error) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function POST() {
  try {
    // Check if already running
    if (fs.existsSync(STATUS_PATH)) {
      const data = JSON.parse(fs.readFileSync(STATUS_PATH, 'utf-8'));
      if (data.status === 'running') {
        return NextResponse.json({ success: false, error: 'Agent is already running' }, { status: 400 });
      }
    }

    // Start agent as detached process
    const child = spawn(VENV_PYTHON, ['job_hunter.py', '--force'], {
      cwd: AGENT_DIR,
      detached: true,
      stdio: 'ignore'
    });

    const pid = child.pid;
    child.unref();

    // Initial status with PID
    const initialStatus = { 
      status: 'running', 
      step: 'Starting...', 
      progress: { done: 0, total: 50 },
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
    if (data.status !== 'running' || !data.pid) {
      return NextResponse.json({ success: false, error: 'Agent not running' }, { status: 400 });
    }

    try {
      process.kill(data.pid, 'SIGTERM');
    } catch (e) {
      // Process might have already finished
      console.log('Process kill failed:', e.message);
    }

    // Update status to finished/idle
    const finalStatus = { 
      ...data, 
      status: 'idle', 
      step: 'Stopped by user', 
      last_update: new Date().toLocaleTimeString() 
    };
    fs.writeFileSync(STATUS_PATH, JSON.stringify(finalStatus), 'utf-8');

    return NextResponse.json({ success: true, message: 'Agent stopped' });
  } catch (error) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
