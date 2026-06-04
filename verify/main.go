// Demo program to verify the fix for cobra issue #1272.
//
// Creates a CLI with:
//   - 2 short visible commands ("up", "down")
//   - 1 very long HIDDEN command ("super-secret-internal-debug-tool")
//
// Before the fix: "Available Commands" section is padded as if the hidden command
// were visible, wasting space between visible command names and their descriptions.
//
// After the fix: padding only considers visible commands.
package main

import (
	"github.com/spf13/cobra"
)

func main() {
	noop := func(cmd *cobra.Command, args []string) {}

	root := &cobra.Command{Use: "mytool"}

	root.AddCommand(&cobra.Command{
		Use:   "up",
		Short: "Bring service up",
		Run:   noop,
	})
	root.AddCommand(&cobra.Command{
		Use:   "down",
		Short: "Bring service down",
		Run:   noop,
	})

	// Hidden command — should NOT influence the padding of visible commands
	root.AddCommand(&cobra.Command{
		Use:    "super-secret-internal-debug-tool",
		Short:  "Internal use only",
		Hidden: true,
		Run:    noop,
	})

	root.SetArgs([]string{"--help"})
	_ = root.Execute()
}
