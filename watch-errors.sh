#!/bin/zsh
# watch-errors.sh — Auto-fix Next.js runtime errors using Claude Code
# Usage: ./watch-errors.sh
# Watches the Next.js dev log and triggers Claude to fix errors automatically.

LOG_FILE="/tmp/next-dev.log"
PROJECT="/Users/andrewpeterson/adaptive-trading-ecosystem"
COOLDOWN=30  # seconds between fixes (avoid hammering on same error)
last_fix=0

echo "👁  Watching $LOG_FILE for runtime errors..."
echo "    Press Ctrl+C to stop."
echo ""

tail -f "$LOG_FILE" 2>/dev/null | while IFS= read -r line; do
  # Detect Next.js / React runtime errors
  if echo "$line" | grep -qE "ReferenceError:|TypeError:|SyntaxError:|Cannot read prop|is not defined|is not a function|Unhandled"; then
    now=$(date +%s)
    elapsed=$(( now - last_fix ))

    if (( elapsed < COOLDOWN )); then
      continue  # skip if we just fixed something
    fi
    last_fix=$now

    # Collect a few more lines for context
    context="$line"
    for i in 1 2 3 4 5; do
      read -t 1 extra && context="$context\n$extra"
    done

    echo ""
    echo "⚠️  Error detected at $(date '+%H:%M:%S'):"
    echo "    $line"
    echo ""
    echo "🤖 Sending to Claude for auto-fix..."

    # Build the prompt
    prompt="Fix this Next.js runtime error in the trading website at $PROJECT/frontend. Do not explain, just fix the file.

Error:
$context

Steps:
1. Identify the file and line from the error
2. Read the file
3. Fix the bug
4. Verify with: cd $PROJECT/frontend && npx tsc --noEmit"

    # Run Claude non-interactively
    cd "$PROJECT" && claude --dangerously-skip-permissions -p "$prompt" 2>&1 | tail -5

    echo ""
    echo "✅ Fix attempted. Watching for next error..."
    echo ""
  fi
done
