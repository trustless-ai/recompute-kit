from mod import is_even
assert is_even(4)
assert not is_even(3)   # load-bearing for is_even, and blind to unreached() by design
print("ok")
