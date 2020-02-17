#from Designer import Part, CMPart

from utils import show

class Part:
    
    def __init__(self,names=""):
        self.__names = [k.strip() for k in names.split(',') if k.strip()]
        
    def __enter__(self):
        """Add all attributes/values to the set of global variables.
        Save enough state so that they can be restored when the context
        manager exits."""
        if hasattr(self,'__saved'):
            raise Exception('Object already is a context manager. Cannot be one again.')
        dct = vars(self)
        _new = []                # save a list of newly added variables
        _old = {}                # remember values of those that already exist in ns.
        ns = get_ipython().user_ns  # get the ns for the user
        for k in self.__names:
            if not hasattr(self,k):
                raise KeyError('Invalid attribute: '+k)
            if k in ns:
                _old[k] = ns[k]
            else:
                _new.append(k)
            ns[k] = getattr(self,k)
        self.__saved = (_new,_old)
        return self
    
    def __exit__(self,*l):
        """When the context exits, restore the global values to what they
        were before entering."""
        _new,_old = self.__saved
        ns = get_ipython().user_ns  # get the ns for the user
        for k,v in _old.items():
            ns[k] = v              # restore old values
        for k in _new:
            del ns[k]              # or delete them if they were newly created
        del self.__saved
        return False              # to re-raise exceptions
    
    
    @classmethod
    def only(cls,names=''):
        newdct = {}
        dct = cls.__dict__
        for k in names.split(','):
            k = k.strip()
            if k and k in dct:
                newdct[k] = dct[k]
        newdct['__doc__'] = dct.get('__doc__')
        newname = 'Part_of_'+cls.__name__
        return type(newname,cls.__bases__,newdct)
    
    def ns(self):
        ans = {}
        for k,v in vars(self).items():
            if not k.startswith('__') and not k.startswith('_Part__'):
                if k not in ans:
                    ans[k] = v
        for cls in self.__class__.__mro__:
            if cls in (Part,object):
                continue
            for k,v in cls.__dict__.items():
                if not k.startswith('__'):
                    if k not in ans:
                        ans[k] = v
        return ans

    def show(self,keys=None):
        """Show variables in same form as show() function. If keys is None,
        show all with _doc first.  keys can be like in show - ie, expressions,
        scales, label=expr, etc.."""
        v = self.ns()
        if keys is None:
            pairs = sorted([(k.lower(),k) for k in v.keys()])
            keys = ','.join([o for k,o in pairs])
        show(keys,data=v)

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
