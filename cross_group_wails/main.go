package main

import (
	"embed"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
	"github.com/wailsapp/wails/v2/pkg/options/windows"

	"cross_group_wails/internal/applog"
	"cross_group_wails/internal/window"
)

//go:embed all:frontend/dist
var assets embed.FS

func main() {
	applog.Init()
	window.MustFocusOrExit()

	app := NewApp()

	err := wails.Run(&options.App{
		Title:             "QQ跨群邀请工具",
		Width:             1440,
		Height:            960,
		MinWidth:          1280,
		MinHeight:         820,
		Frameless:         true,
		StartHidden:       false,
		HideWindowOnClose: false,
		BackgroundColour:  &options.RGBA{R: 246, G: 247, B: 243, A: 1},
		AssetServer: &assetserver.Options{
			Assets: assets,
		},
		OnStartup:     app.startup,
		OnDomReady:    app.domReady,
		OnBeforeClose: app.beforeClose,
		Bind: []interface{}{
			app,
		},
		Windows: &windows.Options{
			WebviewIsTransparent: false,
			WindowIsTranslucent:  false,
		},
	})

	if err != nil {
		applog.Error("wails run error: %v", err)
		println("Error:", err.Error())
	}
}
