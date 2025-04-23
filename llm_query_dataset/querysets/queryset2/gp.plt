set encoding utf8
set termoption noenhanced
set title "* simple rc circuit with 2 r and 1 c"
set xlabel "s"
set ylabel "V"
set grid
unset logscale x 
set xrange [1.000000e-06:1.000000e-02]
unset logscale y 
set yrange [-2.395210e-01:5.249501e+00]
#set xtics 1
#set x2tics 1
#set ytics 1
#set y2tics 1
set format y "%g"
set format x "%g"
plot 'gp.data' using 1:2 with lines lw 1 title "v(2)"
