from __future__ import print_function
import numpy as np
import pandas as pd
import re
import os.path
import inspect
import sys
PYVER = sys.version_info.major

__DIR__ = os.path.dirname(__file__) or '.'


##pd.options.display.max_colwidth = 0

# Read csv data either from a local file or from the network
def xx_sst_read_csv(basename):
    use_local_files = True
    filename = '%s.csv' % (basename,)
    if use_local_files:
        url = __DIR__ + '/sst-data/' + filename
    else:
        url = 'http://holtz2.cee.carleton.ca/notebooks/cive4500/2014/lectures/22/sst/%s' % (filename,)
    return pd.read_csv(url,skipinitialspace=True)

def _sst_read_pickle(basename):
    pathname = '{}/sst-data/sst-{}-{}.p'.format(__DIR__,basename,PYVER)
    t = pd.read_pickle(pathname)
    return t

class Properties(object):

    def __init__(self,series_or_dict={}):
        d = series_or_dict if issubclass(type(series_or_dict),dict) else series_or_dict.to_dict()
        for k,v in d.items():
            setattr(self,k,v)

    def props(self,properties=''):
        props = [x.strip() for x in properties.split(',')]
        return [getattr(self,x) for x in props if x]

    def __getitem__(self,key):
        return getattr(self,key)

    def __setitem__(self,key,value):
        setattr(self,key,value)

