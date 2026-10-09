import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig(({command})=>({base: './', plugins: [react(), {
  name: 'development-csp',
  transformIndexHtml(html) { return command === 'serve' ? html.replace(/<meta http-equiv="Content-Security-Policy"[^>]*\/>/, '') : html; },
}]}));
