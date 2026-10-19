"""Sudoku solver.

solve(puzzle) -> str | None
    puzzle: 81 characters (whitespace/newlines ignored) of digits 1-9 and
            '.' or '0' for empty cells.
    Returns the solved grid as 81 digits, or None if unsolvable / conflicting.
    Raises ValueError for wrong length or invalid characters.

is_valid_solution(grid) -> bool
    True if grid is a fully filled, valid 9x9 sudoku solution.
"""

from __future__ import annotations


def _clean(puzzle: str) -> str:
    """Strip whitespace and validate characters/length. Returns 81-char string."""
    s = ''.join(puzzle.split())
    if len(s) != 81:
        raise ValueError(f"expected 81 cells, got {len(s)}")
    for ch in s:
        if ch == '.' or ch == '0' or ch in '123456789':
            continue
        raise ValueError(f"invalid character: {ch!r}")
    return s


def _conflict_cells(s: str) -> list[int]:
    """Return indices of cells that already violate a row/col/box constraint."""
    bad = [False] * 81
    for r in range(9):
        seen = [False] * 10
        for c in range(9):
            i = r * 9 + c
            d = ord(s[i]) - 48
            if 1 <= d <= 9:
                if seen[d]:
                    bad[i] = True
                seen[d] = True
    for c in range(9):
        seen = [False] * 10
        for r in range(9):
            i = r * 9 + c
            d = ord(s[i]) - 48
            if 1 <= d <= 9:
                if seen[d]:
                    bad[i] = True
                seen[d] = True
    for br in range(3):
        for bc in range(3):
            seen = [False] * 10
            for r in range(br * 3, br * 3 + 3):
                for c in range(bc * 3, bc * 3 + 3):
                    i = r * 9 + c
                    d = ord(s[i]) - 48
                    if 1 <= d <= 9:
                        if seen[d]:
                            bad[i] = True
                        seen[d] = True
    return [i for i in range(81) if bad[i]]


def is_valid_solution(grid: str) -> bool:
    """Return True if grid is a complete, valid 9x9 sudoku solution."""
    s = ''.join(grid.split())
    if len(s) != 81:
        return False
    for ch in s:
        if ch not in '123456789':
            return False
    # every row, column and box must contain each digit 1-9 exactly once
    for r in range(9):
        row = s[r * 9:(r + 1) * 9]
        if set(row) != set('123456789'):
            return False
    for c in range(9):
        col = s[c::9]
        if set(col) != set('123456789'):
            return False
    for br in range(3):
        for bc in range(3):
            box = []
            for r in range(br * 3, br * 3 + 3):
                for c in range(bc * 3, bc * 3 + 3):
                    box.append(s[r * 9 + c])
            if set(box) != set('123456789'):
                return False
    return True


# Precompute peer lists for fast constraint propagation
_PEERS: list[list[int]] = []
for _i in range(81):
    _r, _c = divmod(_i, 9)
    _br, _bc = _r // 3 * 3, _c // 3 * 3
    _peers = set()
    for _k in range(9):
        _peers.add(_r * 9 + _k)
        _peers.add(_k * 9 + _c)
    for _rr in range(_br, _br + 3):
        for _cc in range(_bc, _bc + 3):
            _peers.add(_rr * 9 + _cc)
    _peers.discard(_i)
    _PEERS.append(list(_peers))


def solve(puzzle: str) -> str | None:
    """Solve a sudoku puzzle.

    Returns the solved grid as 81 digits, or None if no solution / conflicting clues.
    """
    s = _clean(puzzle)

    # Quick check: do the given clues already conflict?
    if _conflict_cells(s):
        return None

    grid = list(s)
    # candidates: bitmasks, bit d (1-9) set means digit d is still possible
    FULL = 0x3FE  # bits 1..9
    cands = [0] * 81
    for i in range(81):
        d = ord(grid[i]) - 48
        if 1 <= d <= 9:
            cands[i] = 0
        else:
            cands[i] = FULL

    # Initial propagation from all given digits
    for i in range(81):
        d = ord(grid[i]) - 48
        if 1 <= d <= 9:
            mask = 1 << d
            for p in _PEERS[i]:
                if cands[p] & mask:
                    cands[p] &= ~mask
                    if cands[p] == 0:
                        return None

    # Solve with constraint propagation + backtracking
    def _solve(cands: list[int], grid: list[str]) -> bool:
        # Find a cell with fewest candidates (>0)
        best_i = -1
        best_n = 10
        for i in range(81):
            if grid[i] in '0.':
                n = bin(cands[i]).count('1')
                if n == 0:
                    return False
                if n < best_n:
                    best_i, best_n = i, n
                    if n == 1:
                        break
        if best_i == -1:
            return True  # solved

        i = best_i
        mask = cands[i]
        # Try each candidate digit
        m = mask
        while m:
            bit = m & (-m)
            m ^= bit
            d = bit.bit_length() - 1
            # Try placing digit d at cell i
            grid[i] = chr(48 + d)
            # Save peer cands
            saved = {}
            ok = True
            for p in _PEERS[i]:
                if cands[p] & bit:
                    saved[p] = cands[p]
                    cands[p] &= ~bit
                    if cands[p] == 0:
                        ok = False
                        break
            if ok:
                if _solve(cands, grid):
                    return True
            # Undo
            for p, v in saved.items():
                cands[p] = v
            grid[i] = '.'
        return False

    # Rebuild grid with '.' for empty
    for i in range(81):
        d = ord(grid[i]) - 48
        if not (1 <= d <= 9):
            grid[i] = '.'

    if _solve(cands, grid):
        return ''.join(grid)
    return None
