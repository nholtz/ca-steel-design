#!/usr/bin/env python

import Designer
_get = Designer._get


class Part(object):
    
    def __init__(self,_doc='',**keywd):
        self._doc = _doc
        self.set(**keywd)
            
    def set(self,**keywd):
        for k,v in keywd.items():
            setattr(self,k,v)
            
    def setfrom(self,keys,*others):
        keys = set([k.strip() for k in keys.split(',')])
        for other in others:
            for k,v in other.vars().items():
                if k in keys:
                    setattr(self,k,v)

    def inherit(self,keys,*others):
        if type(keys) == type(''):
            keys = set([k.strip() for k in keys.split(',')])
        else:
            others = (keys,) + others
            keys = None
        for other in others:
            for k,v in other.vars().items():
                if not hasattr(self,k):
                    if keys is None or k in keys:
                        setattr(self,k,v)

    def get(self,keys):
        return _get(self.vars(),keys)
    
    def vars(self):
        return vars(self)
    
    def __getitem__(self,keys):
        return self.get(keys)
    
    def __add__(self,other):
        return PartSet(self,other)

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
