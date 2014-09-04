import os
import sys
import pprint
import logging
import threading
import time


import hphelper


options = hphelper.options
DEBUG = hphelper.DEBUG


def dumpwriter(pipe, ns, ST=None):
    hphelper.set_affinity('parser') 
    DEBUG('starting',  __name__)

    stats = hphelper.stats_stats()

    # start progress bar thread
    hphelper.bar_init(options, stats)

    if not options.start_time:
        options.start_time = time.time()
  
    if not options.savefile:
        # default save name is destination + YYMMDD + HHMM
        options.savefile = options.DST + time.strftime("_%Y%m%d_%H%M", 
                                                       time.localtime(options.start_time)) 

    options.savefile += options.tag 
    options.savefile += '.dump'

    print "saving RTTs to " + options.savefile + " ..."

    
    
    try:
            fs = open(options.savefile, mode='w')
            fs.write('% ' + 'options:' + ' ' + str(options) + '\n')    # save options
    except KeyboardInterrupt:
            print 'canceled writing file.'

    #block until sender + receiver say they are ready
    while not all([ns.RCV_READY,ns.SND_READY]):
        time.sleep(0.1)


    stats.run_start = time.time()
    try:
       while 1:
            (seq, slot, rtt) = pipe.recv()
            if seq == -2: break

            stats.update(seq, rtt=rtt, current_slot=slot)

            fs.write("%d %d %.9f\n" % (seq, slot , rtt))
    except (ValueError, KeyboardInterrupt) as e:
        print 

    fs.close()
    DEBUG('done',  __name__)

    stats.run_end = time.time()
    stats.pprint()







