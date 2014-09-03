# Copyright 2012 IKT Leibniz Universitaet Hannover
# GPL2
# Zdravko Bozakov (zb@ikt.uni-hannover.de)

import os
import sys
import threading
import time
from numpy import *

import hphelper

options = hphelper.options
DEBUG = hphelper.DEBUG
ERROR = hphelper.err


def plot_hist(rtts):
    import hplotting

    gp = hplotting.gp_plotter(loglog=False)

    data = '\n'.join(['%.6f' % rtt for rtt in rtts])

    gp.setup(xlabel='bin width = 1e-6 s')
    gp.cmd('binwidth=1e-6')
    gp.cmd('set boxwidth binwidth')
    gp.cmd('bin(x,width)=width*floor(x/width) + binwidth/2.0')
    gp.cmd("plot '-' using (bin($1,binwidth)):(1.0) smooth freq with boxes\n %s\n e" % (data), flush=True)
    
    gp.quit()



def statsparser(pipe, proc_opts):
    hphelper.set_affinity('parser')
    DEBUG('starting parser ', __name__)

    #block until sender + receiver say they are ready
    while not all([proc_opts.RCV_READY,proc_opts.SND_READY]):
        time.sleep(0.1)

    stats = hphelper.stats_stats()

    # init empty array to store RTTs for histogram
    rtts = -1.0*ones(options.pnum)

    # start progress bar thread
    hphelper.bar_init(options, stats,  proc_opts.cnum)


    run_start = time.time()
    while 1:
        try:
            data = pipe.recv()
            if data == 'RCV_DONE':
                break

            (seq, currslot, rtt) = data
            if currslot == -1:
                 rtt = -1
                 stats.snd_err += 1
                 continue

            stats.update(seq, rtt, currslot)

            if rtt<stats.min_rtt:
                stats.min_rtt = rtt

            rtts[seq] = rtt


        except (KeyboardInterrupt) as e:
            print 'parser canceled'
        except (ValueError) as e:
            print e
            print 'done writing'
        except (IndexError) as e:
            print e, seq
            pass ### TODO last sequence number causes error

    # omit invalid rtts
    rtts = rtts[rtts!=-1]

    if not any(rtts):
        proc_opts.FATAL_ERROR = True
        ERROR("could not calculate average delay")

    # store mean RTT for use in other modules
    proc_opts.mean_rtt = mean(rtts)

    stats.append_stats(median=('RTT median','%.6f' % median(rtts)),
                       std=('RTT std. dev.','%.6f' % std(rtts)),
                       #min=('min RTT','%.6f' % min(rtts)),
                       max=('RTT maximum','%.6f' % max(rtts)),
                       )

    stats.pprint()

    if options.hist:
        plot_hist(rtts)

    return












