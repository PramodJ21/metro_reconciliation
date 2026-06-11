import React, { useState, useRef } from 'react';
import { API_BASE_URL } from '../config';

const FileUploader = ({ onUploadSuccess, setGlobalLoading, dbStatus, showAlert }) => {
  const [appName, setAppName] = useState('mumbaione');
  const [channel, setChannel] = useState('mobile');
  const [clearExisting, setClearExisting] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isDragActive, setIsDragActive] = useState(false);
  
  // Upload States
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadLogs, setUploadLogs] = useState([]);
  
  const fileInputRef = useRef(null);

  // Disable PG option if ONDC is selected
  const handleAppChange = (e) => {
    const app = e.target.value;
    setAppName(app);
    if (app === 'ondc' && channel === 'payment_gateway') {
      setChannel('mobile');
    }
  };

  // Drag and drop handlers
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragActive(true);
    } else if (e.type === "dragleave") {
      setIsDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const files = Array.from(e.dataTransfer.files);
      setSelectedFiles(prev => [...prev, ...files]);
    }
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const files = Array.from(e.target.files);
      setSelectedFiles(prev => [...prev, ...files]);
    }
  };

  const removeFile = (indexToRemove) => {
    setSelectedFiles(prev => prev.filter((_, idx) => idx !== indexToRemove));
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (selectedFiles.length === 0) return;

    const totalFiles = selectedFiles.length;

    setUploading(true);
    setUploadProgress(5);
    setUploadLogs(['Initiating transaction payload...', 'Connecting to Ingest API...']);

    if (setGlobalLoading) {
      setGlobalLoading({
        active: true,
        title: 'Ingesting Data Packets',
        progress: 5,
        message: `Packaging ${totalFiles} file(s) for transmission...`
      });
    }

    const formData = new FormData();
    formData.append('app_name', appName);
    formData.append('channel', channel);
    formData.append('clear_existing', clearExisting ? 'true' : 'false');
    selectedFiles.forEach((file) => formData.append('files', file));

    let completed = false;
    let errorOccurred = false;

    try {
      const response = await fetch(`${API_BASE_URL}/api/reconcile/upload`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok || !response.body) {
        const errText = await response.text().catch(() => 'Unknown server error');
        throw new Error(errText);
      }

      // ── SSE Stream Reader ───────────────────────────────────────────────────
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE lines arrive as "data: {...}\n\n" — split on double newline
        const parts = buffer.split('\n\n');
        buffer = parts.pop(); // keep any incomplete trailing chunk

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith('data:')) continue;

          let evt;
          try {
            evt = JSON.parse(line.slice(5).trim());
          } catch {
            continue;
          }

          const { event, progress, message } = evt;

          // ── Update progress bar and overlay ──────────────────────────────
          if (typeof progress === 'number') {
            setUploadProgress(progress);
            if (setGlobalLoading) {
              setGlobalLoading(prev => ({
                ...prev,
                progress,
                message: message || prev.message
              }));
            }
          }

          // ── Update console log ────────────────────────────────────────────
          if (message) {
            setUploadLogs(prev => [...prev, message]);
          }

          // ── Handle terminal events ────────────────────────────────────────
          if (event === 'completed') {
            completed = true;
            const data = evt;

            setUploadProgress(100);
            if (setGlobalLoading) {
              setGlobalLoading(prev => ({ ...prev, progress: 100, message }));
            }

            setUploadLogs(prev => [
              ...prev,
              `✓ Inserted ${new Intl.NumberFormat('en-IN').format(data.total_rows_loaded || 0)} rows into ${data.staging_table}.`
            ]);
            (data.processed_files || []).forEach(f => {
              setUploadLogs(prev => [...prev, `   ↳ ${f.filename}: ${f.status} (${f.rows_loaded} rows)`]);
            });

            setTimeout(() => {
              setGlobalLoading({ active: false, title: '', progress: 0, message: '' });
            }, 1600);

            setSelectedFiles([]);
            if (onUploadSuccess) onUploadSuccess();

          } else if (event === 'error') {
            errorOccurred = true;
            const errMsg = evt.message || 'Unknown ingestion error';
            setUploadLogs(prev => [...prev, `✕ Error: ${errMsg}`]);
            setUploadProgress(0);

            if (setGlobalLoading) {
              setGlobalLoading(prev => ({
                ...prev,
                progress: 0,
                message: `✕ Ingestion Error: ${errMsg}`
              }));
              setTimeout(() => {
                setGlobalLoading({ active: false, title: '', progress: 0, message: '' });
              }, 2200);
            }

            if (errMsg.includes('Wrong file structure')) {
              showAlert(errMsg.replace('Wrong file structure: ', '') + '\n\nPlease check your spreadsheet columns and try again.', 'Wrong File Structure', 'error');
            } else {
              showAlert(errMsg, 'Ingestion Failure', 'error');
            }
          }
        }
      }

      if (!completed && !errorOccurred) {
        // Stream ended without a completed event — treat as unexpected
        throw new Error('Server closed the stream without a completion signal.');
      }

    } catch (err) {
      console.error(err);
      const errMsg = err.message || 'Network timeout';
      setUploadLogs(prev => [...prev, `✕ Error: ${errMsg}`]);
      setUploadProgress(0);

      if (setGlobalLoading) {
        setGlobalLoading(prev => ({
          ...prev,
          progress: 0,
          message: `✕ Ingestion Error: ${errMsg}`
        }));
        setTimeout(() => {
          setGlobalLoading({ active: false, title: '', progress: 0, message: '' });
        }, 2000);
      }

      showAlert(errMsg, 'Ingestion Failure', 'error');
    } finally {
      setUploading(false);
    }
  };

  const getRowCount = (tableName) => {
    if (!dbStatus || !dbStatus.metrics) return 0;
    const metric = dbStatus.metrics.find(m => m.table_name === tableName);
    return metric ? metric.row_count : 0;
  };

  const totalStagedRows = 
    getRowCount('stg_mobile_mumbaione') +
    getRowCount('stg_mobile_metroconnect3') +
    getRowCount('stg_mobile_ondc') +
    getRowCount('stg_pg_transactions') +
    getRowCount('stg_afc_transactions');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      
      {/* Ready for Transit Connection Card */}
      <div className="widget-card" style={{ borderLeft: dbStatus?.connected ? '4px solid var(--color-secondary)' : '4px solid #ef4444', padding: '1.15rem 1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span 
              className={`ready-bullet ${dbStatus?.connected ? 'pulse-bullet' : ''}`}
              style={{ 
                width: '12px', 
                height: '12px', 
                backgroundColor: dbStatus?.connected ? 'var(--color-secondary)' : '#ef4444',
                boxShadow: dbStatus?.connected ? '0 0 8px var(--color-secondary)' : 'none',
                display: 'inline-block',
                borderRadius: '50%'
              }}
            ></span>
            <div>
              <span style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--color-primary)' }}>
                {dbStatus?.connected ? 'Ready for Transit' : 'Connection Offline'}
              </span>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '0.2rem 0 0 0' }}>
                {dbStatus?.connected 
                  ? `All staging pipelines connected. Database is online and holding ${new Intl.NumberFormat('en-IN').format(totalStagedRows)} staged rows.` 
                  : 'Failed to establish connection to PostgreSQL local database. Please check your credentials in .env.'}
              </p>
            </div>
          </div>
          {dbStatus?.connected && (
            <div style={{ padding: '0.25rem 0.75rem', background: 'var(--color-neutral)', borderRadius: '0px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Staged Rows</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 800, color: 'var(--color-primary)' }}>{new Intl.NumberFormat('en-IN').format(totalStagedRows)}</div>
            </div>
          )}
        </div>
      </div>

      {/* File Deposit Station */}
      <div className="widget-card">

      <form onSubmit={handleUploadSubmit}>
        {/* Form selectors matching Image 1 exactly */}
        <div className="form-grid">
          <div className="select-wrapper">
            <label htmlFor="app-dest">App Line Destination</label>
            <select id="app-dest" className="form-select" value={appName} onChange={handleAppChange}>
              <option value="mumbaione">MumbaiOne App Line</option>
              <option value="metroconnect3">MetroConnect3 App Line</option>
              <option value="ondc">ONDC App Line</option>
            </select>
          </div>

          <div className="select-wrapper">
            <label htmlFor="ingest-channel">Ingestion Channel</label>
            <select id="ingest-channel" className="form-select" value={channel} onChange={(e) => setChannel(e.target.value)}>
              <option value="mobile">Standard Mobile (CSV/Excel)</option>
              {appName !== 'ondc' && (
                <option value="payment_gateway">Payment Gateway Settlement</option>
              )}
              <option value="afc">AFC Turnstiles Report</option>
            </select>
          </div>
        </div>

        {/* Clear Option */}
        <div className="clear-options-group" style={{ marginBottom: '1.25rem' }}>
          <input 
            type="checkbox" 
            id="clear-checkbox" 
            checked={clearExisting} 
            onChange={(e) => setClearExisting(e.target.checked)} 
          />
          <label htmlFor="clear-checkbox" style={{ cursor: 'pointer' }}>Truncate staging table before importing</label>
        </div>

        {/* Dropzone container matching Image 1 exactly */}
        <div 
          className={`dropzone-container ${isDragActive ? 'active' : ''}`}
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current.click()}
          style={{ marginBottom: '1.5rem' }}
        >
          <input 
            type="file" 
            ref={fileInputRef} 
            style={{ display: 'none' }} 
            multiple 
            onChange={handleFileSelect}
            accept=".xlsx,.xls,.csv"
          />
          <div className="dropzone-icon" style={{ color: 'var(--color-primary)' }}>⇪</div>
          <strong>Select or drop file</strong>
          <p>Supported formats: CSV, XLSX, JSON. Max size 500MB.</p>
        </div>

        {/* Selected Files List with Inline Scrolling */}
        {selectedFiles.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Staged Files ({selectedFiles.length})
              </span>
              <button
                type="button"
                onClick={() => setSelectedFiles([])}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#991B1B',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  padding: 0,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em'
                }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: '14px' }}>delete_sweep</span>
                Remove All Files
              </button>
            </div>
            <div 
              className="file-staging-list" 
              style={{ 
                maxHeight: '180px',
                overflowY: 'auto',
                border: '1px solid var(--color-border)',
                padding: '0.5rem',
                backgroundColor: 'rgba(0, 0, 0, 0.02)',
                gap: '0.4rem'
              }}
            >
              {selectedFiles.map((file, idx) => (
                <div key={idx} className="file-staging-item" style={{ margin: 0 }}>
                  <span>⚬ {file.name} ({(file.size / 1024).toFixed(1)} KB)</span>
                  <span className="file-staging-remove" onClick={() => removeFile(idx)}>✕</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Button styled to match the primary Trigger Classify navy/black button */}
        <button 
          type="submit" 
          disabled={selectedFiles.length === 0 || uploading}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            padding: '0.75rem 1.5rem',
            fontFamily: "'Outfit', sans-serif",
            fontWeight: 700,
            fontSize: '0.8rem',
            letterSpacing: '0.06em',
            textTransform: 'uppercase',
            border: 'none',
            borderRadius: '0px',
            backgroundColor: '#0F172A',
            color: '#ffffff',
            opacity: (selectedFiles.length === 0 || uploading) ? 0.35 : 1,
            cursor: (selectedFiles.length === 0 || uploading) ? 'not-allowed' : 'pointer',
            transition: 'all 0.15s ease',
          }}
          onMouseOver={e => {
            if (selectedFiles.length > 0 && !uploading) {
              e.currentTarget.style.backgroundColor = '#1E293B';
            }
          }}
          onMouseOut={e => {
            if (selectedFiles.length > 0 && !uploading) {
              e.currentTarget.style.backgroundColor = '#0F172A';
            }
          }}
        >
          {uploading ? 'Transmitting Packets...' : `Stage ${selectedFiles.length} Selected File(s)`}
        </button>

        {/* Console Log terminal style */}
        {(uploading || uploadLogs.length > 0) && (
          <div className="console-container">
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#FFFFFF', fontWeight: 600, borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '0.25rem' }}>
              <span>Console Log Status</span>
              <span>{uploadProgress}%</span>
            </div>
            {uploadLogs.map((log, idx) => (
              <div key={idx} style={{ marginTop: '0.1rem' }}>{log}</div>
            ))}
          </div>
        )}
      </form>
      </div>
    </div>
  );
};

export default FileUploader;
