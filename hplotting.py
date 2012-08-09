# Copyright 2012 IKT Leibniz Universitaet Hannover
# GPL2
# Zdravko Bozakov (zb@ikt.uni-hannover.de)

import subprocess
import hphelper
import time

try:
    from numpy import *

except ImportError:
    print __name__ + ": please make sure the following packages are installed:"
    print "\tpython-numpy"
    exit(1)

options = hphelper.options


    
class gp_plotter(object):
    def __init__(self, loglog=True, ascii=False):

        self.gp = None
        self.PLOT_LOG = loglog
        try:
            self.gp = subprocess.Popen(['gnuplot', '-noraise', '-persist', '-background', 'white'], 
                                       stdin=subprocess.PIPE, 
                                       stderr=subprocess.STDOUT, stdout=subprocess.PIPE,  # disable output
                                       bufsize=-1)
        except Exception as e:
            print e
            return self.gp


        opt_string = "r=%.3f, l=%d, delta=%.3e" % (options.rate, options.plen, options.delta)
        self.cmd('set title "%s %s ( %s )"' % (options.DST, time.ctime(), opt_string ))
        self.cmd("set datafile missing 'nan'")
        if self.PLOT_LOG:
            self.cmd('set log xy')

        self.cmd('set grid')
        self.cmd('unset key')
        self.cmd('set format y "%.0e"')

        # format plotting styles
        #self.cmd('set linestyle 7 linetype 2 pointsize 0.2 linecolor rgb "green"') 
        self.cmd('set style line 7 lt 2') 
        self.cmd('set style line 3 pointtype 0 pointsize 1.0 linecolor rgb "red"')    
        self.cmd('set style line 8 lt 1 linecolor rgb "blue"')     # blue line

        self.cmd('set term x11')
        if ascii:
            self.cmd('set term dumb')           # ASCII output


        self.gp.stdin.flush()


    def setup(self, **args):
        if not self.gp:
            return
 
        if 'title' in args:
            self.cmd("set title \"%s\"" % (args['title'],))
        if 'xlabel' in args:
            self.cmd("set xlabel \"%s\"" % (args['xlabel'],))
        if 'ylabel' in args:
            self.cmd('set ylabel "%s"' % (args['ylabel'],))
        if 'xrange' in args:
            self.cmd("set xrange [%f:%f]" % args['xrange'])
        if 'yrange' in args:
            self.cmd("set yrange [%f:%f]" % args['yrange'])
        if 'xtics' in args:
            tstr = ','.join([ '"%.2e" %d' % i for i in args['xtics']])
            self.cmd('set xtics (%s)' % tstr)


    def arrow(self,x1,y1,x2,y2, tag=''):
        self.cmd('set arrow '+ str(tag) +' from %f,%f to %f,%f nohead ls 7' % (x1,y1,x2,y2))
#        self.cmd('set arrow '+ str(tag) +' from %f,%f to %f,%f nohead lt 7 linecolor rgb "blue"' % (x1,y1,x2,y2))
        self.cmd('show arrow ' + str(tag))

    

    def label(self,text,x,y,tag=''):
        self.cmd('set label '+ str(tag) +' "%s" at %e,%e\n' % (text, x,y))
        self.cmd('show label ' + str(tag))


    def cmd(self,gp_command, flush=False):
        self.gp.stdin.write(gp_command + '\n')
        if flush:
            self.gp.stdin.flush()

    def flush(self):
        self.gp.stdin.flush()

    def quit(self):
        self.cmd('quit\n')


    def set_term_eps(self, fnamebase):
        # save current plot as EPS file
        
        print "\nsaving plot to " + fnamebase + ".eps ..."
        self.cmd("set term push")
        self.cmd("set terminal postscript eps color")
        self.cmd("set output \"%s.eps\"" % fnamebase)




