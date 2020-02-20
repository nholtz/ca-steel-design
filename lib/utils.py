from __future__ import print_function
import re
import string
import math
import sys
import os
import os.path
import imghdr
import inspect
import numpy as np

try:
    __SHELL = get_ipython()
    def get_locals_globals():
        global __SHELL
        return __SHELL.user_ns, __SHELL.user_global_ns
    from IPython import display
    from IPython.core.magic import register_line_magic
except NameError as e:
    raise Exception("Requires an IPython kernel - i.e., a jupyter notebook")


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
    """Return an SVG image after interpolating kwarg values."""
    with file(filename,"rb") as inf:
        svgdata = inf.read()
    outdata = _formatter.vformat(svgdata,[],kwargs)
    return display.SVG(data=outdata)

def _test_svg(bstream,fileobj):
    """Return indicator if stream or file is svg file.  Made for use in ImageMagik"""
    if fileobj:
        fileobj.seek(0)
        data = fileobj.read(6)
    else:
        data = bstream.read(6)
    if data == '<?xml ':
        return 'svg'
    return None
imghdr.tests.append(_test_svg)

EXTS = ['svg','png','jpeg','jpg']

def showImage(basename,rescan=False):
    """Display an image whose basename is 'basename'.  If an image
    cannot be found, the user is asked to scan an image, which is
    then installed.  Extensions '.jpg', '.png', '.svg' are tried in
    that order.  If rescan is True, scanning a new image is forced."""
    def _display(ifile):
        itype = imghdr.what(ifile)
        img = None
        if itype in ['jpeg','png']:
            img = display.Image(filename=ifile,embed=True)
        elif itype == 'svg':
            with file(ifile,"rb") as inf:
                svgdata = inf.read()
            img = display.SVG(data=svgdata)
        else:
            raise Exception("Invalid image type: {0}".format(itype))
        if img:
            display.display(img)

    if not rescan:
        for ext in EXTS:
            ifile = basename + '.' + ext
            if os.path.exists(ifile):
                _display(ifile)
                return
                
    ifile = basename + '.' + EXTS[-1]
    cmd = "scan-to-file {0}".format(ifile)
    os.system(cmd)
    if os.path.exists(ifile):
        _display(ifile)
    else:
        raise Exception("Unable to find image '{0}'; Tried these extensions: {1}".format(basename,EXTS))
        
__FIGPATH = None
        
def figure(filename):
    """Display an svg file given by filename. Use IMAGEPATH, if it exists,
    to search for the file."""
    global __FIGPATH
    if __FIGPATH is None:
        try:
            with open("IMAGEPATH","r") as ip:
                lines = ip.readlines()
            __FIGPATH = [x.strip() for x in lines]
        except FileNotFoundError:
            __FIGPATH = ['.']
    
    for pfx in __FIGPATH:
        pathname = os.path.join(pfx,filename)
        try:
            with open(pathname,"rb") as inf:
                svgdata = inf.read()
            display.display(display.SVG(svgdata))
            return
        except FileNotFoundError:
            continue
    raise FileNotFoundError(f"Unable to display svg file '{filename}'. Tried: "+', '.join([os.path.join(x,filename) for x in __FIGPATH]))
        
        
_FLOATS = [float,np.float64,np.float32,np.float]

def isfloat(x):
    return type(x) in _FLOATS

def sfround(x, n=3):
    """Returns x rounded to n significant figures."""
    y = abs(x)
    if y <= sys.float_info.min:
        return 0.
    return round(x, int(n - math.ceil(math.log10(y))))

def sfrounds(x, nsf=4):
    """Returns x as a string, rounded to n significant figures."""
    if x == 0.:
        return '0'
    s = str(round(x, int(nsf - math.ceil(math.log10(abs(x))))))
    if s.endswith('.0'):
        if len(s) > nsf+(2 if s.startswith('-') else 1):
            s = s[:-2]
    return s

## disabled Feb 14, 2020. I don't think we want to do it this way any more.
## use shell.ev instead
##def get_locals_globals(depth=2):
##    """Return a tuple of (local,globals) relevant to whoever
##    called this."""
##    #locals = sys._getframe(depth).f_locals      # locals in the caller
##    #globals = get_ipython().user_global_ns
##    #return locals,globals
##    f = sys._getframe(depth)
##    return f.f_locals,f.f_globals

def se_split(s):
    """Split a comma delimited string into sub-expressions.  Commas
    are NOT delimiters when enclosed in strings or brackets.
    sesplit('a,b(2,3),c,') => ['a', 'b(2,3)', 'c', '']
    sesplit('a,"(2,3",c')  => ['a', '"(2,3"', 'c']
    Splitting stops at a '#' not enclosed in string or brackets.
    """
    ans = []
    i = 0     # start of substring
    j = 0
    lev = 0   # bracket count
    sd = ''   # string delimiter
    for j  in range(len(s)):
        if sd:                # if inside string
            if s[j] == sd:    # see if it closes
                sd = ''
            continue          # otherwise, skip it.
        if s[j] == '"' or s[j] == "'":  # are we starting a string?
            sd = s[j]
            continue
        if s[j] in '([{':     # are we entering a bracket region?
            lev += 1
            continue
        if s[j] in ')]}':     # are we leaving a bracket region?
            lev -= 1
            if lev < 0:
                lev = 0
            continue
        if lev > 0:           # are we inside a bracket region?
            continue          # if so, ignore commas
        if s[j] == ',':       # found a comma outside? 
            ans.append(s[i:j].strip())  # then snarf the substring before it
            i = j+1
            continue
        if s[j] == '#':
            ans.append(s[i:j].strip())
            i = len(s)+1
            break
    else:
        if i <= len(s):
            ans.append(s[i:].strip())
    return ans

