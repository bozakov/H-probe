# Copyright 2012 IKT Leibniz Universitaet Hannover
# GPL2
# Zdravko Bozakov (zb@ikt.uni-hannover.de)

import code 
import os
import subprocess
import time

try:
    from numpy import *
except ImportError:
    print __name__ + ": please make sure the following packages are installed:"
    print "\tpython-numpy"
    exit(1)

import hphelper

try:
    import setproctitle
    setproctitle.setproctitle('h-probe')
except:
    pass  # Ignore errors, since this is only cosmetic


options = hphelper.options


class gp_plotter(object):
    def __init__(self, loglog=True, ascii=False):

        self.gp = None
        if os.getenv('DISPLAY') is None:
            options.plot = False
            options.no_plot = True
            print 'DIPLAY variable not set'
            return

        self.PLOT_LOG = loglog
        try:
            gnuplot_cmd = 'gnuplot -persist'  #GNUTERM=x11
            x11_opts = '-noraise -persist -background white'
            self.gp = subprocess.Popen(gnuplot_cmd.split() + x11_opts.split(),
                                       stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,  # disable
                                       bufsize=-1)
        except OSError as e:
            print 'could not run gnuplot!'
            print e
            return self.gp


        termopt = ' persist enhanced'
        self.cmd('set term x11' + termopt, flush=True)

        #self.gp.stdout.readline()
        #if self.gp.stdout.readline()[:31] == 'gnuplot: unable to open display':
        #    print 'could not open X11 display'
        #    options.plot = False
        #    options.no_plot = True
        #    return
        #    # TODO this should be fixed
        
        if ascii:
            self.cmd('set term dumb')           # ASCII output

        opt_string = "r=%.3f, l=%d, delta=%.3e" % (options.rate, options.plen, options.delta)
        self.cmd('set title "%s %s ( %s )"' % (options.DST, time.ctime(options.start_time), opt_string ))
        self.cmd("set datafile missing 'nan'")
        if self.PLOT_LOG:
            self.cmd('set log xy')

        self.cmd('set grid front')
        self.cmd('unset key')
        self.cmd('set format y "%.0e"')

        # format plotting styles
        #self.cmd('set linestyle 7 linetype 2 pointsize 0.2 linecolor rgb "green"') 
        self.cmd('set style line 7 lt 2') 
        self.cmd('set style line 3 pointtype 0 pointsize 1.0 linecolor rgb "red"')    
        self.cmd('set style line 8 lt 1 linecolor rgb "blue"')     # blue line

        self.flush()


    def setup(self, **args):
        if not self.gp: return
 
        if 'title' in args:
            self.cmd("set title \"%s\"" % (args['title'],))
        if 'xlabel' in args:
            self.cmd("set xlabel \"%s\"" % (args['xlabel'],))
        if 'ylabel' in args:
            # seems to be buggy when using enhanced
            self.cmd("set ylabel offset character 0, -5 \"%s\"" % (args['ylabel'],))
        if 'xrange' in args:
            self.cmd("set xrange [%f:%f]" % args['xrange'])
        if 'yrange' in args:
            self.cmd("set yrange [%f:%f]" % args['yrange'])
        if 'xtics' in args:
            tstr = ','.join([ '"%.2e" %d' % i for i in args['xtics']])
            self.cmd('set xtics (%s)' % tstr)


    def arrow(self,x1,y1,x2,y2, tag='', ls=7):
        self.cmd('set arrow '+ str(tag) +' from %f,%f to %f,%f nohead ls %d' % (x1,y1,x2,y2,ls))
        self.cmd('show arrow ' + str(tag))


    def level(self,level,x1,x2, min_level=1e-8, ls=7, tag=1):
        ''' plot a box representing a level'''
        self.cmd('set object ' + str(tag) + ' rect from %e,%e to %e,%e' % (x1,min_level,x2,level) )
        self.cmd('set object ' + str(tag) + ' fillcolor rgb "blue" fillstyle  solid 0.075 noborder')
        self.cmd('show object ' + str(tag))

    def label(self,text,x,y,tag=''):
        self.cmd('set label '+ str(tag) +' "%s" at %e,%e\n' % (text, x,y))
        self.cmd('show label ' + str(tag))

    def cmd(self, gp_command, flush=False):
        if self.gp is None:
            return

        if not self.gp.poll() is None:  # None if process is still alive
            raise ValueError('gnuplot error')
            return

        self.gp.stdin.write(gp_command + '\n')
        if flush:
            try:
                self.gp.stdin.flush()
            except IOError:
                raise ValueError('gnuplot error')

    def flush(self):
        self.gp.stdin.flush()

    def quit(self):
        self.cmd('quit\n')

    def set_term_eps(self, fnamebase):
        # save current plot as EPS file

        print "\nsaving plot to " + fnamebase + ".eps ..."
        self.cmd('set terminal postscript eps enhanced')
        self.cmd('set ylabel offset character 0, 0')
        self.cmd('set output "%s.eps"' % fnamebase)
