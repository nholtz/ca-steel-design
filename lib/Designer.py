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
from utils import SVG, show, sfrounds, sfround, get_locals_globals, isfloat, Recorder

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
            
def table_search(v,table):
    """Search a list of (val,data) tuples representing a table, for the
    first row where v-delta <= val.  Return the data.  delta = (val[i+1]-val[i])/2.
    (half distance to next larger val)."""
    last = len(table)-1
    for i in range(last+1):
        k = i+1 if i < last else last
        delta = (table[k][0] - table[k-1][0])/2.
        if v-table[i][0] <= delta:
            return table[i][1]
    Error('Unable to find value in table')           

class Param(object):
    
    """A Param is one settable parameter, to be used to obtain
    input data for a function.  By default, it uses pretty well the same
    widget abbreviations as @interact.  Values can be obtained via
    widget, or by static declaration."""
    
    __COUNTER__ = 0   ## to maintain relative ordering of widgets
      
    def __init__(self,arg,**kwargs):
        self._relposn = self.__next__()
        self.widget = None
        self.value = None
        
        if arg is None:
            return
        
        if type(arg) in [int,float,str]:
            self.value = arg
            widg = {int:widgets.IntText,float:widgets.FloatText,str:widgets.Text}[type(arg)]
            self.widget = widg(value=str(arg))
        else:
            self.widget = self._make_widget(arg)
                
        if self.widget is None:
            Error("'{0}' cannot be made into a widget.".format(arg))
                
        if self.widget:
            self.value = self.widget.value
            def _update(name,value):
                self.value = value
            self.widget.on_trait_change(_update,'value')

        kwargs = kwargs.copy()
        if 'value' in kwargs:
            self.value = kwargs.pop('value')
            self.widget.value = self.value
        if 'description' in kwargs:
            self.widget.description = kwargs.pop('description')
        if 'disabled' in kwargs:
            self.widget.disabled = kwargs.pop('disabled')
                    
        if kwargs:
            Error('Unused keyword arguments: '+','.join(kwargs.keys()))
            
    @classmethod
    def __next__(cls):
        """Increment the class counter and return its new value."""
        cls.__COUNTER__ += 1
        return cls.__COUNTER__
    
    def _make_tmms(self,arg):
        """Return (type,min,max,step) for widget abbreviation in arg.
        arg is "(min,max[, step])" and if any of these are floats, the
        type is float else int."""
        inttype = type(0)
        floattype = type(0.0)
        numtypes = [inttype,floattype]
        ans = [None,None,None,None]
        if len(arg) < 2 or len(arg) > 3:
            return ans
        if not all([type(x) in numtypes for x in arg]):
            return ans
        ans[0] = int if all([type(x) is inttype for x in arg]) else float
        ans[1] = ans[0](arg[0])
        ans[2] = ans[0](arg[1])
        ans[3] = ans[0](1)
        if len(arg) == 3:
            ans[3] = ans[0](arg[2])
        return ans
    
    def _make_widget(self,arg):
        """Make a widget from the abbreviation in arg."""
        if isinstance(arg,widgets.Widget):
            return arg
        if isinstance(arg,dict):
            return  (widgets.ToggleButtons if len(arg) <= 3 else widgets.Dropdown)(options=arg)
        if type(arg) is bool:
            return widgets.Checkbox(value=arg)
        if isinstance(arg,list) or isinstance(arg,tuple):
            if all([isinstance(x,str) for x in arg]):
                return (widgets.ToggleButtons if len(arg) <= 3 else widgets.Dropdown)(options=arg)
            if len(arg) > 1 and all([(isinstance(x,tuple) and len(x) == 2 and isinstance(x[0],str)) for x in arg]):
                return (widgets.ToggleButtons if len(arg) <= 3 else widgets.Dropdown)(options=arg)
            typ,min,max,step = self._make_tmms(arg)
            if typ is not None:
                cls = widgets.FloatSlider if typ is float else widgets.IntSlider
                return cls(min=min,max=max,step=step,value=(min+max)/2)
        
    
    def __str__(self):
        return "Param(relposn={0},value={1})".format(self._relposn,self.value)
    
    __repr__ = __str__
    
    
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
        show(*vlists,depth=1)
            
    def summary(self,*vars):
        """Display a summary of all recorded notes, checks, records."""

        if vars:
            print("Values Used:")
            print("============")
            print()
            show(*vars,depth=1)
            
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
            
    def _get_params(self):
        """Return a dictionary of the values of all parameters (class variables)."""
        params = [(p,v) for p,v in inspect.getmembers(self.__class__) if p[0] != '_' and not inspect.ismethod(v)]
        params = {p:(v.value if isinstance(v,Param) else v) for (p,v) in params}
        return params
            
    def inject_globals(self):
        """Add all parameters and values to the global namespace."""
        params = self._get_params()
        #ip = get_ipython()
        #ip.push(params)
        g = self._globals
        for k,v in params.items():
            g[k] = v
        return params

    def run_imported_code(self):
        if self.__class__.__module__ == '__main__':
            return
        mod = sys.modules.get(self.__class__.__module__,None)
        if mod is None:
            return
        if not getattr(mod,'__loaded__',False):
            return
        runner = getattr(mod,'__runcode__',None)
        if not callable(runner):
            return
        runner(after=self._execution_count,silent=False)
        return True
        
    def compute(self):
        """The .compute() method is called by .run() (and thus by .interact()).
        The default implementation adds all parameters to the global namespace,
        and executes the rest of the module, if it is an imported file """
        p = self.inject_globals()
        print('Time:', datetime.datetime.now().ctime())
        #print('Globals Set:',', '.join(['{0}={1!r}'.format(k,p[k]) for k in sorted(p.keys(),key=lambda x: x.lower())]))
        print()
        return self.run_imported_code()

    def run(self,show=None,instruct=True):
        """Extract the values of all relevant parameters (class variables) and call
        the .compute() method with those as arguments."""

        try:
            self._execution_count = get_ipython().user_ns['__execution_count__']
        except KeyError:
            pass

        self._notes = []
        self._checks = []
        self._record = []
        params = self._get_params()
        
        fn = self.compute   ## this is the method (function) we will call
            
        # find the parameters of the function
        args,varargs,kwargs,defaults = inspect.getargspec(fn)
        defargs = []
        if defaults:
            defargs = args[-len(defaults):]
            args = args[:-len(defaults)]
            
        for k in args[1:]:
            if k not in params:
                Error("Argument '{0}' not defined in {1}".format(k,self.__class__.__name__))
        
        # build a dictionary of values, and call the method
        chkr_args = {k:params[k] for k in args[1:]}
        if defaults:
            for k,v in zip(defargs,defaults):
                chkr_args = params.get(k,v)
            
        if show is None:
            show = self.show_params
        if show:
            params = [(p,v) for p,v in inspect.getmembers(self.__class__) if p[0] != '_' and isinstance(v,Param)]
            params.sort(key=lambda t: t[1]._relposn)
            width = max([len(p) for p,v in params])
            print('Parameter Values:')
            print('=================')
            print()
            for p,v in params:
                print("{0:<{1}} = {2}".format(p,width,v.value))
            print()

        ans = fn(**chkr_args)
        if instruct:
            print("Select the following cell and execute menu item 'Cell / Run All Below'.")

        return
    
    nointeract = run    # an alternate spelling of .run()

    def set_widget(self,**kw):
        """Reset the Param value (widget) for selected class variables."""
        params = [(p,v) for p,v in inspect.getmembers(self.__class__) if p[0] != '_' and isinstance(v,Param)]
        params = dict(params)
        for k,v in kw.items():
            if k not in params:
                Error('Name not in set of parameters: {0}'.format(k))
            if not isinstance(v,Param):
                Error('Value of name is not of type Param: {0}'.format(k))
            v._relposn = params[k]._relposn
            setattr(self.__class__,k,v)

    def set_default(self,**kw):
        """Reset the default Param value for selected class variables."""
        params = [(p,v) for p,v in inspect.getmembers(self.__class__) if p[0] != '_' and isinstance(v,Param)]
        params = dict(params)
        for k,v in kw.items():
            if k not in params:
                Error('Name not in set of parameters: {0}'.format(k))
            p = params[k]
            p.value = p.widget.value = v

    def interact(self,show=None,instruct=True):
        """Display the widgets created by 'Param()' values in the
        calls variables, in the order defined.  Add a go button
        with a callback that calls the '.run()' method, which in turn
        calls the users '.compute()' method."""
        if show is not None:
            self.show_params = show
        # build an ordered list of all members (instance variables) whose value is instance of Param() 
        # and whose name doesn't start with '_'
        params = [(p,v) for p,v in inspect.getmembers(self.__class__) if p[0] != '_' and isinstance(v,Param)]
        params.sort(key=lambda t: t[1]._relposn)
        # make a list of all the widgets from the list of Param()s
        ws = []
        for name,param in params:
            if param.widget:
                if param.widget.description == '':
                    param.widget.description = name
                ws.append(param.widget)
        # add a 'Run' button to the list
        title = self.title if self.title else self.__class__.__name__
        button = widgets.Button(description="Run {0}".format(title))
        ws.append(button)

        for w in ws:
            w.padding = 2
        
        container = widgets.VBox()
        container.children = ws
        container.result = None

        def call_run(button,instruct=instruct):
            clear_output(wait=True)
            button.disabled = True
            try:
                container.result = self.run(instruct=instruct)
            except Exception as e:
                ip = get_ipython()
                if ip is None:
                    container.log.warn("Exception in interact callback: %s", e, exc_info=True)
                else:
                    ip.showtraceback()
            finally:
                button.disabled = False
            
        button.on_click(call_run)
        call_run(button,instruct=False)  # ensure run() is called before button is clicked

        return container


