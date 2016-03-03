import re
import string
import math
import sys
import inspect
import numpy as np

from IPython import display

class _defaultFormatter(string.Formatter):

    """Formatter dosn't complain about missing field names.  Rather,
    returns a '{field_name}' string for them."""

    def get_value(self,field_name,args,kwargs):
        if type(field_name) is int:
            return args[field_name]
        if field_name in kwargs:
            return kwargs[field_name]
        try:
            v = eval(field_name,{},kwargs)
            return v
        except:
            pass
        return '{'+str(field_name)+'}'

    def format_field(self,value,format_spec):
        if type(value) is str:
            if value.startswith('{'):
                if value.endswith('}'):
                    return value
        return string.Formatter.format_field(self,value,format_spec)


_formatter = _defaultFormatter()

def SVG(filename,**kwargs):
    with file(filename,"rb") as inf:
        svgdata = inf.read()
    outdata = _formatter.vformat(svgdata,[],kwargs)
    return display.SVG(data=outdata)

_FLOATS = [float,np.float64,np.float32,np.float]

def isfloat(x):
    return type(x) in _FLOATS

def sfround(x, n=3):
    """Returns x rounded to n significant figures."""
    if x == 0.:
        return x
    s = round(x, int(n - math.ceil(math.log10(abs(x)))))
    return s

def sfrounds(x, nsf=4):
    """Returns x as a string, rounded to n significant figures."""
    if x == 0.:
        return '0'
    s = str(round(x, int(nsf - math.ceil(math.log10(abs(x))))))
    if s.endswith('.0'):
        if len(s) > nsf+(2 if s.startswith('-') else 1):
            s = s[:-2]
    return s

def get_locals_globals(depth=2):
    """Return a tuple of (local,globals) relevant to whoever
    called this."""
    #locals = sys._getframe(depth).f_locals      # locals in the caller
    #globals = get_ipython().user_global_ns
    #return locals,globals
    f = sys._getframe(depth)
    return f.f_locals,f.f_globals

def show(*vlists,**kw):
    """Display the values of all variables named in
    an arbitrary number of comma-delimited strings. depth=0
    is number of levels above calling level; nsf=4 is number
    of sig figs for floats."""
    depth = kw.get('depth',0)
    locals,globals = get_locals_globals(depth=depth+2) # locals in the caller
    nsigfig = kw.get('nsf',4)

    def _eval(e,locals=locals,globals=globals):
        try:
            return eval(e,globals,locals)
        except:
            return '???'

    names = []
    for el in vlists:
        for v in re.split(r'\s*,\s*',el.strip()):
            names.append(v)
    width = max([len(v) for v in names])
    for v in names:  
        val = _eval(v)
        if isfloat(val):
            val = '{0:.{1}g}'.format(val,nsigfig)
        else:
            val = str(val)
        print '{0:<{width}s} = {1}'.format(v,val,width=width)

def call(func,shape,**kwargs):
    """This is meant as a convenience for calling functions with *many* 
    positional parameters.    
    Calls function 'func' with arguments drawn from dictionary 'shape'
    and keyword arguments 'kwargs'.  'func' may have only positional and
    default parameters; it may not have an excess positional parameters
    nor excess keyword parameters (ie. no parameter names starting with
    '*' or '**'.  All positional names must be defined in 'shape'. kwarg
    names may be defined in shape.  All kwarg names must be in the parameter
    list of the function.  kwarg values override those in 'shape' or in the 
    defaults.
    For example:
        def fn(a,b,c=10,d=20):
            ...
        call(fn,s,b=40)
        'a' and 'b' must be in s, and their values are used, but the value
        of b overides anything in s.
        'c' and 'd' may be in 's'; if not the default values are used.

    :Example:

    >>> def fn(a,b,c=10,d=20):
    ...    return (a,b,c,d)
    ...
    >>> s = dict(a=100,b=200,c=300)
    >>> call(fn,s,b=40)
    (100,40,300,20)
    """

    fargs,fvarargs,fkeywords,fdefaults = inspect.getargspec(func)
    if fvarargs:
        raise Exception('Function may not have a variable positional argument.')
    if fkeywords:
        raise Exception('Function may not have a keyword argument.')

    allargs = fargs
    fdefargs = []
    if fdefaults:
        fdefargs = fargs[-len(fdefaults):]
        fargs = fargs[:-len(fdefaults)]
    for k in kwargs.keys():
        if k not in allargs:
            raise Exception('Invalid keyword argument: '+repr(k))

    args = {k:shape[k] for k in fargs}  # positional params must be in shape dict
    for k in fdefargs:                  # optional params may be in shape dict
        if k in shape:
            args[k] = shape[k]
    args.update(kwargs)                 # keyword args override anything in shape dict
    return func(**args)