class SST(object):

    def __init__(self):

        self.props = _sst_read_pickle('props')
        self.shapes = _sst_read_pickle('shapes')
        self.all = _sst_read_pickle('all')

        self.sections_by_shp = {}

    def shps(self):
        """Return a list of 3-tuples: (shape code,dsg prefix,description)
        for all shape types."""
        return [(row.Shp,row.Dsg,row.Desc) for i,row in self.shapes.iterrows()]

    def pfx2shp(self,slist):
        """Convert a list of shape codes and prefixes into a list of shape codes.
        One prefix may have 3 shape codes (eg, '2L') - return them all."""
        ans = []
        shps = self.shps()
        for shp in slist:
            if type(shp) in [type(0),type(0)]:
                ans.append(shp)
                continue
            ans.extend([x for x,d,c in shps if d == shp])
        return list(set(ans))   # uniquify them

    def section_table(self,shp):
        """Return the section table for shapes of type shp.  shp may
        be a number or a designation prefix.  If its a prefix, and more than
        one table exists for that prefix (eg '2L'), the first one (with
        the smallest Shp code) is returned."""
        if type(shp) != type(0):
            for s,dsg,desc in self.shps():
                if dsg == shp:
                    shp = s
                    break
        if shp not in self.sections_by_shp:
            cols = self.shapes.loc[shp].Propsl
            self.sections_by_shp[shp] = (self.all.loc[self.all['Shp']==shp])[cols]
        return self.sections_by_shp[shp]

    def section_tables(self,shplist,sort_column=None,ascending=True):
        """Return a concatenation of all section tables for the shape codes
        given by shplist (each of which may be an integer or a desgination 
        prefix).  If sort_column is not None, it is the name of a column
        whose values are used to order the rows.  ascending specifies if
        sort is ascending or not."""
        slist = self.pfx2shp(shplist)
        tables = [self.section_table(shp) for shp in slist]
        if len(tables) == 1:
            table = tables[0]
        else:
            table = pd.concat(tables)
        if sort_column:
            table = table.sort_values(sort_column,ascending=ascending)
        return table

    def sections(self,dsg,shp=None):
        """Return list of all section properties records for the section specified
        by designation, 'dsg'.  Search the section tables specified by 'shp'.
        If 'shp' is not given, extract the prefix from the designation and
        use that.  'shp' may be a single or a list of integers and/or
        designation prefixes (eg '2L' or 'W')."""
        if shp is None:
            mo = re.match(r'(\d*[A-Za-z]+)',dsg)
            if not mo:
                raise Exception('Invalid designation: '+dsg)
            shps = [mo.group(1)]
        elif type(shp) in [type(()),type([])]:
            shps = shp
        else:
            shps = [shp]
        shps = self.pfx2shp(shps)
        ans = []
        for shp in shps:
            t = self.section_table(shp)
            try:
                ans.append(t.loc[str(dsg)])
            except KeyError:
                pass
        return ans

    def section(self,dsg,properties=None,shp=None):
        """Return the properties for the single shape whose designation is
        given by 'dsg'.  'shp' can be used to specify the section tables
        to search, otherwise the prefix of the designation is used for that.
        In cases where there is more than one section with the same
        designation (eg '2L203x152x25'), 'shp' *must* be used to 
        disambiguate.  'shp' may be a single or a list of integers and/or
        designation prefixes (eg 12 or 'W'), but would normally be
        a singleton."""
        sections = self.sections(dsg,shp=shp)
        if len(sections) == 1:
            sect = sections[0]
            if properties:
                if type(properties) == type(''):
                    properties = [p.strip() for p in properties.split(',')]
                ans = [sect[p] for p in properties]
                return ans[0] if len(properties) == 1 else ans
            return Properties(sect)
        if len(sections) == 0:
            raise KeyError('No section with designation: ' + dsg)
        raise KeyError('More than one section with designation: ' + dsg)

    def setprops(self,dsg,properties,shp=None):
        """Find the properties for the single shape whose designation is
        given by 'dsg' and set the designated properties as global
        variables. 'shp' can be used to specify the section tables
        to search, otherwise the prefix of the designation is used for that.
        In cases where there is more than one section with the same
        designation (eg '2L203x152x25'), 'shp' *must* be used to 
        disambiguate.  'shp' may be a single or a list of integers and/or
        designation prefixes (eg 12 or 'W'), but would normally be
        a singleton.  EG:

        setprops('W150x22','Dsg,A,Zx')
        Mp = Fy*Zx   """

        sections = self.sections(dsg,shp=shp)
        if len(sections) == 1:
            sect = sections[0]
            if type(properties) == type(''):
                properties = [p.strip() for p in properties.split(',')]
            gv = get_ipython().user_global_ns
            for p in properties:
                gv[p] = sect[p]
            ans = [sect[p] for p in properties]
            return ans[0] if len(properties) == 1 else ans
        if len(sections) == 0:
            raise KeyError('No section with designation: ' + dsg)
        raise KeyError('More than one section with designation: ' + dsg)

    def show(self,section,math='latex'):
        """Augment the property record with common scale factors and units.  In other
        words, prepare the data for display in a form that closesly matches that in
        the CISC section tables in Part 6 of the handbook.  'section' is a 
        property record (i.e., fo rone section and is typically one row from
        the section table.  'math' specififies how to display the multiplier
        and units: =None means no additional formatting of the text; ='latex'
        means to insert latex math markup for display in notebook using mathjax;
        ='html' means use html markup."""

        def _2None(s,mult=False):
            return s

        def _2latex(s,mult=False):
            if not s:
                return s
            s = str(s)
            if mult:
                s = r'\times '+s
            return '$'+s+'$'

        def _2html(s,mult=False):
            s = str(s)
            parts = s.split('^',1)
            if len(parts) == 2:
                s = parts[0] + '<sup>' + parts[1] + '</sup>'
            if mult:
                s = '&times; ' + s
            return '<i>' + s + '</i>'

        if math is None:
            xlate = _2None
        elif math in ['latex','mathjax']:
            xlate = _2latex
        elif math == 'html':
            xlate = _2html
        else:
            raise AssertionError('Invalid value for math: '+math)

        if isinstance(section,pd.Series):
            d = section.to_dict()
        else:
            d = vars(section)
        df = pd.DataFrame.from_dict(d,orient='index')
        props = self.props.loc[d.keys()]
        df['Expo'] = props['Expo']
        df['Units'] = props['Unit']
        df['Property Description'] = props['Desc']
        df.fillna(value='',inplace=True)

        for ix,row in df.iterrows():
            if row.Expo:
                if row.Expo.startswith('10^'):
                    iexp = int(row.Expo[3:])
                    row.iloc[0] /= 10.**iexp
                row.Expo = xlate(row.Expo,mult=True)
            if row.Units:
                row.Units = xlate(row.Units)
        return df

    def select(self,table,func,maxn=None,**kwargs):
        """Select a subset of the rows in the section table, as specified by
        callable 'func'. For each row, 'func()' is called, with positional arguments
        taken from the properties of the same names, and default arguments
        passed as is (unless overridden on the call to .select()).  For example,
           def fn(A,Zx,Fy=350.,Mf=0.):
               ...
        'fn()' will be called with 'A' and 'Zx' getting values from the shape
        properties, and 'Fy' and 'Mf' getting the values  shown there, unless
        overridden.
        If 'func' returns any value that can be interpreted as 'True', the row 
        will be included in the result set.  In addition, if the value 'func' 
        returned was a dictionary for every selected row, that 
        dictionary will be used to provided extra column values to be appended to the 
        columns of the  returned table.  'maxn' specifies the maximum number of rows to be
        returned; 0 or None means no limit.  'table' may be an already 
        prepared section table, or it may be a single or a list of shape codes
        and or designation prefixes.  Extra keyword arguments override the values
        specified for default values on the function definition.
        """

        fargs,fvarargs,fkeywords,fdefaults = inspect.getargspec(func)
        if fvarargs:
            raise Exception('Select function may not have an extra positionals argument: *{0}'.format(fvarargs))
        if fkeywords:
            raise Exception('Select function may not have an extra keywords argument: **{0}'.format(fkeywords))

        fdefargs = []
        fallargs = fargs
        if fdefaults:
            fdefargs = fargs[-len(fdefaults):]
            fargs = fargs[:-len(fdefaults)]
        for k in kwargs.keys():
            if k not in fallargs:
                raise Exception('Invalid keyword argument: '+repr(k))

        def _func(row,__func=func,__fargs=fargs,__kwargs=kwargs):
            args = {k:row[k] for k in __fargs}  # every non-optional arg must be in the row record
            args.update(__kwargs)                 # kwargs may override anything
            return __func(**args)

        return self.select_rows(table,_func,maxn=maxn)

    def select_rows(self,table,func,maxn=None,**kwargs):
        """Select a subset of the rows in the section table, as specified by
        callable 'func'. For each row, 'func()' is called with the row passed
        as the first argument and default arguments
        passed as is (unless overridden on the call to .select()).  For example,
           def fn(shape,Fy=350.,Mf=0.):
               ...
        'fn()' will be called with 'shape' getting the row property record, 
        and 'Fy' and 'Mf' getting the values  shown there, unless overridden.
        If 'func' returns any value that can be interpreted as 'True', the row 
        will be included in the result set.  In addition, if the value 'func' 
        returned was a dictionary for every selected row, that 
        dictionary will be used to provided extra column values to be appended to the 
        columns of the  returned table.  'maxn' specifies the maximum number of rows to be
        returned; 0 or None means no limit.  'table' may be an already 
        prepared section table, or it may be a single or a list of shape codes
        and or designation prefixes.  Extra keyword arguments override the values
        specified for default values on the function definition.
        """
        if type(table) in [type(0),type(""),type(()),type([])]:
            table = self.section_tables(table)
        ixlist = []
        vlist = []
        newcols = True

        for ix,row in table.iterrows():
            v = func(Properties(row),**kwargs)
            if v:
                ixlist.append(ix)
                vlist.append(v)
                if not(isinstance(v,dict)):
                    newcols = False
                if maxn and len(ixlist) >= maxn:
                    break

        ans = table.loc[ixlist]
        if newcols:
            cols = pd.DataFrame.from_records(vlist,index=ixlist)
            ans = ans.merge(cols,left_index=True,right_index=True)
        return ans

