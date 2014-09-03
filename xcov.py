try:
    from numpy import *
    import types                          # for cython binding
except ImportError:
    print __name__ + ": please make sure the following packages are installed:"
    print "\tpython-numpy"
    exit(1)

class XCovEst(object):

    def __init__(self, max_lag):
        self.L = max_lag    # max covariance lag
        self._xc = zeros(self.L, dtype=int)
        self.win = zeros(self.L, dtype=bool)
        self.probe_count = 0
        self.slot_count = 0


    def append(self, x, zero_count = 0):
        """Appends the last received probe to the sliding window win
            containing the last L values (lags) and adds the contents of win
            to the biased covariance vector xc.

        Args:

            x: Contains the probe value which must be 0 or 1
            zero_count: Specifies the number of empty time slots to
            append before the current probe.
            
        """

        self.slot_count  += zero_count+1                # keep track of total number or counted slots (should be all)
        self.probe_count += x                           # increment counter for each was received probe (zero or one)

        zero_count = min(self.L-1, zero_count)
        #if zero_count<0: return                        # ERROR: negative slot increment - should not happen!

        # shift window to the left (concatenate is faster than roll for shifting)
        self.win = concatenate( (self.win[zero_count+1:], zeros(zero_count, dtype=bool), [bool(x)]) )           

        # increment autocovariance (just for non-zero values of win and only if x=1)
        if x==1:
            self._xc[nonzero(self.win)] += x


    def test(self, data=None):
        """Just a simple test for the autocovariance."""
        if data==None:
            data = [1,1,0,1,1,1,1,0,0,1,1,0,0,0,0,0,0,1,0,0,1,0,0,1,0,1]

        for x in data:
            self.append(x)
        print self.mean, mean(data)
        print self.xcov


    @property
    def xc(self):
        """Returns the unscaled autocorrelation."""
        # flip array so that lag zero is on the left hand side
        return self._xc[::-1]

    @property
    def mean(self):
        """Returns the mean of the observation vector."""
        try:
            return self.probe_count*1.0/self.slot_count
        except ZeroDivisionError:
            return nan


    def var(self, mean_w=0.0):
        """Returns the variance of the observation process."""
        if not mean_w:
            mean_w = self.mean

        # the covariance at lag 0 is the variance of the
        # observation process
        try:
            return self._xc[-1]*1.0/self.slot_count - mean_w**2
        except:
            return nan

    @property
    def xcov(self):
        """Calculates the autocovariance estimate from the sliding window sums
        xc. Returns lags 0 to L."""
        N_unbiased = self.slot_count - arange(self.L, dtype=float)
        N_unbiased[N_unbiased<1] = nan
        return self.xc*1.0/N_unbiased - self.mean**2


    def values(self):
    	"""Returns the vector containing the estimated autocovariance self.xcov."""
    	return self.xcov[1:]


    def __repr__(self):
        s = ', '.join(['%.6f' % i for i in self.xcov])
        return 'covariance:\t[' + s + ']'


    def __str__(self):
        """Returns a string of covariance values which can be piped
        into gnuplot."""
        y = self.xcov[1:]

        if any(y):
            return '\n'.join([str(a) for a in y])
        else:
            return None

class AggVarEst(XCovEst):

    def __init__(self, max_lag):
        XCovEst.__init__(self, max_lag)


    def _aggvar_coeff(self, L):
        try:
            av_coeff = diag(ones(L))
        except MemoryError:
            ERROR('L is too large for aggregated variance estimator (L=%d)' % L)
            raise SystemExit(-1)
        for i in xrange(L):
            av_coeff[i,:i+1]=arange(i+1,0,-1)
        av_coeff *= 2
        av_coeff[:,0] /=2
        return av_coeff


    def values(self):
    	"""Returns the vector containing the estimated autocovariance self.aggvar."""
    	return self.aggvar


    @property
    def aggvar(self):
        """Calculate aggregated variance from autocovariance."""
        av = empty(self.L)
        xc = self.xcov

        for m in xrange(1,self.L+1):
            av[m-1]=dot(arange(2*m,0,-2),xc[:m])-xc[0]*m
        return av/arange(1,self.L+1)**2        


    @property
    def aggvar_slow(self):
        """Calculate aggregated variance from autocovariance. Iterative approach."""
        xc = self.xcov
        av = empty(self.L)
        av[0] = nan 
        for m in xrange(1,self.L):
            t = arange(1,m)
            av[m] = xc[0]/m + sum((m-t)*xc[t])*2/m**2

        return av


    @property
    def aggvar_mat(self):
        """Calculate aggregated variance from autocovariance. Matrix approach."""
        try:
            av = dot(self.av_coeff,self.xcov)/arange(1,self.L+1)**2
        except AttributeError:
            print "generating coefficients for aggregated variance estimate..."
            self.av_coeff = self._aggvar_coeff(self.L)
            print 'done.'
            av = dot(self.av_coeff,self.xcov)/arange(1,self.L+1)**2
        return av

    def __repr__(self):
        s = ', '.join(['%.6f' % i for i in self.aggvar])
        return 'aggvar:\t[' + s + ']'


    def __str__(self):
        """Returns a string of aggregated variance values which can be piped
        into gnuplot."""
        y = self.aggvar[1:]
        if any(y):
            return '\n'.join([str(a) for a in y])
        else:
            return None        


if __name__=='__main__':
	import numpy as np
	import code
	import matplotlib.pyplot as plt
	from numpy.random import binomial

	data = np.loadtxt('ffgn_0.8.dat')
	data = (data-mean(data))>0

	L=1000
	xc = XCovEst(L)
	av = AggVarEst(L)

	X = data[:100000]
	for x in X:
		xc.append(x)
		av.append(x)

	
	plt.ion()
	plt.loglog(arange(1,L), xc.values())	
	plt.loglog(arange(1,L+1), av.values())

	av_w = AggVarEst(L)
	A = binomial(1,0.1,len(X))
	for w in A*X:
		av_w.append(w)

	plt.loglog(arange(1,L+1), av_w.values())


	code.interact(local=locals())
