module verify

go 1.21

require github.com/spf13/cobra v1.0.0

require (
	github.com/inconshreveable/mousetrap v1.1.0 // indirect
	github.com/spf13/pflag v1.0.9 // indirect
)

// Use the local cobra workspace (with our patch applied)
replace github.com/spf13/cobra => ../workspaces/cobra
