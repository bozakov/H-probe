import os
import struct
import time
import code

try:
    import pcap               # python-pypcap
    import numpy as np
except ImportError:
    print "!! please make sure the following packages are installed:"
    print "\tpython-pypcap"    
    print "\tpython-numpy"
    exit(1)

try:
    import gzip
except ImportError:
    pass

import hphelper


options = hphelper.options
DEBUG = hphelper.DEBUG
ERROR = hphelper.err

################################################################################
def rcvloop(data_pipe, ns, geotimes=None):
    """receive ICMP packets from pcap, extract sequence number and
    timestamp and forward to parser over pipe q"""

    if ns.cnum:
        pnum = ns.cnum
    else:
        pnum = options.pnum

    hphelper.set_affinity('rcvloop')
    ttl=None

    struct_unpack = struct.unpack
    def pcap_cb(time, pkt):
        (icmp_type,) = struct_unpack('!B',pkt[34:34+1])
        (seq,slot) = struct_unpack('!LL',pkt[50:58])          # ICMP (offset 34) + 16:50+4+4
        if icmp_type==8:                                    # ICMP echo request
            s_times[seq] = time                             # store send time
        elif icmp_type==0:                                  # ICMP echo reply
            snd_time = s_times[seq]                         # use captured send time to calculate RTT 
            data_pipe.send((seq, slot, time-snd_time))      # send to parser process 
            #(ttl,) = struct_unpack('!B',pkt[22:22+1])        # 14 Ethernet 14 + 8 IP  

    DEBUG('starting receiver ', __name__)

    # init empty numpy arrays to store snd/rcv times
    s_times = -1.0*np.ones(pnum)

    try:
        po = pcap.pcap(options.eth, snaplen=80, immediate=False, timeout_ms=3000) # timeout_ms works with dispatch only
        po.setfilter('(icmp[icmptype] == icmp-echoreply or icmp[icmptype] == icmp-echo) and ip host ' + options.IPDST)
        po_dispatch = po.dispatch
    except OSError as e:
        print e

        exit(-1)
        raise SystemExit(-1)


    # notify sender that we are ready to capture
    ns.RCV_READY = True
    # block until sender says it is ready
    while not ns.SND_READY:
        time.sleep(0.1)

    DEBUG('READY', __name__)
    try:
        while po_dispatch(0, pcap_cb):
            pass
    except KeyboardInterrupt:
        pass

    # timeout_ms was reached, notify parser that we are done
    data_pipe.send('RCV_DONE')
    DEBUG('DONE', __name__)


###############################################################################
def dumploop(pipe, ns, geotimes=None):
    if not dump:
        print 'ERROR: dump file not loaded!'
        return

    if ns.cnum:
        pnum = ns.cnum
    else:
        pnum = options.pnum

    hphelper.set_affinity('rcvloop')


    # notify sender that we are ready to capture
    ns.RCV_READY = True
    # block until sender says it is ready
    while not ns.SND_READY:
        time.sleep(0.1)

    DEBUG('READY', __name__)

    try:
        for s in dump.rcv_order[:pnum]:
            if s == -1:
                continue
            seq = s
            slot = dump.slottimes[seq]
            rtt = dump.rtts[seq]
            pipe.send((seq, slot, rtt))      # send to parser process 
    except IndexError:
        print s
        print seq
    except KeyboardInterrupt:
        print s
        print 'canceled reading file.'

    # notify parser that we are done
    pipe.send('RCV_DONE')
    #q.close()
    DEBUG('done ',  __name__)



class dumpdata(object):
    """ Store the data loaded from a dumped trace file. """
    def __init__(self, options):
        self.slottimes = -1*np.ones(options.pnum).astype(int)
        self.rcv_order = -1*np.ones(options.pnum).astype(int)
        self.rtts = np.zeros(options.pnum)  
        self.dump_options = None

    def pprint(self):
        print 'loaded %d samples (dump mean %.6f)\n' % (np.sum(self.rcv_order!=-1), np.mean(self.rtts))



def dump_loader():
    print "loading RTTs from " + options.loaddump 

    try:
        if options.loaddump[-2:].lower()=='gz':
            fs = gzip.open(options.loaddump, mode='r')
        else:
            fs = open(options.loaddump, mode='r')
        # first line should be a comment containing options
        l = fs.readline() 
        (c, opt_key, opt_str) = str.split(l,' ',2)
    except IOError as e:
        print 'error reading dump file'
        print e
        raise SystemExit(1)
    except Exception as e:
        print 'error parsing dump file'
        raise SystemExit(1)

    dump = dumpdata(options)
    #o=options
    #code.interact(local=locals())

    try:
        dump.dump_options = eval(opt_str) # TODO replace with json
        # set some options loaded from the dump file
        options.IPDST = dump.dump_options['IPDST']
        options.DST = dump.dump_options['DST']
        options.pnum = min(dump.dump_options['pnum'],options.pnum)
        options.plen = dump.dump_options['plen']
        options.delta = dump.dump_options['delta']
        options.tag = dump.dump_options['tag'] + options.tag
        options.start_time = dump.dump_options['start_time']
    except KeyError as ke:
        pass
    except SyntaxError as se:
        print 'could not parse options'
        print se


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
            except ValueError as e:
                print e
                break
            except IndexError:
                # specified options.pnum is too small 
                break
            line_count += 1
    except KeyboardInterrupt:
        pass # canceled reading file

    fs.close()
    dump.pprint()

    if options.min_rtt==-1:
        options.min_rtt = np.mean(dump.rtts)

    return dump



if options.loaddump:
    dump = dump_loader()
    options.tag += '_offline'