@register_line_magic
def show(*vlists,**kw):
    """Display the values of all variables and expressions named in
    an arbitrary number of comma-delimited strings.  vlist elements 
    beginning with a '*' give scales to apply to following values.  
    A None or bare * or *1 cancels the scales.  
    
    EG:   %show A,*1E3,Sz,Zx,*,Fy
    or: show('A,*1E3,Sz,Zx,*,Fy')
    
    When called as a normal function, keyword arguments can supply
    additional data: 
    nsf=4 is number of sig figs for floats;
    object=None gives an object whose vars() are added as
        local variables;
    data={} gives a dictionary whose values are added as
        local variables."""

    _locals,_globals = get_locals_globals()
    
    nsigfig = kw.pop('nsf',4)
    obj = kw.pop('object',None)
    if obj:
        _locals = _locals.copy()
        _locals.update(vars(obj))
    dct = kw.pop('data',None)
    if dct:
        _locals = _locals.copy()
        _locals.update(dct)
    if kw:
        raise ValueError('Invalid keyword arguments: '+' '.join(kw.keys()))

    def _eval(e,locals=_locals,globals=_globals):
        try:
            return eval(e,globals,locals)
        except:
            return '???'

    names = []
    scale = None
    for el in vlists:
        if el is None:
            scale = None
            continue
        if callable(getattr(el,'vars',None)):
            _locals = el.vars()
            continue
        for v in se_split(el):
            if v.startswith('*'):
                scale = v[1:].strip()
                if scale == '1':
                    scale = None
                continue
            m = re.match(r'^(.*[^<>=!])(=)([^=].*)$',v)
            if m:
                key,_,expr = m.groups()
            else:
                key = expr = v
            names.append((key,expr,scale,_locals))
    width = max([len(v) for v,e,s,l in names])
    lines = []
    for v,e,s,l in names:
        units = ''
        val = _eval(e,locals=l)
        if hasattr(val,'magnitude') and hasattr(val,'units'):
            units = str(val.units)
            val = val.magnitude
        if isfloat(val):
            if s:
                if '^' in s:
                    ss = '**'.join(s.split('^'))
                    S = float(eval(ss))
                elif '**' in s:
                    S = float(eval(s))
                else:
                    S = float(s)
                val /= S
            val = '{0:g}'.format(sfround(val,n=nsigfig))
            if s:
                val += ' * ' + s
        else:
            val = str(val)
        lines.append((v,val,units))
    valwidth = max([len(val) for v,val,units in lines if len(val) <= 10])
    for v,val,units in lines:
        print('{0:<{width}s} = {1:<{valwidth}s} {2}'.format(v,val,units,width=width,valwidth=valwidth))

def call(func,shape,map={},**kwargs):
    """This is meant as a convenience for calling functions with *many* 
    positional parameters.    
    Calls function 'func' with arguments drawn from dictionary 'shape'
    and keyword arguments 'kwargs'.  'func' may have only positional and
    default parameters; it may not have an excess positional parameters
    nor excess keyword parameters (ie. no parameter names starting with
    '*' or '**'.  All positional names must be defined in 'shape'. kwarg
    names may be defined in shape.  All kwarg names must be in the parameter
    list of the function.  kwarg values override those in 'shape' or in the 
    defaults. map provides an optional mapping from the argument names in func
    to the names in shape.
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
    >>> s = dict(a=100,b=200,c=300,q=500)
    >>> call(fn,s,map={'a':'q'},b=40)
    (500,40,300,20)
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

    def _map(k,map=map):
        return map[k] if k in map else k

    args = {k:shape[_map(k)] for k in fargs}  # positional params must be in shape dict
    for k in fdefargs:                  # optional params may be in shape dict
        km = _map(k)
        if km in shape:
            args[k] = shape[km]
    args.update(kwargs)                 # keyword args override anything in shape dict
    return func(**args)

class Recorder(object):
    
    def __init__(self):
        self.values = []
        
    def record(self,name,value=None,desc=None):
        self.values.append((name,value,value,desc))
        
    __call__ = record

    def summary(self,which=min):
        nsigfig = 4
        table = []
        govtag = 'governs -->'
        for key,val,txt,desc in self.values:
            vat = '{0:g}'.format(sfround(val,n=nsigfig))
            table.append((key,val,vat,desc))
        keywid = max([len(key) for key,val,vat,desc in table])
        vatwid = max([len(vat) for key,val,vat,desc in table])
        descwid = max([len(desc) for key,val,vat,desc in table])
        govval = which([val for key,val,vat,desc in table])
        tagwid = len(govtag)
        for key,val,vat,desc in table:
            tag = govtag if val == govval else ''
            l = '{0:<{1}s} {2:>{3}s} = {4:<{5}s}    - {6:<{7}s}'.format(tag,tagwid,key,keywid,vat,vatwid,desc,descwid)
            print(l)

if __name__ == '__main__':
    shape = dict(a=10,b=20,c=30,d=40,e=50,ee=500)
    def __fn(a,b,c,d=41,e=51):
        return (a,b,c,d,e)
    print(call(__fn,shape,map={'e':'ee'},b=-20))
                    
