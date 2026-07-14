import React, { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card } from './Card';
import type { Card as CardType } from '../types/uno';

interface CardHandProps {
  hand: CardType[]; // List of cards in the player's active hand
  onPlayCard: (index: number) => void; // Triggered when a card from hand is selected
  customAssets?: Record<string, string>; // Dynamic skins lookup dictionary
}

export const CardHand: React.FC<CardHandProps> = ({
  hand,
  onPlayCard,
  customAssets = {},
}) => {
  // Compress array beforehand to avoid math anomalies with empty slots
  const validCards = useMemo(() => hand.filter(Boolean), [hand]);

  // Trigonometric arc calculations memorized to prevent heavy layout recalculation
  const positionedCards = useMemo(() => {
    const N = validCards.length;
    if (N === 0) return [];

    const radius = 350; // The radius of the circular path anchor in pixels
    const maxSpread = Math.min(60, 8 * (N - 1)); // Limits the max fan spread angle to 60 degrees
    const angleStep = N > 1 ? maxSpread / (N - 1) : 0; // Steps between each fanned card
    const midIndex = (N - 1) / 2; // Midpoint reference to balance the arc left and right

    return validCards.map((card, index) => {
      // Calculate relative degrees from the midpoint
      const cardAngleDeg = (index - midIndex) * angleStep;
      // Convert degrees to radians for mathematical functions
      const cardAngleRad = (cardAngleDeg * Math.PI) / 180;

      // Trigonometry calculation for absolute 2D arc coordinate mapping
      const x = Math.sin(cardAngleRad) * radius;
      const y = (Math.cos(cardAngleRad) - 1) * radius; // Depresses the Y-axis symmetrically away from the midpoint
      const rotate = cardAngleDeg; // Aligns card rotation with the circle tangent

      return {
        card,
        originalIndex: index, // Track original index for action callbacks
        transform: { x, y, rotate },
      };
    });
  }, [validCards]);

  return (
    <div className="relative w-full h-40 max-w-md mx-auto flex items-end justify-center overflow-visible pb-4">
      {/* Absolute center zero-point anchor container for trigonometric projection */}
      <div className="absolute bottom-4 flex items-center justify-center w-0 h-0 overflow-visible">
        <AnimatePresence mode="popLayout">
          {positionedCards.map(({ card, originalIndex, transform }) => {
            // Dynamic skin resolve key construction
            const assetKey = `${card.color}_${card.value}`;
            const customAssetUrl = customAssets[assetKey];

            return (
              <motion.div
                key={`${card.color}-${card.value}-${originalIndex}`}
                layout // Smoothly slides adjacent cards when gap transitions occur
                initial={{ opacity: 0, scale: 0.2, y: 100 }}
                animate={{
                  opacity: 1,
                  scale: 1,
                  x: transform.x,
                  y: transform.y,
                  rotate: transform.rotate,
                }}
                exit={{ opacity: 0, scale: 0.5, y: -80, rotate: 0 }}
                transition={{
                  type: 'spring',
                  stiffness: 140,
                  damping: 18,
                  mass: 0.8,
                }}
                style={{
                  position: 'absolute',
                  transformOrigin: 'bottom center', // Crucial: anchor scaling relative to the hand base
                }}
              >
                <Card
                  card={card}
                  onClick={() => onPlayCard(originalIndex)}
                  customAssetUrl={customAssetUrl}
                />
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
};