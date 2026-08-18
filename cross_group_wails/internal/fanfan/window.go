package fanfan

import (
	"strings"
	"syscall"
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
)

const (
	swHide         = 0
	swShow         = 5
	swRestore      = 9
	wsCaption      = 0x00C00000
	wsExToolwindow = 0x00000080
	wsExAppwindow  = 0x00040000
	wsExNoactivate = 0x08000000
	swpNosize      = 0x0001
	swpNomove      = 0x0002
	swpNozorder    = 0x0004
	swpShowwindow  = 0x0040
	gwChild        = 5
	gwHwndNext     = 2
)

func gwlExStyle() uintptr {
	// GWL_EXSTYLE = -20; use uint32 so 32-bit windows/386 builds compile.
	return uintptr(uint32(^uint32(19)))
}

func gwlStyle() uintptr {
	// GWL_STYLE = -16
	return uintptr(uint32(^uint32(15)))
}

var (
	modUser32                    = windows.NewLazySystemDLL("user32.dll")
	procEnumWindows              = modUser32.NewProc("EnumWindows")
	procGetWindowThreadProcessId = modUser32.NewProc("GetWindowThreadProcessId")
	procShowWindow               = modUser32.NewProc("ShowWindow")
	procIsWindowVisible          = modUser32.NewProc("IsWindowVisible")
	procGetWindowRect            = modUser32.NewProc("GetWindowRect")
	procGetWindowLongW           = modUser32.NewProc("GetWindowLongW")
	procSetWindowLongW           = modUser32.NewProc("SetWindowLongW")
	procSetWindowPos             = modUser32.NewProc("SetWindowPos")
	procSetForegroundWindow      = modUser32.NewProc("SetForegroundWindow")
	procIsIconic                 = modUser32.NewProc("IsIconic")
	procGetWindowTextW           = modUser32.NewProc("GetWindowTextW")
	procGetClassNameW            = modUser32.NewProc("GetClassNameW")
	procGetWindow                = modUser32.NewProc("GetWindow")
)

type winRect struct {
	Left, Top, Right, Bottom int32
}

type qqWinInfo struct {
	Title    string
	Class    string
	Width    int32
	Height   int32
	Children int
	Caption  bool
	Tool     bool
	NoAct    bool
	Visible  bool
}

func qqProcessIDs() map[uint32]struct{} {
	want := map[string]struct{}{"qq.exe": {}}
	out := map[uint32]struct{}{}
	snap, err := windows.CreateToolhelp32Snapshot(windows.TH32CS_SNAPPROCESS, 0)
	if err != nil {
		return out
	}
	defer windows.CloseHandle(snap)
	var pe windows.ProcessEntry32
	pe.Size = uint32(unsafe.Sizeof(pe))
	if err := windows.Process32First(snap, &pe); err != nil {
		return out
	}
	for {
		name := strings.ToLower(windows.UTF16ToString(pe.ExeFile[:]))
		if _, ok := want[name]; ok && pe.ProcessID != 0 {
			out[pe.ProcessID] = struct{}{}
		}
		if err := windows.Process32Next(snap, &pe); err != nil {
			break
		}
	}
	return out
}

func utf16BufString(buf []uint16, n uintptr) string {
	if n == 0 {
		return ""
	}
	if int(n) < len(buf) {
		buf = buf[:n]
	}
	return strings.TrimRight(windows.UTF16ToString(buf), "\x00")
}

func windowTitle(hwnd uintptr) string {
	buf := make([]uint16, 256)
	n, _, _ := procGetWindowTextW.Call(hwnd, uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)))
	return utf16BufString(buf, n)
}

func windowClass(hwnd uintptr) string {
	buf := make([]uint16, 256)
	n, _, _ := procGetClassNameW.Call(hwnd, uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)))
	return utf16BufString(buf, n)
}

func childWindowCount(hwnd uintptr) int {
	n := 0
	child, _, _ := procGetWindow.Call(hwnd, gwChild)
	for child != 0 && n < 64 {
		n++
		child, _, _ = procGetWindow.Call(child, gwHwndNext)
	}
	return n
}

func inspectQQWindow(hwnd uintptr) qqWinInfo {
	var rc winRect
	procGetWindowRect.Call(hwnd, uintptr(unsafe.Pointer(&rc)))
	style, _, _ := procGetWindowLongW.Call(hwnd, gwlStyle())
	ex, _, _ := procGetWindowLongW.Call(hwnd, gwlExStyle())
	vis, _, _ := procIsWindowVisible.Call(hwnd)
	return qqWinInfo{
		Title:    windowTitle(hwnd),
		Class:    windowClass(hwnd),
		Width:    rc.Right - rc.Left,
		Height:   rc.Bottom - rc.Top,
		Children: childWindowCount(hwnd),
		Caption:  style&wsCaption != 0,
		Tool:     ex&wsExToolwindow != 0,
		NoAct:    ex&wsExNoactivate != 0,
		Visible:  vis != 0,
	}
}

