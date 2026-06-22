import random
import json
from typing import List, Optional
from pydantic import BaseModel
from redis.asyncio import Redis
from app.utils.redis_keys import get_game_state_key, get_game_lock_key

# ==========================================
# Domain Models (Pydantic Data Structures)
# ==========================================

class Card(BaseModel):
    """Represents a single UNO card."""
    color: str  # 'red', 'blue', 'green', 'yellow', 'black' (for wilds)
    value: str  # '0'-'9', 'skip', 'reverse', 'draw2', 'wild', 'wild4'

class PlayerState(BaseModel):
    """Represents the state of a single player in a game."""
    player_id: str
    hand: List[Card] = []

class GameState(BaseModel):
    """Represents the entire state of an active UNO game."""
    game_id: str
    players: List[PlayerState]
    current_turn_index: int = 0
    direction: int = 1  # 1 for clockwise, -1 for counter-clockwise
    draw_pile: List[Card]
    discard_pile: List[Card] = []
    status: str = "active"  # 'active', 'finished'
    winner: Optional[str] = None

# ==========================================
# Game Logic Service
# ==========================================

class GameService:
    def __init__(self, redis: Redis):
        self.redis = redis

    def _generate_uno_deck(self) -> List[Card]:
        """
        Generates a standard 108-card UNO deck.
        1 Zero, 2 of each 1-9, 2 of each action card per color.
        4 Wild, 4 Wild Draw Four.
        """
        colors = ['red', 'blue', 'green', 'yellow']
        deck = []
        
        for color in colors:
            # Add one '0' card per color
            deck.append(Card(color=color, value='0'))
            
            # Add two of each number (1-9) and action cards
            for value in ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'skip', 'reverse', 'draw2']:
                deck.append(Card(color=color, value=value))
                deck.append(Card(color=color, value=value))
                
        # Add Wild cards (black color)
        for _ in range(4):
            deck.append(Card(color='black', value='wild'))
            deck.append(Card(color='black', value='wild4'))
            
        # Shuffle the deck
        random.shuffle(deck)
        return deck

    async def create_game(self, game_id: str, player_ids: List[str]) -> GameState:
        """
        Initializes a new game, deals cards, and saves the state to Redis.
        """
        deck = self._generate_uno_deck()
        players = []
        
        # Deal 7 cards to each player
        for pid in player_ids:
            hand = [deck.pop() for _ in range(7)]
            players.append(PlayerState(player_id=pid, hand=hand))
            
        # Pop the first card to the discard pile (make sure it's not a wild for simplicity)
        discard_pile = []
        while True:
            first_card = deck.pop()
            if first_card.color != 'black':
                discard_pile.append(first_card)
                break
            else:
                # Put it back randomly if it's a wild card
                deck.insert(random.randint(0, len(deck)), first_card)

        # Create the initial Game State
        game_state = GameState(
            game_id=game_id,
            players=players,
            draw_pile=deck,
            discard_pile=discard_pile
        )
        
        # Save to Redis
        await self.save_game_state(game_state)
        return game_state

    async def get_game_state(self, game_id: str) -> Optional[GameState]:
        """
        Retrieves and parses the game state from Redis.
        """
        key = get_game_state_key(game_id)
        data = await self.redis.get(key)
        if data:
            # Parse the JSON string back into a Pydantic object
            return GameState.model_validate_json(data)
        return None

    async def save_game_state(self, game_state: GameState) -> None:
        """
        Serializes and saves the game state to Redis.
        """
        key = get_game_state_key(game_state.game_id)
        # model_dump_json() safely converts the Pydantic model to a JSON string
        await self.redis.set(key, game_state.model_dump_json())