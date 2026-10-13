import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './ui/App'
import '@design/tokens.css'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
