#!/bin/zsh
# Launch error watcher when Claude opens in this project
PROJECT="$HOME/adaptive-trading-ecosystem"
if ! pgrep -f "watch-errors.sh" > /dev/null 2>&1; then
  osascript -e "tell application \"Terminal\" to do script \"$PROJECT/watch-errors.sh\"" 2>/dev/null &
fi
