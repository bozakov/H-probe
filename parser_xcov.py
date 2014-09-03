# Copyright 2012 IKT Leibniz Universitaet Hannover
# GPL2
# Zdravko Bozakov (zb@ikt.uni-hannover.de)

import os
import sys
import pprint
import logging
import threading
import types                          # for cython binding
import time
import subprocess
from collections import deque


try:
    from numpy import *
except ImportError:
    print __name__ + ": please make sure the following packages are installed:"
    print "\tpython-numpy"
    exit(1)

try:
    import setproctitle
    setproctitle.setproctitle('h-probe')
except:
    pass # Ignore errors, since this is only cosmetic


try:
    # import cython functions if available
    import hpfast
except (ImportError, ValueError) as e:
    pass


import hplotting
import hphelper
from  hphelper import WARN, ERROR, DEBUG
from xcov import XCovEst, AggVarEst

options = hphelper.options


if not options.DEBUG:
    # avoid warnings whe using log10 with negative values
    seterr(invalid='ignore')



class XcovEstimator(threading.Thread):
    """An online estimator for the covariance of a point process.

    The object is fed samples using the append() function. It
    maintains a sliding window self.win and adds its values to self.estimator
    at each time-step.
    """

    def __init__(self, buf, slots, estimator='xcov'):
            threading.Thread.__init__(self)

            self.stats = hphelper.stats_stats()

            if estimator=='xcov':
                self.estimator = XCovEst(options.L)
            elif estimator=='aggvar':
                self.estimator = AggVarEst(options.L)

            self.L = self.estimator.L            # max covariance lag

            self.buf = buf
            self.slots = slots

            self.min_win_seq = 1
            self.max_win_seq = self.L

            self.mean_a = options.rate
            self.var_a = self.mean_a - self.mean_a**2

            # start progress bar thread 
            hphelper.bar_init(options, self.stats)


    def conf_int(self, xcov=None):
        """Returns the 95 confidence interval level for sampled iid Gaussian process."""
        if not xcov:
            xcov = self.estimator.xcov[1:]

        mean_a = self.mean_a
        var_a = self.var_a

        mean_w = self.estimator.mean
        var_w = self.estimator.var(mean_w)

        mean_y_est = mean_w/mean_a
        var_y_est = (var_w - mean_y_est**2*var_a)/(var_a + mean_a**2)

        A = var_a*mean_y_est**2 + mean_a*var_y_est
        return 2*sqrt((A**2 + 4*mean_a**2*mean_y_est**2*A)/self.estimator.slot_count) 


    def fit(self, thresh=None, lag_range=(None,None)):
        """Performs a linear fit on the covariance estimate.

        Performs a regression on the logarithm of the covariance
        estimate returned by xc.xcov. Omits all values larger equal
        thresh.

        Args: 
            thresh: A float above which the covariance values are
            set to NaN.
            lag_range: A an integer tuple specifying the range of lags
            to use for the fitting.

        """
        
        if all(lag_range):
            min_lag, max_lag = lag_range
        else:
            min_lag, max_lag = (1,self.L)


        xc = self.estimator.xcov[1:]
        if thresh:
            xc[xc<=thresh] = nan

        logy = log10(xc[min_lag-1:max_lag-1])
        logx = log10(arange(min_lag,max_lag))

        try:
            (d,y0) = polyfit(logx[~isnan(logy)], logy[~isnan(logy)],1)   
            return (d, 10**y0)
        except Exception as e:
            return (-1, -1)


    def getdata_str(self):
        """Returns a string of covariance values which can be piped
        into gnuplot."""
        return str(self.estimator)


    def hurst(self, d=None, thresh=0):
        """Returns the Hurst parameter estimate."""
        if not d:
            (d,y0) = self.fit(thresh=thresh)
        return (d+2)/2


    def pprint(self):
        """print out the biased covariance"""
        print 'xc=[',
        for i in reversed(self.estimator):
            print '%.8f' % (i),
        print '];'


    def run(self):
        stats = self.stats
        last_seq = -1                                  # store maximum sequence number received until now
        last_slot = 0

        if options.min_rtt == -1.0:
            min_rtt = inf
        else:
            min_rtt = options.min_rtt

        
        while 1:
            try:  # TODO get rid of try block
                (seq, slot, rtt) = self.buf.popleft()
            except IndexError:
                continue                             # loop until buffer is not empty

            if seq == -2: break

            stats.update(seq, rtt, slot)

            if seq!=last_seq+1:
                # unexpected sequence number 
                seq_delta = seq-last_seq-1
                if seq_delta<0:
                    # discard probe if it was received out of order
                    # seq_delta == -1 --> duplicate packet
                    stats.rx_out_of_order += 1
                    continue

                # all intermediate packets were missing
                stats.rcv_err += seq_delta

            ## each dropped probe indicates a full queue append, a
            ## 1 to the covariance vector
            #while seq!=last_seq+1:
            #    last_seq += 1
            #    next_slot = slots[last_seq]
            #    if next_slot==-1:                         # slottimes vector might be incomplete
            #        continue
            #    slot_delta = next_slot - last_slot
            #    last_slot = next_slot
            #    stats.rcv_err += 1                        # increment dropped packets counter
            #    self.append(1, slot_delta)


            last_seq = seq

            slot_delta = slot - last_slot
            last_slot = slot

            # check if the probe saw a busy period (True/False)
            probe = rtt > min_rtt

            self.estimator.append(probe, slot_delta-1)



