/* ── State ────────────────────────────────────────────────────────────── */
const state = {
  sessionId:   null,
  board:       null,      // 8x8 array
  selected:    null,      // [row, col] of selected red piece, or null
  legalMoves:  [],        // moves for the selected piece: [{to:[r,c], captured:[...]}]
  hintMove:    null,      // {from:[r,c], to:[r,c]}
  gameOver:    false,
  waiting:     false,     // true while waiting for AI / tutor
  difficulty:  'medium',
};

/* ── DOM refs ────────────────────────────────────────────────────────── */
const boardEl      = document.getElementById('board');
const statusBar    = document.getElementById('statusBar');
const chatMessages = document.getElementById('chatMessages');
const chatInput    = document.getElementById('chatInput');
const newGameBtn   = document.getElementById('newGameBtn');
const hintBtn      = document.getElementById('hintBtn');
const sendBtn      = document.getElementById('sendBtn');
const diffSelect   = document.getElementById('difficulty');

/* ── Board rendering ─────────────────────────────────────────────────── */
function renderBoard() {
  boardEl.innerHTML = '';

  for (let r = 0; r < 8; r++) {
    for (let c = 0; c < 8; c++) {
      const sq = document.createElement('div');
      const dark = (r + c) % 2 === 1;
      sq.className = 'square ' + (dark ? 'dark' : 'light');

      const piece = state.board[r][c];

      // Piece element
      if (piece !== 0) {
        const p = document.createElement('div');
        const isRed = piece === 1 || piece === 2;
        p.className = 'piece ' + (isRed ? 'red' : 'black') + (piece === 2 || piece === 4 ? ' king' : '');
        sq.appendChild(p);
      }

      // Highlights
      if (state.selected && state.selected[0] === r && state.selected[1] === c) {
        sq.classList.add('selected');
      }
      if (state.hintMove) {
        if (state.hintMove.from[0] === r && state.hintMove.from[1] === c) sq.classList.add('hint-from');
        if (state.hintMove.to[0]   === r && state.hintMove.to[1]   === c) sq.classList.add('hint-to');
      }

      // Legal-move dot
      if (dark && state.legalMoves.some(m => m.to[0] === r && m.to[1] === c)) {
        const dot = document.createElement('div');
        dot.className = 'move-dot';
        sq.appendChild(dot);
      }

      // Click only on dark squares
      if (dark) sq.addEventListener('click', () => handleClick(r, c));

      boardEl.appendChild(sq);
    }
  }
}

/* ── Click handler ───────────────────────────────────────────────────── */
async function handleClick(r, c) {
  if (state.gameOver || state.waiting || !state.board) return;

  const piece = state.board[r][c];

  // If a target of a legal move — execute it
  if (state.selected) {
    const target = state.legalMoves.find(m => m.to[0] === r && m.to[1] === c);
    if (target) {
      await executeMove(state.selected[0], state.selected[1], r, c);
      return;
    }
  }

  // Select a red piece
  if (piece === 1 || piece === 2) {
    state.selected  = [r, c];
    state.hintMove  = null;
    state.legalMoves = [];
    renderBoard();
    await loadLegalMoves(r, c);
    renderBoard();
    return;
  }

  // Deselect
  state.selected   = null;
  state.legalMoves = [];
  renderBoard();
}

async function loadLegalMoves(r, c) {
  try {
    const res = await fetch('/api/checkers/legal_moves', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: state.sessionId, row: r, col: c }),
    });
    const data = await res.json();
    state.legalMoves = data.moves || [];
  } catch {
    state.legalMoves = [];
  }
}

/* ── Execute move ────────────────────────────────────────────────────── */
async function executeMove(fromR, fromC, toR, toC) {
  state.waiting    = true;
  state.selected   = null;
  state.legalMoves = [];
  state.hintMove   = null;
  hintBtn.disabled = true;
  setStatus('Thinking…');
  renderBoard();

  const thinkId = addMsg('coach', '…analyzing your move', 'thinking');

  try {
    const res = await fetch('/api/checkers/move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.sessionId,
        from_row: fromR, from_col: fromC,
        to_row:   toR,   to_col:   toC,
      }),
    });
    const data = await res.json();
    removeMsg(thinkId);

    if (!data.valid) {
      addMsg('coach', data.message || 'Illegal move — try another piece.');
      state.waiting = false;
      hintBtn.disabled = false;
      setStatus('Your turn');
      renderBoard();
      return;
    }

    // Show board after human's move
    state.board = data.board;
    renderBoard();

    // Tutor feedback
    if (data.tutor_feedback) addMsg('coach', data.tutor_feedback);

    // Human wins
    if (data.winner === 'red') {
      addMsg('system', 'You win! Congratulations!');
      setStatus('Game over — You win!');
      state.gameOver = true;
      state.waiting  = false;
      return;
    }

    // Show AI move after short delay
    setTimeout(() => {
      if (data.ai_board) {
        state.board = data.ai_board;
        renderBoard();

        if (data.ai_move) {
          const [ar, ac] = data.ai_move.from;
          const [tr, tc] = data.ai_move.to;
          const capText  = data.ai_move.captured && data.ai_move.captured.length
            ? ` (captured ${data.ai_move.captured.length} piece${data.ai_move.captured.length > 1 ? 's' : ''})`
            : '';
          addMsg('ai-info', `AI moved (${ar},${ac}) → (${tr},${tc})${capText}`);
        }
      }

      if (data.winner === 'black') {
        addMsg('system', 'AI wins this round — keep practicing!');
        setStatus('Game over — AI wins');
        state.gameOver = true;
      } else {
        setStatus('Your turn');
        hintBtn.disabled = false;
      }

      state.waiting = false;
    }, 700);

  } catch (err) {
    removeMsg(thinkId);
    addMsg('coach', 'Network error — please try again.');
    state.waiting    = false;
    hintBtn.disabled = false;
    setStatus('Your turn');
  }
}

