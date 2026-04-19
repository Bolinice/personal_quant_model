import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ThemeProvider, CssBaseline } from '@mui/material'
import theme from '@/styles/theme'
import App from './App'
import { StarfieldBackground } from '@/components/background'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <StarfieldBackground />
        <App />
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>,
)
