def target():
    return "a"


class Box:
    def target(self):
        return "b"


def dispatch(obj):
    return target()
