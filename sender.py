# Copyright 2012 IKT Leibniz Universitaet Hannover
# GPL2
# Zdravko Bozakov (zb@ikt.uni-hannover.de)

import sys
import time
import logging

import hphelper
from hphelper import err, set_affinity 

logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

try:
    from numpy import random as prnd
    import numpy as np

    import pcap               # python-pypcap
    from scapy.all import *
except ImportError:
    print "!! please make sure the following packages are installed:"
    print "\tpython-pypcap"
    print "\tpython-numpy"
    print "\tpython-scapy"
    exit(1)


options = hphelper.options
from hphelper import DEBUG, INFO, ERROR

def checksum(packet):
    """Generates a checksum of a (ICMP) packet. Based on ping.c on
    FreeBSD"""

    #from https://subversion.grenouille.com/svn/pygrenouille/developers/tictactoc/trunk/libs/ping.py

    if len(packet) & 1:                 # any data?
        packet = packet + '\0'          # make null
    words = array.array('h', packet)    # make a signed short array of packet
    sum = 0

    for word in words:
        sum = sum + (word & 0xffff)     # bitwise AND
    hi = sum >> 16                      # bitwise right-shift
    lo = sum & 0xffff                   # bitwise AND
    sum = hi + lo
    sum = sum + (sum >> 16)

    return (~sum) & 0xffff              # bitwise invert + AND



def dummyloop(ns):
    # notify receiver that we are ready to send
    ns.SND_READY=True
    # block until receiver says it is ready
    while not ns.RCV_READY:
        time.sleep(0.1)

    DEBUG('READY', __name__)


################################################################################
def sendloop(ns):
    addr = (options.eth, 0x0800)
    geotimes = options.delta*slottimes

    set_affinity('sendloop')

    timetime = time.time          # faster: http://wiki.python.org/moin/PythonSpeed/PerformanceTips
    time_sleep = time.sleep

 
    if ns.cnum:
        pnum = ns.cnum
    else:
        pnum = options.pnum
        INFO('expected run time', '~%f s (mean inter packet time %.3e s)' % (geotimes[-1], options.delta/options.rate))
        if geotimes[-1]/60/60>4:
            WARN('WARNING', 'stationarity may not hold!')

    try:
        s = socket.socket(socket.PF_PACKET, socket.SOCK_RAW)  # create the raw-socket
        s.bind(addr)                                          # ether type for IP e.g. ('eth1', 0x0800)
        s.setblocking(False)                                  # False = disable blocking
    except socket.error:
        err("could not create raw socket, root privileges are required!")


    # notify receiver that we are ready to send
    ns.SND_READY=True
    # block until receiver says it is ready
    while not ns.RCV_READY:
        time.sleep(0.1)

    DEBUG('READY', __name__)

    busy_sleep = options.delta/10

    payload = '8'*ARRAY_PAYLOAD
    try:
        t_start = timetime()
        geotimes += t_start
        pkt = ''.join([pkts[0],payload])
        for i in xrange(1,pnum):
            #hexdump(pkts[i])
            #Ether(pkts[i]).show2()

            s.send(pkt)
            pkt = ''.join([pkts[i],payload])    # add payload to packet

            while (timetime() < geotimes[i]):
                #time_sleep(busy_sleep)          # TODO we can reduce the load at the expence of accuracy
                pass
        s.send(pkt)                             # send the last prepared packet

    except KeyboardInterrupt:
        pass

    t_total = timetime() - t_start

    print '\a',  
    s.close()                 # close socket
    DEBUG("sender runtime:\t %.8f s" % (t_total))

##############################################################################
# pre-generate probes on import

IP_HDR_LEN    = 20
ETHER_HDR_LEN = 14
ICMP_HDR_LEN  = 8
ARRAY_PLEN    = 100                  # number of packet bytes to store in pkts array
ARRAY_PAYLOAD = max((options.plen + ETHER_HDR_LEN) - ARRAY_PLEN,0) # need to append this number of bytes to the payload while sending
IPDST = options.IPDST



if not options.loaddump:
    print 'generating %i ICMP probes...' % (options.pnum), 
    sys.stdout.flush()

    # store send times as an slot index
    slottimes = np.cumsum(np.random.geometric(options.rate, size=options.pnum)).astype(int)

    # pre-generate all ICMP packets in an numpy array so we do not have to
    # waste time at runtime
    pkts = np.empty(options.pnum, dtype=np.dtype((str, ARRAY_PLEN)))

    try:
        p = Ether()/IP(dst=IPDST, ttl=64)/ICMP(type=8, seq=0, chksum=0)/Raw('8'*(options.plen-ICMP_HDR_LEN-IP_HDR_LEN))     # 8 Byte ICMP header + 20 Byte IP header
        try:
            # generate a packet string which we can modify
            str_p = str(p)
        except socket.error:
            err("scapy needs root privileges!")

        hdr = str_p[:ETHER_HDR_LEN+IP_HDR_LEN]
        pkt = str_p[ETHER_HDR_LEN+IP_HDR_LEN:]
        psize = options.plen + ETHER_HDR_LEN

        # packet and format 
        p = [ hdr, 
              pkt[:2], 
              struct.pack('<H', (0)),                           # p[2] = ICMP checksum
              pkt[4:16], 
              struct.pack('!L', (0) % 0xFFFFFFFF),              # p[4] = sequence number (4 bytes)
              struct.pack('!L', (0) % 0xFFFFFFFF),              # p[5] = slot number (4 bytes)
              pkt[16+4+4:]]                                     # payload

        ck = checksum(''.join(p[1:])) & 0xFFFF                  # calculate initial ICMP cksum
        p[2] = struct.pack('H', (ck))                           # update ICMP cksum



        M_ = sum(struct.unpack('HHHH',''.join(p[4:6])))
        j = 0
        for i in xrange(options.pnum):
            j=long(slottimes[i])
            p[4] = struct.pack('!L', (i) % 0xFFFFFFFF)          # increment 4 byte seq ID in ICMP payload
            p[5] = struct.pack('!L', (j) % 0xFFFFFFFF)          # increment 4 byte slot ID in ICMP payload
            M = sum(struct.unpack('HHHH', ''.join(p[4:6])))
            ck = ck + M_ - M

            p[2] = struct.pack('H', (ck) % 0xFFFF)               # update ICMP cksum
            pkts[i] = ''.join(p)[:ARRAY_PLEN]                   # only store first 100 packet bytes 

            M_=M



    except (MemoryError, ValueError):
        err("Not enough memory!",2)
    except KeyboardInterrupt:
        print 'terminated by user.'
        raise SystemExit(-1)

    print 'done'
 


