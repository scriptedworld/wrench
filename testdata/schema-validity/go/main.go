// Command driver asks the Go pack whether each file is a valid schema.
//
//	driver FILE...
//
// One line per file, "ok NAME" or "INVALID NAME: reason", which is what
// bin/test-schema-validity.py reads. The exit status is not what it reads.
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	wrench "github.com/scriptedworld/wrench/go"
)

func main() {
	refused := 0
	for _, path := range os.Args[1:] {
		name := filepath.Base(path)
		data, err := os.ReadFile(filepath.Clean(path))
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		if _, err := wrench.CompileSchema(name, strings.NewReader(string(data))); err != nil {
			refused++
			fmt.Printf("INVALID %s: %s\n", name, strings.SplitN(err.Error(), "\n", 2)[0])
			continue
		}
		fmt.Printf("ok %s\n", name)
	}
	if refused > 0 {
		os.Exit(1)
	}
}
