import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import '@fontsource-variable/inter';
import '@fontsource-variable/jetbrains-mono';
import { AppV2 } from './v2/AppV2';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AppV2 />
    </BrowserRouter>
  </StrictMode>,
);