func isDebugOrHelperQQ(w qqWinInfo) bool {
	low := strings.ToLower(strings.TrimSpace(w.Title))
	return strings.Contains(low, "napcat") ||
		strings.Contains(w.Title, "\u8c03\u8bd5") ||
		strings.Contains(low, "fanfan")
}

func isQQMainUI(w qqWinInfo) bool {
	if w.Width < 240 || w.Height < 280 {
		return false
	}
	if w.NoAct {
		return false
	}
	cls := strings.ToLower(w.Class)
	if !strings.Contains(cls, "chrome_widgetwin") {
		return false
	}
	if isDebugOrHelperQQ(w) {
		return false
	}
	// QQ NT often has an empty title; children or a caption bar still mean real UI.
	return w.Children >= 1 || w.Caption
}

func isStrayQQWindow(w qqWinInfo) bool {
	if w.Width < 80 || w.Height < 80 {
		return false
	}
	if isQQMainUI(w) {
		return false
	}
	if isDebugOrHelperQQ(w) {
		return false
	}
	cls := strings.ToLower(w.Class)
	if !strings.Contains(cls, "chrome_widgetwin") {
		return false
	}
	// Leftover Chromium shells: no child HWND and no caption bar.
	return w.Children == 0 && !w.Caption
}

func promoteQQWindow(hwnd uintptr) {
	style, _, _ := procGetWindowLongW.Call(hwnd, gwlExStyle())
	style = (style &^ wsExToolwindow) | wsExAppwindow
	procSetWindowLongW.Call(hwnd, gwlExStyle(), style)
	iconic, _, _ := procIsIconic.Call(hwnd)
	if iconic != 0 {
		procShowWindow.Call(hwnd, swRestore)
	}
	procShowWindow.Call(hwnd, swShow)
	procSetWindowPos.Call(hwnd, 0, 0, 0, 0, 0, swpNosize|swpNomove|swpShowwindow)
	procSetForegroundWindow.Call(hwnd)
}

func hideStrayQQWindow(hwnd uintptr) {
	style, _, _ := procGetWindowLongW.Call(hwnd, gwlExStyle())
	style = (style &^ wsExAppwindow) | wsExToolwindow
	procSetWindowLongW.Call(hwnd, gwlExStyle(), style)
	procShowWindow.Call(hwnd, swHide)
	procSetWindowPos.Call(hwnd, 0, 0, 0, 0, 0, swpNosize|swpNomove|swpNozorder)
}

// ShowQQWindows unhides the real QQ NT UI and hides Chromium shell/black frames
// that native bypass (and an earlier overly-broad ShowWindow) left in Alt-Tab.
func ShowQQWindows() int {
	pids := qqProcessIDs()
	if len(pids) == 0 {
		return 0
	}
	type hit struct {
		hwnd uintptr
		info qqWinInfo
	}
	var mains, strays, fallbacks []hit
	cb := syscall.NewCallback(func(hwnd uintptr, _ uintptr) uintptr {
		var pid uint32
		procGetWindowThreadProcessId.Call(hwnd, uintptr(unsafe.Pointer(&pid)))
		if _, ok := pids[pid]; !ok {
			return 1
		}
		info := inspectQQWindow(hwnd)
		item := hit{hwnd: hwnd, info: info}
		if isQQMainUI(info) {
			mains = append(mains, item)
			return 1
		}
		if isStrayQQWindow(info) {
			strays = append(strays, item)
			return 1
		}
		cls := strings.ToLower(info.Class)
		if strings.Contains(cls, "chrome_widgetwin") &&
			info.Width >= 240 && info.Height >= 280 &&
			!info.NoAct && !isDebugOrHelperQQ(info) {
			fallbacks = append(fallbacks, item)
		}
		return 1
	})
	procEnumWindows.Call(cb, 0)

	shown := 0
	for _, item := range mains {
		promoteQQWindow(item.hwnd)
		shown++
	}
	if shown == 0 {
		for _, item := range fallbacks {
			promoteQQWindow(item.hwnd)
			shown++
		}
		// Prefer a visible QQ over hiding a misclassified main window.
		if shown == 0 {
			for _, item := range strays {
				if item.info.Width >= 240 && item.info.Height >= 280 {
					promoteQQWindow(item.hwnd)
					shown++
				}
			}
		}
		return shown
	}
	for _, item := range strays {
		if item.info.Visible {
			hideStrayQQWindow(item.hwnd)
		}
	}
	return shown
}

// RevealQQWindows keeps unhiding the real UI and re-hiding stray frames;
// native bypass may re-hide the main window on login.
func RevealQQWindows(d time.Duration) {
	deadline := time.Now().Add(d)
	for time.Now().Before(deadline) {
		_ = ShowQQWindows()
		time.Sleep(400 * time.Millisecond)
	}
}
