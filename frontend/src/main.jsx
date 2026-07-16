import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './app';
import { AuthProvider } from './contexts/AuthContext';
import 'antd/dist/reset.css';
import './styles/index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  
    <BrowserRouter
      future={{
        v7_relativeSplatPath: true,
        v7_startTransition: true,
      }}
    >
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
 
);
