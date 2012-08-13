# Copyright 2012 IKT Leibniz Universitaet Hannover
# GPL2
# Zdravko Bozakov (zb@ikt.uni-hannover.de)

import time
import threading
import numpy as np
import os 

options = None

class txt_color:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    DEBUG = '\033[31m'
    ERROR = '\033[34m'
    END = '\033[0m'


class stats_stats:

    rx_total = 0              # total number of valid probes received
    rx_slots = 0              # number of corresonding slots received
    snd_err = 0               # packets dropped at sender
    rcv_err = 0               # packets dropped at receiver
    min_rtt = np.inf
    max_rtt = -np.inf
    sum_rtt = 0.0

    runtime = 0.0
    run_start = 0.0
    run_end = 0.0



    rx_out_of_order = 0

    extra_stats = {}
   

    def __init__(self):
        self.seq = 0

    def runtime(self):
        return (self.run_end - self.run_start)


    def update_seq(self, seq):
        self.seq=seq
       

    def update(self, seq, rtt=np.nan, current_slot=np.nan):
        self.seq=seq
        self.rx_total += 1
        self.sum_rtt += rtt
        self.rx_slots = current_slot

        
    def mean_a(self):
        if self.rx_slots:
            return 1.0*self.rx_total/self.rx_slots


    def mean_rtt(self):
        return 1.0*self.sum_rtt/self.rx_total


    def append_stats(self, **kwargs):
        for k,v in kwargs.iteritems():
            self.extra_stats[k]=v
        

    def pprint(self):
        '''print collected statistics'''
        term_width = 80
        print '-'*term_width
        if self.snd_err:
            print "packets dropped at sender:\t%d" % (self.snd_err,)
        if self.rcv_err:
            print "packets dropped at receiver:\t%d" % (self.rcv_err,)
        print "max sqeuence nr.:\t\t%d" % (self.seq)
        if self.rx_total:
            print "total probes received:\t\t%d" %(self.rx_total)
            print "RTT mean:        \t\t%.6f" % (self.mean_rtt())
        if self.rx_slots:
            print "max. slot received:\t\t%d" % (self.rx_slots)
            print "sample probing intensity:\t%.6f" % (self.mean_a())
        if self.min_rtt!=np.inf:
            print "RTT minimum:         \t\t%.6f" % (self.min_rtt)
        if self.max_rtt!=-np.inf:
            print "RTT maximum:         \t\t%.6f" % (self.max_rtt)
         
        # print any extra statistics
        for k,v in self.extra_stats.iteritems():
            print str(v[0]) + ":\t\t\t" + str(v[1])

        rt = self.runtime()
        if rt:
            print "runtime:\t\t\t%.2f s" % rt
        print '-'*term_width



class fixed_buf(object):
        def __init__(self, len):
            self.buf = ones((len+1,3), dtype='float')*-1.0
            self.left = 0
            self.right = 0
            self.done = False
	def append(self,x):
            self.buf[self.right] = x
            self.right += 1
        def popleft(self):
            if not self.left==self.right:
                self.left += 1    
                return self.buf[self.left-1]
            else:
                raise IndexError


def test_time_res():
    timetime = time.time          # faster: http://wiki.python.org/moin/PythonSpeed/PerformanceTips
 
    t=0
    n=10**5

    for i in xrange(n):
        t += -(timetime()-timetime())
    print 'mean time.time() resolution: %e s\n' % (t/n)




def bar(options, stats, max_seq=None):
        pbar = None
        term_columns = 80

        if max_seq==None:
            max_seq = options.pnum


        try:
            import progressbar
            pbar = progressbar.ProgressBar(term_width=term_columns).start()
        except ImportError:
            return 



        while 1:
            time.sleep(0.5)
            try:
                pbar_percent = stats.seq*100.0/(max_seq)
            except NameError:
                continue

            if pbar:
                pbar.update(pbar_percent)
            else:
                print stats.seq


def bar_init(options, stats, max_seq=None):
	# start progress bar thread
	pbar_thread = threading.Thread(target=bar, args=(options,stats,max_seq))
	pbar_thread.daemon = True
        pbar_thread.start()



def set_affinity(ppid):
    """ Attemts to set the affinity of the caller process to the CPU
    specified in options.CPUID. CPUID must be initialized, e.g., using
    load_process_affinities.

    Args:
        ppid: A string containing the name of the caller process. Must 
              be either 'rcvloop','sendloop','parser' or 'main'.
        
    """
    if options.CPUID:
        CPUID = options.CPUID
    else:
        return

    pid = os.getpid()


    try:
        import affinity
        # CPUID contains the CPU number for each process id
        # (e.g. parser:2). The pid of the current process is pinned to
        # the corresponding CPU
        affinity.set_process_affinity_mask(pid, CPUID[ppid])
    except (ImportError, KeyError):
        DEBUG('could not set CPU affinity')

    
    DEBUG('CPU=%d:\t process [%s] (PID=%d)' % (CPUID[ppid], ppid, pid))



def load_process_affinities():
    # CPU pinning/affinity mapping:      'process': CPUID (bitmask)
    #
    # 1:0001 -> CPU 1/4
    # 2:0010 -> CPU 2/4
    # 4:0100 -> CPU 3/4
    # 8:1000 -> CPU 4/4

    mapfile = 'affinity.map'
    keys = ['rcvloop','sendloop','parser','main'] # required keys

    CPUID={}
    defaults = {'rcvloop':1,'sendloop':2,'parser':1,'main':1}
    try:
        f = open(mapfile, mode='r')
        for line in f:
            (pid, cpuid) = str.split(line)
            CPUID[pid] = int(cpuid)
        f.close()
    except IOError as e:
        DEBUG(mapfile + ' not found')
        return defaults
    except ValueError as e:
        pass

    if all([k in keys for k in CPUID.iterkeys()]):
        DEBUG('loaded: ' + str(CPUID))
        return CPUID
    else:
        return defaults

        

def err(errortext, module_name='', errcode=1):
    print txt_color.ERROR + 'ERROR' + txt_color.END + ':\t%s' % (errortext)
    raise SystemExit(errcode)


def DEBUG(infotext, module_name='', level=1):
    if module_name:
        module_name = ' [' + module_name + ']'
    if options.DEBUG:
        print txt_color.DEBUG + 'DEBUG' + txt_color.END + '{0:<27}{1}'.format(module_name+':', infotext)
