import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Dashboard from './components/Dashboard';
import FileUploader from './components/FileUploader';
import ResultsBrowser from './components/ResultsBrowser';
import IngestionLogger from './components/IngestionLogger';

function App() {
  const [dbStatus, setDbStatus] = useState(null);
  const [summaries, setSummaries] = useState([]);
  const [resultsRefreshTrigger, setResultsRefreshTrigger] = useState(0);
  const [ingestionLogs, setIngestionLogs] = useState([]);
  const [reconRunning, setReconRunning] = useState(false);
  const [reconStatus, setReconStatus] = useState(null); // null | 'success' | 'error'
  const [reconMessage, setReconMessage] = useState('');
  const [globalLoading, setGlobalLoading] = useState({ active: false, title: '', progress: 0, message: '' });
  
  // Page Routing: 'dashboard', 'depot', 'logger', 'ledger'
  const [activePage, setActivePage] = useState(() => {
    return localStorage.getItem('transitflow_active_page') || 'dashboard';
  });
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    localStorage.setItem('transitflow_active_page', activePage);
  }, [activePage]);


  // Fetch db row metrics
  const fetchDbStatus = async () => {
    try {
      const response = await axios.get("http://127.0.0.1:8000/api/db/status");
      setDbStatus(response.data);
    } catch (err) {
      console.error("Failed to connect to backend db status API:", err);
      setDbStatus({ connected: false, message: "Backend offline", metrics: [] });
    }
  };

  // Fetch ingestion logs from backend
  const fetchIngestionLogs = async () => {
    try {
      const response = await axios.get("http://127.0.0.1:8000/api/reconcile/logs");
      setIngestionLogs(response.data);
    } catch (err) {
      console.error("Failed to fetch ingestion logs:", err);
    }
  };

  // Fetch summaries from db
  const fetchSummaries = async () => {
    try {
      const response = await axios.get("http://127.0.0.1:8000/api/reconcile/summary");
      setSummaries(response.data);
    } catch (err) {
      console.error("Failed to fetch reconciliation summaries:", err);
    }
  };

  // On mount, load initial states
  useEffect(() => {
    fetchDbStatus();
    fetchSummaries();
    fetchIngestionLogs();
  }, []);

  // When files are successfully uploaded, reload database row counts and logs
  const handleUploadSuccess = () => {
    fetchDbStatus();
    fetchIngestionLogs();
  };

  // When reconciliation completes successfully, refresh metrics and navigate to results ledger
  const handleReconComplete = (newSummaries) => {
    setSummaries(newSummaries);
    fetchDbStatus();
    fetchIngestionLogs();
    setResultsRefreshTrigger(prev => prev + 1);
    setActivePage('ledger');
  };

  // Global trigger classification handler (lives in header)
  const handleTriggerClassification = async () => {
    setReconRunning(true);
    setReconStatus(null);
    setReconMessage('Classifying...');
    setGlobalLoading({
      active: true,
      title: 'Executing Reconciliation Engine',
      progress: 5,
      message: 'Connecting to database ledger...'
    });

    let currentProgress = 5;
    const progressInterval = setInterval(() => {
      if (currentProgress < 90) {
        currentProgress += Math.floor(Math.random() * 8) + 4;
        setGlobalLoading(prev => ({
          ...prev,
          progress: Math.min(92, currentProgress),
          message: currentProgress < 35 
            ? 'Wiping stale classification records...' 
            : currentProgress < 65 
            ? 'Classifying App, PG, and AFC transactions...' 
            : 'Generating live ledger summaries...'
        }));
      }
    }, 450);

    try {
      const response = await axios.post('http://127.0.0.1:8000/api/reconcile/run');
      clearInterval(progressInterval);
      
      if (response.data.success) {
        setGlobalLoading(prev => ({
          ...prev,
          progress: 100,
          message: '✓ Classification completed successfully!'
        }));
        
        setTimeout(() => {
          setGlobalLoading({ active: false, title: '', progress: 0, message: '' });
          handleReconComplete(response.data.summaries);
          setReconStatus('success');
          setReconMessage('Done');
          setTimeout(() => setReconMessage(''), 4000);
        }, 800);
      } else {
        setGlobalLoading(prev => ({
          ...prev,
          progress: 0,
          message: '✕ classification failed on server.'
        }));
        setTimeout(() => {
          setGlobalLoading({ active: false, title: '', progress: 0, message: '' });
          setReconStatus('error');
          setReconMessage('Failed');
          setTimeout(() => setReconMessage(''), 4000);
        }, 1200);
      }
    } catch (err) {
      clearInterval(progressInterval);
      const errMsg = err.response?.data?.detail || err.message || "Network Error";
      setGlobalLoading(prev => ({
        ...prev,
        progress: 0,
        message: `✕ Error: ${errMsg}`
      }));
      setTimeout(() => {
        setGlobalLoading({ active: false, title: '', progress: 0, message: '' });
        setReconStatus('error');
        setReconMessage('Error');
        setTimeout(() => setReconMessage(''), 4000);
      }, 1200);
    } finally {
      setReconRunning(false);
    }
  };

  const handleBulkExport = async () => {
    try {
      setGlobalLoading({
        active: true,
        title: 'Exporting Reconciliation Ledger',
        progress: 30,
        message: 'Fetching full transaction tables...'
      });
      
      const response = await axios.get("http://127.0.0.1:8000/api/reconcile/results?limit=500");
      setGlobalLoading(prev => ({ ...prev, progress: 70, message: 'Structuring CSV text...' }));
      
      const results = response.data?.results || [];
      if (results.length === 0) {
        alert("The ledger is currently empty. There is no data to export.");
        setGlobalLoading({ active: false, title: '', progress: 0, message: '' });
        return;
      }
      
      // Generate CSV
      const headers = ['ID', 'App Line', 'Order ID', 'Ticket Number', 'PG Ref Number', 'Amount (INR)', 'Booking Time', 'Reconciliation Status', 'Data Sources', 'Reconciled At'];
      const csvRows = [headers.join(',')];
      
      results.forEach(r => {
        const row = [
          r.id,
          `"${r.app_source || ''}"`,
          `"${r.order_id || ''}"`,
          `"${r.ticket_no || ''}"`,
          `"${r.pg_ref_no || ''}"`,
          r.amount || 0,
          `"${r.transaction_time || ''}"`,
          `"${r.recon_status || ''}"`,
          `"${r.data_sources || ''}"`,
          `"${r.reconciled_at || ''}"`
        ];
        csvRows.push(row.join(','));
      });
      
      const csvContent = "data:text/csv;charset=utf-8," + csvRows.join("\n");
      const encodedUri = encodeURI(csvContent);
      const link = document.createElement("a");
      link.setAttribute("href", encodedUri);
      link.setAttribute("download", "transitflow_reconciliation_ledger.csv");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      setGlobalLoading(prev => ({ ...prev, progress: 100, message: '✓ Export successful!' }));
      setTimeout(() => setGlobalLoading({ active: false, title: '', progress: 0, message: '' }), 800);
    } catch (err) {
      console.error(err);
      alert("Failed to export ledger data: " + err.message);
      setGlobalLoading({ active: false, title: '', progress: 0, message: '' });
    }
  };

  const handleSidebarNavigate = (page) => {
    setActivePage(page);
    setSidebarOpen(false);
  };

  return (
    <>
      {/* Floating Mobile Sidebar Trigger (only visible on mobile via media queries) */}
      <button 
        type="button"
        className="mobile-sidebar-toggle"
        onClick={() => setSidebarOpen(prev => !prev)}
        style={{
          position: 'fixed',
          top: '1rem',
          left: '1rem',
          zIndex: 1001,
          display: 'none',
          alignItems: 'center',
          justifyContent: 'center',
          width: '42px',
          height: '42px',
          backgroundColor: '#FFFFFF',
          border: '1px solid var(--color-border)',
          color: 'var(--color-primary)',
          cursor: 'pointer',
          boxShadow: '0 4px 12px rgba(15, 23, 42, 0.08)',
          fontSize: '1.25rem',
        }}
      >
        {sidebarOpen ? '✕' : '☰'}
      </button>

      {/* Mobile Sidebar overlay backdrop */}
      {sidebarOpen && (
        <div 
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            backgroundColor: 'rgba(15, 23, 42, 0.3)',
            backdropFilter: 'blur(2px)',
            zIndex: 999,
          }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 1. Sleek Left Sidebar (Single Source of Navigation Truth) */}
      <aside 
        className={`sidebar ${sidebarOpen ? 'open' : ''}`} 
        style={{ 
          backgroundColor: '#FFFFFF', 
          padding: sidebarCollapsed ? '1rem 0 0 0' : '1.25rem 0 0 0',
          width: sidebarCollapsed ? '70px' : '260px',
          transition: 'width 0.2s cubic-bezier(0.4, 0, 0.2, 1)'
        }}
      >
        <div className="sidebar-top" style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {/* Logo Section */}
          <div className="sidebar-logo" style={{
            display: 'flex',
            flexDirection: sidebarCollapsed ? 'column' : 'row',
            alignItems: 'center',
            justifyContent: sidebarCollapsed ? 'center' : 'space-between',
            gap: sidebarCollapsed ? '0.75rem' : '0.5rem',
            padding: sidebarCollapsed ? '0.5rem 0 1rem 0' : '0 1.25rem 1.25rem 1.25rem',
            borderBottom: '1px solid #94A3B8',
            marginBottom: '1rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{
                width: '36px',
                height: '36px',
                backgroundColor: '#000000',
                borderRadius: '6px',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                flexShrink: 0
              }}>
                <span className="material-symbols-outlined" style={{ color: '#FFFFFF', fontSize: '20px' }}>train</span>
              </div>
              {!sidebarCollapsed && (
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <h2 style={{ fontSize: '15px', fontWeight: 700, color: '#0F172A', margin: 0, lineHeight: '1.25' }}>Transit Control</h2>
                  <p style={{ fontSize: '9px', fontWeight: 600, color: '#64748B', letterSpacing: '0.05em', textTransform: 'uppercase', margin: 0 }}>NETWORK MONITOR</p>
                </div>
              )}
            </div>
            
            {/* Collapse Toggle Button */}
            <button
              type="button"
              onClick={() => setSidebarCollapsed(prev => !prev)}
              style={{
                background: 'none',
                border: 'none',
                color: '#64748B',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '0.25rem',
                borderRadius: '4px',
                transition: 'background-color 0.15s ease'
              }}
              onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#F1F5F9'}
              onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              title={sidebarCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
            >
              <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>
                {sidebarCollapsed ? 'chevron_right' : 'chevron_left'}
              </span>
            </button>
          </div>
          
          {/* Group 1 Menu Items (Dashboard) */}
          <div className="sidebar-menu" style={{ display: 'flex', flexDirection: 'column', gap: '0.1rem', paddingBottom: '1rem', borderBottom: '1px solid #94A3B8', marginBottom: '1rem' }}>
            <div 
              className={`sidebar-item ${activePage === 'dashboard' ? 'active' : ''}`}
              onClick={() => handleSidebarNavigate('dashboard')}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
                gap: sidebarCollapsed ? '0' : '0.85rem', 
                padding: sidebarCollapsed ? '0.7rem 0' : '0.7rem 1.25rem', 
                cursor: 'pointer', 
                fontSize: '14px', 
                fontWeight: 500,
                position: 'relative'
              }}
              title={sidebarCollapsed ? "Dashboard" : ""}
            >
              <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>dashboard</span>
              {!sidebarCollapsed && "Dashboard"}
            </div>
          </div>

          {/* Group 2 Menu Items (Depot, Audit, Ledger) */}
          <div className="sidebar-menu" style={{ display: 'flex', flexDirection: 'column', gap: '0.1rem', paddingBottom: '1rem', borderBottom: '1px solid #94A3B8', marginBottom: '1rem' }}>
            <div 
              className={`sidebar-item ${activePage === 'depot' ? 'active' : ''}`}
              onClick={() => handleSidebarNavigate('depot')}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
                gap: sidebarCollapsed ? '0' : '0.85rem', 
                padding: sidebarCollapsed ? '0.7rem 0' : '0.7rem 1.25rem', 
                cursor: 'pointer', 
                fontSize: '14px', 
                fontWeight: 500,
                position: 'relative'
              }}
              title={sidebarCollapsed ? "Depot" : ""}
            >
              <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>storefront</span>
              {!sidebarCollapsed && "Depot"}
            </div>
            
            <div 
              className={`sidebar-item ${activePage === 'ledger' ? 'active' : ''}`}
              onClick={() => handleSidebarNavigate('ledger')}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
                gap: sidebarCollapsed ? '0' : '0.85rem', 
                padding: sidebarCollapsed ? '0.7rem 0' : '0.7rem 1.25rem', 
                cursor: 'pointer', 
                fontSize: '14px', 
                fontWeight: 500,
                position: 'relative'
              }}
              title={sidebarCollapsed ? "Ledger" : ""}
            >
              <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>account_balance_wallet</span>
              {!sidebarCollapsed && "Ledger"}
            </div>
            
            <div 
            className={`sidebar-item ${activePage === 'logger' ? 'active' : ''}`}
            onClick={() => handleSidebarNavigate('logger')}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
              gap: sidebarCollapsed ? '0' : '0.85rem', 
              padding: sidebarCollapsed ? '0.7rem 0' : '0.7rem 1.25rem', 
              cursor: 'pointer', 
              fontSize: '14px', 
              fontWeight: 500,
              position: 'relative'
            }}
            title={sidebarCollapsed ? "Audit" : ""}
          >
            <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>receipt_long</span>
            {!sidebarCollapsed && "Audit"}
          </div>
          
          </div>
        </div>

       


        {/* Sidebar Footer with Status Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0, marginTop: 'auto', borderTop: '1px solid #94A3B8' }}>
          {!sidebarCollapsed ? (
            <div className="sidebar-footer" style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
              padding: '1rem 1.25rem 1.25rem 1.25rem',
              backgroundColor: '#FFFFFF'
            }}>
              {/* Database Online Badge */}
              <div className="db-badge" style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.45rem',
                padding: '0.5rem 0.75rem',
                fontSize: '0.7rem',
                fontWeight: 700,
                letterSpacing: '0.04em',
                borderRadius: '0px',
                backgroundColor: dbStatus?.connected ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.08)',
                border: `1px solid ${dbStatus?.connected ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`,
                color: dbStatus?.connected ? '#047857' : '#991B1B',
                fontFamily: "'Outfit', sans-serif",
                width: '100%',
                boxSizing: 'border-box'
              }}>
                <span 
                  className={`ready-bullet ${dbStatus?.connected ? 'pulse-bullet' : ''}`} 
                  style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    backgroundColor: dbStatus?.connected ? '#10b981' : '#ef4444',
                    boxShadow: dbStatus?.connected ? '0 0 6px #10b981' : 'none',
                    display: 'inline-block'
                  }}
                ></span>
                {dbStatus?.connected ? 'NETWORK ONLINE' : 'DATABASE OFFLINE'}
              </div>

              {/* Trigger Classification Button */}
              <button
                type="button"
                onClick={handleTriggerClassification}
                disabled={reconRunning}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.4rem',
                  padding: '0.65rem 1rem',
                  fontSize: '0.72rem',
                  fontWeight: 700,
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                  fontFamily: "'Outfit', sans-serif",
                  background: reconRunning ? '#cbd5e1' : 'var(--color-primary)',
                  color: reconRunning ? 'var(--text-muted)' : '#ffffff',
                  border: 'none',
                  borderRadius: '0px',
                  cursor: reconRunning ? 'not-allowed' : 'pointer',
                  transition: 'all 0.15s ease',
                  width: '100%',
                  boxSizing: 'border-box',
                }}
                onMouseOver={e => { if (!reconRunning) e.target.style.background = '#1E293B'; }}
                onMouseOut={e => { if (!reconRunning) e.target.style.background = 'var(--color-primary)'; }}
              >
                <span style={{ fontSize: '0.75rem' }}>{reconRunning ? '◌' : '▸'}</span>
                {reconRunning ? 'Classifying...' : 'Trigger Classify'}
              </button>

              {/* Inline Status Message */}
              {reconMessage && (
                <div style={{
                  fontSize: '0.68rem',
                  fontWeight: 600,
                  color: reconStatus === 'success' ? '#10b981' : '#ef4444',
                  letterSpacing: '0.02em',
                  textAlign: 'center',
                }}>
                  {reconStatus === 'success' ? '✓' : '⚠'} {reconMessage}
                </div>
              )}
            </div>
          ) : (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '1rem',
              padding: '1rem 0',
              backgroundColor: '#FFFFFF'
            }}>
              {/* Database status pulsing bullet with hover tooltip */}
              <div 
                className={`ready-bullet ${dbStatus?.connected ? 'pulse-bullet' : ''}`} 
                style={{
                  width: '12px',
                  height: '12px',
                  borderRadius: '50%',
                  backgroundColor: dbStatus?.connected ? '#10b981' : '#ef4444',
                  boxShadow: dbStatus?.connected ? '0 0 6px #10b981' : 'none',
                  cursor: 'pointer'
                }}
                title={dbStatus?.connected ? "Database Online" : "Database Offline"}
              />

              {/* Tiny trigger icon button with hover tooltip */}
              <button 
                type="button" 
                onClick={handleTriggerClassification} 
                disabled={reconRunning}
                style={{
                  background: 'none',
                  border: 'none',
                  color: reconRunning ? '#cbd5e1' : '#000000',
                  cursor: reconRunning ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '0.25rem',
                  borderRadius: '4px',
                  transition: 'background-color 0.15s ease'
                }}
                onMouseOver={(e) => { if (!reconRunning) e.currentTarget.style.backgroundColor = '#F1F5F9'; }}
                onMouseOut={(e) => { if (!reconRunning) e.currentTarget.style.backgroundColor = 'transparent'; }}
                title={reconRunning ? "Classifying..." : "Trigger Classify"}
              >
                <span className="material-symbols-outlined" style={{ fontSize: '20px' }}>
                  {reconRunning ? 'sync' : 'sync_alt'}
                </span>
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* 2. Main Content Layout Area */}
      <div className="main-layout">

        {/* Content Body based on Page Routing */}
        <main className={`content-body ${activePage === 'ledger' ? 'ledger-page' : ''}`}>
          {activePage === 'dashboard' && (
            /* PAGE 1: DASHBOARD */
            <>
              <div className="page-title-section">
                <h1 className="page-title">Executive Reconciliation Dashboard</h1>
                <p className="page-subtext">
                  Real-time overview of network transactions and settlements.
                </p>
              </div>

              {/* Staging & Metrics Row */}
              <Dashboard dbStatus={dbStatus} summaries={summaries} />
            </>
          )}

          {activePage === 'depot' && (
            /* PAGE 2: DEPOT (File Dropzone Inflow, trigger dispatcher) */
            <>
              <div className="page-title-section">
                <h1 className="page-title">Ingestion Hub</h1>
                <p className="page-subtext">
                  Ingest transaction records and settlement packets. Dispatch high-speed set-based reconciliation queries.
                </p>
              </div>

              {/* Ingestion Panel */}
              <FileUploader onUploadSuccess={handleUploadSuccess} setGlobalLoading={setGlobalLoading} dbStatus={dbStatus} />
            </>
          )}

          {activePage === 'logger' && (
            /* PAGE 3: LOGGER (Staging Audit logs and rollback controls) */
            <>
              <div className="page-title-section">
                <h1 className="page-title">Transaction Audit & Rollback</h1>
                <p className="page-subtext">
                  Monitor staged ingestion packets and manage ledger reversals.
                </p>
              </div>

              <IngestionLogger ingestionLogs={ingestionLogs} onRevertSuccess={handleUploadSuccess} setGlobalLoading={setGlobalLoading} />
            </>
          )}

          {activePage === 'ledger' && (
            /* PAGE 4: LEDGER (Results Table grid browser) */
            <>
              <ResultsBrowser refreshTrigger={resultsRefreshTrigger} />
            </>
          )}
        </main>
      </div>

      {/* Global Interactive Loading Overlay Modal */}
      {globalLoading.active && (
        <div className="global-overlay">
          <div className="global-loader-box">
            <div className="loader-spinner-container">
              <div className="loader-spinner"></div>
              <div className="loader-spinner-icon">⊛</div>
            </div>
            <h3 className="loader-title">{globalLoading.title}</h3>
            <div className="loader-progress-container">
              <div className="loader-progress-bar-wrapper">
                <span style={{ color: 'var(--text-muted)', fontSize: '0.65rem', letterSpacing: '0.05em' }}>TRANSMISSION STATUS</span>
                <span style={{ color: 'var(--color-secondary)' }}>{globalLoading.progress}%</span>
              </div>
              <div className="loader-progress-bar">
                <div className="loader-progress-fill" style={{ width: `${globalLoading.progress}%` }}></div>
              </div>
            </div>
            {globalLoading.message && (
              <div className="loader-message" title={globalLoading.message}>{globalLoading.message}</div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

export default App;
