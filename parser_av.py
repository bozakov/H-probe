# Copyright 2012 IKT Leibniz Universitaet Hannover
# GPL2
# Zdravko Bozakov (zb@ikt.uni-hannover.de)

import time
import threading
import warnings
from collections import deque

try:
    import numpy as np
except ImportError:
    print __name__ + ": please make sure the following packages are installed:"
    print "\tpython-numpy"
    exit(1)

try:
    # import cython functions if available
    import hpfast
    import types                          # for cython bindings
except (ImportError, ValueError) as e:
    pass

import hphelper
import hplotting
from aggvar import VarEst

warnings.simplefilter('ignore', np.RankWarning)

np_append = np.append
options = hphelper.options
DEBUG = hphelper.DEBUG
ERROR = hphelper.err



try:
    VarEst = hpfast.VarEst
    DEBUG('using hpfast.VarEst', __name__)
except (NameError, AttributeError) as e:
    pass



class AggVarEstimator(threading.Thread):
  
    def __init__(self, buf, M=None):

        threading.Thread.__init__(self)

        self.buf = buf
        if not M:
            #M = range(options.M[0], options.M[1], 300)
            M = 10**np.linspace(np.log10(options.M[0]),np.log10(options.M[1]),200)
            M = np.unique(np.floor(M)).astype(int)

        self.M = M            

        # sliding window to store arriving values
        self.win = np.zeros(np.max(M)).astype(bool)

        # avars stores an estimator for each aggregation level in M
        self.avars = dict.fromkeys(M,0)
        # ensure that we calculate the variance at the smallest
        # aggregate level, even when it was not specified by the user
        self.avars[1] = 0 
        for m in self.avars.iterkeys():
            self.avars[m] = VarEst(m)


        self.probe_count = 0
        self.slot_count = 0


        self.stats = hphelper.stats_stats()
        self.mean_a = options.rate
        self.var_a = self.mean_a - self.mean_a**2
        self.va = self.var_a*np.ones(len(self.M))/self.M


        # start progress bar thread 
        hphelper.bar_init(options, self.stats)

        self.daemon = True




    def run(self):
        stats = self.stats
        last_seq = -1                                       # store maximum sequence number received until now
        last_slot = 0

        if options.min_rtt == -1.0:
            min_rtt = np.inf
        else:
            min_rtt = options.min_rtt


        while 1:
            try:
                (seq, slot, rtt) = self.buf.popleft()
            except IndexError:
                continue

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

            last_seq = seq


            slot_delta = slot - last_slot
            last_slot = slot

            # update the minimum RTT on the fly. Only update if the
            # RTT was not specified as an option
            #if options.min_rtt == -1.0:                  
            #    min_rtt = min(rtt, min_rtt)

            # check if probe saw a busy period (True/False) 
            probe = rtt > min_rtt

            self.append_fast(probe, slot_delta-1)



    def get_avars(self):
        """Returns the variances estimated so far for all aggregation
        levels stored in M"""
        return [self.avars[m].var() for m in self.M]



    def get_avars_corrected(self):
        """Returns the variances for all aggregation levels, corrected
        to account for the geometric sampling process"""
        var_w = self.avars[1].var()
        vw = self.get_avars()

        mean_y_hat = self.mean()/self.mean_a
        var_y_hat = (var_w - mean_y_hat**2*self.var_a)/(self.var_a + self.mean_a**2);

        return (vw - mean_y_hat**2*self.va - self.var_a*var_y_hat/self.M)/self.mean_a**2;

        

    def fit(self):
        """Performs a linear fit on the aggregated variance estimates"""
        logy = np.log10(self.get_avars_corrected())
        logx = np.log10(self.M)

        try:
            (d,y0) = np.polyfit(logx[~np.isnan(logy)], logy[~np.isnan(logy)],1)
            return (d,10**y0)
        except Exception as e:
            return (-1, -1)



    def hurst(self, d=None):
        ''' return the hurst parameter estimate'''
        if not d:
            (d,y0) = self.fit()
        return (d+2)/2



    def getdata_str(self):
        variances = self.get_avars_corrected()

        if any(variances):
            return '\n'.join([' '.join([str(m*options.delta),str(v)]) for m,v in zip(self.M, variances)])
        else:
            return None



    def append_fast(self, probe, zcount=0):
        ''' Append the latest received probe to a sliding
        window. Update the aggregate variances for each variance
        block '''
        self.probe_count += probe

        z=[False]*zcount
        z.append(bool(probe))

        for x in z:
            # speed: np.r_ < np.roll < np.concatenate < np.append 
            self.win = np_append(self.win[1:], x)
            self.slot_count += 1

            [var.append(np.mean(self.win[-m:])) for m,var in self.avars.iteritems() if not self.slot_count % m]


            
    def mean(self):
        ''' return the mean of the observation vector mu_w '''
        try:
            return self.probe_count*1.0/self.slot_count
        except:
            return np.nan


        


