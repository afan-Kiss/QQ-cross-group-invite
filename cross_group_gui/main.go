//go:build windows

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
		return "\u7fa4\u4e3b"
	case "admin":
		return "\u7ba1\u7406\u5458"
	case "member":
		return "\u6210\u5458"
	default:
		return "\u672a\u77e5"
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
		walk.MsgBox(nil, "\u51fa\u9519\u4e86", err.Error(), walk.MsgBoxIconError)
	}
}

func (a *MainApp) build() error {
	fontUI := Font{Family: "Microsoft YaHei UI", PointSize: 10}
	fontTitle := Font{Family: "Microsoft YaHei UI", PointSize: 13, Bold: true}
	fontSmall := Font{Family: "Microsoft YaHei UI", PointSize: 9}

	if err := (MainWindow{
		AssignTo:   &a.mw,
		Title:      "\u8de8\u7fa4\u9080\u8bf7\u52a9\u624b",
		MinSize:    Size{Width: 920, Height: 780},
		Size:       Size{Width: 980, Height: 820},
		Layout:     VBox{Margins: Margins{14, 12, 14, 12}, Spacing: 8},
		Background: SolidColorBrush{Color: colorBg},
		Children: []Widget{
			Composite{
				Layout:     HBox{Margins: Margins{10, 8, 10, 8}, Spacing: 12},
				Background: SolidColorBrush{Color: colorPanel},
				Children: []Widget{
					Label{Font: fontTitle, Text: "\u8de8\u7fa4\u9080\u8bf7\u52a9\u624b", TextColor: colorText},
					HSpacer{},
					Label{AssignTo: &a.connLabel, Font: fontSmall, Text: "\u25cf \u6b63\u5728\u8fde\u63a5\u540e\u53f0...", TextColor: colorMuted},
				},
			},
			GroupBox{
				Title:      "\u57fa\u672c\u8bbe\u7f6e",
				Font:       fontUI,
				Layout:     Grid{Columns: 4, Spacing: 10},
				Background: SolidColorBrush{Color: colorPanel},
				Children: []Widget{
					Label{Text: "\u8981\u62c9\u8fdb\u54ea\u4e2a\u7fa4", TextColor: colorText, Row: 0, Column: 0},
					LineEdit{AssignTo: &a.targetEdit, Row: 0, Column: 1, MinSize: Size{180, 0}},
					Label{Text: "\u4ece\u54ea\u4e2a\u7fa4\u62c9\u4eba", TextColor: colorText, Row: 0, Column: 2},
					LineEdit{AssignTo: &a.sourceEdit, Row: 0, Column: 3, MinSize: Size{180, 0}},
					Label{Text: "\u4e00\u6b21\u62c9\u51e0\u4e2a\u4eba", TextColor: colorText, Row: 1, Column: 0},
					LineEdit{AssignTo: &a.countEdit, Text: "10", Row: 1, Column: 1, MinSize: Size{120, 0}},
					Label{Text: "\u6bcf\u6b21\u95f4\u9694\uff08\u6beb\u79d2\uff09", TextColor: colorText, Row: 1, Column: 2},
					LineEdit{AssignTo: &a.intervalEdit, Text: "2000", Row: 1, Column: 3, MinSize: Size{120, 0}},
					CheckBox{
						AssignTo:   &a.filterCheck,
						Text:       "\u4e0d\u62c9\u7fa4\u4e3b\u548c\u7ba1\u7406\u5458",
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
							PushButton{AssignTo: &a.loadBtn, Text: "\u52a0\u8f7d\u6210\u5458\u5217\u8868", MinSize: Size{130, 34}, OnClicked: a.onLoadMembers},
							PushButton{AssignTo: &a.startBtn, Text: "\u5f00\u59cb\u9080\u8bf7", MinSize: Size{130, 34}, OnClicked: a.onStart},
							PushButton{AssignTo: &a.stopBtn, Text: "\u505c\u6b62", Enabled: false, MinSize: Size{90, 34}, OnClicked: a.onStop},
						},
					},
					Label{AssignTo: &a.statusLabel, Text: "\u51c6\u5907\u597d\u4e86", TextColor: colorMuted, Font: fontUI},
				},
			},
			GroupBox{
				Title:      "\u53ef\u9080\u8bf7\u7684\u6210\u5458",
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
							{Title: "\u6635\u79f0", Width: 220},
							{Title: "\u8eab\u4efd", Width: 80},
						},
						Model:   a.memberModel,
						MinSize: Size{0, 150},
					},
				},
			},
			GroupBox{
				Title:      "\u5f53\u524d\u8fdb\u5ea6",
				Font:       fontUI,
				Layout:     VBox{Spacing: 6},
				Background: SolidColorBrush{Color: colorPanel},
				Children: []Widget{
					ProgressBar{AssignTo: &a.progressBar, MinSize: Size{0, 20}},
					Label{AssignTo: &a.statLabel, Text: "\u8fd8\u6ca1\u5f00\u59cb", TextColor: colorText, Font: fontUI},
				},
			},
			TabWidget{
				Font:    fontUI,
				MinSize: Size{0, 180},
				Pages: []TabPage{
					{
						Title:  "\u8fd0\u884c\u65e5\u5fd7",
						Layout: VBox{},
						Children: []Widget{
							TextEdit{AssignTo: &a.logEdit, ReadOnly: true, VScroll: true, Font: fontSmall, MinSize: Size{0, 150}},
						},
					},
					{
						Title:  "\u64cd\u4f5c\u592a\u9891\u7e41",
						Layout: VBox{Spacing: 4},
						Children: []Widget{
							Label{Text: "\u4ee5\u4e0b\u4eba\u5458\u89e6\u53d1\u9891\u7e41\u9650\u5236\uff08QQ \u00b7 \u6635\u79f0 \u00b7 \u539f\u56e0\uff09", TextColor: colorWarn, Font: fontSmall},
							ListBox{AssignTo: &a.frequentList, MinSize: Size{0, 130}},
						},
					},
					{
						Title:  "\u9080\u8bf7\u5931\u8d25",
						Layout: VBox{Spacing: 4},
						Children: []Widget{
							Label{Text: "\u4ee5\u4e0b\u4eba\u5458\u9080\u8bf7\u5931\u8d25\uff08QQ \u00b7 \u6635\u79f0 \u00b7 \u539f\u56e0\uff09", TextColor: colorError, Font: fontSmall},
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
			a.connLabel.SetText(dot + " \u540e\u53f0\u5df2\u8fde\u63a5")
			a.connLabel.SetTextColor(colorSuccess)
		} else {
			a.connLabel.SetText("\u25cb \u540e\u53f0\u672a\u542f\u52a8")
			a.connLabel.SetTextColor(colorError)
		}
	})
}

