import React, { useEffect, useState, useMemo } from 'react';
import { useUnoSocket } from '../hooks/useUnoSocket.ts';
import { CardHand } from './CardHand.tsx';
import { DiscardPile } from './DiscardPile.tsx';
import { OpponentSeat } from './OpponentSeat.tsx';
import type { GameState, PlayerState } from '../types/uno';

interface GameRoomProps {
  gameId: string; // The active game UUID to connect to
  playerId: string; // The resolved username of the current player
  onExit: () => void; // Callback to return to the matchmaking lobby
}

export const GameRoom: React.FC<GameRoomProps> = ({
  gameId,
  playerId,
  onExit,
}) => {
  const { connectRoom, sendAction, subscribe, getLatestState } = useUnoSocket();
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [errorLog, setErrorLog] = useState<string | null>(null);
  const [actionLogs, setActionLogs] = useState<string[]>([]);
  
  // Wild card state management
  const [showColorPicker, setShowColorPicker] = useState<boolean>(false);
  const [pendingCardIndex, setPendingCardIndex] = useState<number | null>(null);

  // 1. Setup real-time listeners on mount using the custom PubSub mechanism
  useEffect(() => {
    // Connect to room WebSocket endpoint
    connectRoom(gameId, playerId);

    // Subscribe to state updates to redraw the board layout dynamically
    const unsubscribeState = subscribe('state_update', (newState: GameState) => {
      setGameState(newState);
      setErrorLog(null); // Clear errors on successful synchronization
    });

    // Subscribe to connection changes to alert of drops
    const unsubscribeStatus = subscribe('player_status', (payload) => {
      console.log(`[Game Status Change] Player ${payload.player_id} is ${payload.status}`);
    });

    // Subscribe to gameplay errors to render alert messages
    const unsubscribeError = subscribe('error', (message: string) => {
      setErrorLog(message);
      // Auto-clear error notification banner after 3 seconds
      setTimeout(() => setErrorLog(null), 3000);
    });

    return () => {
      unsubscribeState();
      unsubscribeStatus();
      unsubscribeError();
    };
  }, [gameId, playerId, connectRoom, subscribe]);

  // 2. Separate current player's hand from the server payload
  const myPlayerState = useMemo<PlayerState | null>(() => {
    if (!gameState) return null;
    return gameState.players.find((p) => p.player_id === playerId) || null;
  }, [gameState, playerId]);

  // 3. Symmetrical Seat Sorting algorithm to distribute opponents beautifully
  const sortedOpponents = useMemo<PlayerState[]>(() => {
    if (!gameState) return [];
    
    const myIndex = gameState.players.findIndex((p) => p.player_id === playerId);
    if (myIndex === -1) return [];

    const opponents: PlayerState[] = [];
    const totalPlayers = gameState.players.length;

    for (let i = 1; i < totalPlayers; i++) {
      opponents.push(gameState.players[(myIndex + i) % totalPlayers]);
    }

    return opponents;
  }, [gameState, playerId]);

  // 4. Check if it is currently this player's turn based on turn index
  const isMyTurn = useMemo<boolean>(() => {
    if (!gameState) return false;
    const currentTurnPlayer = gameState.players[gameState.current_turn_index];
    return currentTurnPlayer?.player_id === playerId;
  }, [gameState, playerId]);

  // 5. Card play action pipeline with pre-validation for wildcard picker triggers
  const handlePlayCard = (index: number) => {
    if (!myPlayerState) return;
    const selectedCard = myPlayerState.hand[index];

    if (!selectedCard) return;

    if (selectedCard.color === 'black') {
      // Open modal to resolve wildcard active color before submitting action
      setPendingCardIndex(index);
      setShowColorPicker(true);
    } else {
      sendAction({
        action: 'play_card',
        card_index: index,
        chosen_color: null,
      });
    }
  };

  // 6. Submit wildcard color selections to backend server
  const handleColorSelect = (color: 'red' | 'blue' | 'green' | 'yellow') => {
    if (pendingCardIndex === null) return;

    sendAction({
      action: 'play_card',
      card_index: pendingCardIndex,
      chosen_color: color,
    });

    // Reset picker states
    setShowColorPicker(false);
    setPendingCardIndex(null);
  };

  // 7. Request to draw a card from the deck pile
  const handleDrawCard = () => {
    sendAction({ action: 'draw_card' });
  };

  // Check if target opponent ID has active turn
  const checkOpponentTurn = (opponentId: string): boolean => {
    if (!gameState) return false;
    const activePlayer = gameState.players[gameState.current_turn_index];
    return activePlayer?.player_id === opponentId;
  };

  if (!gameState) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-[#1a2c34] text-white">
        <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-emerald-500 mb-4" />
        <p className="text-sm font-semibold text-slate-400">Loading game room state...</p>
      </div>
    );
  }

  return (
    <div className="relative flex flex-col justify-between w-full h-screen max-h-[640px] bg-[#1a2c34] text-white overflow-hidden p-4 select-none">
      
      {/* 1. Header & Dynamic Error Notification Banner */}
      <header className="flex justify-between items-center h-10 z-10">
        <button 
          onClick={onExit}
          className="text-xs font-bold text-slate-400 hover:text-white px-3 py-1.5 rounded-lg bg-slate-900/30 border border-slate-800 backdrop-blur-sm transition-all"
        >
          ← Leave
        </button>
        <span className="text-xs font-mono font-bold tracking-tight text-slate-500">
          ROOM: {gameId.substring(0, 8)}...
        </span>
      </header>

      {/* Pop-up Error Alerts Banner */}
      {errorLog && (
        <div className="absolute top-14 left-4 right-4 z-50 py-2.5 px-4 bg-rose-950/80 border border-rose-800 backdrop-blur-md rounded-xl text-center shadow-xl shadow-black/40">
          <p className="text-xs font-bold text-rose-200">{errorLog}</p>
        </div>
      )}

      {/* 2. Top Area: Symmetrical Opponents cross-layout representation */}
      <div className="flex justify-center items-center gap-6 h-20 overflow-visible">
        {sortedOpponents.map((opponent) => (
          <OpponentSeat
            key={opponent.player_id}
            player={opponent}
            isCurrentTurn={checkOpponentTurn(opponent.player_id)}
          />
        ))}
      </div>

      {/* 3. Center Area: Deck, Discard Table and Action Logs */}
      <div className="flex flex-col items-center justify-center flex-1 my-2 relative">
        <div className="flex items-center justify-center gap-12 overflow-visible">
          
          {/* Symmetrical stacked Draw Deck pile button */}
          <div 
            onClick={handleDrawCard}
            className={`
              relative w-20 h-28 rounded-xl border-2 border-slate-500 bg-gradient-to-br from-red-700 via-red-800 to-red-950 
              shadow-2xl flex flex-col items-center justify-center cursor-pointer transform-gpu active:scale-95 transition-all
              ${isMyTurn ? 'ring-2 ring-emerald-500 animate-pulse' : ''}
            `}
          >
            <div className="w-14 h-22 rounded-lg border border-red-600/30 flex items-center justify-center">
              <span className="text-xs font-extrabold text-red-100 uppercase tracking-wider rotate-12">UNO</span>
            </div>
            <span className="absolute bottom-1.5 text-[8px] font-bold text-red-300">TAP TO DRAW</span>
          </div>

          {/* Central scatter-throw Discard Pile stack */}
          <DiscardPile
            discardPile={gameState.discard_pile}
            activeColor={gameState.active_color}
          />
        </div>
      </div>

      {/* 4. Bottom Area: Current Player Seat and Mathematical Trigonometric Hand fanning */}
      <div className="flex flex-col items-center gap-4 h-48 overflow-visible relative">
        
        {/* Dynamic Your Turn Status Pill & Timer countdown progress */}
        <div className="flex flex-col items-center z-10">
          <div className={`
            px-4 py-1.5 rounded-full border text-xs font-black tracking-wide flex items-center gap-1.5 transition-all
            ${isMyTurn 
              ? 'bg-emerald-950/50 border-emerald-500 text-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.25)] scale-105 animate-bounce' 
              : 'bg-slate-900/40 border-slate-800 text-slate-400'
            }
          `}>
            {isMyTurn ? '🟢 YOUR TURN' : '🕒 WAITING FOR OTHERS'}
          </div>
        </div>

        {/* Dynamic Card Hand mathematically fanning out from the zero-point */}
        {myPlayerState && (
          <div className="w-full h-32 overflow-visible">
            <CardHand
              hand={myPlayerState.hand}
              onPlayCard={handlePlayCard}
            />
          </div>
        )}
      </div>

      {/* 5. Winner Overlay Screens */}
      {gameState.status === 'finished' && (
        <div className="absolute inset-0 z-50 bg-slate-950/90 backdrop-blur-md flex flex-col items-center justify-center p-6 text-center animate-fade-in">
          <span className="text-6xl mb-4 animate-bounce">🏆</span>
          <h2 className="text-3xl font-extrabold text-yellow-400 tracking-tight">GAME OVER</h2>
          <p className="text-slate-300 text-sm mt-2 max-w-xs">
            Congratulations to <span className="text-white font-extrabold">{gameState.winner}</span> for winning the game!
          </p>
          <button
            onClick={onExit}
            className="mt-6 px-8 py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-xl shadow-lg shadow-emerald-950 transition-all active:scale-95 text-sm"
          >
            Return to Lobby
          </button>
        </div>
      )}

      {/* 6. Wild Card Selection Modal Container */}
      {showColorPicker && (
        <div className="absolute inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-6">
          <div className="bg-slate-900/90 border border-slate-800 p-6 rounded-3xl max-w-xs w-full text-center shadow-2xl">
            <h3 className="text-sm font-bold tracking-tight text-slate-300 mb-4">CHOOSE ACTIVE COLOR</h3>
            <div className="grid grid-cols-2 gap-3">
              <button 
                onClick={() => handleColorSelect('red')}
                className="py-4 rounded-2xl bg-gradient-to-br from-red-500 to-red-600 text-white font-bold text-xs shadow-lg active:scale-95 transition-all"
              >
                RED
              </button>
              <button 
                onClick={() => handleColorSelect('blue')}
                className="py-4 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 text-white font-bold text-xs shadow-lg active:scale-95 transition-all"
              >
                BLUE
              </button>
              <button 
                onClick={() => handleColorSelect('green')}
                className="py-4 rounded-2xl bg-gradient-to-br from-green-500 to-green-600 text-white font-bold text-xs shadow-lg active:scale-95 transition-all"
              >
                GREEN
              </button>
              <button 
                onClick={() => handleColorSelect('yellow')}
                className="py-4 rounded-2xl bg-gradient-to-br from-yellow-400 to-yellow-500 text-slate-900 font-bold text-xs shadow-lg active:scale-95 transition-all"
              >
                YELLOW
              </button>
            </div>
            <button
              onClick={() => {
                setShowColorPicker(false);
                setPendingCardIndex(null);
              }}
              className="mt-4 text-xs font-semibold text-slate-500 hover:text-white underline"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
};