import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import { WalletProvider } from './context/WalletContext.jsx'
import { ToastProvider } from './context/ToastContext.jsx'
import { LanguageProvider } from './i18n/LanguageContext.jsx'
import PwaPrompts from './pwa/PwaPrompts.jsx'
import { registerServiceWorker } from './pwa/registerSW.js'
import './index.css'

// Register the service worker as early as possible. It's a no-op in dev.
registerServiceWorker()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <LanguageProvider>
        <ToastProvider>
          <AuthProvider>
            <WalletProvider>
              <App />
              <PwaPrompts />
            </WalletProvider>
          </AuthProvider>
        </ToastProvider>
      </LanguageProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
