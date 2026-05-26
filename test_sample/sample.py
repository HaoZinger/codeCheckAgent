def divide(a, b):
    return a / b

def read_file(path):
    f = open(path, "r")
    data = f.read()
    return data

def get_user(users, name):
    for u in users:
        if u["name"] == name:
            return u
    return "Not found"
