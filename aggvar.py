from __future__ import division
import numpy as np


class VarEst(object):
    """An online variance estimator. The object is fed new samples
    using the append() method and calulates the variance on the fly.
    """

    N_MIN = 25                 # minimum number of samples required to
                               # return a variance estimate

    def __init__(self, m=1):
        # aggregation level in seconds: only used for printing
        self.M = m
        self.n = np.int(0)
        self.mean = np.float(0.0)
        self.M2 = np.float(0.0)

    def append(self, x):
        """Receive a single sample and update the variance."""
        self.n += 1
        delta = x - self.mean
        self.mean += delta/self.n
        self.M2 += delta*(x - self.mean)

    @property
    def sigma(self):
        """Returns the variance estimate for the current aggregation
        level. Returns NaN if less than N_MIN samples were available
        for calculating the variance
        """
        if self.n<self.N_MIN:
            return np.nan
        else:
            return self.M2/(self.n - 1)

    def var(self):
        """Returns the variance estimate sigma."""
        return self.sigma


    def freeze(self):
        self.M2 = self.M2/self.n
        self.n = 1

    def __str__(self):
        return '%d\t%.6f\t%d\t%.6f\n' % (self.M, self.var(), self.n, self.mean)

    def __repr__(self):
        return 'M%d, samples: %d, var: %.6f' % (self.M, self.n, self.var())





class OfflineVarEst(object):
    """An offline variance estimator. The object is fed new samples
    using the append() method and calulates the variance on the fly.
    """
    # maximum window size/number of past samples to use for calculation (in seconds)
    M_MAX=600

    # minimum number of samples required to return a variance estimate
    N_MIN = 25

    def __init__(self, m=1):
        self.win = np.empty(OfflineVarEst.M_MAX/m)*np.nan
        self.M = m             # aggregation level
        self.n = 0

    def append(self, x):
        self.win = np.append(self.win[1:],x)
        self.n = min(self.n+1, len(self.win))

    def var(self):
        if self.n<self.N_MIN:
            return np.nan
        else:
            return np.var(self.win[~np.isnan(self.win)], ddof=1)

    def __str__(self):
        return '%f\t%.6f\t%d\t%.6f\n' % (self.M, self.var(), self.n, np.mean(self.win[~np.isnan(self.win)]))



class AggVarEst(dict):
    """ sample aggregation window. aggregated variance window of size M_MAX """
    def __init__(self, M_MIN=1, M_MAX=100):
        # min/max aggregation levels in slots
    	dict.__init__(self)

    	M = np.arange(M_MIN, M_MAX+1) # TODO linspace
    	for m in M:
            self[m] = VarEst(m)
        self.probe_count = 0
        self.slot_count = 0

        # sliding window to store arriving values
        self.win = np.zeros(np.max(M)).astype(bool)


    def append_fast(self, probe, zero_count=0):
        """Append the latest received probe (0 or 1) to a sliding
        window. Update the aggregate variances for each variance
        block."""
        self.probe_count += probe

        z = [False]*zero_count
        z.append(bool(probe))

        for x in z:
            # speed: np.r_ < np.roll < np.concatenate < np.append 
            self.win = np.append(self.win[1:], x) # append to the right hand side
            self.slot_count += 1

            [self[m].append(np.mean(self.win[-m:])) for m in self.iterkeys() if self.slot_count%m==0]


    def __repr__(self):
        return 'AggVarEst object <%s>' % str([av.sigma for m,av in self.iteritems()])

    def __str__(self):
        s = ''
        for m in self.keys():
            if np.isnan(self[m].sigma):
                continue
            s += str(self[m])
        return s

    def vars(self):
        return [av.sigma for av in self.itervalues()]

    def mean(self):
    	print 'TODO'
        #return self[self.keys()[0]].mean

    def _fit(self):
        """Performs a linear fit on the aggregated variance estimates"""
        M = self.keys()
        logy = np.log10([self[m].sigma for m in M])
        logx = np.log10(M)

        try:
            (d,y0) = np.polyfit(logx[~np.isnan(logy)], logy[~np.isnan(logy)],1)
            return (d,10**y0)
        except Exception as e:
            return (-1, -1)

    @property
    def H(self):
        return (self._fit()[0]+2)/2

    def hurst(self):
        return self.H

    def save(self, fname):
        s = str(self)

        try:
            f = open(fname, mode='w')
        except IOError as e:
            print(e)
            return
        if s: f.write(s)
        f.close()


def test():
#from aggvar import AggVarEst
	av = AggVarEst()
	data = [1,1,0,1,1,1,1,0,0,1,1,0,0,0,0,0,0,1,0,0,1,0,0,1,0,1]

	for x in data+data+data:
		av.append_fast(x)
