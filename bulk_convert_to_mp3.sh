#!/bin/sh
# convert_to_mp3.sh
# Recursively convert FLAC/M4A/WAV/ALAC/AIFF to high-quality MP3 (LAME V0).
# Skips .mp3 inputs and won't overwrite existing .mp3 files.
# Usage: ./convert_to_mp3.sh /path/to/folder   (defaults to current dir)

set -eu

DIR="${1:-.}"

# Require ffmpeg with libmp3lame
command -v ffmpeg >/dev/null 2>&1 || {
  echo "Error: ffmpeg not found. Please install ffmpeg." >&2; exit 1; }
ffmpeg -hide_banner -encoders 2>/dev/null | grep -qi 'libmp3lame' || {
  echo "Error: ffmpeg is missing the libmp3lame encoder." >&2; exit 1; }

# Find candidates and process them safely (no read -d, no process substitution).
find "$DIR" -type f \
  \( -iname '*.flac' -o -iname '*.m4a' -o -iname '*.wav' -o -iname '*.alac' -o -iname '*.aiff' -o -iname '*.aif' \) \
  -exec sh -c '
    for src do
      case "$src" in
        *.mp3|*.MP3) echo "Skipping already MP3: $src"; continue ;;
      esac
      out="${src%.*}.mp3"
      if [ -e "$out" ]; then
        echo "Target exists, skipping: $out"
        continue
      fi
      echo "Converting: $src -> $out"
      if ! ffmpeg -hide_banner -loglevel error -n \
            -i "$src" -vn -map_metadata 0 \
            -c:a libmp3lame -q:a 0 \
            -id3v2_version 3 -write_id3v1 1 \
            "$out"
      then
        echo "Conversion failed: $src" >&2
      fi
    done
  ' sh {} +
