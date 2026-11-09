import random
from contextlib import asynccontextmanager
from typing import AsyncIterator, List, Optional
from pydantic import BaseModel
from redis.asyncio import Redis
from app.utils.redis_keys import get_game_state_key, get_game_lock_key

# ==========================================
# Action results (نتیجهٔ عملیات بازیکن)
# ==========================================

VALID_COLORS = ('red', 'blue', 'green', 'yellow')

# Game state must not live in Redis forever: an active game is dropped after an
# hour without a write, a finished one is kept only long enough for the clients to
# read the result.
GAME_ACTIVE_TTL_SECONDS = 3600
GAME_FINISHED_TTL_SECONDS = 120

# Reason codes are part of the wire protocol: the client maps them to text, so
# they must stay stable.
REASON_MESSAGES = {
    "game_not_found": "That game does not exist any more.",
    "game_finished": "This game is already over.",
    "not_your_turn": "It is not your turn.",
    "card_not_in_hand": "You do not hold that card.",
    "must_play_drawn_card": "After drawing you may only play the drawn card.",
    "invalid_card": "That card does not match the colour or the value on the table.",
    "color_required": "A wild card needs a colour to be chosen.",
    "invalid_color": "That is not a valid UNO colour.",
    "wild4_has_matching_color": "A Wild Draw Four needs a hand with no card of the active colour.",
    "already_drawn": "You already drew a card this turn.",
    "nothing_to_pass": "There is no drawn card to pass on.",
    "cannot_call_uno": "You can only call UNO while holding exactly one card.",
    "nothing_to_challenge": "There is no UNO call to challenge.",
    "no_cards_left": "Both piles are empty.",
    "queue_full": "The matchmaking queue is busy.",
    "game_busy": "The game is busy, please retry.",
}


class ActionResult(BaseModel):
    """نتیجهٔ یک اقدام بازیکن، همراه با کد دلیل برای کلاینت"""

    ok: bool
    code: str = "ok"
    message: str = ""
    # Set by challenge_uno: the player who took the penalty.
    player_id: Optional[str] = None


def success(**extra) -> ActionResult:
    return ActionResult(ok=True, **extra)


def failure(code: str) -> ActionResult:
    return ActionResult(ok=False, code=code, message=REASON_MESSAGES.get(code, code))


# ==========================================
# Models (ساختار داده‌های بازی)
# ==========================================

class Card(BaseModel):
    color: str
    value: str

class PlayerView(BaseModel):
    """نمای یک بازیکن از بازیکنان دیگر: بدون دست حریف"""

    player_id: str
    player_name: str = ""
    player_avatar: str = ""
    hand: List[Card] = []
    hand_size: int = 0
    uno_declared: bool = False


class GameView(BaseModel):
    """نمای امن وضعیت بازی برای یک بازیکن مشخص"""

    game_id: str
    players: List[PlayerView]
    current_turn_index: int
    direction: int
    discard_pile: List[Card] = []
    active_color: str
    status: str
    winner: Optional[str] = None
    drawn_card_index: Optional[int] = None
    uno_window: Optional[str] = None
    draw_pile_size: int = 0


class PlayerState(BaseModel):
    player_id: str
    player_name: str = ""
    player_avatar: str = ""
    hand: List[Card] = []
    # True once the player has announced UNO while holding one card.
    uno_declared: bool = False

class GameState(BaseModel):
    game_id: str
    players: List[PlayerState]
    current_turn_index: int = 0
    direction: int = 1
    draw_pile: List[Card]
    discard_pile: List[Card] = []
    active_color: str = ""
    status: str = "active"
    winner: Optional[str] = None
    # Set while the current player has drawn and may still play that card.
    # ``None`` means the player must play from hand or draw.
    drawn_card_index: Optional[int] = None
    # Player who went down to one card and can still be challenged for not
    # announcing UNO. Cleared as soon as the next player acts.
    uno_window: Optional[str] = None

    def for_player(self, player_id: str) -> GameView:
        """Project the state for one viewer: only their own hand, opponents as counts.

        The draw pile is reduced to its size: the order of future draws must never
        leave the server.
        """
        return GameView(
            game_id=self.game_id,
            players=[
                PlayerView(
                    player_id=p.player_id,
                    player_name=p.player_name,
                    player_avatar=p.player_avatar,
                    hand=list(p.hand) if p.player_id == player_id else [],
                    hand_size=len(p.hand),
                    uno_declared=p.uno_declared,
                )
                for p in self.players
            ],
            current_turn_index=self.current_turn_index,
            direction=self.direction,
            discard_pile=list(self.discard_pile),
            active_color=self.active_color,
            status=self.status,
            winner=self.winner,
            drawn_card_index=self.drawn_card_index,
            uno_window=self.uno_window,
            draw_pile_size=len(self.draw_pile),
        )

