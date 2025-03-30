# utils/utils.py
# Debug helper to see what's in the string
def debug_string(s):
    print("String content:")
    for i, ch in enumerate(s):
        print(f"Position {i}: '{ch}' (ord: {ord(ch)})")
    print("End of string")
