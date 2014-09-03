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
    W_MAX=600

    # minimum number of samples required to return a variance estimate
    N_MIN = 25

    def __init__(self, m=1):
        self.win = np.empty(OfflineVarEst.W_MAX/m)*np.nan
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


