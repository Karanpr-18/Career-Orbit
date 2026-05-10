'use client';

import { useState, useEffect, useRef } from 'react';
import { 
  ExternalLink, Trash2, Search, Briefcase, Clock, 
  Award, Mail, X, Check, Bot, Play, Loader2, 
  ChevronRight, Send, Sparkles, LayoutDashboard
} from 'lucide-react';

export default function JobHuntApp() {
  // Navigation
  const [activeTab, setActiveTab] = useState('dashboard');
  const [agentLogs, setAgentLogs] = useState('Initializing logs...');
  const [isLogsLoading, setIsLogsLoading] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const terminalRef = useRef(null);
  const [showAssistant, setShowAssistant] = useState(false);

  // Data State
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [stats, setStats] = useState({ total: 0, mailed: 0, accepted: 0, rejected: 0, interview: 0 });

  // Agent State
  const [agentStatus, setAgentStatus] = useState({
    status: 'idle',
    step: 'Ready',
    progress: { done: 0, total: 50 },
    last_update: 'N/A'
  });
  const [isInitializing, setIsInitializing] = useState(false);

  // Assistant State
  const [messages, setMessages] = useState([
    { role: 'assistant', content: "Hello! I'm your AI Job Hunt assistant. How can I help you today?" }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    setMounted(true);
    fetchJobs();
    fetchAgentStatus();
    fetchLogs();
    const interval = setInterval(() => {
      fetchAgentStatus();
      if (activeTab === 'dashboard') fetchJobs();
      if (activeTab === 'agent') fetchLogs();
    }, 2000); // Poll every 2 seconds for snappier feel
    return () => clearInterval(interval);
  }, [activeTab]);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [agentLogs]);

  const fetchLogs = async () => {
    try {
      const response = await fetch('/api/logs');
      const result = await response.json();
      if (result.success) {
        setAgentLogs(result.logs);
      }
    } catch (error) {
      console.error('Failed to fetch logs:', error);
    }
  };

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const fetchJobs = async () => {
    try {
      const response = await fetch('/api/jobs');
      const result = await response.json();
      if (result.success) {
        setJobs(result.data);
        calculateStats(result.data);
      }
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchAgentStatus = async () => {
    try {
      const response = await fetch('/api/agent');
      const result = await response.json();
      if (result.success) {
        setAgentStatus(result.data);
      }
    } catch (error) {
      console.error('Failed to fetch agent status:', error);
    }
  };

  const calculateStats = (data) => {
    const s = { total: data.length, mailed: 0, accepted: 0, rejected: 0, interview: 0 };
    data.forEach(job => {
      const status = (job['Application Status'] || 'Mailed').toLowerCase();
      if (status.includes('accept')) s.accepted++;
      else if (status.includes('reject')) s.rejected++;
      else if (status.includes('interview')) s.interview++;
      else s.mailed++;
    });
    setStats(s);
  };

  const initializeAgent = async () => {
    setIsInitializing(true);
    try {
      const response = await fetch('/api/agent', { 
        method: 'POST',
        headers: { 'Cache-Control': 'no-cache' }
      });
      const result = await response.json();
      if (result.success) {
        // Immediately update status
        setAgentStatus(prev => ({ ...prev, status: 'running', step: 'Starting...' }));
        fetchAgentStatus();
      } else {
        alert('Agent error: ' + (result.error || 'Unknown error'));
      }
    } catch (error) {
      console.error('Error starting agent:', error);
      alert('Network error while starting agent');
    } finally {
      setIsInitializing(false);
    }
  };

  const stopAgent = async () => {
    setIsStopping(true);
    try {
      const response = await fetch('/api/agent', { method: 'DELETE' });
      const result = await response.json();
      if (result.success) {
        setAgentStatus(prev => ({ ...prev, status: 'idle', step: 'Stopping...' }));
        fetchAgentStatus();
      } else {
        alert('Error stopping agent: ' + (result.error || 'Unknown error'));
      }
    } catch (error) {
      console.error('Error stopping agent:', error);
    } finally {
      setIsStopping(false);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || isTyping) return;
    
    const userMsg = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsTyping(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: [...messages, userMsg] })
      });
      const result = await response.json();
      if (result.success) {
        setMessages(prev => [...prev, { role: 'assistant', content: result.content }]);
      }
    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I'm having trouble connecting right now." }]);
    } finally {
      setIsTyping(false);
    }
  };

  const updateStatus = async (index, newStatus) => {
    try {
      const response = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rowIndex: index, status: newStatus }),
      });
      const result = await response.json();
      if (result.success) {
        setJobs(result.data);
        calculateStats(result.data);
      }
    } catch (error) {
      console.error('Failed to update status:', error);
    }
  };

  const deleteJob = async (index) => {
    try {
      const response = await fetch('/api/jobs', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rowIndex: index }),
      });
      const result = await response.json();
      if (result.success) {
        setJobs(result.data);
        calculateStats(result.data);
        setDeleteConfirm(null);
      }
    } catch (error) {
      console.error('Failed to delete job:', error);
    }
  };

  const getStatusClass = (status) => {
    const s = (status || 'mailed').toLowerCase();
    if (s.includes('accept')) return 'status-accepted';
    if (s.includes('reject')) return 'status-rejected';
    if (s.includes('interview')) return 'status-interview';
    return 'status-mailed';
  };

  const filteredJobs = jobs.filter(job => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      (job.Company || '').toLowerCase().includes(q) ||
      (job.Role || '').toLowerCase().includes(q) ||
      (job.Date || '').toLowerCase().includes(q) ||
      (job['Portal Status'] || '').toLowerCase().includes(q) ||
      (job['Application Status'] || '').toLowerCase().includes(q)
    );
  });

  if (!mounted) return null;

  return (
    <div className={`app-wrapper ${showAssistant ? 'assistant-open' : ''}`}>
      {/* Floating AI Assistant Toggle (Dedicated Button) */}
      {!showAssistant && (
        <button 
          className="assistant-fab shadow-premium"
          onClick={() => setShowAssistant(true)}
          title="Open AI Assistant"
        >
          <Bot size={24} />
          <span className="fab-label">Ask AI Assistant</span>
        </button>
      )}

      {/* Navigation Sidebar (Mini) */}
      <nav className="side-nav">
        <div className="nav-logo">
          <Sparkles className="text-accent" size={24} />
        </div>
        <div className="nav-items">
          <button 
            className={`nav-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
            title="Dashboard"
          >
            <LayoutDashboard size={20} />
          </button>
          <button 
            className={`nav-btn ${activeTab === 'agent' ? 'active' : ''}`}
            onClick={() => setActiveTab('agent')}
            title="AI Agent"
          >
            <Bot size={20} />
          </button>
        </div>
      </nav>

      {/* Backdrop for Sidebar Overlay */}
      {showAssistant && (
        <div className="sidebar-backdrop" onClick={() => setShowAssistant(false)} />
      )}

      <main className="main-content">
        <div className="container">
          {/* Header */}
          <header className="page-header">
            <div className="header-info">
              <div className="header-badge">
                <span className={`header-badge-dot ${agentStatus.status === 'running' ? 'pulse' : ''}`} />
                {agentStatus.status === 'running' ? `Agent Active: ${agentStatus.step}` : 'System Idle'}
              </div>
              <h1>{activeTab === 'dashboard' ? 'Career-Orbit' : 'Agent Command Center'}</h1>
              <p className="subtitle">
                {activeTab === 'dashboard' 
                  ? 'Your Autonomous Agentic Job Portal.' 
                  : 'Orchestrate your AI-powered job search pipeline.'}
              </p>
            </div>

            {activeTab === 'dashboard' && (
              <div className="search-container">
                <Search size={16} className="search-icon" />
                <input
                  type="text"
                  className="search-input"
                  placeholder="Filter applications..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            )}
          </header>

          {activeTab === 'dashboard' ? (
            <>
              {/* Stats Grid */}
              <section className="stats-grid">
                <div className="stat-card">
                  <div className="stat-icon stat-icon-total"><Briefcase size={20} /></div>
                  <div className="stat-data">
                    <span className="stat-value">{stats.total}</span>
                    <span className="stat-label">Total Applied</span>
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-icon stat-icon-pending"><Mail size={20} /></div>
                  <div className="stat-data">
                    <span className="stat-value text-mailed">{stats.mailed}</span>
                    <span className="stat-label">Pending</span>
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-icon stat-icon-interview"><Clock size={20} /></div>
                  <div className="stat-data">
                    <span className="stat-value text-interview">{stats.interview}</span>
                    <span className="stat-label">Interviews</span>
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-icon stat-icon-accepted"><Award size={20} /></div>
                  <div className="stat-data">
                    <span className="stat-value text-accepted">{stats.accepted}</span>
                    <span className="stat-label">Accepted</span>
                  </div>
                </div>
              </section>

              {/* Jobs Table */}
              <section className="table-container shadow-premium">
                <div className="table-header">
                  <span className="table-title">Live Application Feed</span>
                  <span className="table-count">{filteredJobs.length} results</span>
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Company</th>
                        <th>Role</th>
                        <th>Application Link</th>
                        <th>Step</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {loading ? (
                        <tr><td colSpan="6" className="text-center py-20"><Loader2 className="spin mx-auto" /></td></tr>
                      ) : filteredJobs.length === 0 ? (
                        <tr><td colSpan="6" className="no-results-cell">No records found.</td></tr>
                      ) : (
                        filteredJobs.map((job, index) => {
                          const realIndex = jobs.indexOf(job);
                          return (
                            <tr key={realIndex}>
                              <td className="font-bold">{job.Company}</td>
                              <td className="text-secondary">{job.Role}</td>
                              <td>
                                {job.URL && job.URL !== 'None' ? (
                                  <a 
                                    href={job.URL} 
                                    target="_blank" 
                                    rel="noreferrer" 
                                    className="cell-url"
                                    title={job.URL}
                                  >
                                    {job.URL.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}...
                                  </a>
                                ) : (
                                  <span className="text-muted text-xs">No Link</span>
                                )}
                              </td>
                              <td className="text-xs italic text-muted max-w-[150px] truncate">{job['Portal Status']}</td>
                              <td>
                                <select
                                  className={`status-pill ${getStatusClass(job['Application Status'])}`}
                                  value={job['Application Status'] || 'Mailed'}
                                  onChange={(e) => updateStatus(realIndex, e.target.value)}
                                >
                                  <option value="Mailed">Mailed</option>
                                  <option value="Interview">Interview</option>
                                  <option value="Accepted">Accepted</option>
                                  <option value="Rejected">Rejected</option>
                                </select>
                              </td>
                              <td>
                                <div className="actions-cell">
                                  {job.URL && job.URL !== 'None' && (
                                    <a href={job.URL} target="_blank" rel="noreferrer" className="btn-icon">
                                      <ExternalLink size={14} />
                                    </a>
                                  )}
                                  {deleteConfirm === realIndex ? (
                                    <div className="flex gap-1">
                                      <button onClick={() => deleteJob(realIndex)} className="btn-icon text-red-500"><Check size={14} /></button>
                                      <button onClick={() => setDeleteConfirm(null)} className="btn-icon"><X size={14} /></button>
                                    </div>
                                  ) : (
                                    <button onClick={() => setDeleteConfirm(realIndex)} className="btn-icon hover:text-red-500"><Trash2 size={14} /></button>
                                  )}
                                </div>
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          ) : (
            /* Agent Control Tab */
            <section className="agent-center">
              <div className="agent-grid">
                {/* Agent Status Card */}
                <div className="agent-card status-card">
                  <div className="flex items-center gap-3 mb-6">
                    <Bot size={24} className="text-accent" />
                    <h3>Agent Status</h3>
                    <span className={`status-indicator ${agentStatus.status}`}>
                      {agentStatus.status.toUpperCase()}
                    </span>
                  </div>
                  
                  <div className="agent-metrics mb-6">
                    <div className="metric">
                      <span className="label">Current Phase</span>
                      <span className="value">{agentStatus.step}</span>
                    </div>
                    <div className="metric">
                      <span className="label">Last Update</span>
                      <span className="value">{agentStatus.last_update}</span>
                    </div>
                  </div>

                  <div className="progress-container mb-8">
                    <div className="progress-header">
                      <span>Mailing Progress</span>
                      <span>{agentStatus.progress.done} / {agentStatus.progress.total}</span>
                    </div>
                    <div className="progress-bar-bg">
                      <div 
                        className="progress-bar-fill" 
                        style={{ width: `${(agentStatus.progress.done / agentStatus.progress.total) * 100}%` }}
                      />
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', width: '100%', marginTop: '1.5rem' }}>
                    <button 
                      className={`btn-control btn-start ${agentStatus.status === 'running' ? 'disabled' : ''}`}
                      onClick={initializeAgent}
                      disabled={agentStatus.status === 'running' || isInitializing}
                      style={{ flex: 1, minWidth: '140px' }}
                    >
                      {isInitializing ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
                      <span>Start</span>
                    </button>

                    <button 
                      className={`btn-control btn-stop-compact ${agentStatus.status !== 'running' ? 'disabled' : 'pulse-red'}`}
                      onClick={stopAgent}
                      disabled={agentStatus.status !== 'running' || isStopping}
                      style={{ flex: 1, minWidth: '140px' }}
                    >
                      {isStopping ? <Loader2 className="spin" size={18} /> : <X size={18} />}
                      <span>Stop</span>
                    </button>
                  </div>
                </div>

                {/* Agent Process Info (Moved Up) */}
                <div className="agent-card info-card">
                  <h3>Execution Pipeline</h3>
                  <div className="pipeline-steps">
                    <div className={`pipeline-step ${['Searching', 'Reviewing', 'Mailing'].includes(agentStatus.step) ? 'active' : ''}`}>
                      <div className="step-num">1</div>
                      <div className="step-content">
                        <h4>Scouting & Sourcing</h4>
                        <p>Finding high-signal roles across 7+ platforms.</p>
                      </div>
                    </div>
                    <div className={`pipeline-step ${['Reviewing', 'Mailing'].includes(agentStatus.step) ? 'active' : ''}`}>
                      <div className="step-num">2</div>
                      <div className="step-content">
                        <h4>Architectural Review</h4>
                        <p>Scoring roles against resume and tech stack.</p>
                      </div>
                    </div>
                    <div className={`pipeline-step ${agentStatus.step === 'Mailing' ? 'active' : ''}`}>
                      <div className="step-num">3</div>
                      <div className="step-content">
                        <h4>Dispatch & Cold Email</h4>
                        <p>Auto-applying and drafting personalized emails.</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Agent CLI Terminal (Moved Down) */}
                <div className="agent-card terminal-card">
                  <div className="terminal-header">
                    <div className="terminal-dots">
                      <span className="dot red" />
                      <span className="dot yellow" />
                      <span className="dot green" />
                    </div>
                    <span className="terminal-title">Agent CLI - Realtime Logs</span>
                  </div>
                  <div className="terminal-body" ref={terminalRef}>
                    <pre>{agentLogs}</pre>
                  </div>
                </div>
              </div>
            </section>
          )}
        </div>
      </main>

      {/* AI Assistant Sidebar */}
      <aside className={`assistant-sidebar shadow-premium ${showAssistant ? 'open' : ''}`}>
        <div className="assistant-header">
          <div className="flex items-center gap-2">
            <Bot size={20} className="text-accent" />
            <h3>AI Assistant</h3>
          </div>
          <button onClick={() => setShowAssistant(false)} className="btn-close">
            <X size={18} />
          </button>
        </div>

        <div className="chat-messages">
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              {msg.content}
            </div>
          ))}
          {isTyping && (
            <div className="message assistant">
              <div className="typing">
                <span className="dot" />
                <span className="dot" />
                <span className="dot" />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="chat-input-container">
          <input 
            type="text" 
            placeholder="Ask anything..." 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          />
          <button onClick={sendMessage} disabled={!input.trim() || isTyping}>
            <Send size={18} />
          </button>
        </div>
      </aside>
    </div>
  );
}
