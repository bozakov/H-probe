import os
import sys
import pprint
import logging
import threading
import time


import hphelper


options = hphelper.options
DEBUG=options.DEBUG


def dumpwriter(pipe, ns, slottimes):

    timetime = time.time
    hphelper.set_affinity('parser') 


    slots = slottimes[:]

    DEBUG('starting ' + __NAME__)
    run_start = timetime()


    stats = hphelper.stats_stats()


    # start progress bar thread
    hphelper.bar_init(options, stats)


    if not options.savefile:
        # default save name is destination + YYMMDD + HHMM
        options.savefile = options.DST + time.strftime("_%Y%m%d_%H%M", time.localtime()) + options.tag 
    options.savefile += '.dump'
    print "saving RTTs to " + options.savefile + " ..."


    try:
            fs = open(options.savefile, mode='w')
            fs.write('% ' + options.IPDST + ' ' + str(options) + '\n')                # save options
    except KeyboardInterrupt:
            print 'canceled writing file.'


    #block until sender + receiver say they are ready                                                    
    while not all([ns.RCV_READY,ns.SND_READY]):
        time.sleep(0.1)


    stats.run_start = time.time()
    options.start_time = time.time()

    try:
       while 1:
            (stats.seq, snd_time, rtt) = pipe.recv()
            currslot = slots[stats.seq]
            if snd_time == -1:
                 rtt = -1
                 stats.snd_err += 1
            else:
                 stats.rx_total += 1 

            fs.write("%d %d %.9f\n" % (stats.seq, currslot , rtt))
    except (ValueError, KeyboardInterrupt) as e:
        print '\ndone writing'
    fs.close()

    stats.run_end = time.time()
    stats.pprint()







