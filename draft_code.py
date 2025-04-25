
def test():
    a = 5
    b = 10
    prog = 'c = a + b'
    try:
        exec(prog)
    except Exception as e:
        print(e)
    
    print(locals())


test()
