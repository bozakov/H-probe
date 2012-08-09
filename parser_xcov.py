# Copyright 2012 IKT Leibniz Universitaet Hannover
# GPL2
# Zdravko Bozakov (zb@ikt.uni-hannover.de)

import os
import sys
import pprint
import logging
import threading
import time
import subprocess
from collections import deque


try:
    from numpy import *
    import types                          # for cython binding
except ImportError:
    print __name__ + ": please make sure the following packages are installed:"
    print "\tpython-numpy"
    exit(1)


import hphelper
import hplotting



try:
    # import cython functions if available
    import hpfast
except ImportError as e:
    pass


options = hphelper.options
DEBUG = hphelper.DEBUG






class XcovEstimator(threading.Thread):
    """An online estimator for the covariance of a point process.

    The object is fed samples using the append() function. It
    maintains a sliding window self.win and adds its values to self.xc
    at each time-step.
    """

    def __init__(self, buf, slots):
            self.stats = hphelper.stats_stats()

            self.L=options.L            # max covariance lag

            self.buf = buf
            self.slots = slots

            self.xc = zeros(self.L, dtype=int)
            self.win = zeros(self.L, dtype=bool)

            self.min_win_seq = 1
            self.max_win_seq = self.L

            self.probe_count = 0
            self.slot_count = self.L 

            self.terminated = False


            # use this to plot x-axis range
            self.min_x = 1
            self.max_x = options.L


            self.mean_a = options.rate
            self.var_a = self.mean_a - self.mean_a**2

            # start progress bar thread 
            hphelper.bar_init(options, self.stats)

            threading.Thread.__init__(self)


    def reset(self):
            self.__init__()



    def append(self, x, zcount = 0):
            """ Appends the last received probe to the sliding window win
            containing the last L values (lags) and adds the contents of win
            to the biased covariance vector xc.

            Args:

                x: Contains the probe value which may be 0 or 1
                zcount: Specifies the number of empty time slots to
                    append before the current probe.
            
            """

            self.slot_count  += zcount+1                    # keep track of total number or counted slots (should be all)
            self.probe_count += x                           # increment counter for each was received probe (zero or one)

            zcount = min(self.L-1, zcount)
            #if zcount<0: return                            # ERROR: negative slot increment - should not happen!

            # shift window to the left (concatenate is faster than roll for shifting)
            self.win = concatenate( (self.win[zcount+1:], zeros(zcount, dtype=bool), [bool(x)]) )           

            # increment autocovariance (just for non-zero values of win and only if x=1)
            if x==1:
                self.xc[nonzero(self.win)] += x


    def mean(self):
            """ return the mean of the observation vector mu_w """
            try:
                return self.probe_count*1.0/self.slot_count
            except:
                return nan


    def xcov(self):
            """Calculates the covariance from the sliding window sums xc."""
            # flip array so that lag zero is on the left hand side
            xc = self.xc[::-1]
            return (xc*1.0/(self.slot_count - arange(self.L, dtype=int)) - self.mean()**2)[1:] 


    def conf_int(self, xcov=None):
            """Returns the 95 confidence interval level for sampled iid Gaussian process."""
            if not xcov:
                xcov = self.xcov()

            mean_a = self.mean_a
            var_a = self.var_a

            # the covariance at lag 0 is the variance of the
            # observation process
            var_w = xcov[0]

            mean_y_est = self.mean()/self.mean_a
            var_y_est = (var_w - mean_y_est**2*var_a)/(var_a + mean_a**2)

            A=var_a*mean_y_est**2 + mean_a*var_y_est
            return 2*A*sqrt((1 + 2*mean_a**2*mean_y_est**2/A)/self.slot_count) # /mean_a**2 
            #return 2*var_a*sqrt(var_a**2 + 4* mean_a**2)/sqrt(self.slot_count) # ca95


    def xcov_int(self):
            """return covariance estimate using the cumulative sum approach TODO"""
            xc = self.xcov()
            var_w = xc[0]

            mean_a = self.mean_a
            var_a = self.var_a

            mean_y_est = self.mean()/mean_a
            var_y_est = (var_w - mean_y_est**2*var_a)/(var_a + mean_a**2)


            # calculate correction factor to correct error due to sampling
            cfactor = insert(var_a/2*ones(self.L-1),0,0)*(var_y_est + mean_y_est**2) #CHECKME TODO

            #cs_xc = (cumsum(xc) - cfactor)/arange(0, self.L)/mean_a**2
            cs_xc = (self.cumtrapz(xc) - cfactor)/arange(0, self.L) 
            return cs_xc[1:] 


    def fit(self, thresh=0, lag_range=None):
            """Performs a linear fit on the covariance estimate.
            
            Performs a regression on the logarithm of the covariance
            estimate returned by xcov(). Omits all values larger equal
            thresh.

            Args: 
                thresh: A float above which the covariance values are
                set to NaN.

            """

            min_lag, max_lag = (1,self.L)

            xc = self.xcov()
            xc[xc<=thresh]=nan

            logy = log10(xc[min_lag-1:max_lag-1])
            logx = log10(arange(min_lag,max_lag))

            try:
                (d,y0) = polyfit(logx[~isnan(logy)], logy[~isnan(logy)],1)   
                return (d, 10**y0)
            except Exception as e:
                return (-1, -1)


    def getdata_str(self):
        """Returns a string of values which can be piped into gnuplot."""
        y = self.xcov()
        if any(y):
            return '\n'.join([str(a) for a in y])
        else:
            return None



    def hurst(self, d=None, thresh=0):
        """Returns the Hurst parameter estimate."""
        if not d:
            (d,y0) = self.fit(thresh=thresh)
        return (d+2)/2


    def pprint(self):
        """print out the biased covariance"""
        print 'xc=[',
        for i in reversed(self.xc):
            print '%.8f' % (i),
        print '];'


    def run(self):
        stats = self.stats
        slots = self.slots[:]                        # create a local copy of the slot array
        last_slot = 0
        current_slot = 0

        # store maximum sequence number received until now
        max_seq = -1
        start_time = None


        if options.min_rtt == -1.0:
            min_rtt = inf
        else:
            min_rtt = options.min_rtt

        
        while 1:
            (seq, snd_time, rtt) = self.buf.popleft()

            if seq==-2:
                break

            #stats.update_seq(seq)
            stats.update(seq, rtt)


            # save arrival time of first packet
            if not start_time: 
                start_time = snd_time             

            # discard probe if it was received out of order
            if seq<=max_seq:
                stats.rx_out_of_order += 1
                continue

            # packet was not sent correctly!!!
            if snd_time == -1.0:
                stats.snd_err += 1
                continue


            # each dropped probe indicates a full queue append, a
            # 1 to the covariance vector
            while seq!=max_seq+1:
                max_seq += 1
                next_slot = slots[max_seq]
                if next_slot==-1:                         # slottimes vector might be incomplete
                    continue

                slot_delta = next_slot - last_slot
                last_slot = next_slot

                # increment dropped packets counter
                stats.rcv_err += 1
                self.append(1, slot_delta)


            max_seq = seq

            current_slot = slots[seq]
            slot_delta = current_slot - last_slot
            last_slot = current_slot

            # update the minimum RTT
            #if options.min_rtt == -1.0:                  # only update if the RTT was not specified as an option 
            #    min_rtt = min(rtt, min_rtt)

            # check if probe saw a busy period (0/1)
            probe = int(rtt > min_rtt)

            self.append(probe, slot_delta)








