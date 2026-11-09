import os
import random
import uuid
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Wordle API Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
WORD_BANK = [
    "APPLE", "TRAIN", "HOUSE", "PLANT", "SMART", "WORLD", "LIGHT", "BRAIN", "CLOUD", "WATER",
    "ABOUT", "ABOVE", "ACTOR", "ACUTE", "ADMIT", "ADOPT", "ADULT", "AFTER", "AGAIN", "AGENT",
    "AGREE", "AHEAD", "ALARM", "ALBUM", "ALERT", "ALIEN", "ALIKE", "ALIVE", "ALLOW", "ALONE",
    "ALONG", "ALTER", "AMONG", "ANGER", "ANGLE", "ANGRY", "APART", "APPLY", "ARGUE", "ARISE",
    "ARRAY", "ARROW", "ASIDE", "ASSET", "AUDIO", "AUDIT", "AVOID", "AWAKE", "AWARE", "BADGE",
    "BAKER", "BASIC", "BASIS", "BEACH", "BEGIN", "BEING", "BELOW", "BENCH", "BLACK", "BLAME",
    "BLANK", "BLAST", "BLEED", "BLEND", "BLOCK", "BLOOD", "BOARD", "BOAST", "BONUS", "BOOST",
    "BOUND", "BREAD", "BREAK", "BRICK", "BRIEF", "BRING", "BROAD", "BROWN", "BRUSH", "BUILD",
    "BUNCH", "BUYER", "CABLE", "CANDY", "CARGO", "CARRY", "CATCH", "CAUSE", "CHAIN", "CHAIR",
    "CHALK", "CHARM", "CHART", "CHASE", "CHEAP", "CHECK", "CHEST", "CHIEF", "CHILD", "CHOSE",
    "CIVIL", "CLAIM", "CLASS", "CLEAN", "CLEAR", "CLIMB", "CLOCK", "CLOSE", "COACH", "COAST",
    "COUNT", "COURT", "COVER", "CRASH", "CREAM", "CRIME", "CROSS", "CROWD", "CROWN", "CURVE",
    "CYCLE", "DAILY", "DANCE", "DEATH", "DELAY", "DEPTH", "DRAFT", "DRAMA", "DREAM", "DRIVE",
    "EAGLE", "EARLY", "EARTH", "EIGHT", "EMPTY", "ENEMY", "ENJOY", "ENTER", "EQUAL", "ERROR",
    "EVENT", "EVERY", "EXACT", "EXIST", "FAITH", "FALSE", "FAULT", "FIELD", "FIGHT", "FINAL",
    "FIRST", "FLAME", "FLASH", "FLOAT", "FLOOR", "FLOUR", "FLUID", "FOCUS", "FORCE", "FORTH",
    "FORTY", "FORUM", "FRAME", "FRESH", "FRONT", "FRUIT", "GIANT", "GLASS", "GLOBE", "GRACE",
    "GRADE", "GRAND", "GRANT", "GRASS", "GREAT", "GREEN", "GROUP", "GUARD", "GUESS", "GUIDE",
    "HAPPY", "HEART", "HEAVY", "HOTEL", "HUMAN", "IMAGE", "INDEX", "INPUT", "ISSUE", "JUDGE",
    "KNIFE", "LAYER", "LEMON", "LEVEL", "LIMIT", "LUNCH", "MAGIC", "MAJOR", "MARCH", "MATCH",
    "MEDAL", "MONEY", "MONTH", "MUSIC", "NIGHT", "NOVEL", "NURSE", "OCEAN", "OFFER", "ORDER"
]

MAX_ATTEMPTS = 6

games_db: Dict[str, dict] = {}

stats = {"total_games": 0, "wins": 0}


def get_stats() -> dict:
    total = stats["total_games"]
    wins = stats["wins"]
    win_rate = round(wins / total * 100, 1) if total > 0 else 0.0
    return {"total_games": total, "wins": wins, "win_rate": win_rate}


class GuessRequest(BaseModel):
    game_id: str
    guess: str


class NewGameRequest(BaseModel):
    hard_mode: bool = False


@app.post("/api/new-game")
def start_new_game(req: Optional[NewGameRequest] = None, hard_mode: bool = False):
    use_hard = hard_mode or (req.hard_mode if req else False)
    game_id = str(uuid.uuid4())
    games_db[game_id] = {
        "target": random.choice(WORD_BANK),
        "status": "PLAYING",
        "attempts": 0,
        "hard_mode": use_hard,
        "greens": {},
    }
    stats["total_games"] += 1
    return {
        "game_id": game_id,
        "message": "New game started!",
        "hard_mode": use_hard,
        "stats": get_stats(),
    }


@app.post("/api/guess")
def process_guess(req: GuessRequest):
    game_id = req.game_id
    guess = req.guess.upper()

    if game_id not in games_db:
        raise HTTPException(status_code=404, detail="Game session not found.")

    if len(guess) != 5:
        raise HTTPException(status_code=400, detail="Word must be 5 letters.")

    if guess not in WORD_BANK:
        raise HTTPException(status_code=400, detail="Word not in dictionary")

    game = games_db[game_id]
    target = game["target"]

    if game["hard_mode"]:
        for pos, letter in game["greens"].items():
            if guess[pos] != letter:
                raise HTTPException(
                    status_code=400,
                    detail="Hard Mode: Must use revealed hint at green position",
                )

    feedback = ["absent"] * 5
    target_letter_counts = {}

    for char in target:
        target_letter_counts[char] = target_letter_counts.get(char, 0) + 1

    for i in range(5):
        if guess[i] == target[i]:
            feedback[i] = "correct"
            target_letter_counts[guess[i]] -= 1

    for i in range(5):
        if feedback[i] != "correct" and guess[i] in target:
            if target_letter_counts[guess[i]] > 0:
                feedback[i] = "present"
                target_letter_counts[guess[i]] -= 1

    for i in range(5):
        if feedback[i] == "correct":
            game["greens"][i] = guess[i]

    game["attempts"] += 1
    is_correct = (guess == target)

    if game["status"] == "PLAYING":
        if is_correct:
            game["status"] = "WON"
            stats["wins"] += 1
        elif game["attempts"] >= MAX_ATTEMPTS:
            game["status"] = "LOST"

    game_over = game["status"] != "PLAYING"

    return {
        "guess": guess,
        "feedback": feedback,
        "is_correct": is_correct,
        "attempts": game["attempts"],
        "tries_left": max(MAX_ATTEMPTS - game["attempts"], 0),
        "target_word": target if game_over else None,
        "stats": get_stats(),
    }


@app.get("/api/stats")
def get_stats_api():
    return get_stats()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)