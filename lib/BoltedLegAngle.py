
# coding: utf-8

# ### Tr for Single Angle Bolted Through One Leg
# 
# Calculate $T_r$ for a single angle bolted through one leg.
# 
# ![Angle bolted through one leg](bolted-single-angle.svg)

# In[1]:

from Designer import Designer, Param, table_search


# In[2]:

Table6 = [(16,(28,22)),    # CSA S16-09 Table 6  - Minimum edge distances
          (20,(34,26)),
          (22,(38,28)),
          (24,(42,30)),
          (27,(48,34)),
          (30,(52,38)),
          (36,(64,46))]

#       (d, (dmax,g))
UG1 = [(45,(16,23)),    # Usual Gauges, Angle, 1 line, Handbook p. 6-168
       (50,(16,28)),
       (55,(22,27)),
       (60,(24,35)),
       (65,(24,35)),
       (75,(24,45)),
       (80,(24,50)),
       (90,(24,60)),
       (100,(27,65)),
       (125,(30,80)),
       (150,(36,90)),
       (200,(36,115)),
       ]

UG2 = [(125,(20,45,54)), # Usual Gauges, Angle, 2 lines, Handbook p. 6-168
       (150,(24,55,65)),
       (200,(30,80,80)),
       ]

class BoltedLegAngle(Designer):
    
    BOLT_SIZES = ['M16','M20','M22','M24','M27','M30','M36']
    BOLT_TYPES = {'A325M':830.,'A490M':1040.}
    
    Fy = Param((300.,450.),value=345.)
    Fu = Param((450.,500.),value=450.)
    Fub = Param(BOLT_TYPES,description='bolt type')
    total_length = Param((0.,10000.,5.),value=0.)  # if 0, KL/r not checked
    AngleDsg = Param('L102x76x13')
    bolt_size = Param(BOLT_SIZES,value='M20')
    hole_type = Param(['punched','drilled'],value='punched')
    pitch = Param((0.,75,1.),value=0)           # if 0, will use minimum
    end_distance = Param((0.,50,.5),value=0)    # if 0, will use minimum
    threads_intercepted = Param(True)
    shear_type = Param(['single','double'],value='single')
    bolted_leg = Param(['long','short'],value='long')
    Nlines = Param((1,2),value=1)
    Nrows = Param((2,10),value=2)
    

    def compute(self,Fy,Fu,Fub,total_length,AngleDsg,bolt_size,hole_type,pitch,end_distance,
                threads_intercepted,shear_type,bolted_leg,Nlines,Nrows):

        # In[3]:

        REQ = self.require   # useful abbreviations
        CHK = self.check       
        REC = self.record


        # ### Sanity check of input data:

        # In[4]:

        REQ(bolt_size in self.BOLT_SIZES,'bolt size is not one of available sizes',
            bolt_size=bolt_size, BOLT_SIZES=self.BOLT_SIZES)
        REQ(hole_type in ['punched','drilled'])
        REQ(threads_intercepted in [False,True])
        REQ(shear_type in ['single','double'])
        REQ(bolted_leg in ['short','long'])
        REQ(Nlines in [1,2])
        REQ(Nrows >= 2 and Nrows <= 10)


        # In[5]:

        # data derived from input data:  pitch, end_distance, gauges, etc.

        Ag,d,b,t,rmin = self.SST.section(AngleDsg,properties='A,D,B,T,Ryp')
        if bolted_leg == 'short':  # bolts go thru leg of size 'd'
            d,b = b,d

        bolt_diameter = float(bolt_size[1:])
        if pitch in [0,None]:
            pitch = 2.7*bolt_diameter

        min_end_distance,min_edge_distance = table_search(bolt_diameter,Table6)
        if Nrows <= 2:
            min_end_distance = 1.5*bolt_diameter  # CSA S16-01 22.3.4
        if end_distance in [0,None]:
            end_distance = min_end_distance

        if Nlines == 1:
            g2 = 0
            dmax,g1 = table_search(d-2,UG1)
        elif Nlines == 2:
            dmax,g1,g2 = table_search(d-2,UG2)
        edge_distance = d-(g1+g2)


        # ### Check Bolting Details
        # Failure to meet requirements is not a fatal error. Results are reported in the work record.

        # In[6]:

        # CSA S16-09  22.3.1 thru .4:
        max_edge_distance = min(12.*t,150.)
        REQ(edge_distance > bolt_diameter/2.,'Angle leg of {0} mm does not support {1} lines of bolts.'.format(d,Nlines))

        CHK(pitch >= 2.7*bolt_diameter,'Pitch','pitch',min_pitch=2.7*bolt_diameter)
        CHK(edge_distance >= min_edge_distance,'Edge distance','edge_distance,min_edge_distance')
        CHK(edge_distance <= max_edge_distance,'Edge distance','edge_distance,max_edge_distance')
        CHK(end_distance >= min_end_distance,'End distance','end_distance,min_end_distance')

        if total_length > 0.:
            lcc = total_length - 2.*(end_distance + (Nrows-1.)*pitch/2.)
            REQ(lcc>0.,"Total Length too short")
            # CSA S16-09 10.4.2.2
            CHK(1.0*lcc/rmin<=300.,"Slenderness Ratio","rmin",net_length=lcc)

        # CSA S16-09  28.4.1:
        hole_allowance = hole_diameter = bolt_diameter + 2.
        if hole_type == 'punched':
            CHK(t < bolt_diameter+4,'Punched holes','bolt_diameter,t',max_t=bolt_diameter+4)

        # CSA S16-09  12.3.2:
        if hole_type == 'punched':
            hole_allowance += 2.


        # ### Strength Calculations

        # In[7]:

        # CSA S16-09  13.1
        phi = 0.90
        phiu = 0.75
        phib = 0.80 
        phibr = 0.80


        # #### Gross section yield:

        # In[8]:

        # CSA S16-09   13.2 (a) (i):
        REC('Gross area yield','Ag',Tr=phi*Ag*Fy/1000.)


        # #### Net section fracture:

        # In[9]:

        # CSA S16-09   13.2 (a) (iii):
        An = Ag - Nlines*hole_allowance*t
        # CSA S16-09   12.3.3.2 (b)
        if Nrows >= 4:
            Ane = 0.80*An
        else:
            Ane = 0.60*An
        REC('Net area fracture','An,Ane',Tr=phiu*Ane*Fu/1000.)


        # #### Block shear failure:
        # ![Block Shear Patterns](bolted-single-angle-shear-blocks.svg)

        # In[10]:

        #  CSA S16-09    13.11
        e = end_distance
        L = (Nrows-1.)*pitch

        # Case 1 - one shear area, tension failure from furthest bolt to edge
        An = (d - g1 - (Nlines-0.5)*hole_allowance)*t
        Agv = (e+L)*t
        Ut = 0.6
        Fv = (Fy+Fu)/2.
        if Fy > 485:     # CSA S16-09   13.11  (foot note)
            Fv = Fy
        REC('Block shear (case 1)','An,Agv,Ut',Tr=phiu*(Ut*An*Fu + 0.6*Agv*Fv)/1000.)


        # In[11]:

        # Case 2 - for 2 or more lines of bolts
        if Nlines > 1:
            An = (g2 - hole_allowance)*t
            Agv = 2.*(e+L)*t
            Ut = 0.6
            REC('Block shear (case 2)','An,Agv,Ut',Tr=phiu*(Ut*An*Fu + 0.6*Agv*Fv)/1000.)


        # In[12]:

        # Case 3 - tearout
        An = 0.
        Agv = 2.*(e+L)*t*Nlines
        Ut = 0.
        REC('Block shear (tearout)','An,Agv,Ut',Tr=phiu*(Ut*An*Fu + 0.6*Agv*Fv)/1000.)


        # #### Fastener strength, bearing-type connection: bolts in shear

        # In[13]:

        m = 1
        if shear_type == 'double':
            m = 2
        n = Nrows*Nlines
        db = bolt_diameter
        L = (Nrows-1.)*pitch   # length of connection

        # CSA S16-09   13.12.1.2 (c)
        multiplier = 1.0
        if L >= 15.*db:
            multiplier = max(0.75,1.075 - 0.005*L/db)
        if threads_intercepted:
            multiplier *= 0.70
        Vr = multiplier*0.6*phib*n*m*(3.1415926*db*db/4.)*Fub/1000.
        REC('Bolt Shear',multiplier=multiplier,n=n,Tr=Vr,L=L)


        # #### Bolts in bearing:

        # In[14]:

        # CSA S16-09    13.12.1.2:
        Br = 3.*phibr*n*t*db*Fu/1000.
        REC('Bolt Bearing',n=n,d=db,t=t,Tr=Br)


        # #### Combined tearout and bearing:

        # In[19]:

        # combine tearout of bolts closest to end with bearing of remainder
        e = end_distance
        Agv = 2.*e*t*Nlines
        n = Nlines*(Nrows-1)
        Tr = phiu*(0.6*Agv*Fv)/1000.
        Br = 3.*phibr*n*t*db*Fu/1000.
        REC('Bolt bearing + end tearout',n=n,t=t,d=db,Agv=Agv,Tr=Tr+Br)


        # ### Summary:

        # In[20]:

        self.show('Fy,Fu,AngleDsg,Ag,d,b,t,rmin,Fub,bolt_size,bolt_diameter,hole_type',
                 'pitch,end_distance,threads_intercepted,shear_type,bolted_leg,Nlines,Nrows',
                 'end_distance,edge_distance,g1,g2')
        self.summary()          


        # In[16]:

if __name__ == '__main__':

    des = BoltedLegAngle(var='Tr',units='kN',trace=True)
    des.run()
