import warnings
warnings.filterwarnings("ignore", message="resource_tracker: There appear to be.*")

import uuid
import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os

from config import config
from checkers_game import (
    initial_board, get_all_legal_moves, get_legal_moves_for_piece,
    check_winner,
)
from checkers_ai import get_ai_move, get_best_red_move
from checkers_tutor import analyze_move, answer_question

app = FastAPI(title="Checkers Tutor", root_path="")

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Anthropic client used by all checkers AI features
_ai_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

# RAG system is optional — only needed for the legacy /api/query endpoint
_rag_system = None

def _get_rag():
    global _rag_system
    if _rag_system is None:
        from rag_system import RAGSystem
        _rag_system = RAGSystem(config)
    return _rag_system

# ── In-memory game sessions ──────────────────────────────────────────────────
_sessions: Dict[str, Dict[str, Any]] = {}


def _session(session_id: str) -> Dict[str, Any]:
    s = _sessions.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found. Start a new game first.")
    return s


# ── Request / Response models ────────────────────────────────────────────────

class NewGameRequest(BaseModel):
    difficulty: str = "medium"
    session_id: Optional[str] = None

class NewGameResponse(BaseModel):
    session_id: str
    board: List[List[int]]
    message: str

class LegalMovesRequest(BaseModel):
    session_id: str
    row: int
    col: int

class MoveRequest(BaseModel):
    session_id: str
    from_row: int
    from_col: int
    to_row: int
    to_col: int

class MoveResponse(BaseModel):
    valid: bool
    message: str
    board: List[List[int]]
    ai_board: Optional[List[List[int]]] = None
    ai_move: Optional[Dict] = None
    tutor_feedback: str = ""
    winner: Optional[str] = None

class HintRequest(BaseModel):
    session_id: str

class HintResponse(BaseModel):
    from_pos: List[int]
    to_pos: List[int]
    message: str

class AskRequest(BaseModel):
    question: str
    session_id: Optional[str] = None

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    session_id: str


# ── Checkers endpoints ────────────────────────────────────────────────────────

@app.post("/api/checkers/new_game", response_model=NewGameResponse)
async def new_game(req: NewGameRequest):
    sid = req.session_id or str(uuid.uuid4())
    board = initial_board()
    _sessions[sid] = {"board": board, "difficulty": req.difficulty}
    return NewGameResponse(
        session_id=sid,
        board=board,
        message="New game started! You play as red (bottom). Make your move.",
    )


@app.post("/api/checkers/legal_moves")
async def legal_moves(req: LegalMovesRequest):
    s = _session(req.session_id)
    moves = get_legal_moves_for_piece(s["board"], req.row, req.col, red_turn=True)
    return {"moves": [{"to": m["to"], "captured": m["captured"]} for m in moves]}


@app.post("/api/checkers/move", response_model=MoveResponse)
async def make_move(req: MoveRequest):
    s = _session(req.session_id)
    board = s["board"]

    all_moves = get_all_legal_moves(board, red_turn=True)
    matching = [
        m for m in all_moves
        if m["from"] == [req.from_row, req.from_col]
        and m["to"]   == [req.to_row,   req.to_col]
    ]

    if not matching:
        return MoveResponse(valid=False, message="Illegal move.", board=board)

    move = matching[0]
    board_after_human = move["board"]

    feedback = analyze_move(_ai_client, config.ANTHROPIC_MODEL, board, move)

    winner = check_winner(board_after_human, red_turn=False)
    if winner == "red":
        s["board"] = board_after_human
        return MoveResponse(
            valid=True, message="You win!",
            board=board_after_human, tutor_feedback=feedback, winner="red",
        )

    ai_move = get_ai_move(board_after_human, s["difficulty"])
    if not ai_move:
        s["board"] = board_after_human
        return MoveResponse(
            valid=True, message="AI has no moves — you win!",
            board=board_after_human, tutor_feedback=feedback, winner="red",
        )

    ai_board = ai_move["board"]
    winner = check_winner(ai_board, red_turn=True)
    s["board"] = ai_board

    return MoveResponse(
        valid=True,
        message="AI moved.",
        board=board_after_human,
        ai_board=ai_board,
        ai_move={"from": ai_move["from"], "to": ai_move["to"], "captured": ai_move["captured"]},
        tutor_feedback=feedback,
        winner=winner,
    )


@app.post("/api/checkers/hint", response_model=HintResponse)
async def hint(req: HintRequest):
    s = _session(req.session_id)
    best = get_best_red_move(s["board"], depth=3)
    if not best:
        return HintResponse(from_pos=[], to_pos=[], message="No moves available.")
    return HintResponse(
        from_pos=best["from"],
        to_pos=best["to"],
        message=f"Try moving from {best['from']} to {best['to']}.",
    )


@app.post("/api/checkers/ask")
async def checkers_ask(req: AskRequest):
    s = _sessions.get(req.session_id or "")
    board = s["board"] if s else None
    answer = answer_question(_ai_client, config.ANTHROPIC_MODEL, req.question, board)
    return {"answer": answer}


# ── Legacy RAG endpoint ───────────────────────────────────────────────────────

@app.post("/api/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    try:
        rag = _get_rag()
        session_id = request.session_id or rag.session_manager.create_session()
        answer, sources = rag.query(request.query, session_id)
        return QueryResponse(answer=answer, sources=sources, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    print("Checkers Tutor ready.")
    print("RAG knowledge base will load on first /api/query request.")


# ── Static files ──────────────────────────────────────────────────────────────

class DevStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if isinstance(response, FileResponse):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")