try:
    # try to bind cython methods
    # http://wiki.cython.org/FAQ#HowdoIimplementasingleclassmethodinaCythonmodule.3F
    XcovEstimator.append = types.MethodType(hpfast.xc_append_f, None, XcovEstimator) 
    XcovEstimator.xcov = types.MethodType(hpfast.xcov2_f, None, XcovEstimator) 
    min = hpfast.min
    max = hpfast.max 
    DEBUG('cython methods bounded')
except (NameError, AttributeError) as e:
    print e
    pass







def xcparser(pipe, ns, slottimes):
    

    if not options.savefile:
        # default save name is destination + YYMMDD_HHMM
        options.savefile = options.DST + time.strftime("_%Y%m%d_%H%M", time.localtime()) + options.tag


    timetime = time.time          # faster: http://wiki.python.org/moin/PythonSpeed/PerformanceTips
    hphelper.set_affinity('parser') 








    rcv_buf = deque() # TODO
    #try:
    #    rcv_buf = xcfast.fixed_buf(options.pnum)
    #except:
    #    rcv_buf = deque() 


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
        while 1:                                              # faster than while True
            data = pipe.recv()
            (seq, snd_time, rtt) = data
            rcv_buf.append((seq, snd_time, rtt))              # receive (seq, snd_time, rtt) from rcvloop process
    except (KeyboardInterrupt):
        rcv_buf.append((-2,-2,-2))
        print '\n\nparse loop interrupted...'
    except (ValueError) as e:
        rcv_buf.append((-2,-2,-2))
        print '\a', # received all packets
        sys.stdout.flush()


    try:
        xc.join()
        xcplotter_thread.join()
    except KeyboardInterrupt:
        pass

    ######################
    # display statistics
    xc.stats.run_end = timetime()
    xc.stats.rx_slots = xc.slot_count
    xc.stats.pprint()


    #print "%d packets received out of order (%d probes, max_seq: %d)" % (stats.rx_out_of_order, options.pnum, max_seq)


    (d,y0) = xc.fit()

    print
    print "\tH=%.2f (slope %.4f y0=%.4f)" % ((d+2)/2, d, y0 )
    print 

    options.savefile += '_xc'
    print "saving covariance to " + options.savefile + " ..."

    try:
        fs = open(options.savefile + '.dat', mode='w')
        fs.write('% ' + options.IPDST + ' ' + str(options))
        
        for j in xc.xcov():
            fs.write("%e\n" % (j))
        fs.close()
    except KeyboardInterrupt:
            print 'canceled saving.'





