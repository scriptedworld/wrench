module github.com/scriptedworld/wrench/testdata/schema-validity/go

go 1.26

require github.com/scriptedworld/wrench/go v0.0.0

require (
	github.com/santhosh-tekuri/jsonschema/v6 v6.0.3 // indirect
	go.yaml.in/yaml/v3 v3.0.5 // indirect
	golang.org/x/text v0.14.0 // indirect
)

replace github.com/scriptedworld/wrench/go => ../../../go
