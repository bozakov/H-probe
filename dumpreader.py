import sys
import pprint
import time
from numpy import *

import hphelper


dump = None
options = hphelper.options

class dumpdata(object):
    def __init__(self, options):
        self.slottimes = -1*ones(options.pnum).astype(int)
        self.rcv_order = -1*ones(options.pnum).astype(int)
        self.rtts = zeros(options.pnum)  

        self.dump_options = None

    def stats(self):
        print 'dump mean %.6f (%d samples)\n' % ( mean(self.rtts), sum(self.rcv_order!=-1))



def init_reader():
    print "loading %d RTTs from " %(options.pnum) + options.loaddump 
    global dump
    dump = dumpdata(options)

    try:
        fs = open(options.loaddump, mode='r')
        l = fs.readline()
        (c, IPDST, opt) = str.split(l,' ',2)
        dump.dump_options = eval(opt)

    except Exception as e:
        print 'error loading file'
        print e
    except SyntaxError as se:
        print 'could not parse options'


    ################################################
    # set some options loaded from the dump file
    options.IPDST = dump.dump_options['IPDST']
    options.DST = dump.dump_options['DST']
    options.plen = dump.dump_options['plen']
    options.delta = dump.dump_options['delta']
    ################################################


    line_count = 0
    try:
        while (line_count < options.pnum):  
            try:
                l = fs.readline()
                (s, snd_slot, rtt) = str.split(l)
                seq = int(s)
                dump.slottimes[seq] = int(snd_slot)
                dump.rtts[seq] = float(rtt)
                dump.rcv_order[line_count] = seq


            except ValueError:
                break
            except IndexError:
                # specified options.pnum is too small 
                break

            line_count += 1
    except KeyboardInterrupt:
        pass # canceled reading file






    fs.close()
    dump.stats()


    if options.min_rtt==-1:
        options.min_rtt=mean(dump.rtts)

 

def get_slottimes():
    # NOTE: slottimes may contain negative values!
    return dump.slottimes



def dumpreader(pipe, ns, geotimes):
    ''' args=(pipe_in, ctrl_pipe_in, options.eth, options.pnum, geotimes) '''
    
    if ns.cnum:
        pnum = ns.cnum
    else:
        pnum = options.pnum
    


    hphelper.set_affinity('rcvloop')


    # start progress bar thread
    #hphelper.bar_init(options, stats)

    # notify sender that we are ready to capture
    ns.RCV_READY = True
    # block until sender says it is ready
    while not ns.SND_READY:
        time.sleep(0.1)

    if options.DEBUG: print 'READY: ' + __name__



    try:
        for s in dump.rcv_order[:pnum]:
            if s == -1:
                continue
            seq = s
            snd_slot = dump.slottimes[seq]
            rtt = dump.rtts[seq]
            pipe.send((seq, snd_slot, rtt))      # send to parser process 
    except IndexError:
        print s
        print seq
    except KeyboardInterrupt:
        print s
        print 'canceled reading file.'

    # notify parser that we are done
    pipe.send('RCV_DONE')
    #q.close()

    if options.DEBUG: 
        print '\ndone sending: ' + __name__









