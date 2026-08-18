package fanfan

import (
	"fmt"
	"net"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
	"golang.org/x/sys/windows/registry"
)

// DetectResult is the user-facing install/process status.
type DetectResult struct {
	ResolvedPath   string `json:"resolvedPath"`
	PathValid      bool   `json:"pathValid"`
	PathKind       string `json:"pathKind"`
	Message        string `json:"message"`
	ProcessRunning bool   `json:"processRunning"`
	ApiOnline      bool   `json:"apiOnline"`
	ApiEndpoint    string `json:"apiEndpoint"`
}

var processNames = []string{
	"napcatwinbootmain.exe",
	"napimain.exe",
	"qq.exe",
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
	if exists(filepath.Join(dir, "napiLoader.bat")) || exists(filepath.Join(dir, "launcher-headed.bat")) {
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
	return processExists(processNames...)
}

func processExists(names ...string) bool {
	want := map[string]struct{}{}
	for _, n := range names {
		want[strings.ToLower(n)] = struct{}{}
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

func tcpOpen(host string, port int) bool {
	if port <= 0 || host == "" {
		return false
	}
	d := net.Dialer{Timeout: 800 * time.Millisecond}
	c, err := d.Dial("tcp", net.JoinHostPort(host, strconv.Itoa(port)))
	if err != nil {
		return false
	}
	_ = c.Close()
	return true
}

func parseOnebotHostPort(onebotURL string) (string, int) {
	u := strings.TrimSpace(onebotURL)
	if u == "" {
		return "127.0.0.1", 6099
	}
	if !strings.Contains(u, "://") {
		u = "http://" + u
	}
	parsed, err := url.Parse(u)
	if err != nil {
		return "127.0.0.1", 6099
	}
	host := parsed.Hostname()
	if host == "" {
		host = "127.0.0.1"
	}
	port := 80
	if parsed.Scheme == "https" {
		port = 443
	}
	if p := parsed.Port(); p != "" {
		if n, err := strconv.Atoi(p); err == nil {
			port = n
		}
	}
	return host, port
}

// ProbeAPI checks whether the WebUI/OneBot port is accepting connections.
func ProbeAPI(onebotURL string) (online bool, endpoint string) {
	host, port := parseOnebotHostPort(onebotURL)
	endpoint = net.JoinHostPort(host, strconv.Itoa(port))
	if tcpOpen(host, port) {
		return true, endpoint
	}
	if port != 6099 && tcpOpen("127.0.0.1", 6099) {
		return true, "127.0.0.1:6099"
	}
	return false, endpoint
}

// Detect inspects install dir, process, and API port.
func Detect(dir string, onebotURL string) DetectResult {
	proc := ProcessRunning()
	apiOnline, endpoint := ProbeAPI(onebotURL)
	resolved, kind, ok := ResolveInstall(dir)
	res := DetectResult{
		ResolvedPath:   resolved,
		PathValid:      ok,
		PathKind:       kind,
		ProcessRunning: proc || apiOnline,
		ApiOnline:      apiOnline,
		ApiEndpoint:    endpoint,
	}
	switch {
	case !ok && !res.ProcessRunning:
		res.Message = "\u672a\u68c0\u6d4b\u5230\u996d\u996d\u5b9a\u5236\uff08\u8bf7\u9009\u62e9\u5b89\u88c5\u76ee\u5f55\u5e76\u542f\u52a8\uff09"
	case ok && apiOnline:
		res.Message = "\u76ee\u5f55\u6709\u6548\uff0cAPI \u5728\u7ebf\uff08" + endpoint + "\uff09"
	case ok && proc && !apiOnline:
		res.Message = "\u8fdb\u7a0b\u5728\u8fd0\u884c\uff0c\u4f46 API \u672a\u5f00\u653e\uff08\u8bf7\u786e\u8ba4\u5df2\u767b\u5f55 QQ\uff0cWebUI \u7aef\u53e3 " + endpoint + "\uff09"
	case ok && !res.ProcessRunning:
		res.Message = "\u76ee\u5f55\u6709\u6548\uff0c\u5f53\u524d\u672a\u8fd0\u884c\uff08\u8bf7\u70b9\u542f\u52a8\u996d\u996d\u5b9a\u5236\uff09"
	case !ok && apiOnline:
		res.Message = "API \u5728\u7ebf\uff08" + endpoint + "\uff09\uff0c\u4f46\u672c\u5730\u76ee\u5f55\u672a\u8bbe\u7f6e"
	default:
		res.Message = "\u8fdb\u7a0b\u5728\u8fd0\u884c"
	}
	return res
}

func findQQExe() (string, error) {
	paths := []string{
		`SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\QQ`,
		`SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\QQ`,
	}
	for _, p := range paths {
		key, err := registry.OpenKey(registry.LOCAL_MACHINE, p, registry.QUERY_VALUE)
		if err != nil {
			continue
		}
		uninstall, _, err := key.GetStringValue("UninstallString")
		_ = key.Close()
		if err != nil || uninstall == "" {
			continue
		}
		uninstall = strings.Trim(uninstall, `"`)
		dir := filepath.Dir(uninstall)
		qq := filepath.Join(dir, "QQ.exe")
		if exists(qq) {
			return qq, nil
		}
	}
	// Common install paths
	for _, c := range []string{
		`D:\Program Files\Tencent\QQNT\QQ.exe`,
		`C:\Program Files\Tencent\QQNT\QQ.exe`,
		`C:\Program Files (x86)\Tencent\QQNT\QQ.exe`,
	} {
		if exists(c) {
			return c, nil
		}
	}
	return "", fmt.Errorf("QQ.exe not found")
}

func killByNames(names ...string) {
	want := map[string]struct{}{}
	for _, n := range names {
		want[strings.ToLower(n)] = struct{}{}
	}
	snap, err := windows.CreateToolhelp32Snapshot(windows.TH32CS_SNAPPROCESS, 0)
	if err != nil {
		return
	}
	defer windows.CloseHandle(snap)
	var pe windows.ProcessEntry32
	pe.Size = uint32(unsafe.Sizeof(pe))
	if err := windows.Process32First(snap, &pe); err != nil {
		return
	}
	for {
		name := strings.ToLower(windows.UTF16ToString(pe.ExeFile[:]))
		if _, ok := want[name]; ok && pe.ProcessID != 0 {
			h, err := windows.OpenProcess(windows.PROCESS_TERMINATE, false, pe.ProcessID)
			if err == nil {
				_ = windows.TerminateProcess(h, 1)
				_ = windows.CloseHandle(h)
			}
		}
		if err := windows.Process32Next(snap, &pe); err != nil {
			break
		}
	}
}

func headedEnvVars() []string {
	return []string{
		"NAPCAT_DISABLE_BYPASS=1",
		"NAPCAT_FORCE_HEADED=1",
		"NAPCAT_PACKET_CAPTURE=1",
		"NAPCAT_ENABLE_VERBOSE_LOG=1",
		"NAPCAT_DEBUG_CONSOLE=0",
	}
}

func killAndWait(names ...string) {
	deadline := time.Now().Add(8 * time.Second)
	for {
		killByNames(names...)
		if !processExists(names...) {
			time.Sleep(400 * time.Millisecond)
			return
		}
		if time.Now().After(deadline) {
			return
		}
		time.Sleep(250 * time.Millisecond)
	}
}

func openVisible(path, dir string) error {
	verb, err := windows.UTF16PtrFromString("open")
	if err != nil {
		return err
	}
	file, err := windows.UTF16PtrFromString(path)
	if err != nil {
		return err
	}
	cwd, err := windows.UTF16PtrFromString(dir)
	if err != nil {
		return err
	}
	return windows.ShellExecute(0, verb, file, nil, cwd, windows.SW_SHOWMINNOACTIVE)
}

func headedLauncherScript(kind string) string {
	common := `@echo off
chcp 65001 >nul
cd /d "%~dp0"
set NAPCAT_WORKDIR=%cd%
set NAPCAT_DISABLE_BYPASS=1
set NAPCAT_FORCE_HEADED=1
set NAPCAT_PACKET_CAPTURE=1
set NAPCAT_ENABLE_VERBOSE_LOG=1
set NAPCAT_DEBUG_CONSOLE=0
title Fanfan Headed QQ

echo Closing existing QQ so headed mode can apply...
taskkill /F /IM QQ.exe >nul 2>&1
taskkill /F /IM napimain.exe >nul 2>&1
taskkill /F /IM NapCatWinBootMain.exe >nul 2>&1
timeout /t 1 /nobreak >nul

set "QQPath="
for /f "tokens=2*" %%a in ('reg query "HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\QQ" /v "UninstallString" 2^>nul') do (
    set "RetString=%%~b"
)
if defined RetString for %%a in ("%RetString%") do set "QQPath=%%~dpaQQ.exe"
if not exist "%QQPath%" if exist "D:\Program Files\Tencent\QQNT\QQ.exe" set "QQPath=D:\Program Files\Tencent\QQNT\QQ.exe"
if not exist "%QQPath%" if exist "C:\Program Files\Tencent\QQNT\QQ.exe" set "QQPath=C:\Program Files\Tencent\QQNT\QQ.exe"
if not exist "%QQPath%" if exist "C:\Program Files (x86)\Tencent\QQNT\QQ.exe" set "QQPath=C:\Program Files (x86)\Tencent\QQNT\QQ.exe"
if not exist "%QQPath%" (
    echo QQ.exe not found. Please install QQ NT first.
    pause
    exit /b 1
)
echo Using QQ: %QQPath%
`
	if kind == "shell" {
		return common + `
set NAPCAT_PATCH_PACKAGE=%cd%\qqnt.json
set NAPCAT_LOAD_PATH=%cd%\loadNapCat.js
set NAPCAT_INJECT_PATH=%cd%\NapCatWinBootHook.dll
set NAPCAT_LAUNCHER_PATH=%cd%\NapCatWinBootMain.exe
set NAPCAT_MAIN_PATH=%cd%\napcat.mjs
set NAPCAT_MAIN_PATH=%NAPCAT_MAIN_PATH:\=/%
echo (async () =^> {await import("file:///%NAPCAT_MAIN_PATH%")})() > "%NAPCAT_LOAD_PATH%"
echo Starting headed Shell...
"%NAPCAT_LAUNCHER_PATH%" "%QQPath%" "%NAPCAT_INJECT_PATH%"
if errorlevel 1 pause
`
	}
	return common + `
set NAPCAT_INJECT_PATH=%cd%\napiloader.dll
set NAPCAT_LAUNCHER_PATH=%cd%\napimain.exe
set NAPCAT_MAIN_PATH=%cd%\nativeLoader.cjs
set NAPCAT_MAIN_PATH=%NAPCAT_MAIN_PATH:\=/%
if not exist "%NAPCAT_LAUNCHER_PATH%" (
    echo napimain.exe not found in this folder.
    pause
    exit /b 1
)
echo Starting headed Framework...
"%NAPCAT_LAUNCHER_PATH%" "%QQPath%" "%NAPCAT_INJECT_PATH%" "%NAPCAT_MAIN_PATH%"
if errorlevel 1 pause
`
}

// Launch starts Framework/Shell in headed mode (QQ window visible).
// It writes launcher-headed.bat and ShellExecute's it so QQ is not a hidden
// child of the Wails GUI process (that path is what made QQ stay headless).
func Launch(dir string) error {
	resolved, kind, ok := ResolveInstall(dir)
	if !ok {
		return os.ErrNotExist
	}
	if _, err := findQQExe(); err != nil {
		return err
	}

	launchKind := kind
	if exists(filepath.Join(resolved, "napimain.exe")) {
		launchKind = "framework"
		if !exists(filepath.Join(resolved, "napiloader.dll")) || !exists(filepath.Join(resolved, "nativeLoader.cjs")) {
			return os.ErrNotExist
		}
	} else if exists(filepath.Join(resolved, "NapCatWinBootMain.exe")) {
		launchKind = "shell"
		if !exists(filepath.Join(resolved, "NapCatWinBootHook.dll")) {
			return os.ErrNotExist
		}
	} else {
		return os.ErrNotExist
	}

	killAndWait("QQ.exe", "napimain.exe", "NapCatWinBootMain.exe")

	bat := filepath.Join(resolved, "launcher-headed.bat")
	script := strings.ReplaceAll(headedLauncherScript(launchKind), "\n", "\r\n")
	if err := os.WriteFile(bat, []byte(script), 0o644); err != nil {
		return err
	}
	if err := openVisible(bat, resolved); err != nil {
		return err
	}
	go RevealQQWindows(45 * time.Second)
	return nil
}