if __name__ == '__main__':

    #pd.options.display.max_colwidth = 20

    sst = SST()
    if 0:
        print(sst.props)
        print(sst.shapes)
        print(sst.shps())
        t = sst.section_table(17)
        print(t)

    print(sst.section('W360x196'))

    print(sst.sections('2L203x152x25'))

    try:
        print(sst.section('2L203x152x25'))
    except Exception as e:
        print("\n***** Error:", e)

    if 1:
        w =  sst.section('W360x196')
        s = sst.show(w)
        print(s)

        print(sst.show(w,'latex'))
        print(sst.show(w,'html'))

    if 1:
        tl = sst.section_tables(['2L'])
        print(tl)
        print(tl.loc['2L203x152x25'])
        print(tl.loc['2L152x152x25'])

    if 1:
        wl = sst.section_tables(['W','WWF'],'Mass')

        def myfunc0(shape,Fy=300.,M=0.):
            My = Fy * shape.Sx / 1E6
            if My >= M:
                return dict(My=My)
    
        s = sst.select_rows(wl,myfunc0,maxn=5,Fy=350.,M=500.)
        print(s[['Mass','Sx','My']])

        def myfunc(Zx,Fy=350.,Mf=0):
            Mp = Fy * Zx / 1E6
            if Mp >= Mf:
                return dict(Mp=Mp,Foo=13,Fy=Fy,Mf=Mf)
            return False

        s = sst.select(wl,myfunc,maxn=10)
        print(s[['Mass','Avl','Use','Zx','Mp','Foo','Fy','Mf']])

        s = sst.select(wl,myfunc,Fy=400.,Mf=100.,maxn=10)
        print(s[['Mass','Avl','Use','Zx','Mp','Foo','Fy','Mf']].sort_values('Mp',ascending=False))
