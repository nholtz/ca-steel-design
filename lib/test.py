def foo(arg):
    def _f(new,old=arg):
        print new,old
    return _f

class One(object):

    A = 1

    def metha():
        pass

@foo(One)
class Two(object):

    B = 2

    def methb():
        pass
