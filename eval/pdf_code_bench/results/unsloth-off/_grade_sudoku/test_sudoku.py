from sudoku import solve, is_valid_solution
p = '53..7....6..195....98....6.8...6...34..8.3..17...2...6.6....28....419..5....8..79'
s = solve(p)
assert s and is_valid_solution(s) and s.startswith('534678912')
print('ok')