def Warn(s):
    print('***** WARNING:',s,'*****')
    
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
    
    
class Part(object):
    
    def __init__(self,_doc='',**keywd):
        self._doc = _doc
        self.set(**keywd)
            
    def set(self,**keywd):
        for k,v in keywd.items():
            setattr(self,k,v)
            
    def copyfrom(self,keys,*others):
        if type(keys) == type('') and keys:
            keys = set([k.strip() for k in keys.split(',')])
        else:
            others = (keys,) + others
            keys = None
        for other in others:
            for k,v in other.vars().items():
                if keys is None or k in keys:
                    setattr(self,k,v)
        return self
        

    def inherit(self,keys,*others):
        if type(keys) == type('') and keys:
            keys = set([k.strip() for k in keys.split(',')])
        else:
            others = (keys,) + others
            keys = None
        for other in others:
            for k,v in other.vars().items():
                if keys is None or k in keys:
                    if not hasattr(self,k):
                        setattr(self,k,v)
        return self

    def get(self,keys):
        return _get(self.vars(),keys)
    
    def vars(self):
        return vars(self)
    
    def __getitem__(self,keys):
        return self.get(keys)

    def __add__(self,other):
        return PartSet(self,other)

    def show(self,keys=None):
        """Show variables in same form as show() function. If keys is None,
        show all with _doc first.  keys can be like in show - ie, expressions,
        scales."""
        v = self.vars()
        if keys is None:
            pairs = sorted([(k.lower(),k) for k in v.keys()])
            keys = ','.join([o for k,o in pairs])
        show(keys,data=v)

    def extract(self,keys):
        """return a part containing only the named keys.  Allow ...,new=old,...
        to rename the key from old to new."""
        pairs = []
        for k in keys.split(','):
            k = k.strip()
            if '=' in k:
                n,k = k.split('=',1)
                n = n.strip()
                k = k.strip()
            else:
                n = k
            pairs.append((n,k))
        d = {n:getattr(self,k) for n,k in pairs}
        return CMPart('A Portion of '+self._doc,**d)

    def __call__(self,keys):
        return self.extract(keys)

    def all(self):
        return CMPart(**self.vars())
    
