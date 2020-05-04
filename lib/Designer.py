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
from IPython.display import display, clear_output
from IPython import get_ipython
from utils import SVG, show, sfrounds, sfround, get_locals_globals, isfloat, Recorder, figure, se_split

# fixup display() of strings; see display() help
def str_formatter(str,pp,cycle):
    return pp.text(str)
plain = get_ipython().display_formatter.formatters['text/plain']
plain.for_type(str,str_formatter)

class DesignerError(Exception):
    pass

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

def fmt_dict(d,varlist='',nsigfigs=4,sort=True):
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
    keys = d.keys()
    if sort:
        keys = sorted(keys,key=str.lower)
    for k in keys:
        ans.append(_fmt_pair(k,d[k]))
    return ', '.join(ans)


def fmt_dict2(d,varlist='',nsigfigs=4,sort=True):
    """Format the values in the dictionary, d, as a 
    set of lines of name=val pairs.  Format floats
    to 4 sig figs.  If a comma-separated list of names
    is given in varlist, do those first in order.  Then
    format whatever is left, in whatever order they come."""
    d = d.copy()
    def _fmt_pair(k,v):
        return '{0} = {1}'.format(k,fmt_quantity(v,nsigfigs=nsigfigs))
    ans = []
    if varlist:
        for k in re.split(r'\s*,\s*',varlist.strip()):
            ans.append(_fmt_pair(k,d.pop(k)))
    keys = d.keys()
    if sort:
        keys = sorted(keys,key=str.lower)
    for k in keys:
        ans.append("    "+_fmt_pair(k,d[k])+"\n")
    return ''.join(ans)


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
            
    def record(self,val,label,_varlist='',values=None,**kwargs):
        """Record a result for an analysis computation."""
        if self.units and hasattr(val,'to'):
            val = val.to(self.units)
        d = {}
        if values:
            d.update(values)
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
        
    def setvars(self,*args,**kwargs):
        return DesignNotes_CM(self,*args,**kwargs)

    def fmt_check(self,chk,width=None):
        """Format a check record for display."""
        flag,label,_varlist,_vars = chk
        if width is None:
            width = len(label)
        if flag:
            return "    {0:<{1}}  OK \n      ({2})".format(label+'?',width,fmt_dict(_vars,_varlist))
        return "    {0:<{1}}  NG! *****\n      ({2})".format(label+'?',width,fmt_dict(_vars,_varlist))
    
    def fmt_recordxxx(self,rec,width=None,var=None,governs=False,nsigfigs=4,showvars=True):
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

    def fmt_record(self,rec,width=None,var=None,governs=False,nsigfigs=4,showvars=True):
        """Format a computation record for display."""
        label,_varlist,_vars = rec
        _vars = _vars.copy()
        if width is None:
            width = len(label)
        if var is None:
            var = self.var
        ans = ""
        if _vars and showvars:
            ans += fmt_dict2(_vars)
            ans += "\n"
        ans += "    {label:<{width}} ".format(label=label+':',width=width)
        if var:
            val = _vars.pop(var)
            ##print(val, type(val))
            ans += '{0} = {1}'.format(var,fmt_quantity(val,nsigfigs=nsigfigs,sep=' '))
            if governs:
                ans += '    <<<--- GOVERNS'
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
    
## perthaps .setvars() should do most of the work of saving/injecting
## then return a context manager to restore/log info
## that way could be used outside of with statement ...
## setvars captures all required variable values, does not log anything
## only .__exit__() logs ....


