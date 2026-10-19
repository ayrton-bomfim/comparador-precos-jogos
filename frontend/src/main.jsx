import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './contextos/AuthContext.jsx'
import { TemaProvider } from './contextos/TemaContext.jsx'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <AuthProvider>
      <TemaProvider>
        <App />
      </TemaProvider>
    </AuthProvider>
  </BrowserRouter>
)
