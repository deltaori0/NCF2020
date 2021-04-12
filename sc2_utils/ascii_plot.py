
import logging
import os
import platform
from pathlib import Path

import numpy as np


def draw_line(values, title=None, print_out=False):
    """
    gnuplot을 이용해서 ascii 문자로 꺽은선 그래프를 그려줌
    GNU plot을 별도로 설치해야 함
    - Windows (C:/Program Files/gnuplot/bin/gnuplot.exe)
    - Linux (/usr/bin/gnuplot)
    설치가 되어있지 않으면 경고 메시지만 출력함
    :param values: value := [(x1, y1), (x2, y2), ...]
    :param title: str, 그래프 위에 표시할 문자열
    :param print_out: bool, True일 때는 반환하는 것과 별개로 그래프를 print 함
    :returns: str, ascii 문자로 만든 그래프
    """
    import subprocess
    import platform
    if platform.system().lower() == 'windows':
        path = 'C:/Program Files (x86)/gnuplot/bin/gnuplot.exe'
        if not Path(path).exists():
            path = 'C:/Program Files/gnuplot/bin/gnuplot.exe'
    else:
        path = "/usr/bin/gnuplot"

    try:
        if 'linux' in platform.system().lower():
            # width = max(50, os.get_terminal_size().columns)
            # width = max(50, os.get_terminal_size().columns - 4)
            width = max(50, os.get_terminal_size().columns - 6)
            height = max(25, os.get_terminal_size().lines / 4)
        else:  # windows
            # width = max(50, os.get_terminal_size().columns - 2)
            width = max(50, os.get_terminal_size().columns - 6)
            height = max(25, os.get_terminal_size().lines / 4)

        gnuplot = subprocess.Popen([path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True)
        input_string = "set term dumb {} {}\n".format(width, height)
        input_string += "set key off\n"

        input_string += "plot "
        input_string += "'-' using 1:2 title 'Line1' with linespoints"
        input_string += '\n'

        xs, ys = zip(*values)
        for i, j in zip(xs, ys):
            input_string += "%f %f\n" % (i, j)
        input_string += "e\n"

        output_string, error_msg = gnuplot.communicate(input_string)

        if title is not None:
            title = '** {} **\n'.format(title.title())
            if 'linux' in platform.system().lower():
                # 불필요한 공백 줄 제거
                # output_string = title + output_string[2 * width:-(width+1)]
                output_string = title + output_string[width:-(width+1)]
            else:  # windows
                output_string = title + output_string[width:-(width+1)]

    except FileNotFoundError:
        logging.warning("Can't find gnuplot")
        sparkline_len = os.get_terminal_size().columns
        if title is not None:
            sparkline_len -= len(title) + 10

        _, ys = zip(*values)

        if len(ys) < sparkline_len:
            sparkline = draw_sparkline(list(ys), max(ys), min(ys))
        else:
            dt = len(ys) // sparkline_len
            ys = [np.mean(ys[i*dt: (i+1)*dt]) for i in range(sparkline_len)]
            sparkline = draw_sparkline(ys, max(ys), min(ys))

        output_string = f'{title}: {sparkline}'

    if print_out:
        print(output_string)

    return output_string


def draw_sparkline(values, max_value, min_value):
    try: bar = u'▁▂▃▄▅▆▇█'
    except: bar = '▁▂▃▄▅▆▇█'
    barcount = len(bar) - 1

    vmin = min(values + [min_value])
    vmax = max(values + [max_value])
    extent = (vmax - vmin + 1e-6)
    sparkline = ''.join(
        bar[int((v - vmin) / extent * barcount)]
        for v in values
    )
    return f'max: {vmax}, min: {vmin}, {sparkline}'


if __name__ == '__main__':

    out = draw_line([[(1, 1), (2, 2)]], title='Test', print_out=True)
    import IPython
    IPython.embed()
