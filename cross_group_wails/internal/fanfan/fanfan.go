package fanfan

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"unsafe"

	"golang.org/x/sys/windows"
)

// DetectResult is the user-facing install/process status.
type DetectResult struct {
	ResolvedPath   string `json:"resolvedPath"`
	PathValid      bool   `json:"pathValid"`
	PathKind       string `json:"pathKind"`
	Message        string `json:"message"`
	ProcessRunning bool   `json:"processRunning"`
}

var processNames = []string{
	"napcatwinbootmain.exe",
	"napimain.exe",
}

func exists(p string) bool {
	st, err := os.Stat(p)
	return err == nil && !st.IsDir()
}

func kindOf(dir string) string {
	if exists(filepath.Join(dir, "NapCatWinBootMain.exe")) {
		return "shell"
	}
	if exists(filepath.Join(dir, "napimain.exe")) {
		return "framework"
	}
	if exists(filepath.Join(dir, "launcher-user.bat")) || exists(filepath.Join(dir, "launcher.bat")) {
		return "shell"
	}
	if exists(filepath.Join(dir, "napiLoader.bat")) {
		return "framework"
	}
	return ""
}

// IsValidInstall reports whether dir looks like a fanfan (NapCat shell/framework) folder.
func IsValidInstall(dir string) bool {
	dir = strings.TrimSpace(dir)
	if dir == "" {
		return false
	}
	if !exists(filepath.Join(dir, "napcat.mjs")) && !exists(filepath.Join(dir, "napcat.cjs")) {
		return false
	}
	return kindOf(dir) != ""
}

// ResolveInstall accepts an install folder or its parent (NapCatQQ-src).
func ResolveInstall(dir string) (resolved string, kind string, ok bool) {
	dir = strings.TrimSpace(dir)
	if dir == "" {
		return "", "", false
	}
	abs, err := filepath.Abs(dir)
	if err != nil {
		return dir, "", false
	}
	if IsValidInstall(abs) {
		return abs, kindOf(abs), true
	}
	for _, sub := range []string{"NapCat.Shell", "NapCat.Framework"} {
		p := filepath.Join(abs, sub)
		if IsValidInstall(p) {
			return p, kindOf(p), true
		}
	}
	return abs, "", false
}

func ProcessRunning() bool {
	want := map[string]struct{}{}
	for _, n := range processNames {
		want[n] = struct{}{}
	}
	snap, err := windows.CreateToolhelp32Snapshot(windows.TH32CS_SNAPPROCESS, 0)
	if err != nil {
		return false
	}
	defer windows.CloseHandle(snap)

	var pe windows.ProcessEntry32
	pe.Size = uint32(unsafe.Sizeof(pe))
	if err := windows.Process32First(snap, &pe); err != nil {
		return false
	}
	for {
		name := strings.ToLower(windows.UTF16ToString(pe.ExeFile[:]))
		if _, ok := want[name]; ok {
			return true
		}
		if err := windows.Process32Next(snap, &pe); err != nil {
			break
		}
	}
	return false
}

// Detect inspects a chosen directory and whether the process is running.
func Detect(dir string) DetectResult {
	running := ProcessRunning()
	resolved, kind, ok := ResolveInstall(dir)
	res := DetectResult{
		ResolvedPath:   resolved,
		PathValid:      ok,
		PathKind:       kind,
		ProcessRunning: running,
	}
	switch {
	case dir == "" && !running:
		res.Message = "\u672a\u6307\u5b9a\u996d\u996d\u5b9a\u5236\u8def\u5f84"
	case !ok && !running:
		res.Message = "\u672a\u68c0\u6d4b\u5230\u996d\u996d\u5b9a\u5236\uff08\u8bf7\u9009\u62e9\u5305\u542b launcher \u6216 napcat.mjs \u7684\u76ee\u5f55\uff09"
	case !ok && running:
		res.Message = "\u8fdb\u7a0b\u5df2\u5728\u8fd0\u884c\uff0c\u4f46\u6307\u5b9a\u76ee\u5f55\u65e0\u6548"
	case ok && running:
		res.Message = "\u5df2\u68c0\u6d4b\u5230\u996d\u996d\u5b9a\u5236\uff0c\u8fdb\u7a0b\u8fd0\u884c\u4e2d"
	default:
		res.Message = "\u76ee\u5f55\u6709\u6548\uff0c\u5f53\u524d\u672a\u8fd0\u884c"
	}
	return res
}

func launcherOf(dir string) string {
	for _, name := range []string{"launcher-user.bat", "launcher.bat", "napiLoader.bat"} {
		p := filepath.Join(dir, name)
		if exists(p) {
			return p
		}
	}
	for _, name := range []string{"NapCatWinBootMain.exe", "napimain.exe"} {
		p := filepath.Join(dir, name)
		if exists(p) {
			return p
		}
	}
	return ""
}

// Launch starts the client from the given install directory (detached).
func Launch(dir string) error {
	resolved, _, ok := ResolveInstall(dir)
	if !ok {
		return os.ErrNotExist
	}
	target := launcherOf(resolved)
	if target == "" {
		return os.ErrNotExist
	}
	cmd := exec.Command("cmd.exe", "/C", "start", "", target)
	cmd.Dir = resolved
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	return cmd.Start()
}
