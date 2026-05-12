'use client';

import { useState, useEffect, useRef } from 'react';
import { 
  ExternalLink, Trash2, Search, Briefcase, Clock, 
  Award, Mail, X, Check, Bot, Play, Loader2, 
  ChevronRight, Send, Sparkles, LayoutDashboard,
  Terminal, Activity, ShieldCheck, Zap
} from 'lucide-react';

export default function JobHuntApp() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [showAssistant, setShowAssistant] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [greeting, setGreeting] = useState('');
  const [stats, setStats] = useState({ total: 0, mailed: 0, accepted: 0, rejected: 0, interview: 0, today: 0 });
  const [theme, setTheme] = useState('dark');

  const [agentStatus, setAgentStatus] = useState({
    status: 'idle',
    step: 'Ready',
    progress: { done: 0, total: 50 },
    last_update: 'N/A'
  });
  const [agentLogs, setAgentLogs] = useState('Initializing telemetry...');
  const [isInitializing, setIsInitializing] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const terminalRef = useRef(null);

  const [messages, setMessages] = useState([{ role: 'assistant', content: "Hello! How can I help you with your job search today?" }]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    const hour = new Date().getHours();
    if (hour < 12) setGreeting('Good morning');
    else if (hour < 18) setGreeting('Good afternoon');
    else setGreeting('Good evening');

    setMounted(true);
    // Sync theme
    document.documentElement.classList.toggle('light', theme === 'light');

    fetchJobs();
    fetchAgentStatus();
    fetchLogs();
    const interval = setInterval(() => {
      fetchAgentStatus();
      fetchJobs();
      fetchLogs();
    }, 3000);
    return () => clearInterval(interval);
  }, [theme]);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [agentLogs]);

  const fetchLogs = async () => {
    try {
      const response = await fetch('/api/logs');
      const result = await response.json();
      if (result.success) setAgentLogs(result.logs);
    } catch (error) { console.error(error); }
  };

  const calculateStats = (data) => {
    const today = new Date().toISOString().split('T')[0];
    const s = { total: data.length, mailed: 0, accepted: 0, rejected: 0, interview: 0, today: 0 };
    data.forEach(job => {
      if (job.Date === today) s.today++;
      const status = (job['Application Status'] || 'Mailed').toLowerCase();
      if (status.includes('accept')) s.accepted++;
      else if (status.includes('reject')) s.rejected++;
      else if (status.includes('interview')) s.interview++;
      else s.mailed++;
    });
    setStats(s);
  };

  const fetchJobs = async () => {
    try {
      const response = await fetch('/api/jobs');
      const result = await response.json();
      if (result.success) {
        setJobs(result.data);
        calculateStats(result.data);
      }
    } catch (error) { console.error(error); }
    finally { setLoading(false); }
  };

  const fetchAgentStatus = async () => {
    try {
      const response = await fetch('/api/agent');
      const result = await response.json();
      if (result.success) setAgentStatus(result.data);
    } catch (error) { console.error(error); }
  };

  const initializeAgent = async () => {
    setIsInitializing(true);
    try {
      await fetch('/api/agent', { method: 'POST' });
      fetchAgentStatus();
    } catch (error) { console.error(error); }
    finally { setIsInitializing(false); }
  };

  const stopAgent = async () => {
    setIsStopping(true);
    try {
      await fetch('/api/agent', { method: 'DELETE' });
      fetchAgentStatus();
    } catch (error) { console.error(error); }
    finally { setIsStopping(false); }
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
      if (result.success) setMessages(prev => [...prev, { role: 'assistant', content: result.content }]);
    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: "Connection error." }]);
    } finally { setIsTyping(false); }
  };

  const updateStatus = async (index, newStatus) => {
    try {
      const response = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rowIndex: index, status: newStatus }),
      });
      const result = await response.json();
      if (result.success) fetchJobs();
    } catch (error) { console.error('Failed to update status:', error); }
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
        setDeleteConfirm(null);
        fetchJobs();
      }
    } catch (error) { console.error('Failed to delete job:', error); }
  };

  if (!mounted) return null;

  return (
    <div className="flex w-full min-h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] overflow-hidden font-sans transition-colors duration-300">
      
      {/* Sidebar Navigation */}
      <nav className="w-72 bg-[var(--bg-sidebar)] border-r border-[var(--border-clr)] flex flex-col shrink-0 z-40">
        <div className="p-8 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white shadow-lg">
            <Sparkles size={20} />
          </div>
          <span className="text-xl font-extrabold tracking-tight">Career-Orbit</span>
        </div>

        <div className="flex-1 px-4 space-y-1 mt-4">
          <div 
            onClick={() => setActiveTab('dashboard')}
            className={`flex items-center gap-4 px-6 py-4 rounded-xl transition-all duration-300 cursor-pointer group ${
              activeTab === 'dashboard' 
                ? 'bg-indigo-600/10 text-white shadow-[0_0_20px_rgba(79,70,229,0.15)] border-l-4 border-indigo-600' 
                : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]'
            }`}
          >
            <LayoutDashboard size={18} /> Dashboard
          </div>
          <div 
            onClick={() => setActiveTab('logs')}
            className={`flex items-center gap-4 px-6 py-4 rounded-xl transition-all duration-300 cursor-pointer group ${
              activeTab === 'logs' 
                ? 'bg-indigo-600/10 text-white shadow-[0_0_20px_rgba(79,70,229,0.15)] border-l-4 border-indigo-600' 
                : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]'
            }`}
          >
            <Terminal size={18} /> Agent Logs
          </div>

          <div className="pt-10 px-6">
            <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-600 mb-4">Operations</h4>
            <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4 mb-6">
              <div className="flex justify-between items-center mb-2">
                <span className="text-[10px] font-bold uppercase text-slate-500">Agent</span>
                <div className="flex items-center gap-1.5">
                  <div className={`w-2 h-2 rounded-full ${agentStatus.status === 'running' ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' : 'bg-rose-500'}`} />
                  <span className="text-[10px] font-black uppercase text-slate-300">{agentStatus.status}</span>
                </div>
              </div>
              <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                <div className={`h-full bg-emerald-500 transition-all duration-1000 ${agentStatus.status === 'running' ? 'w-full' : 'w-0'}`} />
              </div>
            </div>

            <button 
              onClick={initializeAgent}
              disabled={agentStatus.status !== 'idle'}
              className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl py-4 flex items-center justify-center gap-3 font-black uppercase tracking-widest text-[10px] transition-all shadow-lg shadow-indigo-600/20 cursor-pointer mb-3"
            >
              {isInitializing ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} fill="currentColor" />} START HUNT
            </button>
            <button 
              onClick={stopAgent}
              disabled={agentStatus.status === 'idle'}
              className="w-full bg-white/[0.02] hover:bg-white/[0.05] border border-white/5 text-slate-500 hover:text-rose-500 rounded-xl py-3 flex items-center justify-center gap-3 font-black uppercase tracking-widest text-[10px] transition-all cursor-pointer"
            >
              {isStopping ? <Loader2 size={14} className="animate-spin" /> : <X size={14} />} STOP AGENT
            </button>
          </div>
        </div>

        <div className="p-6 border-t border-white/5">
          <div className="flex items-center gap-3 p-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 text-xs font-black">KB</div>
            <div className="min-w-0">
              <p className="text-xs font-bold text-white truncate">Karan Bhoriya</p>
              <p className="text-[10px] text-slate-500">Premium Plan</p>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Workspace */}
      <main className="flex-1 flex flex-col h-screen relative bg-[var(--bg-primary)] overflow-hidden transition-colors duration-300">
        
        {/* Top Header */}
        <header className="h-20 flex items-center justify-between px-10 border-b border-[var(--border-clr)] flex-none bg-[var(--bg-primary)]/80 backdrop-blur-xl z-20 transition-colors duration-300">
          <div>
            <h2 className="text-xl font-bold tracking-tight">{greeting}, Karan</h2>
            <p className="text-[11px] text-slate-500 font-medium uppercase tracking-widest">Orbit Dashboard &bull; Agentic AI applicant</p>
          </div>
          
          <div className="flex items-center gap-6">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-600" size={16} />
              <input 
                type="text" 
                placeholder="Search..." 
                className="bg-white/5 border border-[var(--border-clr)] rounded-xl py-2 pl-11 pr-4 text-sm text-[var(--text-primary)] focus:outline-none focus:border-indigo-500/50 w-64"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <button 
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="w-10 h-10 flex items-center justify-center rounded-xl bg-white/5 border border-[var(--border-clr)] hover:border-indigo-500/50 hover:bg-indigo-500/10 transition-all text-slate-400"
              title={theme === 'dark' ? "Switch to Day Mode" : "Switch to Night Mode"}
            >
              {theme === 'dark' ? <Sparkles size={18} /> : <Zap size={18} />}
            </button>
          </div>
        </header>

        {/* Scrollable Content Container */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-10">
          <div className="max-w-[1700px] mx-auto space-y-10 pb-20">
            
            {activeTab === 'dashboard' ? (
              <>
                {/* Stats Grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                  {[
                    { label: 'Scouted', val: stats.total, color: 'text-indigo-400' },
                    { label: 'Sent', val: stats.total, color: 'text-blue-400' },
                    { label: 'Interviews', val: stats.interview, color: 'text-amber-400' },
                    { label: 'Offers', val: stats.accepted, color: 'text-emerald-400' }
                  ].map((s, i) => (
                    <div key={i} className="bg-[var(--bg-card)] border border-[var(--border-clr)] rounded-2xl p-6 hover:bg-indigo-500/5 transition-all shadow-sm">
                      <p className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-1">{s.label}</p>
                      <h3 className={`text-3xl font-black ${s.color}`}>{s.val}</h3>
                    </div>
                  ))}
                </div>

                {/* Dashboard Main Grid - Expanded for wide view */}
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 items-start">
                  {/* Table Column - Now 3/4 width */}
                  <div className="lg:col-span-3 space-y-6">
                    <div className="bg-[var(--bg-card)] border border-[var(--border-clr)] rounded-2xl overflow-hidden shadow-2xl transition-colors duration-300">
                      <div className="px-6 py-4 border-b border-[var(--border-clr)] bg-[var(--bg-card)] flex justify-between items-center">
                        <h3 className="text-xs font-black uppercase tracking-widest text-[var(--text-primary)]">Live Applications</h3>
                        <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse shadow-[0_0_8px_rgba(99,102,241,0.5)]" />
                      </div>
                      <div className="w-full max-h-[750px] overflow-auto custom-scrollbar">
                        <table className="w-full text-left table-fixed">
                          <thead className="sticky top-0 bg-[var(--bg-sidebar)] z-20">
                            <tr className="text-[10px] font-black uppercase tracking-widest text-slate-500 border-b border-[var(--border-clr)] shadow-sm">
                              <th className="px-6 py-4 w-[22%]">Company</th>
                              <th className="py-4 w-[28%]">Role</th>
                              <th className="py-4 w-[12%]">Link</th>
                              <th className="py-4 w-[15%]">Step</th>
                              <th className="py-4 w-[13%] text-center">Status</th>
                              <th className="py-4 px-6 w-[10%] text-right">Actions</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-[var(--border-clr)]">
                            {loading ? (
                              <tr><td colSpan="6" className="text-center py-10"><Loader2 size={24} className="animate-spin mx-auto text-indigo-500" /></td></tr>
                            ) : jobs.length === 0 ? (
                              <tr><td colSpan="6" className="text-center py-10 text-xs text-slate-500">No data available.</td></tr>
                            ) : (
                              jobs.map((job, i) => {
                                const realIndex = jobs.indexOf(job);
                                return (
                                  <tr key={i} className="hover:bg-indigo-500/5 transition-colors group">
                                    <td className="px-6 py-4">
                                      <span className="font-bold text-[var(--text-primary)] text-sm block truncate">{job.Company}</span>
                                      <span className="text-[10px] text-slate-600 uppercase font-black">{job.Date || 'Recent'}</span>
                                    </td>
                                    <td className="py-4">
                                      <span className="text-xs text-slate-400 font-medium block truncate">{job.Role}</span>
                                    </td>
                                    <td className="py-4 px-4">
                                      <a href={job.URL} target="_blank" className="text-[10px] text-blue-500 hover:text-blue-400 font-black uppercase tracking-widest transition-all whitespace-nowrap bg-blue-500/5 px-3 py-1.5 rounded-lg border border-blue-500/10 cursor-pointer inline-block">View Link</a>
                                    </td>
                                    <td className="py-4 px-4">
                                      <div className="flex items-center gap-2">
                                        <div className="w-1.5 h-1.5 rounded-full bg-slate-500" />
                                        <span className="text-[10px] text-slate-500 font-bold uppercase tracking-tight">{job['Portal Status'] || 'Applied'}</span>
                                      </div>
                                    </td>
                                    <td className="py-4 px-4 text-center">
                                      <div className={`inline-flex items-center rounded-lg border px-2 py-1 ${
                                        job['Application Status']?.toLowerCase().includes('accept') ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-500' :
                                        job['Application Status']?.toLowerCase().includes('reject') ? 'bg-rose-500/10 border-rose-500/20 text-rose-500' :
                                        job['Application Status']?.toLowerCase().includes('interview') ? 'bg-amber-500/10 border-amber-500/20 text-amber-500' :
                                        'bg-indigo-600/10 border-indigo-600/20 text-indigo-400'
                                      }`}>
                                        <select 
                                          className="bg-transparent text-[10px] font-black uppercase tracking-widest outline-none cursor-pointer"
                                          value={job['Application Status'] || 'Mailed'}
                                          onChange={(e) => updateStatus(realIndex, e.target.value)}
                                        >
                                          <option value="Mailed">Mailed</option>
                                          <option value="Interview">Interview</option>
                                          <option value="Accepted">Accepted</option>
                                          <option value="Rejected">Rejected</option>
                                        </select>
                                      </div>
                                    </td>
                                    <td className="py-4 px-6">
                                      <div className="flex items-center gap-2">
                                        {deleteConfirm === realIndex ? (
                                          <div className="flex items-center gap-2">
                                            <button onClick={() => deleteJob(realIndex)} className="text-emerald-500 hover:scale-110 transition-transform cursor-pointer"><Check size={14} /></button>
                                            <button onClick={() => setDeleteConfirm(null)} className="text-slate-500 hover:scale-110 transition-transform cursor-pointer"><X size={14} /></button>
                                          </div>
                                        ) : (
                                          <button onClick={() => setDeleteConfirm(realIndex)} className="text-slate-600 hover:text-rose-500 transition-colors cursor-pointer"><Trash2 size={14} /></button>
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
                    </div>
                  </div>

                  {/* Sidebar Analytics - Now 1/4 width */}
                  <div className="lg:col-span-1 space-y-6">
                    <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-8 flex flex-col items-center">
                      <h4 className="text-[10px] font-black uppercase tracking-widest text-slate-500 mb-8">Daily Progress</h4>
                      <div className="relative w-40 h-40 mb-8 flex items-center justify-center">
                        <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                          <circle cx="50" cy="50" r="44" fill="transparent" stroke="rgba(255,255,255,0.02)" strokeWidth="8" />
                          <circle 
                            cx="50" cy="50" r="44" fill="transparent" stroke="#4f46e5" strokeWidth="8" 
                            strokeDasharray="276" 
                            strokeDashoffset={276 - (276 * (Math.min(stats.today, 50) / 50))}
                            strokeLinecap="round"
                            className="transition-all duration-1000"
                          />
                        </svg>
                        <div className="absolute flex flex-col items-center">
                          <span className="text-4xl font-black text-white leading-none">{stats.today}</span>
                          <span className="text-[10px] font-black text-slate-600 uppercase tracking-widest mt-1">Today</span>
                        </div>
                      </div>
                      <div className="w-full space-y-4">
                        <div className="flex justify-between items-center text-[10px] font-black uppercase text-slate-500">
                          <span>Daily Target</span>
                          <span>50 Units</span>
                        </div>
                        <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                          <div className="h-full bg-indigo-600 transition-all duration-1000" style={{ width: `${(Math.min(stats.today, 50) / 50) * 100}%` }} />
                        </div>
                      </div>
                    </div>

                    <div className="bg-indigo-600/10 border border-indigo-600/20 rounded-2xl p-6">
                      <div className="flex items-center gap-3 mb-4">
                        <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white"><ShieldCheck size={18} /></div>
                        <h4 className="text-xs font-black uppercase tracking-widest">Active Safety</h4>
                      </div>
                      <p className="text-[11px] text-indigo-400 font-medium leading-relaxed">Agent is operating within safety thresholds. Hallucination check enabled for personalized drafts.</p>
                    </div>
                  </div>

                </div>
              </>
            ) : (
              /* Agent Logs View */
              <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div className="bg-[var(--bg-card)] border border-[var(--border-clr)] rounded-2xl p-8">
                  <div className="flex justify-between items-center mb-8">
                    <h3 className="text-xs font-black uppercase tracking-widest text-[var(--text-primary)]">Execution Strategy</h3>
                    <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 text-emerald-500 rounded-full text-[10px] font-black uppercase tracking-widest border border-emerald-500/20">
                      <div className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
                      Step: {agentStatus.step}
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    {['Scouting', 'Reviewing', 'Drafting', 'Mailing'].map((step, i) => {
                      const isActive = agentStatus.step.toLowerCase().includes(step.toLowerCase());
                      return (
                        <div 
                          key={i} 
                          className={`flex-1 p-5 rounded-xl border text-center transition-all duration-500 ${
                            isActive 
                              ? 'bg-indigo-600/20 border-indigo-500 shadow-[0_0_20px_rgba(99,102,241,0.3)] text-white scale-[1.02] z-10 animate-pulse' 
                              : 'bg-white/[0.01] border-white/5 text-slate-600 opacity-50'
                          }`}
                        >
                          <p className={`text-[10px] font-black uppercase tracking-widest ${isActive ? 'text-indigo-400' : 'text-slate-600'}`}>{step}</p>
                          {isActive && <div className="mt-2 h-0.5 w-8 mx-auto bg-indigo-500 rounded-full" />}
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="bg-[var(--terminal-bg)] border border-[var(--border-clr)] rounded-2xl overflow-hidden h-[500px] flex flex-col shadow-2xl transition-colors duration-300">
                  <div className="px-6 py-3 border-b border-[var(--border-clr)] bg-[var(--bg-sidebar)] flex justify-between items-center">
                    <div className="flex items-center gap-4">
                      <div className="flex gap-1.5">
                        <div className="w-2 h-2 rounded-full bg-rose-500" />
                        <div className="w-2 h-2 rounded-full bg-amber-500" />
                        <div className="w-2 h-2 rounded-full bg-emerald-500" />
                      </div>
                      <span className="text-[11px] font-mono text-slate-500">session_telemetry --raw --verbose</span>
                    </div>
                    <Terminal size={14} className="text-slate-600" />
                  </div>
                  <div className="flex-1 p-8 font-mono text-xs overflow-y-auto custom-scrollbar bg-black/5" ref={terminalRef}>
                    <pre className="text-[var(--terminal-text)] whitespace-pre-wrap leading-relaxed filter drop-shadow-[var(--terminal-glow)]">{agentLogs}</pre>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Floating AI Assistant Tag */}
      <div 
        onClick={() => setShowAssistant(!showAssistant)}
        className="fixed bottom-8 right-8 z-[100] flex items-center gap-3 bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-3 rounded-2xl shadow-2xl shadow-indigo-600/40 transition-all hover:-translate-y-1 cursor-pointer group"
      >
        <div className="bg-white/10 p-1.5 rounded-lg group-hover:bg-white/20 transition-colors">
          <Bot size={18} strokeWidth={2.5} />
        </div>
        <span className="text-[11px] font-black uppercase tracking-widest">AI Assistant</span>
      </div>

      {/* Orbit Assistant Sidebar */}
      <div className={`fixed inset-0 bg-black/60 backdrop-blur-sm z-[110] transition-opacity duration-300 ${showAssistant ? 'opacity-100' : 'opacity-0 pointer-events-none'}`} onClick={() => setShowAssistant(false)} />
      
      <aside className={`fixed top-0 right-0 w-[420px] h-full bg-[var(--bg-sidebar)] z-[120] shadow-2xl transition-transform duration-500 ease-in-out p-10 flex flex-col ${showAssistant ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="flex justify-between items-center mb-10 flex-none">
          <div className="flex items-center gap-3">
            <Bot size={24} className="text-indigo-500" />
            <h2 className="text-xl font-black uppercase tracking-tighter text-[var(--text-primary)]">Career-Orbit <span className="text-indigo-500 italic">Copilot</span></h2>
          </div>
          <button onClick={() => setShowAssistant(false)} className="text-slate-500 hover:text-indigo-500 transition-colors"><X size={24} /></button>
        </div>

        <div className="flex-1 overflow-y-auto space-y-6 pr-2 custom-scrollbar mb-8">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] px-4 py-3 rounded-2xl text-sm font-medium leading-relaxed ${m.role === 'user' ? 'bg-indigo-600 text-white rounded-tr-none' : 'bg-white/5 text-slate-400 border border-white/5 rounded-tl-none'}`}>
                {m.content}
              </div>
            </div>
          ))}
          {isTyping && (
            <div className="flex justify-start">
              <div className="bg-white/5 px-4 py-3 rounded-2xl flex items-center gap-1">
                <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce" />
                <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:0.2s]" />
                <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:0.4s]" />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="relative">
          <input 
            type="text" 
            placeholder="Ask Copilot..." 
            className="w-full bg-black/40 border border-white/5 rounded-2xl py-4 px-6 text-sm text-white focus:outline-none focus:border-indigo-500/50 transition-all pr-14"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          />
          <button onClick={sendMessage} className="absolute right-3 top-2.5 w-11 h-11 rounded-xl bg-indigo-600 flex items-center justify-center text-white hover:bg-indigo-500 transition-all">
            <Send size={18} />
          </button>
        </div>
      </aside>
    </div>
  );
}
