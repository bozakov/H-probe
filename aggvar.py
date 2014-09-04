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
    def __init__(self, samp_rate=1.0, M_MIN=1, M_MAX=100):
        # min/max aggregation levels in slots
    	dict.__init__(self)

        M = 10**np.linspace(np.log10(M_MIN),np.log10(M_MAX),250) # 250 points
        self.M = np.unique(np.append(1, M).astype(int)) # always evaluate interval M=1

    	for m in self.M:
    		self[m] = VarEst(m)


        self.probe_count = 0
        self.slot_count = 0

        # we use geometric sampling
        self.samp_rate = samp_rate
        self.samp_var = samp_rate*(1-samp_rate)

        # sliding window to store arriving values
        self.win = np.zeros(np.max(self.M)).astype(bool)
        print len(self.win)


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
            #[self[m].append(np.mean(self.win[-m:])) for m in self.iterkeys() if self.slot_count%m==0]
            [self[m].append(np.mean(self.win[-m:])) for m in self.iterkeys() if not self.slot_count%m ]            


    def __repr__(self):
        return 'AggVarEst object <%s>' % str(self.vars())

    def __str__(self):
        s = ''
        for m in self.keys():
            if np.isnan(self[m].sigma):
                continue
            s += str(self[m])
        return s

    @property
    def avars(self):
        return np.array([av.sigma for av in self.itervalues()]) # observed aggregated variance


    def vars(self):
        """Returns the variances for all aggregation levels."""

    	if self.samp_rate==1.0:
    		return self.avars
    	else:
    		# correction to account for the geometric sampling process
    		w_var = self[1].sigma  # variance of the observed sampled process
    		w_mean = self[1].mean  # mean of the observed sampled process

    		y_mean = w_mean/self.samp_rate 
    		y_var = (w_var - self.samp_var*y_mean**2)/(self.samp_var + self.samp_rate**2);

    		return (self.avars - self.samp_var/self.M*y_mean**2 - self.samp_var/self.M*y_var)/self.samp_rate**2;


    def dump(self, fname):
        s = str(self)

        try:
            f = open(fname, mode='w')
        except IOError as e:
            print(e)
            return
        if s: f.write(s)
        f.close()



def test(data=None, p=1.0):
	"""Just a simple test for the autocovariance."""
	if data==None:
		data = [1,1,0,1,1,1,1,0,0,1,1,0,0,0,0,0,0,1,0,0,1,0,0,1,0,1]

	X = data
	A = np.random.binomial(1,p,len(X))
	W=A*X
	#from aggvar import AggVarEst
	av = AggVarEst(samp_rate=p, M_MIN=10, M_MAX=1000)
	
	for x in W:
		av.append_fast(x)
	return av

if __name__ == '__main__':
	import code
	import numpy as np
	print 'loading data...'
	data = np.loadtxt('ffgn_0.8.dat')
	data = (data-np.mean(data))>0

	import matplotlib.pyplot as plt
	plt.ion()
	av=test(data,1.0)
	plt.loglog(av.M,av.vars())
	av=test(data,.1)
	plt.loglog(av.M,av.vars())
	code.interact(local=locals())




