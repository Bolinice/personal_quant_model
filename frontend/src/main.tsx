import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import theme from '@/styles/theme';
import App from './App';
import { StarfieldBackground, BackgroundProvider } from '@/components/background';
import { LanguageProvider } from '@/i18n';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <BackgroundProvider>
          <LanguageProvider>
            <StarfieldBackground />
            <App />
          </LanguageProvider>
        </BackgroundProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>
);
