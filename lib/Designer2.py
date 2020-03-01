from __future__ import print_function
import sys
import re
import inspect
import numpy
import sst
import math
import datetime
#from warnings import filterwarnings
#filterwarnings('ignore', module='IPython.html.widgets')
import ipywidgets as widgets
from IPython.display import display, clear_output
from IPython import get_ipython
from utils import SVG, show, sfrounds, sfround, get_locals_globals, isfloat, Recorder, figure, se_split

# fixup display() of strings; see display() help
def str_formatter(str,pp,cycle):
    return pp.text(str)
plain = get_ipython().display_formatter.formatters['text/plain']
plain.for_type(str,str_formatter)

class CheckerError(Exception):
    pass

class CheckerWarning(Warning):
    pass

def Error(msg):
    raise CheckerError(msg)

def Warn(s):
    print('***** WARNING:',s,'*****')
    
def fmt_quantity(v,nsigfigs=4,sep=''):
    u = ''
    if hasattr(v,'magnitude') and hasattr(v,'units'):
        u = str(v.units)
        v = v.magnitude
    if isfloat(v):
        v = sfrounds(v,nsigfigs)
    else:
        v = str(v)
    if u:
        v = v + sep + u
    return v

def fmt_dict(d,varlist='',nsigfigs=4):
    """Format the values in the dictionary, d, as a 
    comma-separated list of name=val pairs.  Format floats
    to 4 sig figs.  If a comma-separated list of names
    is given in varlist, do those first in order.  Then
    format whatever is left, in whatever order they come."""
    d = d.copy()
    def _fmt_pair(k,v):
        return '{0}={1}'.format(k,fmt_quantity(v,nsigfigs=nsigfigs))
    ans = []
    if varlist:
        for k in re.split(r'\s*,\s*',varlist.strip()):
            ans.append(_fmt_pair(k,d.pop(k)))
    sorted = lambda l: l
    for k in sorted(d.keys()):
        ans.append(_fmt_pair(k,d[k]))
    return ', '.join(ans)


def _get(dct,keys):
    """Return the value, in dct, of all comma-sperated expressions
    in keys.  Each key expression can be:
       - an identifier, or
       - and identifier=default_value, or
       - an expression that is evaluated
    If there is only one key, return a singleton, else return a list of values.
    eg:  d = dict(a=10,b=20)
         _get(d,'a,b=40,c=50,a+b') => [10,20,50,30]
    """
    ans = []
    keys = keys.split(',')
    for k in keys:
        default = None
        if '=' in k:
            k,default = k.split('=',1)
        k = k.strip()
        if k in dct:
            ans.append(dct[k])
        elif default is not None:
            ans.append(eval(default,{},dct))
        else:
            ans.append(eval(k,{},dct))
    if len(keys) == 1:
        return ans[0]
    return ans


################################################################
#### DesignNotes
################################################################

## see Parameters.py for the'needs-to-be-updated' widget thingee.
            
class DesignNotes(object):
    
    def __init__(self,var,trace=False,units=None,selector=min,title='',nsigfigs=3,show_params=False):
        self.trace = trace
        self.var = var
        self.units = units
        self.selector = selector
        self.title = title
        self.nsigfigs = nsigfigs
        self.show_params = show_params
        self._notes = []
        self._checks = []
        self._record = []
        self._execution_count = None
        self._locals,self._globals = get_locals_globals()
        
        self.SST = sst.SST()
            
    def require(self,val,msg='',_varlist='',**kwargs):
        """Raise an exception with a msg if flag is not True."""
        if msg == '':
            msg = 'Error'
        if not val:
            Error('FATAL!! '+msg+': '+fmt_dict(kwargs))
            
    def note(self,msg):
        """Record an arbitrary note."""
        self._notes.append(msg)
        if self.trace:
            print('Note:',msg)
            
    def check(self,val,msg='',_varlist='',**kwargs):
        """Record the result of checking a requirement."""
        d = {}
        if _varlist:
            locals,globals = get_locals_globals()
            for v in re.split(r'\s*,\s*',_varlist.strip()):
                d[v] = locals[v] if v in locals else globals[v]
        d.update(kwargs)
        self._checks.append((val,msg,_varlist,d))
        if self.trace:
            print(self.fmt_check(self._checks[-1]))
        ##return val

