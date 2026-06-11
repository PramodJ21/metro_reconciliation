import React from 'react';

/**
 * Custom Error Display Alert Component.
 * ImplementsOutfit font, 100% sharp corners, and highly visual border-coded themeing.
 *
 * @param {Object} props
 * @param {boolean} props.show
 * @param {string} props.title
 * @param {string} props.message
 * @param {'error'|'success'|'warning'} props.type
 * @param {function} props.onClose
 */
function ErrorDisplay({ show, title, message, type = 'error', onClose }) {
  if (!show) return null;

  let iconText = '✕';
  if (type === 'success') iconText = '✓';
  if (type === 'warning') iconText = '⚠';

  return (
    <div className="custom-alert-overlay" onClick={onClose}>
      <div 
        className={`custom-alert-box ${type}`} 
        onClick={(e) => e.stopPropagation()}
      >
        <div className="custom-alert-header">
          <span className="custom-alert-icon">{iconText}</span>
          <h3 className="custom-alert-title">{title}</h3>
        </div>
        
        <div className="custom-alert-body">
          {message}
        </div>
        
        <div className="custom-alert-btn-container">
          <button 
            type="button" 
            className="btn-alert-close"
            onClick={onClose}
          >
            Acknowledge
          </button>
        </div>
      </div>
    </div>
  );
}

export default ErrorDisplay;
