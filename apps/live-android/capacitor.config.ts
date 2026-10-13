import type { CapacitorConfig } from '@capacitor/cli'

// androidScheme https: the WebView serves the app from https://localhost, which Web Workers
// and WebAssembly (Pyodide) need.
const config: CapacitorConfig = {
  appId: 'es.basketlab.live',
  appName: 'BasketLab Live',
  webDir: 'dist',
  android: { allowMixedContent: false },
  server: { androidScheme: 'https' },
  // Native HTTP for fetch/XHR: FEB's match page sends no CORS headers, so the live mode (issue #217) could not
  // read the JWT from a WebView otherwise.
  plugins: { CapacitorHttp: { enabled: true } },
}

export default config