func (a *MainApp) parseInt64(le *walk.LineEdit, name string) (int64, error) {
	v, err := strconv.ParseInt(strings.TrimSpace(le.Text()), 10, 64)
	if err != nil || v <= 0 {
		return 0, fmt.Errorf("\u8bf7\u586b\u5199\u6b63\u786e\u7684%s", name)
	}
	return v, nil
}

func (a *MainApp) parseInt(le *walk.LineEdit, name string) (int, error) {
	v, err := strconv.Atoi(strings.TrimSpace(le.Text()))
	if err != nil || v < 0 {
		return 0, fmt.Errorf("\u8bf7\u586b\u5199\u6b63\u786e\u7684%s", name)
	}
	return v, nil
}

func (a *MainApp) onLoadMembers() {
	if a.loading {
		return
	}
	if !a.api.Health() {
		walk.MsgBox(a.mw, "\u63d0\u793a", "\u8bf7\u5148\u53cc\u51fb\u300c\u542f\u52a8\u8de8\u7fa4\u9080\u8bf7\u52a9\u624b_Walk\u7248.bat\u300d\n\u7b49\u540e\u53f0\u542f\u52a8\u540e\u518d\u8bd5\u3002", walk.MsgBoxIconWarning)
		return
	}
	source, err := a.parseInt64(a.sourceEdit, "\u6765\u6e90\u7fa4\u53f7")
	if err != nil {
		walk.MsgBox(a.mw, "\u63d0\u793a", err.Error(), walk.MsgBoxIconWarning)
		return
	}
	_ = a.api.SaveConfig(map[string]any{
		"source_group_id": strconv.FormatInt(source, 10),
		"filter_staff":    a.filterCheck.Checked(),
	})
	a.loading = true
	a.loadBtn.SetEnabled(false)
	a.statusLabel.SetText("\u6b63\u5728\u52a0\u8f7d\u6210\u5458...")
	go func() {
		members, err := a.api.LoadMembers(source, a.filterCheck.Checked())
		a.mw.Synchronize(func() {
			a.loading = false
			a.loadBtn.SetEnabled(true)
			if err != nil {
				a.statusLabel.SetText("\u52a0\u8f7d\u5931\u8d25")
				walk.MsgBox(a.mw, "\u51fa\u9519\u4e86", err.Error(), walk.MsgBoxIconError)
				return
			}
			a.members = members
			a.memberModel.items = members
			a.memberModel.PublishRowsReset()
			if len(members) == 0 {
				a.statusLabel.SetText("\u52a0\u8f7d\u5931\u8d25")
				walk.MsgBox(a.mw, "\u63d0\u793a", "\u6ca1\u6709\u52a0\u8f7d\u5230\u53ef\u9080\u8bf7\u6210\u5458\u3002\u8bf7\u68c0\u67e5\u7fa4\u53f7\u662f\u5426\u6b63\u786e\uff0c\u6216\u786e\u8ba4 NapCat \u5728\u7ebf\u3002", walk.MsgBoxIconWarning)
				return
			}
			a.statusLabel.SetText(fmt.Sprintf("\u5df2\u52a0\u8f7d %d \u4eba", len(members)))
		})
	}()
}

