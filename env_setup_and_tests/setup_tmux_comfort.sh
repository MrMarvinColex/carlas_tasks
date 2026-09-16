#!/usr/bin/env bash
# Настраивает tmux для удобной прокрутки и выделения текста мышью.
# Не удаляет существующие настройки: добавляет/обновляет только свой блок.

set -euo pipefail

config_file="${HOME}/.tmux.conf"
tmp_file="$(mktemp "${TMPDIR:-/tmp}/tmux-conf.XXXXXX")"
backup_file=""

cleanup() {
  rm -f "$tmp_file"
}
trap cleanup EXIT

if [[ -f "$config_file" ]]; then
  # Удаляем прошлую версию блока, чтобы повторный запуск был идемпотентным.
  awk '
    /^# >>> tmux-comfort-settings >>>$/ { inside = 1; next }
    /^# <<< tmux-comfort-settings <<<$/{ inside = 0; next }
    !inside { print }
  ' "$config_file" >"$tmp_file"
else
  : >"$tmp_file"
fi

clipboard_command=""
if command -v wl-copy >/dev/null 2>&1; then
  clipboard_command="wl-copy"
elif command -v xclip >/dev/null 2>&1; then
  clipboard_command="xclip -in -selection clipboard"
elif command -v xsel >/dev/null 2>&1; then
  clipboard_command="xsel --clipboard --input"
elif command -v pbcopy >/dev/null 2>&1; then
  clipboard_command="pbcopy"
fi

printf '%s\n' \
  '# >>> tmux-comfort-settings >>>' \
  '# Long scrollback and mouse-friendly copy mode.' \
  'set -g history-limit 100000' \
  'set -g mouse on' \
  'set -g mode-keys emacs' \
  '# Copy to the terminal clipboard via OSC 52 when the terminal supports it.' \
  'set -s set-clipboard on' \
  '# Releasing the left mouse button after a drag copies the selection.' \
  'bind-key -T copy-mode MouseDragEnd1Pane send-keys -X copy-selection-and-cancel' \
  'bind-key -T copy-mode-vi MouseDragEnd1Pane send-keys -X copy-selection-and-cancel' \
  >>"$tmp_file"

if [[ -n "$clipboard_command" ]]; then
  printf '%s\n' \
    '# A local clipboard utility was found; use it for drag-to-copy as well.' \
    "bind-key -T copy-mode MouseDragEnd1Pane send-keys -X copy-pipe-and-cancel \"$clipboard_command\"" \
    "bind-key -T copy-mode-vi MouseDragEnd1Pane send-keys -X copy-pipe-and-cancel \"$clipboard_command\"" \
    >>"$tmp_file"
fi

printf '%s\n' '# <<< tmux-comfort-settings <<<' >>"$tmp_file"

if [[ -f "$config_file" ]] && cmp -s "$tmp_file" "$config_file"; then
  echo "Настройки tmux уже актуальны: $config_file"
else
  if [[ -f "$config_file" ]]; then
    backup_file="${config_file}.backup.$(date +%Y%m%d-%H%M%S)"
    cp -p "$config_file" "$backup_file"
  fi
  mv "$tmp_file" "$config_file"
  trap - EXIT
  [[ -n "$backup_file" ]] && echo "Предыдущая конфигурация сохранена: $backup_file"
  echo "Настройки записаны: $config_file"
fi

if command -v tmux >/dev/null 2>&1 && tmux list-sessions >/dev/null 2>&1; then
  tmux source-file "$config_file"
  echo "Настройки применены к запущенному tmux."
else
  echo "Откройте новый сеанс tmux — настройки применятся автоматически."
fi

echo
echo "Колёсико мыши прокручивает историю. Потяните левой кнопкой для выделения;"
echo "отпустите кнопку, чтобы скопировать. Для нативного выделения терминала используйте Shift+перетаскивание."
