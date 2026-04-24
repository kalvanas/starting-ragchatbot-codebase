from copy import deepcopy
from typing import List, Tuple, Optional, Set, Dict

EMPTY = 0
RED = 1        # Human player — moves toward row 0 (up)
RED_KING = 2
BLACK = 3      # AI opponent — moves toward row 7 (down)
BLACK_KING = 4


def initial_board() -> List[List[int]]:
    board = [[EMPTY] * 8 for _ in range(8)]
    for row in range(3):
        for col in range(8):
            if (row + col) % 2 == 1:
                board[row][col] = BLACK
    for row in range(5, 8):
        for col in range(8):
            if (row + col) % 2 == 1:
                board[row][col] = RED
    return board


def is_red(piece: int) -> bool:
    return piece in (RED, RED_KING)


def is_black(piece: int) -> bool:
    return piece in (BLACK, BLACK_KING)


def is_king(piece: int) -> bool:
    return piece in (RED_KING, BLACK_KING)


def _directions(piece: int) -> List[Tuple[int, int]]:
    if piece == RED:
        return [(-1, -1), (-1, 1)]
    if piece == BLACK:
        return [(1, -1), (1, 1)]
    return [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def _try_promote(piece: int, row: int) -> int:
    if piece == RED and row == 0:
        return RED_KING
    if piece == BLACK and row == 7:
        return BLACK_KING
    return piece


def get_all_legal_moves(board: List[List[int]], red_turn: bool) -> List[Dict]:
    """
    Return all legal moves for the current player.
    Captures are mandatory (returned exclusively when available).

    Each move dict:
      from:     [row, col]
      to:       [row, col]
      captured: [[row, col], ...]  (empty for simple moves)
      board:    resulting 8x8 board
    """
    my_piece = is_red if red_turn else is_black
    captures: List[Dict] = []
    simple:   List[Dict] = []

    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if not my_piece(piece):
                continue

            caps = _find_captures(board, r, c, red_turn, set(), [r, c])
            captures.extend(caps)

    if captures:
        return captures

    for r in range(8):
        for c in range(8):
            piece = board[r][c]
            if not my_piece(piece):
                continue
            for dr, dc in _directions(piece):
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8 and board[nr][nc] == EMPTY:
                    new_board = deepcopy(board)
                    new_board[r][c] = EMPTY
                    new_board[nr][nc] = _try_promote(piece, nr)
                    simple.append({"from": [r, c], "to": [nr, nc], "captured": [], "board": new_board})

    return simple


def _find_captures(
    board: List[List[int]],
    r: int,
    c: int,
    red_turn: bool,
    captured_set: Set[Tuple[int, int]],
    path: List[int],
) -> List[Dict]:
    """Recursively enumerate all capture sequences from (r, c)."""
    piece = board[r][c]
    is_enemy = is_black if red_turn else is_red
    found: List[Dict] = []

    for dr, dc in _directions(piece):
        mr, mc = r + dr, c + dc      # enemy square
        lr, lc = r + 2 * dr, c + 2 * dc  # landing square

        if not (0 <= mr < 8 and 0 <= mc < 8):
            continue
        if not (0 <= lr < 8 and 0 <= lc < 8):
            continue
        if (mr, mc) in captured_set:
            continue
        if not is_enemy(board[mr][mc]):
            continue
        if board[lr][lc] != EMPTY:
            continue

        new_board = deepcopy(board)
        new_board[r][c] = EMPTY
        new_board[mr][mc] = EMPTY
        new_piece = _try_promote(piece, lr)
        new_board[lr][lc] = new_piece
        new_captured = captured_set | {(mr, mc)}
        new_path = path + [lr, lc]

        # American rules: promotion ends the turn
        if new_piece != piece:
            found.append({
                "from": [path[0], path[1]],
                "to": [lr, lc],
                "captured": [[x[0], x[1]] for x in new_captured],
                "board": new_board,
            })
            continue

        further = _find_captures(new_board, lr, lc, red_turn, new_captured, new_path)
        if further:
            found.extend(further)
        else:
            found.append({
                "from": [path[0], path[1]],
                "to": [lr, lc],
                "captured": [[x[0], x[1]] for x in new_captured],
                "board": new_board,
            })

    return found


def get_legal_moves_for_piece(board: List[List[int]], row: int, col: int, red_turn: bool) -> List[Dict]:
    """Return only the moves belonging to the piece at (row, col)."""
    all_moves = get_all_legal_moves(board, red_turn)
    return [m for m in all_moves if m["from"] == [row, col]]


def check_winner(board: List[List[int]], red_turn: bool) -> Optional[str]:
    """Return 'red', 'black', or None. The player whose turn it is loses if they have no moves."""
    if not get_all_legal_moves(board, red_turn):
        return "black" if red_turn else "red"
    return None


def board_to_str(board: List[List[int]]) -> str:
    symbols = {EMPTY: ".", RED: "r", RED_KING: "R", BLACK: "b", BLACK_KING: "B"}
    lines = ["  0 1 2 3 4 5 6 7"]
    for r, row in enumerate(board):
        lines.append(f"{r} " + " ".join(symbols[p] for p in row))
    return "\n".join(lines)