try:
    # try to bind cython methods
    # http://wiki.cython.org/FAQ#HowdoIimplementasingleclassmethodinaCythonmodule.3F
    AggVarEstimator.append_fast = types.MethodType(hpfast.av_append_f, None, AggVarEstimator) 
    AggVarEstimator.get_avars_corrected = types.MethodType(hpfast.get_avars_corrected_f, None, AggVarEstimator) 
    min = hpfast.min
    max = hpfast.max 
    DEBUG('cython methods bounded', __name__)

except (NameError, AttributeError) as e:
    pass



def avparser(pipe, proc_opts, ST=None):
    if not options.start_time:
        options.start_time = time.time()
  
    if not options.savefile:
        # default save name is destination + YYMMDD + HHMM
        options.savefile = options.DST + time.strftime("_%Y%m%d_%H%M", 
                                                       time.localtime(options.start_time)) 
    options.savefile += options.tag 
    options.savefile += '_av'


    rcv_buf = deque() # TODO

    # init estimator thread
    av = AggVarEstimator(rcv_buf, ST)

    # init plotter thread
    avplotter_thread = threading.Thread(target=avplotter, args=(av,))
    avplotter_thread.daemon = True

    #block until sender + receiver say they are ready
    while not all([proc_opts.RCV_READY,proc_opts.SND_READY]):
        time.sleep(0.1)

    av.stats.run_start = time.time()

    # start threads
    avplotter_thread.start()
    av.start()

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



    try:
        av.join()
        avplotter_thread.join()
    except KeyboardInterrupt:
        pass

    av.stats.run_end = time.time()
    av.stats.pprint()

    print
    print "\tH=%.2f" % (av.hurst(),)
    print 


    
    
    fname = options.savefile + '.dat'
    print "saving variances to " + fname + " ..."
    try:
            fs = open(fname, mode='w')
            fs.write('% ' + options.IPDST + ' ' + str(options))

            for m,v in zip(av.get_avars_corrected(), av.M):
                fs.write("%e\t%d\n" % (m,v))
            fs.close()
    except IOError:
            ERROR('could not write to file')
            return
    except KeyboardInterrupt:
            print 'canceled saving.'

    DEBUG('done', __name__ )



def avplotter(av):
        if not options.plot: return

        gp = hplotting.gp_plotter()
        if not gp.gp: return        

        getdata_str =  av.getdata_str
        gp_cmd = gp.cmd

        fps = 1.0/options.fps



        # use these to plot axis ranges
        min_x = options.M[0]*options.delta
        max_x = options.M[1]*options.delta
        min_y, max_y = (1e-5,1e-0)


        # set plot options
        gp.setup(xlabel='log_{10}(M) [s]', 
                 ylabel='log_{10}(aggregate variance)', 
                 xrange=(min_x, max_x), 
                 yrange=(min_y, max_y),
                 )

        # draw auxiliarry lines
        #y0=1e-0
        #gp.arrow(min_x,y0,    max_x,y0/(max_x/options.delta))
        #gp.arrow(min_x,y0,    y0/0.1,1e-4)


        i = 0
        while av.is_alive():
            i += 1
            if i%10==0:                              # calculate and plot hurst fit every 10 frames
                (d,y0) = av.fit()
                if y0!=-1:
                    # plot H linear fit and label it
                    gp.arrow(min_x, y0*(min_x/options.delta)**d, max_x, y0*(max_x/options.delta)**d,'2')

            # sleep before redrawing
            time.sleep(fps)

            data = getdata_str()
            if data:
                gp_cmd("plot '-' with points ls 4\n %s\n e\n"  % (data), flush=True)


        # replot with label
        (d,y0) = av.fit()
        if y0!=-1:
            # plot H linear fit and label it
            gp.label('H=%.2f' % (av.hurst(d)), min_x*5, 2*y0*(min_x*5/options.delta)**d, '2')
            gp.arrow(min_x, y0*(min_x/options.delta)**d, max_x, y0*(max_x/options.delta)**d,'2')
        data = getdata_str()
        if data:
            gp_cmd("plot '-' with points ls 4\n %s\n e\n"  % (data), flush=True)


        # save plot to EPS
        gp.set_term_eps(options.savefile)
        # we must replot everything to save it to the file
        (d,y0) = av.fit()
        if y0!=-1:
            # plot H linear fit and label it
            gp.label('H=%.2f' % (av.hurst(d)), min_x*5, 2*y0*(min_x*5/options.delta)**d, '2')
            gp.arrow(min_x, y0*(min_x/options.delta)**d, max_x, y0*(max_x/options.delta)**d,'2')


        data = getdata_str()
        gp_cmd("plot '-' with points ls 4\n %s\n e\n"  % (data), flush=True)
        gp.quit()

