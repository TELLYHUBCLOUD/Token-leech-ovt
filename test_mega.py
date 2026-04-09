try:
    from mega import Mega
    print("Mega imported from mega")
except Exception as e:
    print(f"Error 1: {e}")

try:
    import mega.mega
    print(dir(mega.mega))
except Exception as e:
    print(f"Error 2: {e}")