func (a *MainApp) onStart() {
	if !a.api.Health() {
		walk.MsgBox(a.mw, "\u63d0\u793a", "\u8bf7\u5148\u542f\u52a8\u540e\u53f0\uff08\u53cc\u51fb Walk \u7248\u542f\u52a8\u811a\u672c\uff09", walk.MsgBoxIconWarning)
		return
	}
	target, err := a.parseInt64(a.targetEdit, "\u76ee\u6807\u7fa4\u53f7")
	if err != nil {
		walk.MsgBox(a.mw, "\u63d0\u793a", err.Error(), walk.MsgBoxIconWarning)
		return
	}
	source, err := a.parseInt64(a.sourceEdit, "\u6765\u6e90\u7fa4\u53f7")
	if err != nil {
		walk.MsgBox(a.mw, "\u63d0\u793a", err.Error(), walk.MsgBoxIconWarning)
		return
	}
	if target == source {
		walk.MsgBox(a.mw, "\u63d0\u793a", "\u76ee\u6807\u7fa4\u548c\u6765\u6e90\u7fa4\u4e0d\u80fd\u76f8\u540c", walk.MsgBoxIconWarning)
		return
	}
	count, err := a.parseInt(a.countEdit, "\u9080\u8bf7\u4eba\u6570")
	if err != nil {
		walk.MsgBox(a.mw, "\u63d0\u793a", err.Error(), walk.MsgBoxIconWarning)
		return
	}
	interval, err := a.parseInt(a.intervalEdit, "\u95f4\u9694\u6beb\u79d2")
	if err != nil {
		walk.MsgBox(a.mw, "\u63d0\u793a", err.Error(), walk.MsgBoxIconWarning)
		return
	}
	if count == 0 {
		count = len(a.members)
	}
	if count == 0 {
		walk.MsgBox(a.mw, "\u63d0\u793a", "\u8bf7\u5148\u52a0\u8f7d\u6210\u5458\u5217\u8868\uff0c\u6216\u586b\u5199\u9080\u8bf7\u4eba\u6570\u3002", walk.MsgBoxIconWarning)
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
	a.statusLabel.SetText("\u6b63\u5728\u542f\u52a8...")
	go func() {
		err := a.api.StartInvite(target, source, count, interval, a.filterCheck.Checked())
		a.mw.Synchronize(func() {
			if err != nil {
				a.startBtn.SetEnabled(true)
				a.stopBtn.SetEnabled(false)
				a.loadBtn.SetEnabled(true)
				a.statusLabel.SetText("\u542f\u52a8\u5931\u8d25")
				walk.MsgBox(a.mw, "\u51fa\u9519\u4e86", err.Error(), walk.MsgBoxIconError)
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
			"%s  |  \u5df2\u5b8c\u6210 %d/%d  \u6210\u529f %d  \u9891\u7e41 %d  \u5931\u8d25 %d",
			st.Message, st.Done, st.Total, st.Success,
			len(st.Frequent), len(st.Errors),
		))
		if st.Running {
			a.statusLabel.SetText(fmt.Sprintf("\u6b63\u5728\u9080\u8bf7: %s\uff08QQ %d\uff09", st.CurrentNickname, st.CurrentQQ))
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
				a.statusLabel.SetText("\u51c6\u5907\u597d\u4e86")
			}
		}
		if len(st.Logs) > 0 {
			a.logEdit.SetText(strings.Join(st.Logs, "\r\n"))
		}
		freqItems := make([]string, 0, len(st.Frequent))
		for _, r := range st.Frequent {
			freqItems = append(freqItems, fmt.Sprintf("%d  %s  \u2014  %s", r.QQ, r.Nickname, r.Reason))
		}
		_ = a.frequentList.SetModel(freqItems)
		errItems := make([]string, 0, len(st.Errors))
		for _, r := range st.Errors {
			errItems = append(errItems, fmt.Sprintf("%d  %s  \u2014  %s", r.QQ, r.Nickname, r.Reason))
		}
		_ = a.errorList.SetModel(errItems)
	})
}
