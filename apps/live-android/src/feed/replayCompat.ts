/** What a match kept on the device is stamped with (issue #562); the same number as ``REPLAY_COMPAT`` of ``src/live_core/version.py`` (a test keeps them equal).
 *  A match kept under an older number (or under none: before 0.4.1) may replay with errors, so the app says so and offers to delete it. */
export const REPLAY_COMPAT = 3

export const isStale = (compat?: number): boolean => (compat ?? 1) < REPLAY_COMPAT

export const STALE_NOTE = 'Guardado con una versión anterior de la app: al revisarlo puede mostrar avisos, alineaciones o duraciones incorrectas. Si ves errores, elimínalo.'
