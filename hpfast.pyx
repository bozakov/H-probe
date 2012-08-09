# Copyright 2012 IKT Leibniz Universitaet Hannover
# GPL2
# Zdravko Bozakov (zb@ikt.uni-hannover.de)

# cython hpfast.pyx
# gcc -shared -pthread -fPIC -fwrapv -O2 -Wall -fno-strict-aliasing -I/usr/include/python2.6 -o hpfast.so hpfast.c

from __future__ import division

import numpy as np
cimport numpy as np

ones = np.ones
zeros = np.zeros
concatenate = np.concatenate
nonzero = np.nonzero
arange = np.arange

DTYPE = np.uint8
ctypedef np.uint8_t DTYPE_t


cdef inline int int_max(int a, int b): return a if a >= b else b
cdef inline int int_min(int a, int b): return a if a <= b else b

def min(int a, int b): 
    return a if a <= b else b

def max(int a, int b): 
    return a if a <= b else b


print 'loading cython modules ...'

class fixed_buf(object):
        def __init__(self, len):
            self.buf = ones((len+1,3), dtype='float')*-1.0
            self.left = 0
            self.right = 0
            self.done = False
        def append(self,x):
            self.buf[self.right] = x
            self.right += 1
        def popleft(self):
            if not self.left==self.right:
                self.left += 1    
                return self.buf[self.left-1]
            else:
                raise IndexError

########################################################################
# parser_av.py

cimport cython
@cython.boundscheck(False) # turn off bounds-checking for entire function
def av_append_f(self, int probe, int zcount=0):
        ''' Append the latest received probe to a sliding
        window. Update the aggregate variances for each variance
        block '''
        cdef np.ndarray[DTYPE_t, ndim=1] win = self.win.astype(DTYPE)
        cdef int probe_count = <int>self.probe_count
        cdef int slot_count = <int>self.slot_count

        cdef int m
        cdef int i

        probe_count += probe     
        for i in xrange(zcount+1):
            win = np.append(win[1:], np.uint8(probe if i==zcount else 0))
            slot_count += 1

            for m,var in self.avars.iteritems():
                if not slot_count % m:
                    var.step(np.mean(win[-m:])) 

        self.win = win.astype(bool)
        self.slot_count = slot_count
        self.probe_count = probe_count



def get_avars_corrected_f(self):
    cdef float var_w = <float>self.avars[1].var()
    cdef float var_a = <float>self.var_a
    cdef float mean_a = <float>self.mean_a

    vw = self.get_avars()

    cdef float mean_y_hat = self.mean()/self.mean_a
    cdef float var_y_hat = (var_w - mean_y_hat**2*self.var_a)/(var_a + mean_a**2)

    return (vw - mean_y_hat**2*self.va - var_a*var_y_hat/self.M)/mean_a**2



########################################################################
# parser_xcov.py
def xc_append_f(self, int x, int zcount = 0):

        self.slot_count  += zcount+1                    # keep track of total number or counted slots (should be all)
        self.probe_count += x                           # increment counter for each was received probe (zero or one)

        zcount = int_min(self.L-1, zcount)

        # shift window to the left (concatenate is faster than roll for shifting)
        self.win = concatenate( (self.win[zcount+1:], zeros(zcount, dtype=bool), [bool(x)]) )           


        # increment autocovariance (just for non-zero values of win and only if x=1)
        if x==1:
            self.xc[nonzero(self.win)] += x



def xcov_f(self):
    # flip array so that lag zero is on the left hand side
    xc = self.xc[::-1]
    return (xc*1.0/(self.slot_count - arange(self.L, dtype=int)) - self.mean()**2)[1:] 




DFLOAT = np.float
ctypedef np.float_t DFLOAT_t

def xcov2_f(self):
    cdef float m2 = self.mean()**2
    cdef np.ndarray[DFLOAT_t, ndim=1] xcov = -arange(self.L, dtype=DFLOAT)
    cdef np.ndarray[DFLOAT_t, ndim=1] xc = self.xc[::-1].astype(DFLOAT)

    xcov += <int>self.slot_count  
    xcov = xc/xcov - m2 
    return xcov[1:]


def getdata_str_f(self):

    y = self.xcov()[1:]
    if any(y):
        return '\n'.join([str(a) for a in y])
    else:
        return None
