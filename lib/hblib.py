#!/sr/bin/env python3

"""Useful library functions for varios CISC Handbook Tables."""

def UG_Angle(b):
    """Return the usual gauge for a singe line of bolts on the leg
    of an angle whose dimension is b (can be actual or nominal).
    This implements one column of the table on page 6-173 of 11th
    edition, third revised printing, of the CISC Handbook of Steel
    Construction."""
    gvs = [(44,25),
           (51,29),
           (64,35),
           (76,45),
           (89,50),
           (102,65),
           (127,75),
           (152,90),
           (178,100),
           (203,115),
           ]
    for lsize,g in gvs:
        if b <= lsize+0.5:
            return g
    raise Exception(f'Leg size of {b} exceeds last value in Usual Gauge table.')

if __name__ == '__main__':
    for b in [25.4,38.1,50.8,63.5,76.2,203,254.,300.]:
        print( 'b =',b,'   Usual gauge =', UG_Angle(b))
        
