/**
 * BasketLab API client — v1
 *
 * All requests target /api/v1/ (versioned for future auth middleware).
 * In development the Vite proxy forwards /api/* → localhost:8000.
 * In production set VITE_API_BASE to the FastAPI server URL.
 *
 * Split by domain (issue #201): every name that pages import is still exported from here, so no page changes.
 */
export { API_BASE } from './http'
export * from './collections'
export * from './teams'
export * from './players'
export * from './lineups'
export * from './rotations'
export * from './shots'
export * from './possessions'
export * from './matches'
export * from './multiPhase'
export * from './predictive'
