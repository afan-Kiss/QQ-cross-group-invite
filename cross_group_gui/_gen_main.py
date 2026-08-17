# -*- coding: utf-8 -*-
from pathlib import Path

OUT = Path(__file__).with_name("main.go")

S = {
    "owner": "\\u7fa4\\u4e3b",
    "admin": "\\u7ba1\\u7406\\u5458",
    "member": "\\u6210\\u5458",
    "unknown": "\\u672a\\u77e5",
    "err": "\\u51fa\\u9519\\u4e86",
    "title": "\\u8de8\\u7fa4\\u9080\\u8bf7\\u52a9\\u624b",
    "detect": "\\u25cf \\u6b63\\u5728\\u8fde\\u63a5\\u540e\\u53f0...",
    "settings": "\\u57fa\\u672c\\u8bbe\\u7f6e",
    "target": "\\u8981\\u62c9\\u8fdb\\u54ea\\u4e2a\\u7fa4",
    "source": "\\u4ece\\u54ea\\u4e2a\\u7fa4\\u62c9\\u4eba",
    "count": "\\u4e00\\u6b21\\u62c9\\u51e0\\u4e2a\\u4eba",
    "interval": "\\u6bcf\\u6b21\\u95f4\\u9694\\uff08\\u6beb\\u79d2\\uff09",
    "filter": "\\u4e0d\\u62c9\\u7fa4\\u4e3b\\u548c\\u7ba1\\u7406\\u5458",
    "load": "\\u52a0\\u8f7d\\u6210\\u5458\\u5217\\u8868",
    "start": "\\u5f00\\u59cb\\u9080\\u8bf7",
    "stop": "\\u505c\\u6b62",
    "ready": "\\u51c6\\u5907\\u597d\\u4e86",
    "members": "\\u53ef\\u9080\\u8bf7\\u7684\\u6210\\u5458",
    "nick": "\\u6635\\u79f0",
    "role": "\\u8eab\\u4efd",
    "status": "\\u5f53\\u524d\\u8fdb\\u5ea6",
    "wait": "\\u8fd8\\u6ca1\\u5f00\\u59cb",
    "log_tab": "\\u8fd0\\u884c\\u65e5\\u5fd7",
    "freq_tab": "\\u64cd\\u4f5c\\u592a\\u9891\\u7e41",
    "freq_hint": "\\u4ee5\\u4e0b\\u4eba\\u5458\\u89e6\\u53d1\\u9891\\u7e41\\u9650\\u5236\\uff08QQ \\u00b7 \\u6635\\u79f0 \\u00b7 \\u539f\\u56e0\\uff09",
    "err_tab": "\\u9080\\u8bf7\\u5931\\u8d25",
    "err_hint": "\\u4ee5\\u4e0b\\u4eba\\u5458\\u9080\\u8bf7\\u5931\\u8d25\\uff08QQ \\u00b7 \\u6635\\u79f0 \\u00b7 \\u539f\\u56e0\\uff09",
    "svc_ok": " \\u540e\\u53f0\\u5df2\\u8fde\\u63a5",
    "svc_no": "\\u25cb \\u540e\\u53f0\\u672a\\u542f\\u52a8",
    "fill": "\\u8bf7\\u586b\\u5199\\u6b63\\u786e\\u7684%s",
    "tip": "\\u63d0\\u793a",
    "start_svc": "\\u8bf7\\u5148\\u53cc\\u51fb\\u300c\\u542f\\u52a8\\u8de8\\u7fa4\\u9080\\u8bf7\\u52a9\\u624b_Walk\\u7248.bat\\u300d\\n\\u7b49\\u540e\\u53f0\\u542f\\u52a8\\u540e\\u518d\\u8bd5\\u3002",
    "start_svc2": "\\u8bf7\\u5148\\u542f\\u52a8\\u540e\\u53f0\\uff08\\u53cc\\u51fb Walk \\u7248\\u542f\\u52a8\\u811a\\u672c\\uff09",
    "loading": "\\u6b63\\u5728\\u52a0\\u8f7d\\u6210\\u5458...",
    "load_fail": "\\u52a0\\u8f7d\\u5931\\u8d25",
    "loaded": "\\u5df2\\u52a0\\u8f7d %d \\u4eba",
    "invite_count": "\\u9080\\u8bf7\\u4eba\\u6570",
    "interval_ms": "\\u95f4\\u9694\\u6beb\\u79d2",
    "starting": "\\u6b63\\u5728\\u542f\\u52a8...",
    "start_fail": "\\u542f\\u52a8\\u5931\\u8d25",
    "progress": "%s  |  \\u5df2\\u5b8c\\u6210 %d/%d  \\u6210\\u529f %d  \\u9891\\u7e41 %d  \\u5931\\u8d25 %d",
    "inviting": "\\u6b63\\u5728\\u9080\\u8bf7: %s\\uff08QQ %d\\uff09",
    "target_name": "\\u76ee\\u6807\\u7fa4\\u53f7",
    "source_name": "\\u6765\\u6e90\\u7fa4\\u53f7",
    "no_members": "\\u8bf7\\u5148\\u52a0\\u8f7d\\u6210\\u5458\\u5217\\u8868\\uff0c\\u6216\\u586b\\u5199\\u9080\\u8bf7\\u4eba\\u6570\\u3002",
    "done_ready": "\\u51c6\\u5907\\u597d\\u4e86",
    "same_group": "\\u76ee\\u6807\\u7fa4\\u548c\\u6765\\u6e90\\u7fa4\\u4e0d\\u80fd\\u76f8\\u540c",
    "zero_members": "\\u6ca1\\u6709\\u52a0\\u8f7d\\u5230\\u53ef\\u9080\\u8bf7\\u6210\\u5458\\u3002\\u8bf7\\u68c0\\u67e5\\u7fa4\\u53f7\\u662f\\u5426\\u6b63\\u786e\\uff0c\\u6216\\u786e\\u8ba4 NapCat \\u5728\\u7ebf\\u3002",
    "loading_wait": "\\u6b63\\u5728\\u52a0\\u8f7d\\u4e2d\\uff0c\\u8bf7\\u7a0d\\u5019",
}

