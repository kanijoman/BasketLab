/** The key that identifies a player across games: his uuid when the table gives one (FBCYL lists him by the `actorId` of one game, which changes from game to game; the analyses
 *  and the consistency are keyed by the uuid), else his id (FEB's is stable). Issue #711. */
export const playerKey = (player: { player_id: string | number; player_uuid?: string | null }): string => String(player.player_uuid ?? player.player_id)
