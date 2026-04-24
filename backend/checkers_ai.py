from typing import List, Optional, Dict, Tuple
from checkers_game import get_all_legal_moves, is_red, is_black, RED, RED_KING, BLACK, BLACK_KING, EMPTY


def _evaluate(board: List[List[int]]) -> float:
    """Score the board from black's perspective (positive = good for black/AI)."""
    score = 0.0
    for r in range(8):
        for c in range(8):
            p = board[r][c]
            if p == RED:
                score -= 1.0
                score -= (7 - r) * 0.04   # penalise red advancement
            elif p == RED_KING:
                score -= 1.75
                # Kings prefer the center
                score += 0.05 * (min(r, 7 - r) + min(c, 7 - c))
            elif p == BLACK:
                score += 1.0
                score += r * 0.04          # reward black advancement
            elif p == BLACK_KING:
                score += 1.75
                score -= 0.05 * (min(r, 7 - r) + min(c, 7 - c))
    return score


def _minimax(
    board: List[List[int]],
    depth: int,
    alpha: float,
    beta: float,
    maximizing: bool,
) -> Tuple[float, Optional[Dict]]:
    moves = get_all_legal_moves(board, not maximizing)  # maximizing = black

    if depth == 0 or not moves:
        return _evaluate(board), None

    best_move: Optional[Dict] = None

    if maximizing:
        best_val = float("-inf")
        for move in moves:
            val, _ = _minimax(move["board"], depth - 1, alpha, beta, False)
            if val > best_val:
                best_val = val
                best_move = move
            alpha = max(alpha, val)
            if beta <= alpha:
                break
        return best_val, best_move
    else:
        best_val = float("inf")
        for move in moves:
            val, _ = _minimax(move["board"], depth - 1, alpha, beta, True)
            if val < best_val:
                best_val = val
                best_move = move
            beta = min(beta, val)
            if beta <= alpha:
                break
        return best_val, best_move


_DIFFICULTY_DEPTH = {"easy": 2, "medium": 4, "hard": 6}


def get_ai_move(board: List[List[int]], difficulty: str = "medium") -> Optional[Dict]:
    """Return the best move for the AI (black pieces) at the given difficulty."""
    depth = _DIFFICULTY_DEPTH.get(difficulty, 4)
    _, move = _minimax(board, depth, float("-inf"), float("inf"), True)
    return move


def get_best_red_move(board: List[List[int]], depth: int = 3) -> Optional[Dict]:
    """Return the best move for red (used for hints)."""
    _, move = _minimax(board, depth, float("-inf"), float("inf"), False)
    return move