try:
    # try to bind cython methods
    # http://wiki.cython.org/FAQ#HowdoIimplementasingleclassmethodinaCythonmodule.3F
    XcovEstimator.append = types.MethodType(hpfast.xc_append_f, None, XcovEstimator) 
    XcovEstimator.xcov = types.MethodType(hpfast.xcov2_f, None, XcovEstimator) 
    min = hpfast.min
    max = hpfast.max 
    DEBUG('cython methods bounded')
except (NameError, AttributeError) as e:
    if options.DEBUG:
        print e





def xcparser(pipe, ns, slottimes):
    if not options.start_time:
        options.start_time = time.time()
  
    if not options.savefile:
        # default save name is destination + YYMMDD + HHMM
        options.savefile = options.DST + time.strftime("_%Y%m%d_%H%M", 
                                                       time.localtime(options.start_time)) 
    options.savefile += options.tag 
    options.savefile += '_xc'

    timetime = time.time          # faster: http://wiki.python.org/moin/PythonSpeed/PerformanceTips
    hphelper.set_affinity('parser') 

    rcv_buf = deque() # TODO  rcv_buf = xcfast.fixed_buf(options.pnum)

    xc = XcovEstimator(rcv_buf, slottimes)
    xc.daemon = True
    xc.name='parseloop'


    # start xcplotter Thread
    xcplotter_thread = threading.Thread(target=xcplotter, args=(xc,))
    xcplotter_thread.daemon = True

    #block until sender + receiver say they are ready
    while not all([ns.RCV_READY,ns.SND_READY]):
        time.sleep(0.1)

    DEBUG('starting parser: '+__name__)
    xc.stats.run_start = timetime()

    xcplotter_thread.start()
    xc.start()


    data = None
    try:
        while 1:                              # faster than while True
            data = pipe.recv()                # get (seq, slot, rtt) from capture process
            (seq, slot, rtt) = data
            rcv_buf.append((seq, slot, rtt))   
    except (KeyboardInterrupt):
        rcv_buf.append((-2,-2,-2))
        print '\n\nparse loop interrupted...'
    except (ValueError) as e:
        rcv_buf.append((-2,-2,-2))
        print '\a', # all packets received

    try:
        xc.join()
        xcplotter_thread.join()
    except KeyboardInterrupt:
        pass
    

    # display statistics
    xc.stats.run_end = timetime()
    xc.stats.rx_slots = xc.estimator.slot_count
    xc.stats.pprint()


    (d,y0) = xc.fit()
    print
    print "\tH=%.2f (slope %.4f y0=%.4f)" % ((d+2)/2, d, y0 )
    print 


    fname = options.savefile + '.dat'
    print "saving covariance to " + fname + " ..."
    try:
        fs = open(fname, mode='w')
        fs.write('% ' + options.IPDST + ' ' + str(options))
        
        for j in xc.estimator.xcov[1:]:
            fs.write("%e\n" % (j))
        fs.close()
    except KeyboardInterrupt:
            print 'canceled saving.'



def xcplotter(xc, gp=None):
    """Initialize gnuplot and periodically update the graph."""
    if options.no_plot: return

    gp = hplotting.gp_plotter()
    if not gp.gp: return        

    getdata_str = xc.getdata_str
    gp_cmd = gp.cmd
    xc_conf_int = xc.conf_int

    fps = 1.0/options.fps

    # use these to plot axis ranges
    min_x, max_x = (1,options.L)
    min_y, max_y = (1e-6,1e-0)

    # set plot options
    gp.setup(xlabel='log_{10}(lag) [s]', 
             ylabel='log_{10}(autocovariance)', 
             xrange=(min_x, max_x), 
             yrange=(min_y,max_y),
             xtics=[(i*options.delta,i) for i in 10**arange(log10(options.L)+1)],
             )

    ydata = ''

    i=0
    while xc.is_alive():
        i += 1
        if i%10==0:             # plot confidence levels every 10 frames
            ci_level = xc_conf_int()
            #gp.arrow(min_x, ci_level, max_x, ci_level, '3', 8)
            gp.level(ci_level, min_x, max_x)

        # TODO does not terminate cleanly if X11 display cannot be opened
        time.sleep(fps)

        ydata = getdata_str()
        if ydata:
            gp_cmd("plot '-' with points ls 3\n %s\n e"  % ydata, flush=True)


    # calculate confidence interval
    ci_level = xc_conf_int()
    # plot confidence interval level
    #gp.arrow(min_x, ci_level, max_x, ci_level, '3', 8)
    gp.level(ci_level, min_x, max_x)

    # perform fitting for values larger than ci_level
    (d,y0) = xc.fit() # TODO thresh=ci_level
    H = xc.hurst(d)

    ydata = getdata_str()
    if H:
        # plot H linear fit and label it
        gp.label('H=%.2f' % H, 2, 1.2*(y0))      
        gp.arrow(1, y0, xc.L, y0*xc.L**d, '4')

        #xh = 10**((log10(ci_level)-log10(y0))/d)
        #gp.arrow(1, y0, xh, y0*xh**d, '4')

        if ydata:
            gp_cmd("plot '-' with points ls 3\n %s\n e"  % ydata)


    # save plot to EPS
    gp.set_term_eps(options.savefile)


    # we must replot everything to save it to the file
    # plot H linear fit and label it
    gp.label('H=%.2f' % H, 2, 1.2*(y0))      
    #gp.arrow(1, y0, xc.L, y0*xc.L**d, '4')
    gp.level(ci_level, min_x, max_x)
    if ydata:
        gp_cmd("plot '-' with points ls 3\n %s\n e"  % ydata)

    gp.quit()