class DesignNotes_CM(object):

    """DesignNotes Context Manager."""

    def __init__(self, notes, *objattrs, label=None, result_var=None,
                 local='', locals='', globals='', trace=None, record=True):
        self.notes = notes
        self.objattrs = objattrs
        self.label = label
        if result_var is None:
            result_var = notes.var
        self.result_var = result_var
        self.local = local + locals   # get rid of local some day, locals is preferred because of globals
        self.globals = globals
        if trace is None:
            trace = notes.trace
        self.trace = trace
        self.record = record
        self._setup()

    def _setup(self):
        """Add all attributes/values to the set of global variables.
        Save enough state so that they can be restored when the context
        manager exits."""
        gns = get_ipython().user_ns  # get the ns for the user
        d = {}
        gns = get_ipython().user_ns
        for ob in self.objattrs:
            if ispartial(ob):
                for target,value in ob.ns().items():
                    if target in d:
                        raise DesignerError('''Name '{}' has been used more than once.'''.format(target))
                    d[target] = value
                continue
            else:
                obj,names = ob
            objns = obj.ns()
            for expr in se_split(names):
                if '=' in expr:
                    target,rhs = [x.strip() for x in expr.split('=',1)]
                    if rhs in objns:
                        value = objns[rhs]
                    else:
                        value = eval(rhs,gns,objns)
                else:
                    target = expr
                    value = objns[expr]
                if target in d:
                    raise DesignerError('''Name '{}' has been used more than once.'''.format(target))
                d[target] = value
        self.new_values = d
        self.local_vars = [y for y in [x.strip() for x in self.local.split(',')] if y] + [self.result_var]
        self.global_vars = [y for y in [x.strip() for x in self.globals.split(',')] if y]
        
        self.changed_values = {}
        self.added_vars = []
        
    def __enter__(self):
        gns = get_ipython().user_ns
        for k,v in self.new_values.items():
            if k in gns:
                self.changed_values[k] = gns[k]
            else:
                self.added_vars.append(k)
            gns[k] = v
            
        for k in self.local_vars:
            if k in self.changed_values or k in self.added_vars:
                raise DesignerError('''Name '{}' has been used more than once.'''.format(k))
            if k in gns:
                self.changed_values[k] = gns[k]
                del gns[k]
            else:
                self.added_vars.append(k)
        return self
    
    enter = __enter__
    
    def __exit__(self,exc_type,exc_value,exc_tb):
        """When the context exits, restore the global values to what they
        were before entering."""
        gns = get_ipython().user_ns  # get the ns for the user
        
        # capture current values of all local variables
        dct = {}
        for k,v in self.changed_values.items():
            if k in gns:
                dct[k] = gns[k]
        for k in self.added_vars + self.global_vars:
            if k in gns:
                dct[k] = gns[k]
        self.ending_values = dct
        
        # record the result produced
        if self.record and self.label and exc_type is None:
            rkey = self.result_var
            if rkey in gns:
                rval = gns[rkey]
            else:
                raise DesignerError('''Result variable '{}' is not defined.'''.format(rkey))
            self.notes.record(rval,self.label,values=self.ending_values)
        
        # now change the user ns back to what it was before __enter__
        for k,v in self.changed_values.items():
            gns[k] = v               # restore old values
        for k in self.added_vars:
            if k in gns:
                del gns[k]           # or delete them if they were newly created
        self.changed_values = {}
        self.added_vars = []
        return False              # to re-raise exceptions
    
    exit = __exit__
    
################################################################
################ Parts
################################################################

class PartMeta(type):
    
    def __call__(cls,*args,**kwargs):
        raise TypeError("It is not possible to create an instance of this class: "+repr(cls))
        
    def __ns__(cls):
        """Return the namespace."""
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
        v = cls.__ns__()
        if keys is None:
            keys = ','.join(sorted(v.keys(),key=lambda s: s.lower()))
        show(keys,data=v)
        
    def values(cls,keys):
        keys = [x.strip() for x in keys.split(',') if x]
        ans = tuple([cls.__dict__[k] for k in keys])
        if not ans:
            raise ValueError('No keys found')
        return ans if len(ans) > 1 else ans[0]
    
    def items(cls,keys):
        keys = [k for k in se_split(keys) if k]
        dct = cls.__ns__()
        ans = []
        for k in keys:
            if '=' in k:
                k,e = [x.strip() for x in k.split('=',1)]
                v = eval(e,dct)
            else:
                v = dct[k]
            ans.append((k,v))
        return ans
        
        
class Part(metaclass=PartMeta):
    
    pass

def extract(s,*objs,**kwds):
    if not objs:
        raise ValueError('No part objects given.')
    dct = {}
    for o in objs:
        for k,v in o.__dict__.items():
            if not k.startswith('__'):
                if k not in dct:
                    dct[k] = v
    dct.update(kwds)
    newdct = {}
    for k in se_split(s):
        if not k:
            continue
        if '=' in k:
            k,e = [x.strip() for x in k.split('=',1)]
            v = eval(e,dct)
            newdct[k] = v
        else:
            newdct[k] = dct[k]
    newdct['__doc__'] = objs[0].__dict__.get('__doc__')
    newname = objs[0].__name__ + '_Extract'
    return PartMeta(newname,(Part.__bases__),newdct)


def makePart(cls):
    """Returns an object of type Part from the class definition and class attributes
    of 'cls'.  Intended to be used as a decorator so we can use class definitions
    to build parts (syntactic sugar)."""
    dct = cls.__dict__
    bases = cls.__bases__
    bad = [k for k in dct if k.startswith('__') and k not in ['__module__','__dict__','__weakref__','__doc__']]
    if bad:
        raise TypeError('Invalid key names: {}'.format(', '.join(bad)))
    newdct = {k:v for k,v in dct.items() if not k.startswith('__')}
    return PartMeta(cls.__name__,bases,newdct)


def ispartial(cls):
    if callable(getattr(cls,'ispartial',None)):
        return cls.ispartial()
    return False

################################################################
# instantiate the section tables

SST = sst.SST()
