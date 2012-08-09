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



def plot_hist(rtts):
    import hplotting

    gp = hplotting.gp_plotter(loglog=False)

    data = '\n'.join(['%.6f' % rtt for rtt in rtts])

    gp.setup(xlabel='[1e-6 s]')
    gp.cmd('binwidth=1e-6')
    gp.cmd('set boxwidth binwidth')
    gp.cmd('bin(x,width)=width*floor(x/width) + binwidth/2.0')
    gp.cmd("plot '-' using (bin($1,binwidth)):(1.0) smooth freq with boxes\n %s\n e" % (data), flush=True)
    
    gp.quit()
    #(hist,edges) = histogram(zrtts,bins=bins)



def statsparser(pipe, ns, slottimes):
    hphelper.set_affinity('parser')
    if options.DEBUG:
        print 'starting parser: ' + __name__
    


    #block until sender + receiver say they are ready
    while not all([ns.RCV_READY,ns.SND_READY]):
        time.sleep(0.1)

    stats = hphelper.stats_stats()
    slots = slottimes[:]


    # init empty array to store RTTs for histogram
    rtts = -1.0*ones(options.pnum)



    # start progress bar thread
    hphelper.bar_init(options, stats,  ns.cnum)


    run_start = time.time()


    while 1:
        try:
            data = pipe.recv()
            if data == 'RCV_DONE':
                break
           
            (seq, snd_time, rtt) = data
            currslot = slots[seq]

            if snd_time == -1:
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


    stats.append_stats(median=('median RTT','%.6f' % median(rtts)),
                       std=('std RTT','%.6f' % std(rtts)),
                       min=('min RTT','%.6f' % min(rtts)),
                       max=('max RTT','%.6f' % max(rtts)), )




    # store mean RTT for use in other modules
    ns.mean_rtt = mean(rtts)

    stats.pprint()

    if options.hist:
        plot_hist(rtts)

    return












