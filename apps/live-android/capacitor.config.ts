import type { CapacitorConfig } from '@capacitor/cli'

// androidScheme https: the WebView serves the app from https://localhost, which Web Workers
// and WebAssembly (Pyodide) need.
const config: CapacitorConfig = {
  appId: 'es.basketlab.live',
  appName: 'BasketLab Live',
  webDir: 'dist',
  android: { allowMixedContent: false },
  server: { androidScheme: 'https' },
}

export default config
