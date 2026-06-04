import sys
lines = sys.stdin.read().splitlines()
filtered = [l for l in lines if 'Co-Authored-By: Claude' not in l]
while filtered and not filtered[-1].strip():
    filtered.pop()
print('\n'.join(filtered))
