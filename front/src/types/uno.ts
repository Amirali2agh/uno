// --- Core Card Entities ---

export interface Card {
  color: 'red' | 'blue' | 'green' | 'yellow' | 'black'; // Standard UNO colors, black represents special/wild cards
  value: '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9' | 'skip' | 'reverse' | 'draw2' | 'wild' | 'wild4'; // All possible values on UNO cards
}

// --- Player & Game State Entities ---

export interface PlayerState {
  player_id: string; // Unique string identifier for the player
  hand: Card[]; // List of cards in this player's hand (filtered or unfiltered from backend)
}

export interface GameState {
  game_id: string; // UUID of the active game session
  players: PlayerState[]; // Array of players participating in this match
  current_turn_index: number; // Index indicating whose turn it is in the players array
  direction: number; // Game rotation direction: 1 for clockwise, -1 for counter-clockwise
  draw_pile: Card[]; // Unplayed draw deck (exposed in raw payload)
  discard_pile: Card[]; // Cards played so far on the board
  active_color: string; // The color currently in play on the discard table
  status: 'active' | 'finished'; // Current execution status of the game room
  winner: string | null; // Winner's player_id, null if game is ongoing
}

// --- Server-to-Client WebSocket Payloads (Incoming) ---

export interface MatchFoundMessage {
  event: 'match_found'; // Event key dispatched from matchmaking queue
  game_id: string; // Game room ID assigned for the connection
}

export interface StateUpdateMessage {
  type: 'state_update'; // Broadcasted state payload after turns/draws
  state: GameState; // Complete payload of the active game state
}

export interface PlayerStatusMessage {
  type: 'player_status'; // Disconnected or reconnected notifications
  player_id: string; // The target player affected by this connection status
  status: 'connected' | 'disconnected'; // Action state of connection lifecycle
}

export interface ErrorMessage {
  type: 'error'; // Error packet for illegal moves or out of turn actions
  message: string; // System message to print/display to the active user
}

// Union representing all possible messages from Room WebSocket
export type RoomMessage = StateUpdateMessage | PlayerStatusMessage | ErrorMessage;

// --- Client-to-Server WebSocket Payloads (Outgoing Actions) ---

export interface DrawCardAction {
  action: 'draw_card'; // Requests drawing one card from the deck
}

export interface PlayCardAction {
  action: 'play_card'; // Requests playing a specific card from the hand
  card_index: number; // The index inside the current hand of the client player
  chosen_color: 'red' | 'blue' | 'green' | 'yellow' | null; // Color picked for 'black' wildcards
}

// Union representing all actions playable by client
export type GameAction = DrawCardAction | PlayCardAction;
// --- Dynamic Asset & Theme System Types ---

export interface CardAssetMap {
  // Key format: "color_value" (e.g., "red_7", "black_wild4"). Value: path to SVG/PNG
  [key: string]: string; 
}

export interface GameTheme {
  id: string; // Unique identifier for the active custom theme
  name: string; // Display name of the theme shown in settings (e.g., "Plato Style")
  tableBackgroundUrl: string; // URL/Path for the central table background image/texture
  cardAssets: CardAssetMap; // Dynamic mapping dictionary to resolve card face image paths
  cardBackUrl: string; // URL/Path for the opponent's card backs and draw pile graphic
}