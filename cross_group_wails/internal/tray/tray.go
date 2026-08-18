package tray

import (
	_ "embed"

	"github.com/getlantern/systray"
)

//go:embed icon.ico
var iconICO []byte

// Hooks are callbacks invoked from the tray menu thread.
type Hooks struct {
	OnShow    func()
	OnRestart func()
	OnQuit    func()
}

// Start runs the system tray in a background goroutine (Windows-safe with Wails).
func Start(h Hooks) {
	go systray.Run(func() {
		systray.SetIcon(iconICO)
		systray.SetTitle("QQ\u8de8\u7fa4\u9080\u8bf7\u5de5\u5177")
		systray.SetTooltip("QQ\u8de8\u7fa4\u9080\u8bf7\u5de5\u5177")

		mShow := systray.AddMenuItem("\u663e\u793a\u4e3b\u754c\u9762", "\u663e\u793a\u4e3b\u754c\u9762")
		mRestart := systray.AddMenuItem("\u91cd\u65b0\u542f\u52a8", "\u91cd\u65b0\u542f\u52a8")
		systray.AddSeparator()
		mQuit := systray.AddMenuItem("\u9000\u51fa", "\u9000\u51fa")

		go func() {
			for {
				select {
				case <-mShow.ClickedCh:
					if h.OnShow != nil {
						h.OnShow()
					}
				case <-mRestart.ClickedCh:
					if h.OnRestart != nil {
						h.OnRestart()
					}
				case <-mQuit.ClickedCh:
					if h.OnQuit != nil {
						h.OnQuit()
					}
					return
				}
			}
		}()
	}, func() {})
}

// Quit stops the tray event loop.
func Quit() {
	systray.Quit()
}