def makePart(cls):
    """Returns an object of type Part from the class definition and class attributes
    of 'cls'.  Intended to be used as a decorator so we can use class definitions
    to build parts (syntactic sugar)."""
    dct = cls.__dict__
    vars = dict([pair for pair in dct.items() if not pair[0].startswith('__')])
    prt = Part(dct.get('__doc__',''),**vars)
    return prt

class CMPart(Part):
    
    def __enter__(self):
        """Add all attributes/values to the set of global variables.
        Save enough state so that they can be restored when the context
        manager exits."""
        if hasattr(self,'__saved__'):
            raise Exception('Object already is a context manager. Cannot be one again.')
        dct = vars(self)
        _new = []                # save a list of newly added variables
        _old = {}                # remember values of those that already exist in globals.
        f = sys._getframe(1)     # get the globals from the caller
        globs = f.f_globals
        for k,v in dct.items():
            if k.startswith('_'):
                continue
            if k in globs:
                _old[k] = globs[k]
            else:
                _new.append(k)
            globs[k] = v
        self.__saved__ = (_new,_old)
        return self
    
    def __exit__(self,*l):
        """When the context exits, restore the global values to what they
        were before entering."""
        _new,_old = self.__saved__
        f = sys._getframe(1)          # restore the global values
        globs = f.f_globals
        for k,v in _old.items():
            globs[k] = v              # restore old values
        for k in _new:
            del globs[k]              # or delete them if they were newly created
        del self.__saved__
        return False              # to re-raise exceptions
    

class PartSet(object):
    
    def __init__(self,*all):
        self.parts = []
        for p in all:
            if type(p) in [list,tuple]:
                for pp in p:
                    self.addpart(pp)
                continue
            if type(p) is self.__class__:
                for pp in p.parts:
                    self.addpart(pp)
                continue
            self.addpart(p)
            
    def addpart(self,part):
        if type(part) is Part:
            if part not in self.parts:
                self.parts.append(part)
            return
        raise TypeError('Invalid part type: "{}"'.format(part))
        
    def vars(self):
        ans = {}
        for p in self.parts:
            ans.update(p.vars())
        return ans
    
    def get(self,keys):
        return _get(self.vars(),keys)
    
    def __getitem__(self,keys):
        return self.get(keys)    
    
    def __add__(self,other):
        return self.__class__(self.parts,other)

def extract(keys,*parts):
    dct = {}
    for part in reversed(parts):  # that way, priority is left to right
        dct.update( part.vars() )
    return _get(dct,keys)

# instantiate the section tables

SST = sst.SST()