/* ── New Game ────────────────────────────────────────────────────────── */
async function newGame() {
  newGameBtn.disabled = true;
  setStatus('Starting…');

  try {
    const res = await fetch('/api/checkers/new_game', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ difficulty: state.difficulty }),
    });
    const data = await res.json();

    state.sessionId  = data.session_id;
    state.board      = data.board;
    state.selected   = null;
    state.legalMoves = [];
    state.hintMove   = null;
    state.gameOver   = false;
    state.waiting    = false;

    renderBoard();
    setStatus('Your turn — click a red piece');
    hintBtn.disabled = false;

    addMsg('coach',
      `New game started on ${state.difficulty} difficulty. ` +
      `You are red (bottom), AI is black (top). ` +
      `Red moves UP toward row 0. Click a piece to see your options!`
    );
  } catch {
    addMsg('coach', 'Could not start a new game. Is the server running?');
  }

  newGameBtn.disabled = false;
}

/* ── Hint ────────────────────────────────────────────────────────────── */
async function getHint() {
  if (state.gameOver || state.waiting || !state.sessionId) return;

  try {
    const res = await fetch('/api/checkers/hint', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: state.sessionId }),
    });
    const data = await res.json();

    if (data.from_pos && data.from_pos.length) {
      state.hintMove   = { from: data.from_pos, to: data.to_pos };
      state.selected   = null;
      state.legalMoves = [];
      renderBoard();
      addMsg('coach',
        `Hint: move from (${data.from_pos[0]},${data.from_pos[1]}) ` +
        `to (${data.to_pos[0]},${data.to_pos[1]}). ` +
        `Yellow squares show the suggestion.`
      );
    } else {
      addMsg('coach', 'No moves available.');
    }
  } catch {
    addMsg('coach', 'Could not fetch hint.');
  }
}

/* ── Ask a question ──────────────────────────────────────────────────── */
async function askQuestion() {
  const q = chatInput.value.trim();
  if (!q) return;
  chatInput.value = '';

  addMsg('user', q);
  const thinkId = addMsg('coach', '…', 'thinking');

  try {
    const res = await fetch('/api/checkers/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: q, session_id: state.sessionId }),
    });
    const data = await res.json();
    removeMsg(thinkId);
    addMsg('coach', data.answer);
  } catch {
    removeMsg(thinkId);
    addMsg('coach', 'Sorry, something went wrong. Try again.');
  }
}

/* ── Chat helpers ────────────────────────────────────────────────────── */
let _msgId = 0;

function addMsg(type, text, extraClass = '') {
  const id  = 'msg-' + (++_msgId);
  const div = document.createElement('div');
  div.id = id;
  div.className = 'message ' + type + (extraClass ? ' ' + extraClass : '');

  const labels = { coach: 'Coach', user: 'You', 'ai-info': 'AI', system: '', thinking: 'Coach' };
  const label  = labels[type] ?? '';
  if (label) {
    const span = document.createElement('span');
    span.className   = 'msg-label';
    span.textContent = label;
    div.appendChild(span);
  }

  const content = document.createElement('div');
  content.className   = 'msg-content';
  content.textContent = text;
  div.appendChild(content);

  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return id;
}

function removeMsg(id) {
  document.getElementById(id)?.remove();
}

function setStatus(text) {
  statusBar.textContent = text;
}

/* ── Event listeners ─────────────────────────────────────────────────── */
newGameBtn.addEventListener('click', newGame);
hintBtn.addEventListener('click', getHint);
sendBtn.addEventListener('click', askQuestion);
diffSelect.addEventListener('change', e => { state.difficulty = e.target.value; });
chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') askQuestion(); });

/* ── Boot ────────────────────────────────────────────────────────────── */
addMsg('coach',
  'Welcome to Checkers Tutor! Press "New Game" to start. ' +
  'After each move, I\'ll coach you on your play. ' +
  'You can also ask me any checkers question below.'
);
