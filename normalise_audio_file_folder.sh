#!/bin/sh
# normalise_folder_to_minus1db.sh
# Peak-normalise audio files in the current folder to -1 dBFS (linear),
# with a safety limiter to prevent clipping. Writes <name>_normalised.<ext>.
# Compatible with /bin/sh on macOS.

set -eu

TARGET_DB="-1"   # target peak (dBFS)
ROOT="${1:-.}"   # folder to process (default: current dir)

# Require ffmpeg
command -v ffmpeg >/dev/null 2>&1 || { echo "Error: ffmpeg not found in PATH." >&2; exit 1; }

# Optional: ffprobe to detect ALAC in .m4a
HAS_FFPROBE=0
if command -v ffprobe >/dev/null 2>&1; then HAS_FFPROBE=1; fi

# Detect encoders
HAS_LIBMP3LAME=0
HAS_LIBFDK=0
if ffmpeg -hide_banner -encoders 2>/dev/null | grep -q '[[:space:]]libmp3lame[[:space:]]'; then HAS_LIBMP3LAME=1; fi
if ffmpeg -hide_banner -encoders 2>/dev/null | grep -q '[[:space:]]libfdk_aac[[:space:]]'; then HAS_LIBFDK=1; fi

lower() { printf "%s" "$1" | tr '[:upper:]' '[:lower:]'; }

codec_opts_for_file() {
  in="$1"
  ext_lc="$(lower "$2")"

  case "$ext_lc" in
    wav)
      echo "-c:a pcm_s16le"
      ;;
    flac)
      echo "-c:a flac -compression_level 8"
      ;;
    mp3)
      if [ "$HAS_LIBMP3LAME" -eq 1 ]; then
        echo "-c:a libmp3lame -b:a 320k"     # highest practical MP3
      else
        echo "-c:a mp3 -b:a 320k"
      fi
      ;;
    m4a|aac)
      # Preserve ALAC if source is ALAC; otherwise AAC at highest quality available
      if [ "$HAS_FFPROBE" -eq 1 ]; then
        SRC_CODEC="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name \
                     -of default=nw=1:nk=1 "$in" 2>/dev/null || true)"
      else
        SRC_CODEC=""
      fi
      if [ "x$SRC_CODEC" = "xalac" ]; then
        echo "-c:a alac"
      else
        if [ "$HAS_LIBFDK" -eq 1 ]; then
          echo "-c:a libfdk_aac -vbr 5"
        else
          echo "-c:a aac -b:a 320k -profile:a aac_low"
        fi
      fi
      ;;
    *)
      echo "-c:a aac -b:a 320k -profile:a aac_low"
      ;;
  esac
}

echo "Scanning: $ROOT"
echo "Target peak: ${TARGET_DB} dBFS"
echo "Encoders: libmp3lame=$HAS_LIBMP3LAME, libfdk_aac=$HAS_LIBFDK"
echo

# Iterate ONLY the top-level of $ROOT (no recursion), portable across shells.
# (Hidden files aren't matched; add ".*.ext" globs if you need those.)
set -- "$ROOT"/*.wav "$ROOT"/*.flac "$ROOT"/*.mp3 "$ROOT"/*.m4a "$ROOT"/*.aac

# If none matched, $1 will be the literal pattern; guard with -f checks below.
for in in "$@"; do
  [ -f "$in" ] || continue

  dir=$(dirname "$in")
  file=$(basename "$in")
  base=${file%.*}
  ext=${file##*.}

  case "$base" in
    *_normalised) echo "Skipping already normalised: $file"; continue ;;
  esac

  out="${dir}/${base}_normalised.${ext}"
  if [ -e "$out" ]; then
    echo "Output exists, skipping: $out"
    continue
  fi

  echo "Analyzing peak: $file"

  detect_log=$(mktemp)
  # Use -v info so volumedetect actually prints its stats (stderr).
  if ! ffmpeg -hide_banner -nostats -v info -i "$in" -af volumedetect -f null - 2> "$detect_log"; then
    echo "  ! Analysis failed, skipping: $file"
    rm -f "$detect_log"
    continue
  fi

  # Parse e.g. "max_volume: -3.2 dB"
  max_db=$(awk -F'max_volume:[ ]*' '/max_volume/ {split($2,a," dB"); print a[1]; exit}' "$detect_log" || true)
  rm -f "$detect_log"

  if [ -z "${max_db:-}" ] || [ "$max_db" = "inf" ] || [ "$max_db" = "-inf" ]; then
    echo "  ? Could not determine max_volume; applying no gain change."
    gain_db="0"
  else
    # gain = TARGET_DB - max_db
    gain_db=$(awk -v t="$TARGET_DB" -v m="$max_db" 'BEGIN { printf "%.6f", (t - m) }')
  fi

  # Apply linear gain, then hard-limit to TARGET_DB for safety
  af="volume=${gain_db}dB,alimiter=limit=${TARGET_DB}dB"

  a_opts=$(codec_opts_for_file "$in" "$ext")

  echo "  max_peak=${max_db:-unknown} dB  ->  gain=${gain_db} dB  ->  $out"

  if ! ffmpeg -hide_banner -y -i "$in" -map 0 -filter:a "$af" \
      $a_opts -c:v copy -c:s copy -c:d copy \
      -movflags use_metadata_tags "$out"; then
    echo "  ! Failed to write: $out"
    continue
  fi

  echo "  ✓ Done: $out"
  echo
done

echo "All done."
