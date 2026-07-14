import React from 'react';
import type { Card as CardType } from '../types/uno';

interface CardProps {
  card: CardType; // The card data model
  onClick?: () => void; // Click handler when the card is pressed
  customAssetUrl?: string; // Optional dynamic asset URL for custom skins
  isHoverable?: boolean; // Determines if hover scaling effects should apply
}

export const Card: React.FC<CardProps> = ({
  card,
  onClick,
  customAssetUrl,
  isHoverable = true,
}) => {
  // Map standard colors to beautiful Tailwind color classes
  const getColorClass = (color: string) => {
    switch (color) {
      case 'red': return 'bg-gradient-to-br from-red-500 to-red-600 text-white border-red-400';
      case 'blue': return 'bg-gradient-to-br from-blue-500 to-blue-600 text-white border-blue-400';
      case 'green': return 'bg-gradient-to-br from-green-500 to-green-600 text-white border-green-400';
      case 'yellow': return 'bg-gradient-to-br from-yellow-400 to-yellow-500 text-slate-900 border-yellow-300';
      case 'black': return 'bg-slate-950 text-white border-slate-800';
      default: return 'bg-slate-800 text-white border-slate-700';
    }
  };

  // Convert special action values to clean typography indicators
  const getDisplayValue = (value: string) => {
    switch (value) {
      case 'skip': return '🚫';
      case 'reverse': return '🔁';
      case 'draw2': return '+2';
      case 'wild': return '🌈';
      case 'wild4': return '+4';
      default: return value;
    }
  };

  return (
    <div
      onClick={onClick}
      className={`
        relative w-16 h-24 min-w-[4rem] rounded-xl border-2 flex flex-col items-center justify-between p-2 
        shadow-lg select-none cursor-pointer transform-gpu transition-all duration-200 origin-bottom
        ${getColorClass(card.color)}
        ${isHoverable ? 'hover:-translate-y-4 hover:scale-105 hover:shadow-2xl hover:z-50' : ''}
      `}
    >
      {/* If custom image skin exists, render it. Otherwise, fallback to the elegant CSS card face */}
      {customAssetUrl ? (
        <img
          src={customAssetUrl}
          alt={`${card.color} ${card.value}`}
          className="w-full h-full object-contain"
          draggable={false}
        />
      ) : (
        <>
          {/* Top-Left Tiny Value */}
          <span className="self-start text-xs font-black tracking-tight leading-none uppercase">
            {getDisplayValue(card.value)}
          </span>

          {/* Central Stylized Bold Value */}
          <div className="flex items-center justify-center flex-1">
            <span className={`text-xl font-black tracking-tighter leading-none uppercase ${card.color === 'black' ? 'animate-pulse' : ''}`}>
              {getDisplayValue(card.value)}
            </span>
          </div>

          {/* Bottom-Right Tiny Value (Inverted for real-card design) */}
          <span className="self-end text-xs font-black tracking-tight leading-none uppercase rotate-180">
            {getDisplayValue(card.value)}
          </span>
        </>
      )}
    </div>
  );
};