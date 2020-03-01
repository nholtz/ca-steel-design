from .Designer2 import DesignNotes

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
    
    
################################################################
#### Designer
################################################################

class Designer(DesignNotes):

    """This class needs to be updated.  The intent is to allow definitions of
    widgets in class variables sort of like Django."""
            
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
