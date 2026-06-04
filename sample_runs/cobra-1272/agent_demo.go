package main

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

func main() {
	var rootCmd = &cobra.Command{
		Use:   "mycli",
		Short: "A sample CLI",
		Long:  "A longer description for the sample CLI.",
	}

	var visibleCmd = &cobra.Command{
		Use:   "visible",
		Short: "This is a visible command",
		Run: func(cmd *cobra.Command, args []string) {
			fmt.Println("Visible command executed")
		},
	}

	var hiddenCmd = &cobra.Command{
		Use:   "hidden",
		Short: "This is a hidden command",
		Hidden: true,
		Run: func(cmd *cobra.Command, args []string) {
			fmt.Println("Hidden command executed")
		},
	}

	rootCmd.AddCommand(visibleCmd, hiddenCmd)

	// Set Stdout to a buffer to capture the usage output
	// This is a simplified approach for demoing the fix.
	// In a real scenario, we'd capture os.Stdout or use cobra's output capture.
	rootCmd.SetArgs([]string{"help"})
	err := rootCmd.Execute()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error executing command: %v\n", err)
		os.Exit(1)
	}
}
