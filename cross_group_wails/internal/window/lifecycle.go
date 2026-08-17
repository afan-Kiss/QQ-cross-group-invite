package window

import (
	"context"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

func FocusMain(ctx context.Context) {
	runtime.WindowUnminimise(ctx)
	runtime.WindowShow(ctx)
}
