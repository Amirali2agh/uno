import React, { useEffect, useState, useMemo } from 'react';
import { useUnoSocket } from '../hooks/useUnoSocket.ts';
import { CardHand } from './CardHand.tsx';
import { DiscardPile } from './DiscardPile.tsx';
import { OpponentSeat } from './OpponentSeat.tsx';
import type { GameState, PlayerState } from '../types/uno';

interface GameRoomProps {
  gameId: string;
  playerId: string;
  playerName: string;
  playerAvatar: string;
  onExit: () => void;
}

export const GameRoom: React.FC<GameRoomProps> = ({ gameId, playerId, playerName, playerAvatar, onExit }) => {
  const { connectRoom, sendAction, subscribe, roomStatus } = useUnoSocket();
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [errorLog, setErrorLog] = useState<string | null>(null);
  const [showColorPicker, setShowColorPicker] = useState<boolean>(false);
  const [pendingCardIndex, setPendingCardIndex] = useState<number | null>(null);
  const [gameOver, setGameOver] = useState<{ reason: string } | null>(null);
  // Set when the player intends to announce UNO together with the next play.
  const [unoIntent, setUnoIntent] = useState(false);

  useEffect(() => {
    connectRoom(gameId, playerId, playerName, playerAvatar);
    const unsubscribeState = subscribe('state_update', (newState) => {
      setGameState(newState);
      setErrorLog(null);
      // If state says finished but no game_over event came, still show the overlay
      if (newState.status === 'finished' && !gameOver) {
        setGameOver({ reason: newState.winner ? `${newState.winner} won!` : 'Game finished' });
      }
    });
    const unsubscribeError = subscribe('error', (message) => {
      setErrorLog(message);
      setTimeout(() => setErrorLog(null), 3000);
    });
    const unsubscribeGameOver = subscribe('game_over', (payload) => {
      setGameOver({ reason: payload.reason });
    });
    return () => {
      unsubscribeState();
      unsubscribeError();
      unsubscribeGameOver();
    };
  }, [gameId, playerId, connectRoom, subscribe]);

  const myPlayerState = useMemo(() => gameState?.players.find((p) => p.player_id === playerId) || null, [gameState, playerId]);

  const sortedOpponents = useMemo(() => {
    if (!gameState) return [];
    const myIndex = gameState.players.findIndex((p) => p.player_id === playerId);
    if (myIndex === -1) return [];
    const opponents: PlayerState[] = [];
    for (let i = 1; i < gameState.players.length; i++) {
      opponents.push(gameState.players[(myIndex + i) % gameState.players.length]);
    }
    return opponents;
  }, [gameState, playerId]);

  const isMyTurn = useMemo(() => {
    if (!gameState) return false;
    return gameState.players[gameState.current_turn_index]?.player_id === playerId;
  }, [gameState, playerId]);

  // After drawing a playable card the turn is kept: the player decides whether to
  // play it or pass.
  const canPass = isMyTurn && gameState?.drawn_card_index != null;

  // A draw is only allowed on your turn and only once per turn.
  const canDraw = isMyTurn && gameState?.drawn_card_index == null;

  /** Mirrors the server's playability rules so illegal cards are never clickable. */
  const isCardPlayable = (index: number): boolean => {
    if (!gameState || !myPlayerState || !isMyTurn) return false;

    const card = myPlayerState.hand[index];
    if (!card) return false;

    // While the drawn card is pending it is the only card that may be played.
    if (gameState.drawn_card_index != null) {
      return index === gameState.drawn_card_index;
    }

    const topCard = gameState.discard_pile[gameState.discard_pile.length - 1];
    const matches = card.color === 'black'
      || card.color === gameState.active_color
      || (topCard ? card.value === topCard.value : false);
    if (!matches) return false;

    // Wild Draw Four requires a hand with no card of the active colour.
    if (card.value === 'wild4') {
      const holdsActiveColor = myPlayerState.hand.some(
        (other, otherIndex) => otherIndex !== index && other.color === gameState.active_color,
      );
      if (holdsActiveColor) return false;
    }

    return true;
  };

  const canPlay = isMyTurn && myPlayerState ? myPlayerState.hand.some((_, index) => isCardPlayable(index)) : false;

  // Escape closes the colour picker: it must never trap the player.
  useEffect(() => {
    if (!showColorPicker) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') cancelColorPicker();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [showColorPicker]);

  const handleUnoButton = () => {
    if (!myPlayerState) return;
    if (myPlayerState.hand.length === 1) {
      sendAction({ action: 'say_uno' });
      setUnoIntent(false);
    } else {
      setUnoIntent((intent) => !intent);
    }
  };

  const handleChallenge = () => {
    sendAction({ action: 'challenge_uno' });
  };

  const handlePlayCard = (index: number) => {
    if (!myPlayerState || !isCardPlayable(index)) return;
    const selectedCard = myPlayerState.hand[index];
    if (!selectedCard) return;

    if (selectedCard.color === 'black') {
      setPendingCardIndex(index);
      setShowColorPicker(true);
    } else {
      sendAction({ action: 'play_card', card_index: index, chosen_color: null, say_uno: unoIntent });
      setUnoIntent(false);
    }
  };

  const cancelColorPicker = () => {
    setShowColorPicker(false);
    setPendingCardIndex(null);
  };

  const handleColorSelect = (color: 'red' | 'blue' | 'green' | 'yellow') => {
    if (pendingCardIndex === null) return;
    sendAction({
      action: 'play_card',
      card_index: pendingCardIndex,
      chosen_color: color,
      say_uno: unoIntent,
    });
    setUnoIntent(false);
    setShowColorPicker(false);
    setPendingCardIndex(null);
  };

  // --- Connecting / failed-connection states (never a blank screen) ---
  if (!gameState) {
    const failed = roomStatus === 'closed';
    return (
      <div className="flex flex-col items-center justify-center w-full h-screen bg-slate-950 text-white p-6 select-none">
        <div className="bg-slate-900/70 border border-slate-800 p-8 rounded-3xl shadow-2xl max-w-sm w-full text-center">
          {failed ? (
            <>
              <div className="text-4xl mb-4">🔌</div>
              <h2 className="text-lg font-black text-white mb-2">Connection lost</h2>
              <p className="text-sm text-slate-400 mb-6">
                The game room could not be reached. You can head back to the lobby and start a new match.
              </p>
              <button
                onClick={onExit}
                className="w-full py-3 rounded-xl bg-orange-600 text-white font-bold text-sm hover:bg-orange-500 transition-all active:scale-95 shadow-lg"
              >
                ← Back to Lobby
              </button>
            </>
          ) : (
            <>
              <div className="relative w-14 h-14 mx-auto mb-5">
                <div className="absolute inset-0 rounded-full border-t-4 border-orange-500 animate-spin" />
                <div className="absolute inset-2 rounded-full border-b-4 border-slate-600 animate-spin" />
              </div>
              <h2 className="text-lg font-black text-white mb-1">Joining the table…</h2>
              <p className="text-xs text-slate-400 mb-6">
                {roomStatus === 'reconnecting' ? 'Reconnecting to the game room…' : `Room ${gameId.substring(0, 8)}`}
              </p>
              <button
                onClick={onExit}
                className="w-full py-3 rounded-xl bg-slate-800 text-slate-300 font-bold text-sm border border-slate-700 hover:bg-slate-700 transition-all active:scale-95"
              >
                ← Leave
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    // بک‌گراند کاملاً تاریک و شیک
    <div className="relative flex flex-col w-full h-screen max-h-[640px] bg-slate-950 text-white overflow-hidden p-4 pt-4 pb-2 select-none">
      
      {/* هاله نوری نارنجی ملایم در مرکز میز */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_rgba(234,88,12,0.15)_0%,_transparent_60%)] pointer-events-none z-0"></div>

      {/* واترمارک مدرن، افقی و بسیار تمیز در مرکز */}
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none z-0">
        <span className="text-6xl sm:text-7xl font-black text-white opacity-[0.03] tracking-[0.3em] uppercase">
          Porteghal
        </span>
        <span className="text-xl sm:text-2xl font-bold text-orange-500 opacity-[0.15] tracking-[0.8em] mt-2 ml-3">
          پرتغال
        </span>
      </div>

      {/* Header */}
      <header className="relative flex justify-between items-center h-10 shrink-0 z-10">
        <button onClick={onExit} className="text-xs font-bold text-slate-400 hover:text-white px-4 py-2 rounded-full bg-slate-900/80 border border-slate-800 backdrop-blur-md transition-all">
          ← Leave
        </button>
        <span className="text-xs font-mono font-bold text-orange-400/70 bg-slate-900/80 px-3 py-1 rounded-full border border-slate-800">
          ROOM: {gameId.substring(0, 8)}
        </span>
      </header>

      {roomStatus === 'closed' && (
        <div className="absolute inset-0 z-50 bg-slate-950/90 backdrop-blur-md flex items-center justify-center p-6">
          <div className="bg-slate-900 border border-slate-700 p-8 rounded-3xl max-w-sm w-full text-center shadow-2xl">
            <div className="text-4xl mb-4">🔌</div>
            <h2 className="text-lg font-black text-white mb-2">Connection lost</h2>
            <p className="text-sm text-slate-400 mb-6">
              We could not reconnect to the game room. Your seat stays reserved for a short while, but
              this table can no longer be updated.
            </p>
            <button
              onClick={onExit}
              className="w-full py-3 rounded-xl bg-orange-600 text-white font-bold text-sm hover:bg-orange-500 transition-all active:scale-95 shadow-lg"
            >
              ← Back to Lobby
            </button>
          </div>
        </div>
      )}

      {roomStatus === 'reconnecting' && (
        <div className="absolute top-14 left-4 right-4 z-40 py-2 px-4 bg-amber-500/90 border border-amber-300 backdrop-blur-md rounded-2xl text-center shadow-2xl">
          <p className="text-xs font-bold text-slate-950">Connection lost — reconnecting…</p>
        </div>
      )}

      {errorLog && (
        <div className="absolute top-14 left-4 right-4 z-50 py-3 px-4 bg-rose-600/90 border border-rose-400 backdrop-blur-md rounded-2xl text-center shadow-2xl animate-fade-in">
          <p className="text-sm font-bold text-white">{errorLog}</p>
        </div>
      )}

      {/* Opponents */}
      <div className="relative flex justify-center items-center gap-6 h-16 shrink-0 overflow-visible mt-1 z-10">
        {sortedOpponents.map((opponent) => (
          <OpponentSeat
            key={opponent.player_id}
            player={opponent}
            isCurrentTurn={gameState.players[gameState.current_turn_index]?.player_id === opponent.player_id}
            canChallenge={gameState.uno_window === opponent.player_id}
            onChallenge={handleChallenge}
          />
        ))}
      </div>

      {/* Center Table */}
      <div className="relative flex flex-col items-center justify-center flex-1 min-h-0 z-10">
        <div className="flex items-center justify-center gap-10 overflow-visible">
          
          {/* Draw Deck */}
          <button
            type="button"
            onClick={() => sendAction({ action: 'draw_card' })}
            disabled={!canDraw}
            aria-label={canDraw ? 'Draw a card' : 'Waiting for your turn'}
            className={`
              relative w-20 h-28 rounded-xl border-[3px] border-white bg-red-600 
              shadow-[0_8px_15px_rgba(0,0,0,0.5)] flex flex-col items-center justify-center transform-gpu active:scale-95 transition-all
              ${canDraw ? 'cursor-pointer ring-4 ring-orange-500 ring-offset-4 ring-offset-slate-950 animate-pulse' : 'opacity-60 cursor-not-allowed'}
              focus:outline-none focus-visible:ring-4 focus-visible:ring-orange-400
            `}
          >
            <div className="absolute -bottom-2 -right-2 w-full h-full rounded-xl border-[3px] border-white bg-red-800 -z-10"></div>
            <div className="absolute -bottom-1 -right-1 w-full h-full rounded-xl border-[3px] border-white bg-red-700 -z-10"></div>
            
            <div className="w-14 h-20 bg-white rounded-[40%] transform -rotate-12 shadow-inner flex items-center justify-center">
              <span className="text-xl font-black text-red-500 transform rotate-12 tracking-tighter">UNO</span>
            </div>
          </button>

          <DiscardPile discardPile={gameState.discard_pile} activeColor={gameState.active_color} />
        </div>
      </div>

      {/* Player Hand & Turn Indicator */}
      <div className="relative flex flex-col items-center z-10">

        {/* Local Player Info */}
        <div className="flex items-center gap-2 px-3 py-0.5 rounded-full bg-slate-900/60 border border-slate-800/50 backdrop-blur-sm">
          <div className="w-5 h-5 rounded-full bg-slate-800 flex items-center justify-center border border-slate-700 overflow-hidden shrink-0">
            {playerAvatar ? (
              <img src={playerAvatar} alt="" className="w-full h-full object-cover" />
            ) : (
              <span className="text-[10px] font-bold text-slate-300">
                {(playerName || playerId).substring(0, 2).toUpperCase()}
              </span>
            )}
          </div>
          <span className="text-xs font-semibold text-slate-200">{playerName || playerId}</span>
          {isMyTurn && (myPlayerState?.hand.length ?? 99) <= 2 && (
            <button
              onClick={handleUnoButton}
              aria-label="Announce UNO"
              aria-pressed={myPlayerState?.hand.length === 1 ? undefined : unoIntent}
              className={`ml-1 px-2 py-0.5 rounded-full text-[9px] font-black tracking-wider transition-all active:scale-95 ${
                unoIntent || myPlayerState?.hand.length === 1
                  ? 'bg-orange-500 text-white shadow-lg shadow-orange-900/50 animate-pulse'
                  : 'bg-slate-800 text-slate-300 border border-slate-600 hover:bg-slate-700'
              }`}
            >
              UNO!
            </button>
          )}
        </div>

        <div className="flex flex-col items-center mt-1">
          <div className={`
            px-5 py-1.5 rounded-full border-2 text-[11px] font-black tracking-widest flex items-center gap-2 transition-all shadow-xl
            ${isMyTurn 
              ? 'bg-orange-500 border-orange-400 text-white scale-110 animate-bounce' 
              : 'bg-slate-900/80 border-slate-800 text-slate-500 backdrop-blur-md'
            }
          `}>
            {isMyTurn ? 'YOUR TURN' : 'WAITING...'}
          </div>

          {canPass && (
            <button
              onClick={() => sendAction({ action: 'pass_turn' })}
              className="mt-2 px-4 py-1 rounded-full bg-slate-800 border border-slate-600 text-[10px] font-black tracking-widest text-slate-200 hover:bg-slate-700 active:scale-95 transition-all"
            >
              PASS
            </button>
          )}
        </div>

        {isMyTurn && !canPlay && !canPass && (
          <p className="mt-1 text-[10px] font-bold tracking-wide text-slate-400">
            No playable card — draw from the deck.
          </p>
        )}

        {myPlayerState && (
          <div className="w-full overflow-visible -mt-1">
            <CardHand
              hand={myPlayerState.hand}
              onPlayCard={handlePlayCard}
              isPlayable={isCardPlayable}
            />
          </div>
        )}
      </div>

      {/* Game Over Overlay */}
      {gameOver && (
        <div className="absolute inset-0 z-40 bg-black/85 backdrop-blur-md flex flex-col items-center justify-center p-8">
          <div className="bg-slate-900 border border-slate-700/50 p-8 rounded-3xl max-w-xs w-full text-center shadow-2xl">
            <div className="text-5xl mb-4">🏆</div>
            <h2 className="text-xl font-black text-white mb-2">Game Over</h2>
            <p className="text-sm text-slate-400 mb-6">{gameOver.reason}</p>
            <button
              onClick={onExit}
              className="w-full py-3 rounded-xl bg-orange-600 text-white font-bold text-sm hover:bg-orange-500 transition-all active:scale-95 shadow-lg"
            >
              ← Back to Lobby
            </button>
          </div>
        </div>
      )}

      {/* Color Picker Modal */}
      {showColorPicker && (
        <div
          className="absolute inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-6"
          role="presentation"
          onClick={cancelColorPicker}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="color-picker-title"
            className="bg-slate-900 border border-slate-700 p-6 rounded-3xl max-w-xs w-full text-center shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <h3 id="color-picker-title" className="text-sm font-black tracking-widest text-white mb-1">
              CHOOSE COLOR
            </h3>
            <p className="text-[10px] font-semibold text-slate-400 mb-5">
              Pick the colour that continues the round.
            </p>
            <div className="grid grid-cols-2 gap-4">
              {([
                { color: 'red', label: 'Red', className: 'bg-red-500' },
                { color: 'blue', label: 'Blue', className: 'bg-blue-500' },
                { color: 'green', label: 'Green', className: 'bg-green-500' },
                { color: 'yellow', label: 'Yellow', className: 'bg-yellow-400' },
              ] as const).map(({ color, label, className }) => (
                <button
                  key={color}
                  type="button"
                  onClick={() => handleColorSelect(color)}
                  aria-label={`Choose ${label}`}
                  autoFocus={color === 'red'}
                  className={`h-16 rounded-2xl ${className} border-2 border-white shadow-lg active:scale-95 transition-all flex items-end justify-center pb-1 focus:outline-none focus-visible:ring-4 focus-visible:ring-white`}
                >
                  <span className="text-[10px] font-black tracking-wider text-slate-900/80">{label}</span>
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={cancelColorPicker}
              className="mt-5 w-full py-2.5 rounded-xl bg-slate-800 border border-slate-700 text-slate-300 text-xs font-bold hover:bg-slate-700 transition-all active:scale-95"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

    </div>
  );
};