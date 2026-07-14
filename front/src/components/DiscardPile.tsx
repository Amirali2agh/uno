import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Card } from './Card.tsx'; // Explicitly typed with TSX extension
import type { Card as CardType } from '../types/uno';

interface DiscardPileProps {
  discardPile: CardType[]; // List of all cards played in the discard pile
  activeColor: string; // The current active color governing game rules
}

// Simple Linear Congruential Generator (LCG) for deterministic seeded random results
const getSeededRandom = (seed: string): number => {
  let h = 2166136261 >>> 0; // FNV-1a 32-bit offset basis
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619); // Multiply by FNV-1a 32-bit prime
  }
  // Extract a fractional float value between 0 and 1
  const x = Math.sin(h >>> 0) * 10000;
  return x - Math.floor(x);
};

export const DiscardPile: React.FC<DiscardPileProps> = ({
  discardPile,
  activeColor,
}) => {
  // Extract only the top few cards to keep DOM rendering lightweight
  const visibleCards = useMemo(() => {
    return discardPile.slice(-5); // Render only the top 5 cards for layout stack depth
  }, [discardPile]);

  // Generate unique rotation and offset for each card in the stack deterministically
  const scatterEffects = useMemo(() => {
    return visibleCards.map((card, idx) => {
      // Create a unique seed using color, value, and absolute index in the stack
      const seed = `${card.color}_${card.value}_${discardPile.length - visibleCards.length + idx}`;
      
      // Calculate scatter values using Seeded Random to prevent rendering flickering
      const rotate = (getSeededRandom(seed + '-rot') * 30) - 15; // Range: -15 to +15 deg
      const x = (getSeededRandom(seed + '-x') * 16) - 8; // Range: -8px to +8px
      const y = (getSeededRandom(seed + '-y') * 16) - 8; // Range: -8px to +8px

      return { x, y, rotate };
    });
  }, [visibleCards, discardPile.length]);

  // Inline styling helper for active border glow representing active_color
  const getGlowColor = (color: string) => {
    switch (color) {
      case 'red': return 'shadow-[0_0_20px_rgba(239,68,68,0.5)] border-red-500';
      case 'blue': return 'shadow-[0_0_20px_rgba(59,130,246,0.5)] border-blue-500';
      case 'green': return 'shadow-[0_0_20px_rgba(16,185,129,0.5)] border-green-500';
      case 'yellow': return 'shadow-[0_0_20px_rgba(234,179,8,0.5)] border-yellow-500';
      default: return 'shadow-xl border-slate-700';
    }
  };

  return (
    <div className="relative w-36 h-44 flex items-center justify-center select-none">
      {/* Visual dynamic perimeter glow outlining the board table state */}
      <div className={`absolute w-32 h-40 rounded-2xl border-2 transition-all duration-500 ${getGlowColor(activeColor)} bg-slate-900/40 backdrop-blur-sm`} />

      {/* Layered deterministic throw layout stack */}
      {visibleCards.map((card, idx) => {
        const style = scatterEffects[idx] || { x: 0, y: 0, rotate: 0 };

        return (
          <motion.div
            key={`${card.color}-${card.value}-${discardPile.length - visibleCards.length + idx}`}
            initial={{ scale: 1.5, opacity: 0, y: -100 }}
            animate={{
              scale: 1,
              opacity: 1,
              x: style.x,
              y: style.y,
              rotate: style.rotate,
            }}
            transition={{
              type: 'spring',
              stiffness: 150,
              damping: 15,
            }}
            style={{ position: 'absolute' }}
          >
            <Card
              card={card}
              isHoverable={false} // Disable hover effects for discard pile to match Plato style
            />
          </motion.div>
        );
      })}

      {/* Edge-case fallback: Render empty container if discard pile contains no cards */}
      {visibleCards.length === 0 && (
        <span className="text-slate-500 text-xs font-semibold">Ready</span>
      )}
    </div>
  );
};