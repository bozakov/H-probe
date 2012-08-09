import os
import hphelper
import struct
import time

try:
    import pcap               # python-pypcap
    from numpy import *

except ImportError:
    print "!! please make sure the following packages are installed:"
    print "\tpython-pypcap"    
    print "\tpython-numpy"
    exit(1)

options = hphelper.options

################################################################################
def rcvloop(data_pipe, ns, geotimes):
    """receive ICMP packets from pcap, extract sequence number and
    timestamp and forward to parser over pipe q"""


    if ns.cnum:
        pnum = ns.cnum
    else:
        pnum = options.pnum

    hphelper.set_affinity('rcvloop')

    IPDST = options.IPDST

    struct_unpack = struct.unpack
    def pcap_cb(time, pkt):

        (icmp_type,) = struct_unpack('!B',pkt[34:34+1])
        (seq,) = struct_unpack('!L',pkt[50:50+4])           # ICMP (offset 34) + 16

        if icmp_type==8:                                    # ICMP echo request
            s_times[seq] = time
        elif icmp_type==0:                                  # ICMP echo reply
            #r_times[seq] = time
            #snd_time = geotimes[seq]                       # use pre-generated send times rather than the actual send times for RTT 
            snd_time = s_times[seq]                         # use actual send time to calculate RTT 
            data_pipe.send((seq, snd_time, time-snd_time))          # send to parser process 
#            slot = geotimes[seq]
#            data_pipe.send((seq, slot, time-snd_time))          # send to parser process 

    if options.DEBUG:
        print 'starting receiver ' + __name__
    # init empty numpy arrays to store snd/rcv times
    s_times = -1.0*ones(pnum)

    try:
        po = pcap.pcap(options.eth, snaplen=80, immediate=False, timeout_ms=3000) # timeout_ms works with dispatch only
        po.setfilter('(icmp[icmptype] == icmp-echoreply or icmp[icmptype] == icmp-echo) and ip host ' + IPDST)
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

    if options.DEBUG: print 'READY: ' + __name__

    try:
        while po_dispatch(0, pcap_cb):
            pass
    except KeyboardInterrupt:
        pass

    # timeout_ms was reached, notify parser that we are done
    data_pipe.send('RCV_DONE')
    #q.close()