### See Updating-Cells.ipynb for ideas about how we could add a '<<<--- GOVERNS' tag
### When results are finally summarized.  Use display() rather than print and gen a display_id
            
    def record(self,val,label,_varlist='',**kwargs):
        """Record a result for an analysis computation."""
        if self.units and hasattr(val,'to'):
            val = val.to(self.units)
        d = {}
        if _varlist:
            locals,globals = get_locals_globals()
            for v in re.split(r'\s*,\s*',_varlist.strip()):
                d[v] = locals[v] if v in locals else globals[v]
        d.update(kwargs)
        if self.var:
            d[self.var] = val
        rec = (label,_varlist,d)
        cell = None
        if self.trace:
            cell = display(self.fmt_record(rec),display_id=True)
        self._record.append((rec,cell))
        ##return val

    def fmt_check(self,chk,width=None):
        """Format a check record for display."""
        flag,label,_varlist,_vars = chk
        if width is None:
            width = len(label)
        if flag:
            return "    {0:<{1}}  OK \n      ({2})".format(label+'?',width,fmt_dict(_vars,_varlist))
        return "    {0:<{1}}  NG! *****\n      ({2})".format(label+'?',width,fmt_dict(_vars,_varlist))
    
    def fmt_record(self,rec,width=None,var=None,governs=False,nsigfigs=4,showvars=True):
        """Format a computation record for display."""
        label,_varlist,_vars = rec
        _vars = _vars.copy()
        if width is None:
            width = len(label)
        if var is None:
            var = self.var
        ans = "    {label:<{width}} ".format(label=label+':',width=width)
        if var:
            val = _vars.pop(var)
            ##print(val, type(val))
            ans += '{0} = {1}'.format(var,fmt_quantity(val,nsigfigs=nsigfigs,sep=' '))
            if governs:
                ans += '    <<<--- GOVERNS'
        if _vars and showvars:
            ans += '\n       ('+fmt_dict(_vars)+')'
        return ans

    def show(self,*vlists):
        show(*vlists,object=self)
            
    def summary(self,*vars):
        """Display a summary of all recorded notes, checks, records."""

        if vars:
            print("Values Used:")
            print("============")
            print()
            show(*vars)
            
        var = self.var
        hd = 'Summary of '
        hd += self.__class__.__name__
        if var is not None:
            hd += ' for '+var
        if self.title:
            hd += ': '+str(self.title)
        
        print()
        print(hd)
        print('=' * len(hd))
        print()
        if self._notes:
            print('Notes:')
            print('------')
            for txt in self._notes:
                print('    -',txt)
            print()
            
        if self._checks:
            print('Checks:')
            print('-------')
            width = max([len(l) for f,l,v,d in self._checks])
            for chk in self._checks:
                print(self.fmt_check(chk,width=width+2))
            print()
                
        hd = 'Values'
        if self.var:
            hd += ' of '+self.var
        hd += ':'
        print(hd)
        print('-'*len(hd))
        width = max([len(l) for (l,v,d),c in self._record])
        
        govval = None
        if var:
            govval = self.selector([d[var] for (l,v,d),c in self._record])
        for (l,v,d),c in self._record:
            print(self.fmt_record((l,v,d),var=var,width=width+1,governs=govval is not None and govval == d.get(var,None),
                                  nsigfigs=self.nsigfigs,showvars=False))

        if govval is not None:
            print()
            h = 'Governing Value:'
            print('   ',h)
            print('   ','-'*len(h))
            print('      ','{0} = {1}'.format(var,fmt_quantity(govval,self.nsigfigs,' ')))

            for (_label,_vlist,_vars),_cell in self._record:
                if _cell and govval == _vars.get(var,None):
                    ##print('Updating')
                    _cell.update(self.fmt_record((_label,_vlist,_vars),governs=True))

    ################################################################ Caution! not yet finished below

class DesignNotes_CM(object):

    """DesignNotes Context Manager."""

    def __init__(self, notes, objattrs, title=None, result=None, record=None, trace=None):
        if trace is None:
            trace = notes.trace
        self.notes = notes
        self.title = title
        self.result = result
        self.record = record
        self.trace = trace
        d = {}
        gns = get_ipython().user_ns
        for obj,names in objattrs:
            objns = obj.ns()
            for expr in se_split(names):
                if '=' in expr:
                    target,rhs = [x.strip() for x in expr.split('=',1)]
                    if rhs in objns:
                        value = objns[rhs]
                    else:
                        value = eval(rhs,{},objns)
                else:
                    target = expr
                    value = objns[expr]
                if target in d:
                    raise KeyError('''Name '{}' has been extracted multiple times.'''.format(target))
                d[target] = value
        self.new_ns = d
        self.old_vars = {}
        self.new_vars = []
                                   

    def __enter__(self):
        """Add all attributes/values to the set of global variables.
        Save enough state so that they can be restored when the context
        manager exits."""
        gns = get_ipython().user_ns  # get the ns for the user
        for k,v in self.new_ns.items():
            if k in gns:
                self.old_vars[k] = gns[k]
            else:
                self.new_vars.append(k)
            gns[k] = v
        return self
    
    def __exit__(self,*l):
        """When the context exits, restore the global values to what they
        were before entering."""
        gns = get_ipython().user_ns  # get the ns for the user
        for k,v in self.old_vars.items():
            gns[k] = v               # restore old values
        for k in self.new_vars:
            if k in gns:
                del gns[k]           # or delete them if they were newly created
        self.old_vars = {}
        self.new_vars = []
        return False              # to re-raise exceptions
    
################################################################
################ Parts
################################################################

class PartMeta(type):
    
    def __call__(cls,*args,**kwargs):
        raise TypeError("It is not possible to create an instance of this class: "+repr(cls))
    
    def __getitem__(cls,keys):
        if not type(keys) == type(()):
            keys = (keys,)
        ##print(cls,keys)
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
                        cls_ns = (globals(),cls.ns())
                    v = eval(e,*cls_ns)
                    newdct[k] = v
                else:
                    newdct[k] = dct[k]
        newdct['__doc__'] = dct.get('__doc__')
        newname = cls.__name__ + '_Partial'
        return PartMeta(newname,cls.__bases__,newdct)

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

    def get(cls,keys):
        v = (globals(),cls.ns())
        ans = []
        for k in keys.split(','):
            k = k.strip()
            if k:
                ans.append(eval(k,*v))
        return ans[0] if len(ans) == 1 else ans
                

class Part(metaclass=PartMeta):
    
    pass
     
def makePart(cls):
    """Returns an object of type Part from the class definition and class attributes
    of 'cls'.  Intended to be used as a decorator so we can use class definitions
    to build parts (syntactic sugar)."""
    dct = cls.__dict__
    bases = cls.__bases__
    newdct = {k:v for k,v in dct.items() if not k.startswith('__')}
    return PartMeta(cls.__name__,bases,newdct)

################################################################
# instantiate the section tables

SST = sst.SST()
