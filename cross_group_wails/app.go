package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	goruntime "runtime"
	"strconv"
	"strings"
	"sync/atomic"

	"github.com/wailsapp/wails/v2/pkg/runtime"
	"golang.org/x/sys/windows/registry"

	"cross_group_wails/internal/applog"
	"cross_group_wails/internal/config"
	"cross_group_wails/internal/service"
	"cross_group_wails/internal/tray"
	"cross_group_wails/internal/window"
)

const (
	fallbackAppVersion = "1.0.0"
	wailsVersion       = "2.12.0"
	frontendVersion    = "1.0.0"
)

type AppInfo struct {
	AppVersion      string `json:"appVersion"`
	WailsVersion    string `json:"wailsVersion"`
	GoVersion       string `json:"goVersion"`
	FrontendVersion string `json:"frontendVersion"`
	PythonVersion   string `json:"pythonServiceVersion"`
	LogsDir         string `json:"logsDir"`
}

type DiagnosticItem struct {
	Label string `json:"label"`
	Value string `json:"value"`
	OK    bool   `json:"ok"`
}

type App struct {
	ctx      context.Context
	sidecar  *service.Manager
	quitting atomic.Bool
}

func NewApp() *App {
	return &App{
		sidecar: service.NewManager(""),
	}
}

func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
	applog.Init()
	applog.Info("app startup")
	window.StartFocusListener(func() {
		a.ShowMainWindow()
	})
	tray.Start(tray.Hooks{
		OnShow:    a.ShowMainWindow,
		OnRestart: a.RestartApp,
		OnQuit:    a.QuitApp,
	})
}

func (a *App) domReady(ctx context.Context) {
	a.ctx = ctx
}

func (a *App) beforeClose(ctx context.Context) (prevent bool) {
	if a.quitting.Load() {
		applog.Info("app beforeClose: quitting, shutting down sidecar if owned")
		a.sidecar.Shutdown()
		return false
	}
	applog.Info("app beforeClose: hide to tray")
	runtime.WindowHide(ctx)
	return true
}

// ShowMainWindow brings the main window to the foreground.
func (a *App) ShowMainWindow() {
	if a.ctx == nil {
		return
	}
	runtime.WindowUnminimise(a.ctx)
	runtime.WindowShow(a.ctx)
	window.FocusMain(a.ctx)
}

// HideToTray hides the main window; the app keeps running in the tray.
func (a *App) HideToTray() {
	if a.ctx == nil {
		return
	}
	runtime.WindowHide(a.ctx)
}

// QuitApp fully exits the application (tray "退出").
func (a *App) QuitApp() {
	if !a.quitting.CompareAndSwap(false, true) {
		return
	}
	applog.Info("quit from tray/request")
	a.sidecar.Shutdown()
	tray.Quit()
	if a.ctx != nil {
		runtime.Quit(a.ctx)
	}
}