go = r'''//go:build windows

package main

import (
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/lxn/walk"
	. "github.com/lxn/walk/declarative"
)

var (
	colorBg      = walk.RGB(255, 250, 243)
	colorPanel   = walk.RGB(255, 248, 238)
	colorText    = walk.RGB(92, 72, 58)
	colorMuted   = walk.RGB(160, 140, 125)
	colorSuccess = walk.RGB(118, 178, 132)
	colorWarn    = walk.RGB(230, 168, 88)
	colorError   = walk.RGB(218, 118, 108)
)

type MemberModel struct {
	walk.TableModelBase
	items []Member
}

func (m *MemberModel) RowCount() int { return len(m.items) }

func (m *MemberModel) Value(row, col int) any {
	if row < 0 || row >= len(m.items) {
		return ""
	}
	it := m.items[row]
	switch col {
	case 0:
		return strconv.FormatInt(it.QQ, 10)
	case 1:
		return it.Nickname
	case 2:
		return roleLabel(it.Role)
	default:
		return ""
	}
}

func roleLabel(r string) string {
	switch r {
	case "owner":
		return "%(owner)s"
	case "admin":
		return "%(admin)s"
	case "member":
		return "%(member)s"
	default:
		return "%(unknown)s"
	}
}

type MainApp struct {
	api          *APIClient
	mw           *walk.MainWindow
	memberModel  *MemberModel
	members      []Member
	statusLabel  *walk.Label
	connLabel    *walk.Label
	progressBar  *walk.ProgressBar
	statLabel    *walk.Label
	logEdit      *walk.TextEdit
	frequentList *walk.ListBox
	errorList    *walk.ListBox
	pulseOn      bool

	targetEdit   *walk.LineEdit
	sourceEdit   *walk.LineEdit
	countEdit    *walk.LineEdit
	intervalEdit *walk.LineEdit
	filterCheck  *walk.CheckBox
	loadBtn      *walk.PushButton
	startBtn     *walk.PushButton
	stopBtn      *walk.PushButton
	loading      bool
}

func main() {
	app := &MainApp{api: NewAPIClient(), memberModel: &MemberModel{}}
	if err := app.build(); err != nil {
		walk.MsgBox(nil, "%(err)s", err.Error(), walk.MsgBoxIconError)
	}
}

func (a *MainApp) build() error {
	fontUI := Font{Family: "Microsoft YaHei UI", PointSize: 10}
	fontTitle := Font{Family: "Microsoft YaHei UI", PointSize: 13, Bold: true}
	fontSmall := Font{Family: "Microsoft YaHei UI", PointSize: 9}

	if err := (MainWindow{
		AssignTo:   &a.mw,
		Title:      "%(title)s",
		MinSize:    Size{Width: 920, Height: 780},
		Size:       Size{Width: 980, Height: 820},
		Layout:     VBox{Margins: Margins{14, 12, 14, 12}, Spacing: 8},
		Background: SolidColorBrush{Color: colorBg},
		Children: []Widget{
			Composite{
				Layout:     HBox{Margins: Margins{10, 8, 10, 8}, Spacing: 12},
				Background: SolidColorBrush{Color: colorPanel},
				Children: []Widget{
					Label{Font: fontTitle, Text: "%(title)s", TextColor: colorText},
					HSpacer{},
					Label{AssignTo: &a.connLabel, Font: fontSmall, Text: "%(detect)s", TextColor: colorMuted},
				},
			},
			GroupBox{
				Title:      "%(settings)s",
				Font:       fontUI,
				Layout:     Grid{Columns: 4, Spacing: 10},
				Background: SolidColorBrush{Color: colorPanel},
				Children: []Widget{
					Label{Text: "%(target)s", TextColor: colorText, Row: 0, Column: 0},
					LineEdit{AssignTo: &a.targetEdit, Row: 0, Column: 1, MinSize: Size{180, 0}},
					Label{Text: "%(source)s", TextColor: colorText, Row: 0, Column: 2},
					LineEdit{AssignTo: &a.sourceEdit, Row: 0, Column: 3, MinSize: Size{180, 0}},
					Label{Text: "%(count)s", TextColor: colorText, Row: 1, Column: 0},
					LineEdit{AssignTo: &a.countEdit, Text: "10", Row: 1, Column: 1, MinSize: Size{120, 0}},
					Label{Text: "%(interval)s", TextColor: colorText, Row: 1, Column: 2},
					LineEdit{AssignTo: &a.intervalEdit, Text: "2000", Row: 1, Column: 3, MinSize: Size{120, 0}},
					CheckBox{
						AssignTo:   &a.filterCheck,
						Text:       "%(filter)s",
						Checked:    true,
						Row:        2,
						Column:     0,
						ColumnSpan: 4,
					},
				},
			},
			Composite{
				Layout: VBox{Spacing: 6},
				Children: []Widget{
					Composite{
						Layout: HBox{Spacing: 10},
						Children: []Widget{
							PushButton{AssignTo: &a.loadBtn, Text: "%(load)s", MinSize: Size{130, 34}, OnClicked: a.onLoadMembers},
							PushButton{AssignTo: &a.startBtn, Text: "%(start)s", MinSize: Size{130, 34}, OnClicked: a.onStart},
							PushButton{AssignTo: &a.stopBtn, Text: "%(stop)s", Enabled: false, MinSize: Size{90, 34}, OnClicked: a.onStop},
						},
					},
					Label{AssignTo: &a.statusLabel, Text: "%(ready)s", TextColor: colorMuted, Font: fontUI},
				},
			},
			GroupBox{
				Title:      "%(members)s",
				Font:       fontUI,
				Layout:     VBox{},
				Background: SolidColorBrush{Color: colorPanel},
				Children: []Widget{
					TableView{
						AlternatingRowBG: true,
						ColumnsOrderable: true,
						MultiSelection:   true,
						Columns: []TableViewColumn{
							{Title: "QQ", Width: 120},
							{Title: "%(nick)s", Width: 220},
							{Title: "%(role)s", Width: 80},
						},
						Model:   a.memberModel,
						MinSize: Size{0, 150},
					},
				},
			},
			GroupBox{
				Title:      "%(status)s",
				Font:       fontUI,
				Layout:     VBox{Spacing: 6},
				Background: SolidColorBrush{Color: colorPanel},
				Children: []Widget{
					ProgressBar{AssignTo: &a.progressBar, MinSize: Size{0, 20}},
					Label{AssignTo: &a.statLabel, Text: "%(wait)s", TextColor: colorText, Font: fontUI},
				},
			},
			TabWidget{
				Font:    fontUI,
				MinSize: Size{0, 180},
				Pages: []TabPage{
					{
						Title:  "%(log_tab)s",
						Layout: VBox{},
						Children: []Widget{
							TextEdit{AssignTo: &a.logEdit, ReadOnly: true, VScroll: true, Font: fontSmall, MinSize: Size{0, 150}},
						},
					},
					{
						Title:  "%(freq_tab)s",
						Layout: VBox{Spacing: 4},
						Children: []Widget{
							Label{Text: "%(freq_hint)s", TextColor: colorWarn, Font: fontSmall},
							ListBox{AssignTo: &a.frequentList, MinSize: Size{0, 130}},
						},
					},
					{
						Title:  "%(err_tab)s",
						Layout: VBox{Spacing: 4},
						Children: []Widget{
							Label{Text: "%(err_hint)s", TextColor: colorError, Font: fontSmall},
							ListBox{AssignTo: &a.errorList, MinSize: Size{0, 130}},
						},
					},
				},
			},
		},
	}.Create()); err != nil {
		return err
	}

	a.loadSavedConfig()

	go func() {
		ticker := time.NewTicker(500 * time.Millisecond)
		defer ticker.Stop()
		for range ticker.C {
			a.pulseOn = !a.pulseOn
			a.refreshConnIndicator()
		}
	}()

	go func() {
		ticker := time.NewTicker(450 * time.Millisecond)
		defer ticker.Stop()
		for range ticker.C {
			a.pollStatus()
		}
	}()

	a.refreshConnIndicator()
	a.mw.Run()
	return nil
}

func (a *MainApp) loadSavedConfig() {
	cfg, err := a.api.GetConfig()
	if err != nil || cfg == nil {
		return
	}
	if cfg.TargetGroupID != "" {
		a.targetEdit.SetText(cfg.TargetGroupID)
	}
	if cfg.SourceGroupID != "" {
		a.sourceEdit.SetText(cfg.SourceGroupID)
	}
	if cfg.BatchCount != "" {
		a.countEdit.SetText(cfg.BatchCount)
	}
	if cfg.IntervalMs != "" {
		a.intervalEdit.SetText(cfg.IntervalMs)
	}
	a.filterCheck.SetChecked(cfg.FilterStaff)
}

func (a *MainApp) refreshConnIndicator() {
	if a.mw == nil {
		return
	}
	ok := a.api.Health()
	a.mw.Synchronize(func() {
		if ok {
			dot := "\u25cf"
			if a.pulseOn {
				dot = "\u25c9"
			}
			a.connLabel.SetText(dot + "%(svc_ok)s")
			a.connLabel.SetTextColor(colorSuccess)
		} else {
			a.connLabel.SetText("%(svc_no)s")
			a.connLabel.SetTextColor(colorError)
		}
	})
}

func (a *MainApp) parseInt64(le *walk.LineEdit, name string) (int64, error) {
	v, err := strconv.ParseInt(strings.TrimSpace(le.Text()), 10, 64)
	if err != nil || v <= 0 {
		return 0, fmt.Errorf("%(fill)s", name)
	}
	return v, nil
}

func (a *MainApp) parseInt(le *walk.LineEdit, name string) (int, error) {
	v, err := strconv.Atoi(strings.TrimSpace(le.Text()))
	if err != nil || v < 0 {
		return 0, fmt.Errorf("%(fill)s", name)
	}
	return v, nil
}

func (a *MainApp) onLoadMembers() {
	if a.loading {
		return
	}
	if !a.api.Health() {
		walk.MsgBox(a.mw, "%(tip)s", "%(start_svc)s", walk.MsgBoxIconWarning)
		return
	}
	source, err := a.parseInt64(a.sourceEdit, "%(source_name)s")
	if err != nil {
		walk.MsgBox(a.mw, "%(tip)s", err.Error(), walk.MsgBoxIconWarning)
		return
	}
	_ = a.api.SaveConfig(map[string]any{
		"source_group_id": strconv.FormatInt(source, 10),
		"filter_staff":    a.filterCheck.Checked(),
	})
	a.loading = true
	a.loadBtn.SetEnabled(false)
	a.statusLabel.SetText("%(loading)s")
	go func() {
		members, err := a.api.LoadMembers(source, a.filterCheck.Checked())
		a.mw.Synchronize(func() {
			a.loading = false
			a.loadBtn.SetEnabled(true)
			if err != nil {
				a.statusLabel.SetText("%(load_fail)s")
				walk.MsgBox(a.mw, "%(err)s", err.Error(), walk.MsgBoxIconError)
				return
			}
			a.members = members
			a.memberModel.items = members
			a.memberModel.PublishRowsReset()
			if len(members) == 0 {
				a.statusLabel.SetText("%(load_fail)s")
				walk.MsgBox(a.mw, "%(tip)s", "%(zero_members)s", walk.MsgBoxIconWarning)
				return
			}
			a.statusLabel.SetText(fmt.Sprintf("%(loaded)s", len(members)))
		})
	}()
}

func (a *MainApp) onStart() {
	if !a.api.Health() {
		walk.MsgBox(a.mw, "%(tip)s", "%(start_svc2)s", walk.MsgBoxIconWarning)
		return
	}
	target, err := a.parseInt64(a.targetEdit, "%(target_name)s")
	if err != nil {
		walk.MsgBox(a.mw, "%(tip)s", err.Error(), walk.MsgBoxIconWarning)
		return
	}
	source, err := a.parseInt64(a.sourceEdit, "%(source_name)s")
	if err != nil {
		walk.MsgBox(a.mw, "%(tip)s", err.Error(), walk.MsgBoxIconWarning)
		return
	}
	if target == source {
		walk.MsgBox(a.mw, "%(tip)s", "%(same_group)s", walk.MsgBoxIconWarning)
		return
	}
	count, err := a.parseInt(a.countEdit, "%(invite_count)s")
	if err != nil {
		walk.MsgBox(a.mw, "%(tip)s", err.Error(), walk.MsgBoxIconWarning)
		return
	}
	interval, err := a.parseInt(a.intervalEdit, "%(interval_ms)s")
	if err != nil {
		walk.MsgBox(a.mw, "%(tip)s", err.Error(), walk.MsgBoxIconWarning)
		return
	}
	if count == 0 {
		count = len(a.members)
	}
	if count == 0 {
		walk.MsgBox(a.mw, "%(tip)s", "%(no_members)s", walk.MsgBoxIconWarning)
		return
	}
	_ = a.api.SaveConfig(map[string]any{
		"target_group_id": strconv.FormatInt(target, 10),
		"source_group_id": strconv.FormatInt(source, 10),
		"batch_count":     strconv.Itoa(count),
		"interval_ms":     strconv.Itoa(interval),
		"filter_staff":    a.filterCheck.Checked(),
	})
	a.startBtn.SetEnabled(false)
	a.stopBtn.SetEnabled(true)
	a.loadBtn.SetEnabled(false)
	a.statusLabel.SetText("%(starting)s")
	go func() {
		err := a.api.StartInvite(target, source, count, interval, a.filterCheck.Checked())
		a.mw.Synchronize(func() {
			if err != nil {
				a.startBtn.SetEnabled(true)
				a.stopBtn.SetEnabled(false)
				a.loadBtn.SetEnabled(true)
				a.statusLabel.SetText("%(start_fail)s")
				walk.MsgBox(a.mw, "%(err)s", err.Error(), walk.MsgBoxIconError)
			}
		})
	}()
}

func (a *MainApp) onStop() {
	go func() { _ = a.api.StopInvite() }()
}

func (a *MainApp) pollStatus() {
	if a.mw == nil || !a.api.Health() {
		return
	}
	st, err := a.api.GetStatus()
	if err != nil {
		return
	}
	a.mw.Synchronize(func() {
		if st.Total > 0 {
			a.progressBar.SetMarqueeMode(false)
			a.progressBar.SetRange(0, st.Total)
			a.progressBar.SetValue(st.Done)
		} else if st.Running {
			a.progressBar.SetMarqueeMode(true)
		}
		a.statLabel.SetText(fmt.Sprintf(
			"%(progress)s",
			st.Message, st.Done, st.Total, st.Success,
			len(st.Frequent), len(st.Errors),
		))
		if st.Running {
			a.statusLabel.SetText(fmt.Sprintf("%(inviting)s", st.CurrentNickname, st.CurrentQQ))
			a.startBtn.SetEnabled(false)
			a.stopBtn.SetEnabled(true)
			a.loadBtn.SetEnabled(false)
		} else {
			a.startBtn.SetEnabled(true)
			a.stopBtn.SetEnabled(false)
			if !a.loading {
				a.loadBtn.SetEnabled(true)
			}
			if st.Message != "" {
				a.statusLabel.SetText(st.Message)
			} else {
				a.statusLabel.SetText("%(done_ready)s")
			}
		}
		if len(st.Logs) > 0 {
			a.logEdit.SetText(strings.Join(st.Logs, "\r\n"))
		}
		freqItems := make([]string, 0, len(st.Frequent))
		for _, r := range st.Frequent {
			freqItems = append(freqItems, fmt.Sprintf("%%d  %%s  \u2014  %%s", r.QQ, r.Nickname, r.Reason))
		}
		_ = a.frequentList.SetModel(freqItems)
		errItems := make([]string, 0, len(st.Errors))
		for _, r := range st.Errors {
			errItems = append(errItems, fmt.Sprintf("%%d  %%s  \u2014  %%s", r.QQ, r.Nickname, r.Reason))
		}
		_ = a.errorList.SetModel(errItems)
	})
}
''' % S

OUT.write_text(go, encoding="utf-8", newline="\r\n")
print("wrote", OUT)