def xcplotter(xc, gp=None):

        if not options.plot:
            return

        gp = hplotting.gp_plotter()
        gp_cmd = gp.cmd

        fps = 1.0/options.fps

        getdata_str = xc.getdata_str
        xc_conf_int = xc.conf_int

        min_y, max_y = (1e-6,1e-2)

        # set plot options
        gp.setup(xlabel='log_10(lag) [s]', 
                 ylabel='covariance', 
                 xrange=(xc.min_x, xc.max_x), 
                 yrange=(min_y,max_y),
                 xtics=[(i*options.delta,i) for i in 10**arange(log10(options.L)+1)],
                 )


        while xc.is_alive():
            time.sleep(fps)

            if options.ci:
                ci_level = xc_conf_int()
                gp.arrow(xc.min_x, ci_level, xc.max_x, ci_level, '3')

            ydata = getdata_str()
            if ydata:
                gp_cmd("plot '-' with points ls 3\n %s\n e"  % ydata, flush=True)


        # calculate confidence interval and 
        ci_level = xc_conf_int()



        # perform fitting for values larger than ci_level
        (d,y0) = xc.fit(thresh=ci_level)
        H = xc.hurst(d)

        # plot confidence interval level
        gp.arrow(xc.min_x, ci_level, xc.max_x, ci_level, '3')


        ydata = getdata_str()
            
        if H:
            # plot H linear fit and label it
            gp_cmd("set label \"H=%.2f\" at %e,%e\n" % (H, 2, 1.2*(y0)))
            xh = 10**((log10(ci_level)-log10(y0))/d)
            gp.arrow(1, y0, xh, y0*xh**d, '4')

            #hdata_str = '\n'.join(["%f %f" % (x,y) for x,y in [(1, y0), (xc.L, y0*xc.L**d )]])
            #gp_cmd("plot '-' lt 8\n %s\n e" % hdata_str)
            gp_cmd("plot '-' with points ls 3\n %s\n e"  % ydata, flush=True)


        try:
            # save current plot as EPS file
            if options.savefile:
                # we must replot everything to save it to the file
                print "saving plot to " + options.savefile + ".eps ..."
                gp_cmd("set terminal postscript eps color\n")
                gp_cmd("set output \"%s.eps\"\n" % options.savefile)
                gp_cmd("set label \"H=%.2f\" at %e,%e\n" % (H, 2, 1.2*y0))
                gp_cmd("set arrow 2 from 1,%e to %d,%e nohead lw 0 linecolor rgb 'blue'\n" % (y0, xc.L, y0*xc.L**d ))
                gp_cmd("plot '-' with points ls 1\n %s\n e\n" % (ydata))

        except KeyboardInterrupt:
            print 'canceled saving.'


        gp_cmd('quit\n') 
        gp.flush()
