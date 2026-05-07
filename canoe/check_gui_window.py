import ctypes
import ctypes.wintypes as w
user32 = ctypes.windll.user32
EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
GetWindowText = user32.GetWindowTextW
GetWindowTextLength = user32.GetWindowTextLengthW
IsWindowVisible = user32.IsWindowVisible
wins=[]
def foreach_window(hwnd,lParam):
    if IsWindowVisible(hwnd):
        length = GetWindowTextLength(hwnd)
        if length>0:
            buf = ctypes.create_unicode_buffer(length+1)
            GetWindowText(hwnd, buf, length+1)
            title = buf.value
            if 'LUXOFT' in title or 'CANoe' in title or 'DVT' in title:
                wins.append((hwnd,title))
    return True
EnumWindows(EnumWindowsProc(foreach_window),0)
print(wins)