// RestartApp relaunches this executable after a short delay, then quits.
func (a *App) RestartApp() {
	if !a.quitting.CompareAndSwap(false, true) {
		return
	}
	applog.Info("restart requested")
	a.sidecar.Shutdown()
	tray.Quit()
	window.ReleaseSingleInstance()

	exe, err := os.Executable()
	if err != nil {
		applog.Error("restart: executable path: %v", err)
		if a.ctx != nil {
			runtime.Quit(a.ctx)
		}
		return
	}
	exe, _ = filepath.Abs(exe)
	// Detach a delayed start so the new process starts after this instance exits.
	script := fmt.Sprintf(
		"Start-Sleep -Milliseconds 800; Start-Process -FilePath '%s' -WorkingDirectory '%s'",
		strings.ReplaceAll(exe, "'", "''"),
		strings.ReplaceAll(filepath.Dir(exe), "'", "''"),
	)
	cmd := exec.Command("powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script)
	if err := cmd.Start(); err != nil {
		applog.Error("restart: start failed: %v", err)
	}
	if a.ctx != nil {
		runtime.Quit(a.ctx)
	}
}

func (a *App) EnsureBackend() service.BootstrapStatus {
	return a.sidecar.EnsureBackend()
}

func (a *App) ProbeHealth() service.BootstrapStatus {
	return a.sidecar.ProbeHealthStatus()
}

func (a *App) ShutdownBackend() {
	a.sidecar.Shutdown()
}

func (a *App) OpenLogsDir() error {
	return exec.Command("explorer", config.LogsDir()).Start()
}

func (a *App) GetAppInfo() AppInfo {
	pythonVer := ""
	health := service.ProbeHealth()
	if health.Probe == service.ProbeReady {
		pythonVer = health.Version
	}

	return AppInfo{
		AppVersion:      readAppVersion(),
		WailsVersion:    wailsVersion,
		GoVersion:       goruntime.Version(),
		FrontendVersion: frontendVersion,
		PythonVersion:   pythonVer,
		LogsDir:         config.LogsDir(),
	}
}

// SaveFileDialog opens a native save dialog and returns the chosen path (empty if cancelled).
func (a *App) SaveFileDialog(defaultFilename string) (string, error) {
	if a.ctx == nil {
		return "", nil
	}
	if strings.TrimSpace(defaultFilename) == "" {
		defaultFilename = "export.txt"
	}
	return runtime.SaveFileDialog(a.ctx, runtime.SaveDialogOptions{
		Title:           "导出文件",
		DefaultFilename: defaultFilename,
		Filters: []runtime.FileFilter{
			{DisplayName: "Text Files (*.txt)", Pattern: "*.txt"},
			{DisplayName: "All Files (*.*)", Pattern: "*.*"},
		},
	})
}

// ExportLogs shows a save dialog and writes content to the chosen path.
func (a *App) ExportLogs(content string) (string, error) {
	path, err := a.SaveFileDialog("logs-export.txt")
	if err != nil {
		return "", err
	}
	if path == "" {
		return "", nil
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		applog.Error("ExportLogs write failed: %v", err)
		return "", err
	}
	applog.Info("logs exported to %s", path)
	return path, nil
}

func (a *App) RunDiagnostics() []DiagnosticItem {
	items := make([]DiagnosticItem, 0, 8)

	wvOK, wvMsg := checkWebView2()
	items = append(items, DiagnosticItem{Label: "WebView2", Value: wvMsg, OK: wvOK})

	sidecarPath := service.ResolveSidecarPath()
	if sidecarPath == "" {
		items = append(items, DiagnosticItem{Label: "Sidecar 文件", Value: "未找到 cross-group-service.exe", OK: false})
	} else {
		items = append(items, DiagnosticItem{Label: "Sidecar 文件", Value: sidecarPath, OK: true})
	}

	health := service.ProbeHealth()
	switch health.Probe {
	case service.ProbeReady:
		items = append(items, DiagnosticItem{Label: "17888 探测", Value: "正常", OK: true})
		items = append(items, DiagnosticItem{Label: "服务标识", Value: health.Service, OK: health.Service == service.ServiceID})
		pidVal := "—"
		if health.PID > 0 {
			pidVal = strconv.Itoa(health.PID)
		}
		items = append(items, DiagnosticItem{Label: "服务 PID", Value: pidVal, OK: health.PID > 0})
		napMsg := health.NapcatMsg
		if napMsg == "" {
			if health.NapcatOnline {
				napMsg = "在线"
			} else {
				napMsg = "离线"
			}
		}
		items = append(items, DiagnosticItem{Label: "饭饭定制", Value: napMsg, OK: health.NapcatOnline})
	case service.ProbePortConflict:
		items = append(items, DiagnosticItem{Label: "17888 探测", Value: health.ConflictMsg, OK: false})
		items = append(items, DiagnosticItem{Label: "服务标识", Value: "冲突/非本服务", OK: false})
		items = append(items, DiagnosticItem{Label: "服务 PID", Value: "—", OK: false})
		items = append(items, DiagnosticItem{Label: "饭饭定制", Value: "未知", OK: false})
	default:
		items = append(items, DiagnosticItem{Label: "17888 探测", Value: "不可用", OK: false})
		items = append(items, DiagnosticItem{Label: "服务标识", Value: "—", OK: false})
		items = append(items, DiagnosticItem{Label: "服务 PID", Value: "—", OK: false})
		items = append(items, DiagnosticItem{Label: "饭饭定制", Value: "未知", OK: false})
	}

	logsOK, logsMsg := checkDirWritable(config.LogsDir())
	items = append(items, DiagnosticItem{Label: "日志目录可写", Value: logsMsg, OK: logsOK})

	cfgOK, cfgMsg := checkConfigWritable()
	items = append(items, DiagnosticItem{Label: "配置可写", Value: cfgMsg, OK: cfgOK})

	return items
}

func readAppVersion() string {
	candidates := []string{}
	if exe, err := os.Executable(); err == nil {
		dir := filepath.Dir(exe)
		candidates = append(candidates,
			filepath.Join(dir, "VERSION"),
			filepath.Join(dir, "..", "VERSION"),
		)
	}
	if wd, err := os.Getwd(); err == nil {
		candidates = append(candidates,
			filepath.Join(wd, "VERSION"),
			filepath.Join(wd, "..", "VERSION"),
		)
	}
	for _, p := range candidates {
		data, err := os.ReadFile(p)
		if err != nil {
			continue
		}
		v := strings.TrimSpace(string(data))
		if v != "" {
			return v
		}
	}
	return fallbackAppVersion
}

func checkWebView2() (bool, string) {
	keys := []struct {
		root registry.Key
		path string
	}{
		{registry.LOCAL_MACHINE, `SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-A6AB-CFDA76A8A9F6}`},
		{registry.LOCAL_MACHINE, `SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-A6AB-CFDA76A8A9F6}`},
		{registry.CURRENT_USER, `SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-A6AB-CFDA76A8A9F6}`},
	}
	for _, k := range keys {
		key, err := registry.OpenKey(k.root, k.path, registry.QUERY_VALUE)
		if err != nil {
			continue
		}
		pv, _, err := key.GetStringValue("pv")
		_ = key.Close()
		if err == nil && pv != "" && pv != "0.0.0.0" {
			return true, "已安装 " + pv
		}
	}

	dirs := []string{
		filepath.Join(os.Getenv("ProgramFiles(x86)"), "Microsoft", "EdgeWebView", "Application"),
		filepath.Join(os.Getenv("ProgramFiles"), "Microsoft", "EdgeWebView", "Application"),
	}
	for _, d := range dirs {
		if st, err := os.Stat(d); err == nil && st.IsDir() {
			return true, d
		}
	}
	return false, "未检测到 WebView2 Runtime"
}

func checkDirWritable(dir string) (bool, string) {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return false, err.Error()
	}
	f, err := os.CreateTemp(dir, ".writetest-*")
	if err != nil {
		return false, err.Error()
	}
	name := f.Name()
	_ = f.Close()
	_ = os.Remove(name)
	return true, dir
}

func checkConfigWritable() (bool, string) {
	path := config.ConfigPath()
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return false, err.Error()
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0o644)
	if err != nil {
		return false, err.Error()
	}
	_ = f.Close()
	return true, path
}
