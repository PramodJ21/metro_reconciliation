import React, { useState, useEffect } from 'react';
import axios from 'axios';

const IngestionLogger = ({ ingestionLogs = [], onRevertSuccess, setGlobalLoading }) => {
  const [revertingId, setRevertingId] = useState(null);
  const [activeTab, setActiveTab] = useState('staged'); // 'staged' | 'reverted'
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [sortOrder, setSortOrder] = useState('desc'); // 'desc' | 'asc'

  // Pagination states
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(10);
  const [pageInputVal, setPageInputVal] = useState('1');
  const [limitInputVal, setLimitInputVal] = useState('10');

  // Reset page to 1 when filters or tabs change
  useEffect(() => {
    setPage(1);
    setPageInputVal('1');
  }, [activeTab, startDate, endDate, sortOrder]);

  // Sync inputs with page/limit changes
  useEffect(() => {
    setPageInputVal(page.toString());
  }, [page]);

  useEffect(() => {
    setLimitInputVal(limit.toString());
  }, [limit]);

  const handlePageInputChange = (e) => {
    setPageInputVal(e.target.value);
  };

  const handlePageInputBlur = (totalPages) => {
    let p = parseInt(pageInputVal, 10);
    if (isNaN(p) || p < 1) {
      p = 1;
    } else if (p > totalPages) {
      p = totalPages;
    }
    setPage(p);
    setPageInputVal(p.toString());
  };

  const handlePageInputKeyDown = (e, totalPages) => {
    if (e.key === 'Enter') {
      handlePageInputBlur(totalPages);
    }
  };

  const handleLimitInputChange = (e) => {
    setLimitInputVal(e.target.value);
  };

  const handleLimitInputBlur = () => {
    let l = parseInt(limitInputVal, 10);
    if (isNaN(l) || l < 1) {
      l = 10;
    } else if (l > 500) {
      l = 500;
    }
    setLimit(l);
    setLimitInputVal(l.toString());
    setPage(1);
  };

  const handleLimitInputKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleLimitInputBlur();
    }
  };

  const handleRevertClick = async (logId, filename) => {
    if (!window.confirm(`Are you sure you want to revert file '${filename}'? This will permanently delete all associated transaction rows from the database and wipe the current reconciliation results.`)) {
      return;
    }

    setRevertingId(logId);
    if (setGlobalLoading) {
      setGlobalLoading({
        active: true,
        title: 'Reverting Ingestion Packet',
        progress: 20,
        message: `Wiping transaction entries of '${filename}'...`
      });
    }

    let currentProgress = 20;
    const progressInterval = setInterval(() => {
      if (currentProgress < 85) {
        currentProgress += 15;
        if (setGlobalLoading) {
          setGlobalLoading(prev => ({
            ...prev,
            progress: currentProgress,
            message: 'Cascading changes and clearing ledger cache...'
          }));
        }
      }
    }, 250);

    try {
      const response = await axios.post("http://127.0.0.1:8000/api/reconcile/revert", { log_id: logId });
      clearInterval(progressInterval);
      
      if (setGlobalLoading) {
        setGlobalLoading(prev => ({
          ...prev,
          progress: 100,
          message: '✓ Ingestion successfully rolled back. Database clean.'
        }));
        setTimeout(() => {
          setGlobalLoading({ active: false, title: '', progress: 0, message: '' });
        }, 800);
      }
      
      alert(response.data.message || "File reverted successfully!");
      if (onRevertSuccess) onRevertSuccess();
    } catch (err) {
      clearInterval(progressInterval);
      console.error(err);
      const errMsg = err.response?.data?.detail || err.message || "Failed to revert file.";
      
      if (setGlobalLoading) {
        setGlobalLoading(prev => ({
          ...prev,
          progress: 0,
          message: `✕ Revert Error: ${errMsg}`
        }));
        setTimeout(() => {
          setGlobalLoading({ active: false, title: '', progress: 0, message: '' });
        }, 1500);
      }
      
      alert(`Error reverting file: ${errMsg}`);
    } finally {
      setRevertingId(null);
    }
  };

  // Helper styles dynamically matching your brand specification colors
  const getAppLineStyle = (appName) => {
    const name = appName ? appName.toLowerCase() : '';
    if (name.includes('connect')) {
      return {
        backgroundColor: '#d8e2ff',
        color: '#001a42',
        border: '1px solid #adc6ff'
      };
    } else if (name.includes('mumbai') || name.includes('one')) {
      return {
        backgroundColor: '#dfe3e7',
        color: '#171c1f',
        border: '1px solid #c6c6cd'
      };
    } else {
      // ONDC Hub
      return {
        backgroundColor: '#ffdbca',
        color: '#341100',
        border: '1px solid #ffb690'
      };
    }
  };

  const getAppLineDisplayName = (appName) => {
    const name = appName ? appName.toLowerCase() : '';
    if (name.includes('connect')) return 'Metro Connect';
    if (name.includes('mumbai') || name.includes('one')) return 'Mumbai One';
    return 'ONDC Hub';
  };

  const formatDateString = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    const pad = (num) => String(num).padStart(2, '0');
    
    const mm = pad(date.getMonth() + 1);
    const dd = pad(date.getDate());
    const yy = String(date.getFullYear()).slice(-2);
    
    const hh = pad(date.getHours());
    const min = pad(date.getMinutes());
    const ss = pad(date.getSeconds());
    
    return `${mm}/${dd}/${yy} ${hh}:${min}:${ss}`;
  };

  // Filter staged vs reverted logs
  const stagedLogs = (ingestionLogs || []).filter(log => log.status === 'STAGED');
  const revertedLogs = (ingestionLogs || []).filter(log => log.status === 'REVERTED');

  const filteredStagedLogs = stagedLogs.filter(log => {
    if (!log.uploaded_at) return false;
    const logDate = new Date(log.uploaded_at);
    if (startDate) {
      const start = new Date(startDate);
      start.setHours(0,0,0,0);
      if (logDate < start) return false;
    }
    if (endDate) {
      const end = new Date(endDate);
      end.setHours(23,59,59,999);
      if (logDate > end) return false;
    }
    return true;
  });

  const filteredRevertedLogs = revertedLogs.filter(log => {
    const logDate = log.reverted_at ? new Date(log.reverted_at) : (log.uploaded_at ? new Date(log.uploaded_at) : null);
    if (!logDate) return false;
    if (startDate) {
      const start = new Date(startDate);
      start.setHours(0,0,0,0);
      if (logDate < start) return false;
    }
    if (endDate) {
      const end = new Date(endDate);
      end.setHours(23,59,59,999);
      if (logDate > end) return false;
    }
    return true;
  });

  const sortedStagedLogs = [...filteredStagedLogs].sort((a, b) => {
    const dateA = new Date(a.uploaded_at);
    const dateB = new Date(b.uploaded_at);
    return sortOrder === 'desc' ? dateB - dateA : dateA - dateB;
  });

  const sortedRevertedLogs = [...filteredRevertedLogs].sort((a, b) => {
    const dateA = a.reverted_at ? new Date(a.reverted_at) : (a.uploaded_at ? new Date(a.uploaded_at) : 0);
    const dateB = b.reverted_at ? new Date(b.reverted_at) : (b.uploaded_at ? new Date(b.uploaded_at) : 0);
    return sortOrder === 'desc' ? dateB - dateA : dateA - dateB;
  });

  // Dynamic Pagination calculations based on tab
  const activeRecords = activeTab === 'staged' ? sortedStagedLogs : sortedRevertedLogs;
  const total = activeRecords.length;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const paginatedLogs = activeRecords.slice((page - 1) * limit, page * limit);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: 'Outfit, sans-serif' }}>
      
      {/* Workspace Area */}
      <div style={{
        backgroundColor: '#ffffff',
        border: '1px solid #c6c6cd',
        borderRadius: '0px',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: 'none',
        overflow: 'hidden'
      }}>
        
        {/* Segmented Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid #c6c6cd', backgroundColor: '#f6fafe' }}>
          {/* Active Tab Button */}
          <button
            type="button"
            onClick={() => setActiveTab('staged')}
            style={{
              flex: 1,
              padding: '1rem 0',
              fontFamily: 'Outfit, sans-serif',
              fontSize: '14px',
              fontWeight: 600,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              border: 'none',
              borderBottom: activeTab === 'staged' ? '4px solid #0058be' : '4px solid transparent',
              backgroundColor: activeTab === 'staged' ? '#f0f4f8' : 'transparent',
              color: activeTab === 'staged' ? '#0058be' : '#45464d',
              transition: 'all 0.2s ease'
            }}
          >
            Active Staged Packets
            <span style={activeTab === 'staged' ? {
              backgroundColor: '#0058be',
              color: '#ffffff',
              padding: '0.15rem 0.5rem',
              fontSize: '10px',
              fontWeight: 700,
              letterSpacing: '0.05em'
            } : {
              backgroundColor: '#dfe3e7',
              color: '#45464d',
              border: '1px solid #c6c6cd',
              padding: '0.15rem 0.5rem',
              fontSize: '10px',
              fontWeight: 700,
              letterSpacing: '0.05em'
            }}>
              {stagedLogs.length}
            </span>
          </button>

          {/* Reverted Tab Button */}
          <button
            type="button"
            onClick={() => setActiveTab('reverted')}
            style={{
              flex: 1,
              padding: '1rem 0',
              fontFamily: 'Outfit, sans-serif',
              fontSize: '14px',
              fontWeight: 600,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              border: 'none',
              borderBottom: activeTab === 'reverted' ? '4px solid #0058be' : '4px solid transparent',
              backgroundColor: activeTab === 'reverted' ? '#f0f4f8' : 'transparent',
              color: activeTab === 'reverted' ? '#0058be' : '#45464d',
              transition: 'all 0.2s ease'
            }}
          >
            Reverted Inflow Archives
            <span style={activeTab === 'reverted' ? {
              backgroundColor: '#0058be',
              color: '#ffffff',
              padding: '0.15rem 0.5rem',
              fontSize: '10px',
              fontWeight: 700,
              letterSpacing: '0.05em'
            } : {
              backgroundColor: '#dfe3e7',
              color: '#45464d',
              border: '1px solid #c6c6cd',
              padding: '0.15rem 0.5rem',
              fontSize: '10px',
              fontWeight: 700,
              letterSpacing: '0.05em'
            }}>
              {revertedLogs.length}
            </span>
          </button>
        </div>

        {/* Toolbar */}
        <div style={{
          padding: '1rem',
          borderBottom: '1px solid #c6c6cd',
          backgroundColor: '#f6fafe',
          display: 'flex',
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '1rem',
          flexWrap: 'wrap'
        }}>
          {/* Date Picker Range Group */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              backgroundColor: '#ffffff',
              border: '1px solid #c6c6cd',
              borderRadius: '0px',
              overflow: 'hidden'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', padding: '0.4rem 0.75rem', borderRight: '1px solid #c6c6cd' }}>
                <span className="material-symbols-outlined" style={{ fontSize: '18px', color: '#76777d', marginRight: '0.5rem' }}>calendar_today</span>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  style={{
                    border: 'none',
                    outline: 'none',
                    padding: 0,
                    fontSize: '12px',
                    fontFamily: 'Outfit, sans-serif',
                    fontWeight: 500,
                    color: '#171c1f',
                    width: '115px',
                    cursor: 'pointer'
                  }}
                />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', padding: '0.4rem 0.75rem' }}>
                <span style={{ fontSize: '12px', color: '#76777d', marginRight: '0.5rem', fontWeight: 500 }}>to</span>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  style={{
                    border: 'none',
                    outline: 'none',
                    padding: 0,
                    fontSize: '12px',
                    fontFamily: 'Outfit, sans-serif',
                    fontWeight: 500,
                    color: '#171c1f',
                    width: '115px',
                    cursor: 'pointer'
                  }}
                />
              </div>
            </div>
            
            {(startDate || endDate) && (
              <button
                type="button"
                onClick={() => { setStartDate(''); setEndDate(''); }}
                style={{
                  background: 'none',
                  border: '1px solid #ba1a1a',
                  color: '#ba1a1a',
                  fontSize: '12px',
                  fontWeight: 600,
                  padding: '0.4rem 0.75rem',
                  borderRadius: '0px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                  transition: 'all 0.15s ease'
                }}
              >
                ✕ Clear
              </button>
            )}
          </div>

          {/* Dynamic Sort Button */}
          <div>
            <button
              type="button"
              onClick={() => setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                border: '1px solid #c6c6cd',
                padding: '0.5rem 1rem',
                backgroundColor: '#ffffff',
                fontFamily: 'Outfit, sans-serif',
                fontSize: '12px',
                fontWeight: 500,
                color: '#000000',
                cursor: 'pointer',
                transition: 'background-color 0.15s ease'
              }}
              onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#f0f4f8'}
              onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#ffffff'}
            >
              <span className="material-symbols-outlined" style={{ fontSize: '18px' }}>sort</span>
              {sortOrder === 'desc' ? 'Latest First' : 'Oldest First'}
            </button>
          </div>
        </div>

        {/* Table Canvas internally scrollable table wrapper */}
        <div className="table-wrapper">
          {paginatedLogs.length === 0 ? (
            <div style={{ padding: '4rem 2rem', textAlign: 'center', color: '#64748b' }}>
              No staged packets match the selected date filters.
            </div>
          ) : (
            activeTab === 'staged' ? (
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '800px' }}>
                <thead style={{
                  backgroundColor: '#f6fafe',
                  color: '#45464d',
                  fontSize: '12px',
                  fontWeight: 500,
                  letterSpacing: '0.05em',
                  position: 'sticky',
                  top: 0,
                  zIndex: 10,
                  boxShadow: 'inset 0 -1px 0 #c6c6cd'
                }}>
                  <tr style={{ borderBottom: '1px solid #c6c6cd' }}>
                    <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>Filename</th>
                    <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>App Line</th>
                    <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>Ingestion Channel</th>
                    <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500, textAlign: 'right' }}>Staged Rows</th>
                    <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>Timestamp</th>
                    <th style={{ padding: '1rem', fontWeight: 500, textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody style={{ fontSize: '14px', color: '#000000' }}>
                  {paginatedLogs.map((log) => {
                    const chipStyle = getAppLineStyle(log.app_name);
                    const displayName = getAppLineDisplayName(log.app_name);
                    
                    return (
                      <tr
                        key={log.id}
                        className="staged-row-hover"
                        style={{ borderBottom: '1px solid #c6c6cd', transition: 'background-color 0.15s ease', verticalAlign: 'middle' }}
                      >
                        {/* Filename with monospace font */}
                        <td style={{
                          padding: '1rem',
                          borderRight: '1px solid #c6c6cd',
                          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                          fontWeight: 600,
                          color: '#000000'
                        }}>
                          {log.filename}
                        </td>
                        
                        {/* App Line customized chip */}
                        <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd' }}>
                          <span style={{
                            display: 'inline-block',
                            padding: '0.25rem 0.5rem',
                            fontSize: '12px',
                            fontFamily: 'Outfit, sans-serif',
                            fontWeight: 600,
                            letterSpacing: '0.02em',
                            ...chipStyle
                          }}>
                            {displayName}
                          </span>
                        </td>
                        
                        {/* Ingestion Channel */}
                        <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', color: '#171c1f' }}>
                          {log.channel === 'Mobile' ? 'Mobile Gateway' : log.channel === 'PG' ? 'PG Webhook' : log.channel === 'AFC' ? 'AFC Node 2' : log.channel}
                        </td>
                        
                        {/* Staged Rows right-aligned monospaced */}
                        <td style={{
                          padding: '1rem',
                          borderRight: '1px solid #c6c6cd',
                          textAlign: 'right',
                          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                          fontWeight: 600,
                          color: '#000000'
                        }}>
                          {log.row_count.toLocaleString()}
                        </td>
                        
                        {/* Timestamp in monospaced MM/DD/YY HH:MM:SS format */}
                        <td style={{
                          padding: '1rem',
                          borderRight: '1px solid #c6c6cd',
                          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                          color: '#45464d'
                        }}>
                          {formatDateString(log.uploaded_at)}
                        </td>
                        
                        {/* Danger revert action column */}
                        <td style={{ padding: '1rem', textAlign: 'right' }}>
                          <button
                            onClick={() => handleRevertClick(log.id, log.filename)}
                            disabled={revertingId !== null}
                            className="btn-revert-action"
                            style={{
                              border: '1px solid #c6c6cd',
                              backgroundColor: '#ffffff',
                              color: '#000000',
                              padding: '0.35rem 0.75rem',
                              fontFamily: 'Outfit, sans-serif',
                              fontSize: '12px',
                              fontWeight: 600,
                              cursor: revertingId !== null ? 'not-allowed' : 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              gap: '0.25rem',
                              transition: 'all 0.2s ease',
                              marginLeft: 'auto'
                            }}
                          >
                            <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>history</span>
                            {revertingId === log.id ? 'Reverting...' : 'Revert Ingestion'}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              // Reverted Tab contents
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '800px' }}>
                <thead style={{
                  backgroundColor: '#f6fafe',
                  color: '#45464d',
                  fontSize: '12px',
                  fontWeight: 500,
                  letterSpacing: '0.05em',
                  position: 'sticky',
                  top: 0,
                  zIndex: 10,
                  boxShadow: 'inset 0 -1px 0 #c6c6cd'
                }}>
                  <tr style={{ borderBottom: '1px solid #c6c6cd' }}>
                    <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>Filename</th>
                    <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>App Line</th>
                    <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>Ingestion Channel</th>
                    <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500, textAlign: 'right' }}>Staged Rows</th>
                    <th style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', fontWeight: 500 }}>Timestamp</th>
                    <th style={{ padding: '1rem', fontWeight: 500, textAlign: 'right' }}>Status</th>
                  </tr>
                </thead>
                <tbody style={{ fontSize: '14px', color: '#45464d' }}>
                  {paginatedLogs.map((log) => {
                    const chipStyle = getAppLineStyle(log.app_name);
                    const displayName = getAppLineDisplayName(log.app_name);
                    
                    return (
                      <tr
                        key={log.id}
                        style={{
                          borderBottom: '1px solid #c6c6cd',
                          backgroundColor: '#dfe3e7',
                          opacity: 0.75,
                          verticalAlign: 'middle'
                        }}
                      >
                        {/* Filename line-through */}
                        <td style={{
                          padding: '1rem',
                          borderRight: '1px solid #c6c6cd',
                          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                          textDecoration: 'line-through',
                          color: '#76777d'
                        }}>
                          {log.filename}
                        </td>
                        
                        {/* App Line faded chip */}
                        <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd' }}>
                          <span style={{
                            display: 'inline-block',
                            padding: '0.25rem 0.5rem',
                            fontSize: '12px',
                            fontFamily: 'Outfit, sans-serif',
                            fontWeight: 600,
                            letterSpacing: '0.02em',
                            opacity: 0.5,
                            ...chipStyle
                          }}>
                            {displayName}
                          </span>
                        </td>
                        
                        {/* Ingestion Channel line-through */}
                        <td style={{ padding: '1rem', borderRight: '1px solid #c6c6cd', textDecoration: 'line-through' }}>
                          {log.channel === 'Mobile' ? 'Mobile Gateway' : log.channel === 'PG' ? 'PG Webhook' : log.channel === 'AFC' ? 'AFC Node 2' : log.channel}
                        </td>
                        
                        {/* Staged rows right-aligned monospaced line-through */}
                        <td style={{
                          padding: '1rem',
                          borderRight: '1px solid #c6c6cd',
                          textAlign: 'right',
                          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                          textDecoration: 'line-through',
                          color: '#76777d'
                        }}>
                          {log.row_count.toLocaleString()}
                        </td>
                        
                        {/* Timestamp in monospaced */}
                        <td style={{
                          padding: '1rem',
                          borderRight: '1px solid #c6c6cd',
                          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace'
                        }}>
                          {formatDateString(log.reverted_at || log.uploaded_at)}
                        </td>
                        
                        {/* Audit status block tag */}
                        <td style={{ padding: '1rem', textAlign: 'right' }}>
                          <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                            padding: '0.25rem 0.5rem',
                            backgroundColor: '#ffdad6',
                            color: '#ba1a1a',
                            border: '1px solid #ba1a1a',
                            fontFamily: 'Outfit, sans-serif',
                            fontSize: '12px',
                            fontWeight: 600,
                            letterSpacing: '0.02em',
                            marginLeft: 'auto'
                          }}>
                            <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>block</span>
                            REVERTED
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )
          )}
        </div>

        {/* Pagination Footer - Identical to Reconciliation Ledger */}
        {total > 0 && (
          <div className="pagination-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', borderTop: '1px solid #c6c6cd', backgroundColor: '#f6fafe' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
              <p style={{ fontSize: '0.8rem', color: '#45464d', margin: 0 }}>
                Showing {total > 0 ? (page - 1) * limit + 1 : 0} to {Math.min(total, page * limit)} of {total.toLocaleString()} records
              </p>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', borderLeft: '1px solid #c6c6cd', paddingLeft: '1.25rem' }}>
                <span style={{ fontSize: '0.75rem', color: '#45464d', fontWeight: 700, letterSpacing: '0.04em' }}>SHOW:</span>
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={limitInputVal}
                  onChange={handleLimitInputChange}
                  onKeyDown={handleLimitInputKeyDown}
                  style={{
                    width: '56px',
                    height: '32px',
                    padding: '0 0.35rem',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    textAlign: 'center',
                    backgroundColor: '#ffffff',
                    border: '1px solid #c6c6cd',
                    borderRadius: '0px',
                    color: '#000000',
                    outline: 'none',
                    boxSizing: 'border-box',
                    transition: 'border-color 0.2s ease',
                  }}
                  onFocus={(e) => e.target.style.borderColor = '#0058be'}
                  onBlur={(e) => {
                    e.target.style.borderColor = '#c6c6cd';
                    handleLimitInputBlur();
                  }}
                />
                <span style={{ fontSize: '0.75rem', color: '#45464d', fontWeight: 600 }}>per page</span>
              </div>
            </div>

            <div className="pagination-btn-group" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <button
                className="page-btn"
                disabled={page <= 1}
                onClick={() => setPage(prev => Math.max(1, prev - 1))}
              >
                ‹
              </button>

              <button className="page-btn active" type="button">
                {page}
              </button>

              {page < totalPages && (
                <button className="page-btn" type="button" onClick={() => setPage(page + 1)}>
                  {page + 1}
                </button>
              )}

              {page + 1 < totalPages && (
                <span style={{ display: 'flex', alignItems: 'center', padding: '0 0.25rem', color: '#45464d' }}>...</span>
              )}

              {page < totalPages && page + 1 !== totalPages && (
                <button className="page-btn" type="button" onClick={() => setPage(totalPages)}>
                  {totalPages}
                </button>
              )}

              <button
                className="page-btn"
                disabled={page >= totalPages}
                onClick={() => setPage(prev => Math.min(totalPages, prev + 1))}
              >
                ›
              </button>

              {/* Custom typed page navigation */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', marginLeft: '0.75rem', borderLeft: '1px solid #c6c6cd', paddingLeft: '0.75rem' }}>
                <span style={{ fontSize: '0.75rem', color: '#45464d', fontWeight: 600 }}>GO TO:</span>
                <input
                  type="number"
                  min={1}
                  max={totalPages}
                  value={pageInputVal}
                  onChange={handlePageInputChange}
                  onKeyDown={(e) => handlePageInputKeyDown(e, totalPages)}
                  style={{
                    width: '52px',
                    height: '32px',
                    padding: '0 0.25rem',
                    fontSize: '0.8rem',
                    fontWeight: 700,
                    textAlign: 'center',
                    backgroundColor: '#ffffff',
                    border: '1px solid #c6c6cd',
                    borderRadius: '0px',
                    color: '#000000',
                    outline: 'none',
                    boxSizing: 'border-box',
                    transition: 'border-color 0.2s ease',
                  }}
                  onFocus={(e) => e.target.style.borderColor = '#0058be'}
                  onBlur={(e) => {
                    e.target.style.borderColor = '#c6c6cd';
                    handlePageInputBlur(totalPages);
                  }}
                />
                <span style={{ fontSize: '0.75rem', color: '#45464d', fontWeight: 600 }}>/ {totalPages}</span>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

export default IngestionLogger;
