import React, { useState } from 'react';
import axios from 'axios';

const ReconRunner = ({ onReconComplete }) => {
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');

  const handleRunRecon = async () => {
    setRunning(true);
    setError(null);
    setStatusMessage('Initiating classification engines...');
    
    try {
      const response = await axios.post("http://127.0.0.1:8000/api/reconcile/run");
      
      if (response.data.success) {
        setStatusMessage('Classification complete! Network metrics refreshed.');
        if (onReconComplete) {
          onReconComplete(response.data.summaries);
        }
      } else {
        setError(response.data.message || 'Execution error.');
      }
    } catch (err) {
      console.error(err);
      const errMsg = err.response?.data?.detail || err.message || 'Database connection error';
      setError(errMsg);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="widget-card" style={{ padding: '1.25rem 1.5rem' }}>
      <div className="dispatcher-flex">
        {/* Left Descriptive Text */}
        <div className="dispatcher-text">
          <h4 style={{ fontFamily: "'Outfit', sans-serif", fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
            Reconciliation Dispatcher
          </h4>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Initiate manual classification protocol for queued staging data.
          </p>
        </div>

        {/* Right Action Black Button matching Image 1 exactly */}
        <button 
          type="button" 
          className="btn-primary-black" 
          onClick={handleRunRecon}
          disabled={running}
        >
          {running ? 'Classifying...' : '▸ TRIGGER CLASSIFICATION'}
        </button>
      </div>

      {/* Logs console */}
      {statusMessage && !error && (
        <div style={{ fontSize: '0.75rem', color: 'var(--status-settled-text)', fontStyle: 'italic', marginTop: '0.75rem' }}>
          ✓ {statusMessage}
        </div>
      )}

      {error && (
        <div style={{ fontSize: '0.75rem', color: 'var(--status-failed-text)', fontStyle: 'italic', marginTop: '0.75rem' }}>
          ⚠ {error}
        </div>
      )}
    </div>
  );
};

export default ReconRunner;
