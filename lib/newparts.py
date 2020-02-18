#from Designer import Part, CMPart

from utils import show

class PartMeta(type):
    
    def __call__(cls,*args,**kwargs):
        raise TypeError("It is not possible to create an instance of this class: "+repr(cls))
    
    def __getitem__(cls,*keys):
        newdct = {}
        cls_ns = None
        dct = cls.ns()
        for names in keys:
            for k in names.split(','):
                k = k.strip()
                if not k:
                    continue
                if '=' in k:
                    k,e = k.split('=',1)
                    k = k.strip()
                    if cls_ns is None:
                        cls_ns = cls.ns()
                    v = eval(e,None,cls_ns)
                    newdct[k] = v
                else:
                    newdct[k] = dct[k]
        newdct['__doc__'] = dct.get('__doc__')
        newname = cls.__name__ + '_Partial'
        return type(newname,cls.__bases__,newdct)

    def __enter__(cls):
        """Add all attributes/values to the set of global variables.
        Save enough state so that they can be restored when the context
        manager exits."""
        if not hasattr(cls,'__saved'):
            cls.__saved = []
        dct = cls.__dict__
        _new = []                # save a list of newly added variables
        _old = {}                # remember values of those that already exist in ns.
        ns = get_ipython().user_ns  # get the ns for the user
        for k,v in dct.items():
            if k in ns:
                _old[k] = ns[k]
            else:
                _new.append(k)
            ns[k] = v
        cls.__saved.append((_new,_old))
##        print('Push:',dct.keys(),_new,_old)
        return cls
    
    def __exit__(cls,*l):
        """When the context exits, restore the global values to what they
        were before entering."""
        _new,_old = cls.__saved.pop()
##        print('Pop:',_new,_old)
        ns = get_ipython().user_ns  # get the ns for the user
        for k,v in _old.items():
            ns[k] = v              # restore old values
        for k in _new:
            del ns[k]              # or delete them if they were newly created
        if not cls.__saved:
            del cls.__saved
        return False              # to re-raise exceptions
    
    def ns(cls):
        """Return namespace."""
        ans = {}
        for c in cls.__mro__:
            if c in (Part,object):
                continue
            for k,v in c.__dict__.items():
                if not k.startswith('_'):
                    if k not in ans:
                        ans[k] = v
        return ans

    def show(cls,keys=None):
        """Show variables in same form as show() function. If keys is None,
        show all with _doc first.  keys can be like in show - ie, expressions,
        scales, label=expr, etc.."""
        v = cls.ns()
        if keys is None:
            pairs = sorted([(k.lower(),k) for k in v.keys()])
            keys = ','.join([o for k,o in pairs])
        show(keys,data=v)

class Part(metaclass=PartMeta):
    
    pass
     
def makePart(cls):
    """Returns an object of type Part from the class definition and class attributes
    of 'cls'.  Intended to be used as a decorator so we can use class definitions
    to build parts (syntactic sugar)."""
    dct = cls.__dict__
    bases = cls.__bases__
    if Part not in cls.mro():
        if len(bases) > 0 and bases[-1] is object:
            bases = bases[:-1] + (Part,) + bases[-1:]
        else:
            bases = bases + (Part,)
        newdct = {k:v for k,v in dct.items() if not k.startswith('__')}
        newdct['__doc__'] = dct.get('__doc__')
        return type(cls.__name__,bases,newdct)
    return cls
