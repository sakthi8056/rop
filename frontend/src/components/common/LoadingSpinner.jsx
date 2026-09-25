import React from 'react';
import './common.css';

const LoadingSpinner = ({ size = 'medium', message }) => {
  return (
    <div className={`loading-container ${size}`}>
      <div className="spinner"></div>
      {message && <div className="loading-message">{message}</div>}
    </div>
  );
};

export default LoadingSpinner;
