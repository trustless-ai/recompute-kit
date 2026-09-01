from mod import is_even
assert is_even(4)
assert not is_even(3)   # load-bearing: catches "always true" mutation
print("ok")
