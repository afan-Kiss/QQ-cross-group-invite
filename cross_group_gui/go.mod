module cross_group_gui

go 1.21

require github.com/lxn/walk v0.0.0-20210112085537-c389da54e794

require (
	github.com/lxn/win v0.0.0-20191208154110-509771f367bc // indirect
	golang.org/x/sys v0.0.0-20201018230417-eeed37f84f13 // indirect
	gopkg.in/Knetic/govaluate.v3 v3.0.0 // indirect
)

replace (
	github.com/lxn/walk => ./vendor/walk
	github.com/lxn/win => ./vendor/win
)
