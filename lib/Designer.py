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

class CheckerError(Exception):
    pass

class CheckerWarning(Warning):
    pass

def Error(msg):
    raise CheckerError(msg)

def fmt_dict(d,varlist='',nsigfigs=4):
    """Format the values in the dictionary, d, as a 
    comma-separated list of name=val pairs.  Format floats
    to 4 sig figs.  If a comma-separated list of names
    is given in varlist, do those first in order.  Then
    format whatever is left, in whatever order they come."""
    d = d.copy()
    def _fmt_pair(k,v):
        if isfloat(v):
            v = sfrounds(v,nsigfigs)
        else:
            v = repr(v)
        return '{0}={1}'.format(k,v)
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
    
    
class Designer(object):
    
    def __init__(self,trace=False,var=None,units=None,selector=min,title='',nsigfigs=3,show_params=False):
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
            
    def require(self,val,msg='',**kwargs):
        """Raise an exception with a msg if flag is not True."""
        if msg == '':
            msg = 'Error'
        if not val:
            Error(msg+': '+fmt_dict(kwargs))
            
    def note(self,msg):
        """Record an arbitrary note."""
        self._notes.append(msg)
        if self.trace:
            print('Note:',msg)
            
    def check(self,flag,msg='',_varlist='',**kwargs):
        """Record the result of checking a requirement."""
        d = {}
        if _varlist:
            locals,globals = get_locals_globals()
            for v in re.split(r'\s*,\s*',_varlist.strip()):
                d[v] = locals[v] if v in locals else globals[v]
        d.update(kwargs)
        self._checks.append((flag,msg,_varlist,d))
        if self.trace:
            print(self.fmt_check(self._checks[-1]))
            
    def record(self,label,_varlist='',**kwargs):
        """Record a result for an analysis computation."""
        d = {}
        if _varlist:
            locals,globals = get_locals_globals()
            for v in re.split(r'\s*,\s*',_varlist.strip()):
                d[v] = locals[v] if v in locals else globals[v]
        d.update(kwargs)
        self._record.append((label,_varlist,d))
        if self.trace:
            print(self.fmt_record(self._record[-1]))

    def fmt_check(self,chk,width=None):
        """Format a check record for display."""
        flag,label,_varlist,_vars = chk
        if width is None:
            width = len(label)
        if flag:
            return "    {0:<{1}}  OK - ({2})".format(label+':',width,fmt_dict(_vars,_varlist))
        return "    {0:<{1}}  NG! - ({2}) ****".format(label+':',width,fmt_dict(_vars,_varlist))
    
    def fmt_record(self,rec,width=None,var=None,govval=None,nsigfigs=4,showvars=True):
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
            ans += '{0} = {1}'.format(var,(sfrounds(val,nsigfigs) if isfloat(val) else "{0!r}".format(val)))
            if self.units:
                ans += ' '+str(self.units)
            if govval is not None:
                if val == govval:
                    ans += '  <-- governs'
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
        hd = 'Summary of'
        if var is not None:
            hd += ' '+var+' for '
        hd += self.__class__.__name__
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
        width = max([len(l) for l,v,d in self._record])
        
        govval = None
        if var:
            govval = self.selector([d[var] for l,v,d in self._record])
        for rec in self._record:
            print(self.fmt_record(rec,var=var,width=width+1,govval=govval,nsigfigs=self.nsigfigs,showvars=False))

        if govval is not None:
            print()
            h = 'Governing Value:'
            print('   ',h)
            print('   ','-'*len(h))
            print('      ','{0} = {1}'.format(var,(sfrounds(govval,self.nsigfigs) if isfloat(govval) else "{0!r}".format(govval))), self.units if self.units is not None else '')
            
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

class Data:

    """Class Data is a convenience for maintaining separate data namespaces (records)"""
    
    def __init__(self,**keywrds):
        for k,v in keywrds.items():
            setattr(self,k,v)
            
    def __getitem__(self,s):
        """Return a tuple of all named data values. If only one, return it bare."""
        r = [getattr(self,n) for n in s.split(',')]
        if len(r) == 1:
            return r[0]
        return r
    
    def __call__(self,s):
        """Return a tuple of all named data values. If only one, return it bare."""
        return self[s]

# instantiate the section tables

SST = sst.SST()
