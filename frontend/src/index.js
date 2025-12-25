import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

// Create stylesheet dynamically if not exists or rely on App's imports
// For this setup, we'll assume index.css might be missing so we won't import it if it breaks, 
// but standard CRA expects it. I'll include it and create a dummy one if needed.

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
