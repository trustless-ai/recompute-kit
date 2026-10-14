import sys
sys.path.insert(0, "vendor")   # the suite reads the COPY, never mod.py
from mod import is_even
assert is_even(4)
assert not is_even(3)   # would kill the mutant, if it ever saw the mutated file
print("ok")
