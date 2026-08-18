package fanfan

import "testing"

func TestIsQQMainUI(t *testing.T) {
	main := qqWinInfo{
		Title:    "QQ",
		Class:    "Chrome_WidgetWin_1",
		Width:    1440,
		Height:   759,
		Children: 3,
		Caption:  true,
	}
	if !isQQMainUI(main) {
		t.Fatal("expected main QQ window")
	}
	login := qqWinInfo{
		Title:    "QQ",
		Class:    "Chrome_WidgetWin_1",
		Width:    320,
		Height:   460,
		Children: 1,
		Caption:  true,
	}
	if !isQQMainUI(login) {
		t.Fatal("expected QQ login window")
	}
	untitled := qqWinInfo{
		Title:    "",
		Class:    "Chrome_WidgetWin_1",
		Width:    1440,
		Height:   759,
		Children: 2,
		Caption:  true,
	}
	if !isQQMainUI(untitled) {
		t.Fatal("empty-title NT main window with children must stay visible")
	}
	captionOnly := qqWinInfo{
		Title:    "",
		Class:    "Chrome_WidgetWin_1",
		Width:    900,
		Height:   600,
		Children: 0,
		Caption:  true,
	}
	if !isQQMainUI(captionOnly) {
		t.Fatal("captioned chrome window must be treated as the QQ UI")
	}
}

func TestIsStrayQQWindowBlackFrames(t *testing.T) {
	empty := qqWinInfo{
		Title:    "",
		Class:    "Chrome_WidgetWin_1",
		Width:    1440,
		Height:   759,
		Children: 0,
		Visible:  true,
	}
	if !isStrayQQWindow(empty) {
		t.Fatal("empty-title chrome frame should be hidden")
	}
	if isQQMainUI(empty) {
		t.Fatal("empty-title must not be treated as main UI")
	}
	noChild := qqWinInfo{
		Title:    "QQ",
		Class:    "Chrome_WidgetWin_1",
		Width:    800,
		Height:   600,
		Children: 0,
		Visible:  true,
	}
	if !isStrayQQWindow(noChild) {
		t.Fatal("title-only chrome shell should be hidden")
	}
	debug := qqWinInfo{
		Title:    "NapCat QQ " + string([]rune{0x8c03, 0x8bd5, 0x63a7, 0x5236, 0x53f0}),
		Class:    "Chrome_WidgetWin_1",
		Width:    993,
		Height:   519,
		Children: 2,
		Visible:  true,
	}
	if isQQMainUI(debug) {
		t.Fatal("debug console is not the QQ UI")
	}
	if isStrayQQWindow(debug) {
		t.Fatal("debug console should not be force-hidden as a stray black frame")
	}
}