# ==========================================
# Game Service (منطق اصلی بازی)
# ==========================================

class GameService:
    def __init__(
        self,
        redis: Redis,
        lock_ttl_seconds: float = 10.0,
        lock_blocking_timeout: float = 3.0,
    ):
        self.redis = redis
        self.lock_ttl_seconds = lock_ttl_seconds
        self.lock_blocking_timeout = lock_blocking_timeout

    @asynccontextmanager
    async def _game_lock(self, game_id: str) -> AsyncIterator[bool]:
        """Acquire the per-game distributed lock with a bounded wait.

        Yields False when the lock could not be acquired in time, so callers can
        answer with a structured error instead of hanging forever.
        """
        lock = self.redis.lock(
            get_game_lock_key(game_id),
            timeout=self.lock_ttl_seconds,
            blocking_timeout=self.lock_blocking_timeout,
        )
        try:
            acquired = await lock.acquire(blocking=True)
        except Exception:  # connection/lock errors must not escape as 500s
            acquired = False

        try:
            yield acquired
        finally:
            if acquired:
                try:
                    await lock.release()
                except Exception:
                    # The lock may have expired; the game state is still consistent.
                    pass

    def _generate_uno_deck(self) -> List[Card]:
        """تولید و بُر زدن ۱۰۸ کارت استاندارد اونو"""
        colors = ['red', 'blue', 'green', 'yellow']
        deck = []
        for color in colors:
            deck.append(Card(color=color, value='0'))
            for value in ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'skip', 'reverse', 'draw2']:
                deck.append(Card(color=color, value=value))
                deck.append(Card(color=color, value=value))
        for _ in range(4):
            deck.append(Card(color='black', value='wild'))
            deck.append(Card(color='black', value='wild4'))
        random.shuffle(deck)
        return deck

    async def create_game(self, game_id: str, players_data: list[dict]) -> GameState:
        """ساخت بازی جدید و پخش کارت‌ها"""
        deck = self._generate_uno_deck()
        players = [
            PlayerState(
                player_id=p["player_id"],
                player_name=p.get("player_name", ""),
                player_avatar=p.get("player_avatar", ""),
                hand=[deck.pop() for _ in range(7)]
            )
            for p in players_data
        ]
        
        discard_pile = []
        while True:
            first_card = deck.pop()
            if first_card.color != 'black':
                discard_pile.append(first_card)
                break
            deck.insert(random.randint(0, len(deck)), first_card)

        game_state = GameState(
            game_id=game_id,
            players=players,
            draw_pile=deck,
            discard_pile=discard_pile,
            active_color=discard_pile[-1].color
        )

        # The card that opens the game applies its effect immediately.
        start_steps = self._apply_starting_card(game_state, discard_pile[-1])
        if start_steps:
            self._next_turn(game_state, start_steps)

        await self.save_game_state(game_state)
        return game_state

    def _apply_starting_card(self, state: GameState, card: Card) -> int:
        """اعمال اثر کارت شروع بازی و برگرداندن تعداد گام از صندلی صفر"""
        if card.value == 'skip':
            return 1  # صندلی صفر می‌سوزد و بازی از صندلی یک شروع می‌شود

        if card.value == 'reverse':
            state.direction *= -1
            if len(state.players) == 2:
                return 1  # در بازی دو نفره ریورس مثل پرش است
            return 0  # ترتیب برعکس می‌شود ولی همان بازیکن اول شروع می‌کند

        if card.value == 'draw2':
            state.players[0].hand.extend(self._draw_cards_from_pile(state, 2))
            return 1  # دو کارت می‌گیرد و نوبتش می‌سوزد

        return 0

    async def get_game_state(self, game_id: str) -> Optional[GameState]:
        """گرفتن وضعیت بازی از ردیس"""
        data = await self.redis.get(get_game_state_key(game_id))
        return GameState.model_validate_json(data) if data else None

    def _state_ttl(self, game_state: GameState) -> int:
        return (
            GAME_FINISHED_TTL_SECONDS
            if game_state.status == "finished"
            else GAME_ACTIVE_TTL_SECONDS
        )

    async def save_game_state(self, game_state: GameState) -> None:
        """ذخیره وضعیت بازی در ردیس همراه با انقضا"""
        await self.redis.set(
            get_game_state_key(game_state.game_id),
            game_state.model_dump_json(),
            ex=self._state_ttl(game_state),
        )

    async def delete_game_state(self, game_id: str) -> None:
        """حذف فوری وضعیت بازی (پایان بازی یا لغو مسابقه)"""
        await self.redis.delete(get_game_state_key(game_id))

    def _next_turn(self, state: GameState, steps: int = 1) -> None:
        """محاسبه نوبت نفر بعدی"""
        num_players = len(state.players)
        state.current_turn_index = (state.current_turn_index + (state.direction * steps)) % num_players

    def _card_matches(self, state: GameState, card: Card) -> bool:
        """آیا کارت با رنگ فعال یا کارت روی زمین هم‌خوانی دارد؟"""
        top_card = state.discard_pile[-1]
        return (
            card.color == 'black'
            or card.color == state.active_color
            or card.value == top_card.value
        )

    def _holds_active_color(self, player: PlayerState, excluded_index: int, active_color: str) -> bool:
        """آیا بازیکن کارتی هم‌رنگ رنگ فعال دارد؟ (کارت در حال بازی نادیده گرفته می‌شود)"""
        return any(
            card.color == active_color
            for index, card in enumerate(player.hand)
            if index != excluded_index
        )

    def _recycle_discard_pile(self, state: GameState) -> bool:
        """برگرداندن کارت‌های سوخته (به‌جز کارت روی زمین) به زمین بازی

        Returns True when a new draw pile was built. The top discard card always
        stays on the table, and a recycled wild card is a plain wild again — the
        colour chosen for it only lives in ``active_color``.
        """
        if len(state.discard_pile) <= 1:
            return False  # nothing to recycle; the top card must stay on the table

        top_card = state.discard_pile[-1]
        recycled_cards = state.discard_pile[:-1]
        random.shuffle(recycled_cards)
        state.draw_pile = recycled_cards
        state.discard_pile = [top_card]
        return True

    def _draw_cards_from_pile(self, state: GameState, count: int) -> List[Card]:
        """برداشتن کارت از زمین (اگر کارت‌ها تمام شد، کارت‌های سوخته را بُر می‌زند)

        Returns whatever could actually be dealt: with both piles exhausted the
        result may hold fewer than ``count`` cards, and callers must not assume
        otherwise.
        """
        drawn: List[Card] = []
        for _ in range(count):
            if not state.draw_pile and not self._recycle_discard_pile(state):
                break
            drawn.append(state.draw_pile.pop())
        return drawn

    def _check_turn(self, state: Optional[GameState], player_id: str) -> Optional[ActionResult]:
        """بررسی‌های مشترک: وجود بازی، فعال بودن و نوبت بازیکن"""
        if state is None:
            return failure("game_not_found")
        if state.status != "active":
            return failure("game_finished")
        if not state.players:
            return failure("game_not_found")
        if state.players[state.current_turn_index].player_id != player_id:
            return failure("not_your_turn")
        return None

    async def draw_card(self, game_id: str, player_id: str) -> ActionResult:
        """بازیکن یک کارت از زمین برمی‌دارد (اگر کارت قابل بازی باشد نوبتش می‌ماند)"""
        async with self._game_lock(game_id) as acquired:
            if not acquired:
                return failure("game_busy")
            state = await self.get_game_state(game_id)
            error = self._check_turn(state, player_id)
            if error is not None:
                return error

            # Only one draw per turn: the player is deciding whether to play it.
            if state.drawn_card_index is not None:
                return failure("already_drawn")

            current_player = state.players[state.current_turn_index]
            state.uno_window = None
            drawn_cards = self._draw_cards_from_pile(state, 1)

            if not drawn_cards:
                # Nothing left in either pile: the turn simply passes.
                self._next_turn(state)
                await self.save_game_state(state)
                return success()

            current_player.hand.extend(drawn_cards)
            drawn_index = len(current_player.hand) - 1

            if self._card_matches(state, drawn_cards[0]):
                # Official rule: after drawing a playable card the player may play
                # it (or pass). The turn is kept until play_card / pass_turn.
                state.drawn_card_index = drawn_index
            else:
                self._next_turn(state)

            await self.save_game_state(state)
            return success()

    async def say_uno(self, game_id: str, player_id: str) -> ActionResult:
        """اعلام «اونو» توسط بازیکنی که یک کارت دارد"""
        async with self._game_lock(game_id) as acquired:
            if not acquired:
                return failure("game_busy")
            state = await self.get_game_state(game_id)
            if not state:
                return failure("game_not_found")
            if state.status != "active":
                return failure("game_finished")

            player = next((p for p in state.players if p.player_id == player_id), None)
            if player is None:
                return failure("not_your_turn")
            if len(player.hand) != 1:
                return failure("cannot_call_uno")

            player.uno_declared = True
            await self.save_game_state(state)
            return success()

    async def challenge_uno(self, game_id: str, challenger_id: str) -> ActionResult:
        """اعتراض به بازیکنی که اونو اعلام نکرده است

        در صورت موفقیت، ``player_id`` نتیجه، بازیکنی است که دو کارت جریمه گرفت.
        """
        async with self._game_lock(game_id) as acquired:
            if not acquired:
                return failure("game_busy")
            state = await self.get_game_state(game_id)
            if not state:
                return failure("game_not_found")
            if state.status != "active":
                return failure("game_finished")

            offender_id = state.uno_window
            if offender_id is None or offender_id == challenger_id:
                return failure("nothing_to_challenge")

            offender = next((p for p in state.players if p.player_id == offender_id), None)
            if offender is None or len(offender.hand) != 1:
                return failure("nothing_to_challenge")

            # A wrong challenge costs the challenger two cards.
            penalised_player_id = challenger_id if offender.uno_declared else offender_id
            penalised = next(p for p in state.players if p.player_id == penalised_player_id)
            penalised.hand.extend(self._draw_cards_from_pile(state, 2))

            state.uno_window = None
            await self.save_game_state(state)
            return success(player_id=penalised_player_id)

    async def pass_turn(self, game_id: str, player_id: str) -> ActionResult:
        """بازیکن پس از برداشتن کارت، از بازی کردن آن صرف‌نظر می‌کند"""
        async with self._game_lock(game_id) as acquired:
            if not acquired:
                return failure("game_busy")
            state = await self.get_game_state(game_id)
            error = self._check_turn(state, player_id)
            if error is not None:
                return error

            if state.drawn_card_index is None:
                return failure("nothing_to_pass")  # نوبت را فقط بعد از برداشتن کارت می‌توان رد کرد

            state.drawn_card_index = None
            state.uno_window = None
            self._next_turn(state)
            await self.save_game_state(state)
            return success()

    async def play_card(
        self,
        game_id: str,
        player_id: str,
        card_index: int,
        chosen_color: Optional[str] = None,
        say_uno: bool = False,
    ) -> ActionResult:
        """بازیکن یک کارت را بازی می‌کند"""
        async with self._game_lock(game_id) as acquired:
            if not acquired:
                return failure("game_busy")
            state = await self.get_game_state(game_id)
            error = self._check_turn(state, player_id)
            if error is not None:
                return error

            current_player = state.players[state.current_turn_index]

            if card_index < 0 or card_index >= len(current_player.hand):
                return failure("card_not_in_hand")

            card_to_play = current_player.hand[card_index]

            # After drawing, only the drawn card may be played.
            if state.drawn_card_index is not None and card_index != state.drawn_card_index:
                return failure("must_play_drawn_card")

            # بررسی اینکه آیا کارت مجاز است یا خیر
            if not self._card_matches(state, card_to_play):
                return failure("invalid_card")

            if card_to_play.color == 'black':
                if not chosen_color:
                    return failure("color_required")
                if chosen_color not in VALID_COLORS:
                    return failure("invalid_color")

            # Wild Draw Four is only legal when the player holds no card that
            # matches the active colour (the card being played excluded).
            if card_to_play.value == 'wild4' and self._holds_active_color(current_player, card_index, state.active_color):
                return failure("wild4_has_matching_color")
                
            # Any action by the player on turn closes the previous UNO window.
            state.uno_window = None

            # بازی کردن کارت
            current_player.hand.pop(card_index)
            state.drawn_card_index = None
            state.discard_pile.append(card_to_play)
            state.active_color = chosen_color if card_to_play.color == 'black' else card_to_play.color

            # Apply the card effect *before* checking for a win: a Draw Two or Wild
            # Draw Four played as the last card still forces the next player to draw.
            steps = self._apply_card_effect(state, card_to_play)
            self._next_turn(state, steps)

            # UNO announcement: going down to one card opens a challenge window
            # unless the player announced it together with the play.
            if len(current_player.hand) == 1:
                current_player.uno_declared = bool(say_uno)
                state.uno_window = None if current_player.uno_declared else player_id
            elif current_player.hand:
                current_player.uno_declared = False

            # بررسی برنده شدن
            if len(current_player.hand) == 0:
                state.status = "finished"
                state.winner = player_id

            await self.save_game_state(state)
            return success(winner=player_id) if state.status == "finished" else success()

    def _apply_card_effect(self, state: GameState, card: Card) -> int:
        """اعمال اثر کارت بازی‌شده و برگرداندن تعداد گام تا نوبت بعدی"""
        steps = 1

        if card.value == 'reverse':
            state.direction *= -1
            if len(state.players) == 2:
                steps = 2  # در بازی دو نفره، ریورس مثل پرش عمل می‌کند
        elif card.value in ('skip', 'draw2', 'wild4'):
            steps = 2
            draw_count = {'draw2': 2, 'wild4': 4}.get(card.value, 0)
            if draw_count:
                victim = state.players[
                    (state.current_turn_index + state.direction) % len(state.players)
                ]
                victim.hand.extend(self._draw_cards_from_pile(state, draw_count))

        return steps