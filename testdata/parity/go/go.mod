// A module of its own, outside go/, because the packs are being worked on and
// a driver must not land inside a pack's tree. It reaches the pack by relative
// path, so the driver and the pack it measures always move together.
module wrench-parity-driver

go 1.26

require github.com/scriptedworld/wrench/go v0.0.0

require (
	github.com/santhosh-tekuri/jsonschema/v6 v6.0.3 // indirect
	go.yaml.in/yaml/v3 v3.0.5 // indirect
	golang.org/x/text v0.14.0 // indirect
)

replace github.com/scriptedworld/wrench/go => ../../../go
