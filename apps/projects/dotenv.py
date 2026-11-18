import re

PLAIN = re.compile(r"^[A-Za-z0-9_./:@+,=-]*$")


def env_line(name, value):
    """One line of a .env file. Values with spaces, quotes, # or new lines are double-quoted and escaped."""
    if PLAIN.match(value):
        return f"{name}={value}"
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'{name}="{escaped}"'


def env_file(secrets):
    return "".join(f"{env_line(s.name, s.value)}\n" for s in secrets)
