/**
 * BasketLab data layer: what the pages read, by the published files
 *
 * The web reads the published files (`localdata`, `webdata`) and nothing else: the API was retired (epic #1199).
 *
 * Split by domain (issue #201): every name that pages import is still exported from here, so no page changes.
 */
export * from './collections'
export * from './teams'
export * from './players'
export * from './lineups'
export * from './rotations'
export * from './shots'
export * from './possessions'
export * from './matches'
export * from './multiPhase'
