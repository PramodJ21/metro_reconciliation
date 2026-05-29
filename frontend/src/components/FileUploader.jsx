import React, { useState, useRef } from 'react';
import axios from 'axios';

const FileUploader = ({ onUploadSuccess, setGlobalLoading, dbStatus }) => {
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
    let stagingInterval = null;
    let currentStagedCount = 0;

    const clearStagingInterval = () => {
      if (stagingInterval) {
        clearInterval(stagingInterval);
        stagingInterval = null;
      }
    };

    const startStagingSimulation = () => {
      if (stagingInterval) return;
      
      // Start counting up from 1 to totalFiles
      currentStagedCount = 1;
      
      if (setGlobalLoading) {
        setGlobalLoading(prev => ({
          ...prev,
          progress: 82,
          message: `Staging database: file ${currentStagedCount} of ${totalFiles} successfully staged...`
        }));
      }

      stagingInterval = setInterval(() => {
        if (currentStagedCount < totalFiles) {
          currentStagedCount += 1;
          const computedProgress = Math.min(98, 80 + Math.round((currentStagedCount / totalFiles) * 18));
          setUploadProgress(computedProgress);
          if (setGlobalLoading) {
            setGlobalLoading(prev => ({
              ...prev,
              progress: computedProgress,
              message: `Staging database: file ${currentStagedCount} of ${totalFiles} successfully staged...`
            }));
          }
        }
      }, Math.max(300, 3000 / totalFiles)); // Stagger files smoothly over 3 seconds max
    };

    setUploading(true);
    setUploadProgress(10);
    setUploadLogs(["Initiating transaction payload...", "Connecting to Ingest API..."]);

    if (setGlobalLoading) {
      setGlobalLoading({
        active: true,
        title: 'Ingesting Data Packets',
        progress: 10,
        message: `Packaging file data stream (0 of ${totalFiles} files staged)...`
      });
    }

    const formData = new FormData();
    formData.append("app_name", appName);
    formData.append("channel", channel);
    formData.append("clear_existing", clearExisting ? "true" : "false");
    
    selectedFiles.forEach((file) => {
      formData.append("files", file);
    });

    try {
      setUploadProgress(30);
      setUploadLogs(prev => [...prev, `Uploading packet ${totalFiles} file(s)...`]);
      
      if (setGlobalLoading) {
        setGlobalLoading(prev => ({
          ...prev,
          progress: 30,
          message: `Transmitting ${totalFiles} file(s) to Ingest server...`
        }));
      }
      
      const response = await axios.post("http://127.0.0.1:8000/api/reconcile/upload", formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          
          if (percentCompleted < 100) {
            const computedProgress = Math.min(80, 10 + Math.round(percentCompleted * 0.7));
            const filesUploaded = Math.min(totalFiles, Math.ceil((percentCompleted / 100) * totalFiles));
            setUploadProgress(computedProgress);
            if (setGlobalLoading) {
              setGlobalLoading(prev => ({
                ...prev,
                progress: computedProgress,
                message: `Transmitting data: ${filesUploaded} of ${totalFiles} file(s) uploaded (${percentCompleted}%)`
              }));
            }
          } else {
            // Upload complete, starting staging database simulation
            setUploadProgress(80);
            if (setGlobalLoading) {
              setGlobalLoading(prev => ({
                ...prev,
                progress: 80,
                message: `Staging database: file 1 of ${totalFiles} successfully staged...`
              }));
            }
            startStagingSimulation();
          }
        }
      });

      clearStagingInterval();
      setUploadProgress(100);
      
      const data = response.data;
      if (data.success) {
        setUploadLogs(prev => [
          ...prev, 
          `✓ File transmission successful!`, 
          `Inserted ${data.total_rows_loaded.toLocaleString()} rows into ${data.staging_table}.`
        ]);
        
        data.processed_files.forEach(f => {
          setUploadLogs(prev => [...prev, `   ↳ ${f.filename}: ${f.status} (${f.rows_loaded} rows)`]);
        });
        
        if (setGlobalLoading) {
          setGlobalLoading(prev => ({
            ...prev,
            progress: 100,
            message: `✓ Success! Staged ${totalFiles} of ${totalFiles} file(s). Bulk inserted ${data.total_rows_loaded.toLocaleString()} rows.`
          }));
          setTimeout(() => {
            setGlobalLoading({ active: false, title: '', progress: 0, message: '' });
          }, 1500);
        }

        setSelectedFiles([]);
        if (onUploadSuccess) onUploadSuccess();
      } else {
        setUploadLogs(prev => [...prev, `⚠ Ingestion reported error: ${data.message || 'Unknown'}`]);
        if (setGlobalLoading) {
          setGlobalLoading(prev => ({
            ...prev,
            progress: 0,
            message: `⚠ Failed: ${data.message || 'Unknown'}`
          }));
          setTimeout(() => {
            setGlobalLoading({ active: false, title: '', progress: 0, message: '' });
          }, 1800);
        }
      }
    } catch (err) {
      clearStagingInterval();
      console.error(err);
      const errMsg = err.response?.data?.detail || err.message || "Network timeout";
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

      // Beautiful flat B&W toast alert for structure/header validation failures
      if (err.response?.status === 400 && errMsg.includes("Wrong file structure")) {
        alert(`✕ WRONG FILE STRUCTURE DETECTED\n\n${errMsg.replace("Wrong file structure: ", "")}\n\nPlease check your spreadsheet columns and try again.`);
      } else {
        alert(`✕ INGESTION FAILURE\n\n${errMsg}`);
      }
    } finally {
      clearStagingInterval();
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
                  ? `All staging pipelines connected. Database is online and holding ${totalStagedRows.toLocaleString()} staged rows.` 
                  : 'Failed to establish connection to PostgreSQL local database. Please check your credentials in .env.'}
              </p>
            </div>
          </div>
          {dbStatus?.connected && (
            <div style={{ padding: '0.25rem 0.75rem', background: 'var(--color-neutral)', borderRadius: '0px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Staged Rows</div>
              <div style={{ fontSize: '0.95rem', fontWeight: 800, color: 'var(--color-primary)' }}>{totalStagedRows.toLocaleString()}</div>
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
          <div 
            className="file-staging-list" 
            style={{ 
              marginBottom: '1.5rem',
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
        )}

        {/* Action Button styled as the styleguide's secondary button or black button */}
        <button 
          type="submit" 
          className="btn-primary-black"
          disabled={selectedFiles.length === 0 || uploading}
          style={{ width: '100%', justifyContent: 'center' }}
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
