import anthropic
from typing import List, Dict, Optional
from checkers_game import board_to_str

_COACH_SYSTEM = """You are a friendly, encouraging checkers coach helping a student improve their game.
Keep responses concise (2-4 sentences). Be specific about the position when explaining moves.
Use plain language — no jargon the student won't know. Always end with one actionable tip."""

_QA_SYSTEM = """You are an expert checkers coach and teacher.
Answer questions about checkers rules, strategy, tactics, openings, and endgames clearly and concisely.
Use examples where helpful. Keep responses under 150 words unless the topic genuinely requires more."""


def analyze_move(
    client: anthropic.Anthropic,
    model: str,
    board_before: List[List[int]],
    move: Dict,
) -> str:
    """Give coaching feedback on the human's move."""
    from_pos = move["from"]
    to_pos   = move["to"]
    captured = move.get("captured", [])

    cap_text = ""
    if captured:
        locs = ", ".join(f"({r},{c})" for r, c in captured)
        cap_text = f", capturing {locs}"

    board_str = board_to_str(board_before)

    prompt = (
        f"Board before the move (r=red/you, R=red king, b=black/AI, B=black king, .=empty):\n"
        f"{board_str}\n\n"
        f"The student moved from ({from_pos[0]},{from_pos[1]}) to ({to_pos[0]},{to_pos[1]}){cap_text}.\n\n"
        f"Red pieces move UP (toward row 0), black move DOWN (toward row 7).\n\n"
        f"Briefly evaluate this move: was it good? Any missed opportunity or risk? One tip."
    )

    response = client.messages.create(
        model=model,
        max_tokens=200,
        system=_COACH_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def answer_question(
    client: anthropic.Anthropic,
    model: str,
    question: str,
    board: Optional[List[List[int]]] = None,
) -> str:
    """Answer a general checkers question, optionally with current board context."""
    context = ""
    if board:
        context = f"\nCurrent board for context:\n{board_to_str(board)}\n\n"

    prompt = f"{context}Question: {question}"

    response = client.messages.create(
        model=model,
        max_tokens=300,
        system=_QA_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
