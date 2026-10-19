def is_valid_solution(grid: str) -> bool:
    """Check if a 81-character grid is a valid solved Sudoku."""
    if len(grid) != 81:
        return False
    if not all(c in '123456789' for c in grid):
        return False
    
    # Check rows
    for i in range(9):
        row = grid[i*9:(i+1)*9]
        if len(set(row)) != 9:
            return False
    
    # Check columns
    for j in range(9):
        col = ''.join(grid[i*9 + j] for i in range(9))
        if len(set(col)) != 9:
            return False
    
    # Check 3x3 boxes
    for box_row in range(3):
        for box_col in range(3):
            box = ''
            for i in range(3):
                for j in range(3):
                    box += grid[(box_row*3 + i)*9 + (box_col*3 + j)]
            if len(set(box)) != 9:
                return False
    
    return True


def solve(puzzle: str) -> str | None:
    """
    Solve a Sudoku puzzle.
    
    puzzle: 81 characters, digits 1-9 and '.' or '0' for empty cells.
    Whitespace and newlines anywhere are ignored.
    
    Returns: solved grid as 81 digits, or None if no solution.
    Raises: ValueError for invalid input.
    """
    # Validate and preprocess input
    if not isinstance(puzzle, str):
        raise ValueError("Puzzle must be a string")
    
    # Remove all whitespace
    cleaned = ''.join(c for c in puzzle if not c.isspace())
    
    if len(cleaned) != 81:
        raise ValueError(f"Puzzle must have exactly 81 non-whitespace characters, got {len(cleaned)}")
    
    # Validate characters
    valid_chars = set('123456789.0')
    for c in cleaned:
        if c not in valid_chars:
            raise ValueError(f"Invalid character '{c}' in puzzle")
    
    # Convert to list of integers (0 for empty)
    board = []
    for c in cleaned:
        if c == '.' or c == '0':
            board.append(0)
        else:
            board.append(int(c))
    
    # Check for immediate conflicts
    if not _is_consistent(board):
        return None
    
    # Solve using backtracking with constraint propagation
    result = _backtrack(board)
    if result is None:
        return None
    return ''.join(str(x) for x in result)


def _is_consistent(board: list[int]) -> bool:
    """Check if the current board state has no conflicts."""
    # Check rows
    for i in range(9):
        seen = set()
        for j in range(9):
            val = board[i*9 + j]
            if val != 0:
                if val in seen:
                    return False
                seen.add(val)
    
    # Check columns
    for j in range(9):
        seen = set()
        for i in range(9):
            val = board[i*9 + j]
            if val != 0:
                if val in seen:
                    return False
                seen.add(val)
    
    # Check boxes
    for box_row in range(3):
        for box_col in range(3):
            seen = set()
            for i in range(3):
                for j in range(3):
                    val = board[(box_row*3 + i)*9 + (box_col*3 + j)]
                    if val != 0:
                        if val in seen:
                            return False
                        seen.add(val)
    
    return True


def _backtrack(board: list[int]) -> list[int] | None:
    """Backtracking solver with MRV (Most Restricted Variable) heuristic."""
    # Find empty cells
    empty_cells = [i for i in range(81) if board[i] == 0]
    
    if not empty_cells:
        return board  # Solution found
    
    # MRV: choose the cell with fewest possible values
    best_cell = None
    best_options = None
    min_options = 10
    
    for idx in empty_cells:
        possible = _get_possible_values(board, idx)
        count = len(possible)
        if count == 0:
            return None  # Dead end
        if count < min_options:
            min_options = count
            best_cell = idx
            best_options = possible
    
    # Try each possible value
    for val in best_options:
        board[best_cell] = val
        if _backtrack(board) is not None:
            return board
        board[best_cell] = 0
    
    return None


def _get_possible_values(board: list[int], idx: int) -> set[int]:
    """Get possible values for a given cell index."""
    row = idx // 9
    col = idx % 9
    box_row = row // 3
    box_col = col // 3
    
    used = set()
    
    # Check row
    for j in range(9):
        val = board[row*9 + j]
        if val != 0:
            used.add(val)
    
    # Check column
    for i in range(9):
        val = board[i*9 + col]
        if val != 0:
            used.add(val)
    
    # Check box
    for i in range(3):
        for j in range(3):
            val = board[(box_row*3 + i)*9 + (box_col*3 + j)]
            if val != 0:
                used.add(val)
    
    return {v for v in range(1, 10) if v not in used}