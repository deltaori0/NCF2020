"""
키보드 이벤트 검출 모듈
"""

__author__ = '박현수(hspark8312@ncsoft.com), NCSOFT Game AI Lab'

import platform
import sys
import time

from IPython import embed


if platform.system() == 'Windows':
    from msvcrt import kbhit
    from msvcrt import getch
 
    def key_event():
        buff = list()
        while kbhit():
            # windows에서는 multi-byte 키를 여러번에 걸쳐 반환함
            buff.append(getch())

        if len(buff) == 1:
            # single byte 문자만 인식
            return ord(buff[0])

elif platform.system() == 'Linux':
    import curses
    import time
 
    def _event(stdscr):
        stdscr.nodelay(True)
        # multi-byte 키를 한번에 반환함
        return stdscr.getch()
 
    _event._last_check_time = time.time()
 
    def key_event():
        if time.time() - _event._last_check_time > 3:
            _event._last_check_time = time.time()
            key = curses.wrapper(_event)
            if 0 <= key <= 256:
                # single byte 문자만 인식
                return key
 

# 현재는 esc만 사용
keymap = {
    27: 'esc',
}

def event(key):
    code = key_event()
    if code is None:
        return False

    pressed = None
    if code in keymap:
        pressed = keymap[code] 
    else:
        pressed = chr(code)
    return key == pressed


if __name__ == '__main__':

    # 키보드 모듈 사용 예
    while True:
        code = key_event()
        if code:
            print(f'키 눌림: {code}, {keymap.get(code)}, {chr(code)}')
        # if event('esc'):
        #     print('!')
        time.sleep(1)
