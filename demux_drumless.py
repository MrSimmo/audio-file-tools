
#!/usr/bin/env python3

"""
Automated Drumless folder Demuxer
Removes drums from FLAC files using Demucs and manages metadata

By Andy (Lakota) 2025.

Dependencies:
- ffmpeg (in PATH)
- mutagen (Python package)
- rsgain (in PATH)
- audio-separator (Python package)
"""

import os
import sys
import subprocess
import shutil
import re
from pathlib import Path

import glob

# Supported input extensions (case-insensitive)
SUPPORTED_INPUT_EXTENSIONS = {
    ".flac",
    ".wav",
    ".m4a",
    ".mp4",
    ".mp3",
    ".alac"
}

# Try to import optional dependencies - will be checked in main()
try:
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import ID3, APIC, COMM, TIT2, TALB, TPE1, TPE2, TRCK, TCON, TDRC, TXXX
    from mutagen.mp3 import MP3
    from mutagen.mp4 import MP4, MP4Cover
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

try:
    from audio_separator.separator import Separator
    AUDIO_SEPARATOR_AVAILABLE = True
except ImportError:
    AUDIO_SEPARATOR_AVAILABLE = False


def check_dependency(command, check_type="command"):
    """Check if a required dependency is available"""
    if check_type == "command":
        result = shutil.which(command)
        if not result:
            print(f"Error: '{command}' not found in PATH.")
            sys.exit(1)
    elif check_type == "file":
        if not os.path.isfile(command):
            print(f"Error: File '{command}' does not exist.")
            sys.exit(1)
    elif check_type == "python_module":
        try:
            __import__(command)
        except ImportError:
            print(f"Error: Python module '{command}' is not installed.")
            sys.exit(1)


def is_flac_file(path):
    return os.path.splitext(path)[1].lower() == ".flac"


def find_audio_files(root_dir, extensions):
    """Recursively find supported audio files under root_dir, skipping generated folders"""
    audio_paths = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip folders that the script generates itself
        dirnames[:] = [
            d for d in dirnames
            if d.lower() != "separated" and not d.lower().startswith("normalised")
        ]

        for filename in filenames:
            if os.path.splitext(filename)[1].lower() in extensions:
                full_path = os.path.join(dirpath, filename)
                audio_paths.append(os.path.relpath(full_path, root_dir))

    return sorted(audio_paths, key=lambda p: p.lower())


def get_model_selection():
    """Ask user to select the stem separation model"""
    print("\nPlease select stem separation model:")
    print("  1. htdemucs_ft.yaml")
    print("  2. BS-Roformer-SW.ckpt (Default)")
    print("  3. Other (enter custom model name)")
    print()

    while True:
        response = input('Enter your choice (1/2/3) or press Enter for default [2]: ').strip()

        # Default to option 2 if user just presses Enter
        if response == '':
            print("Selected: BS-Roformer-SW.ckpt (Default)")
            return "BS-Roformer-SW.ckpt"

        if response == '1':
            print("Selected: htdemucs_ft.yaml")
            return "htdemucs_ft.yaml"
        elif response == '2':
            print("Selected: BS-Roformer-SW.ckpt")
            return "BS-Roformer-SW.ckpt"
        elif response == '3':
            custom_model = input('Enter custom model name: ').strip()
            if custom_model:
                print(f"Selected: {custom_model}")
                return custom_model
            else:
                print("Error: Model name cannot be empty. Please try again.")
        else:
            print("Invalid input. Please enter 1, 2, 3, or press Enter for default.")


def get_compilation_input():
    """Ask user if this is a compilation album"""
    while True:
        response = input('Is this a compilation rather than one artist? y/n or Y/N: ').strip()
        if response in ['y', 'Y', 'n', 'N']:
            return response in ['y', 'Y']
        else:
            print("Invalid input. Please enter y/Y or n/N.")


def get_normalization_input():
    """Ask user if they want normalized MP3 versions"""
    while True:
        response = input('\nWould you like a normalised (-0.1dB) version of the output files to a sub folder as MP3s ready for the Roland V71? y/n or Y/N: ').strip()
        if response in ['y', 'Y', 'n', 'N']:
            return response in ['y', 'Y']
        else:
            print("Invalid input. Please enter y/Y or n/N.")


def run_command(cmd, capture_output=False):
    """Run a shell command and return success status"""
    try:
        if capture_output:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=True)
            return True, result.stdout
        else:
            result = subprocess.run(cmd, shell=True, check=True)
            return True, None
    except subprocess.CalledProcessError:
        return False, None


def detect_peak_level(wav_dir):
    """Detect the peak level of merged audio files (excluding drums)"""
    wav_files = sorted([f for f in glob.glob(f"{wav_dir}/*.wav") if "drums" not in f.lower()])

    if not wav_files:
        return None

    input_args = " ".join([f'-i "{f}"' for f in wav_files])
    num_inputs = len(wav_files)

    cmd = f'ffmpeg {input_args} -filter_complex "amix=inputs={num_inputs}:duration=longest:normalize=0,volumedetect" -f null - 2>&1'
    success, output = run_command(cmd, capture_output=True)

    if success and output:
        match = re.search(r'max_volume:\s*([-\d.]+)', output)
        if match:
            return float(match.group(1))

    return None


def detect_file_peak_level(file_path):
    """Detect the peak level of a single audio file"""
    cmd = f'ffmpeg -i "{file_path}" -af "volumedetect" -f null - 2>&1'
    success, output = run_command(cmd, capture_output=True)

    if success and output:
        match = re.search(r'max_volume:\s*([-\d.]+)', output)
        if match:
            return float(match.group(1))

    return None


def merge_audio_files(wav_dir, output_file, gain_db=None):
    """Merge audio files (excluding drums) with optional gain adjustment"""
    wav_files = sorted([f for f in glob.glob(f"{wav_dir}/*.wav") if "drums" not in f.lower()])

    if not wav_files:
        return False

    input_args = " ".join([f'-i "{f}"' for f in wav_files])
    num_inputs = len(wav_files)

    if gain_db is not None:
        filter_complex = f'"amix=inputs={num_inputs}:duration=longest:normalize=0,volume={gain_db}dB"'
    else:
        filter_complex = f'"amix=inputs={num_inputs}:duration=longest:normalize=0"'

    cmd = f'ffmpeg {input_args} -compression_level 8 -filter_complex {filter_complex} "{output_file}"'
    success, _ = run_command(cmd)

    return success


def copy_metadata(source_file, audio_file, output_file, is_compilation):
    """Copy metadata from source file to output file"""
    if is_compilation:
        cmd = (f'ffmpeg -y -i "{source_file}" -i "{audio_file}" -map_metadata 0 -map 1:a '
               f'-c copy -movflags use_metadata_tags -write_id3v2 1 '
               f'-metadata compilation="1" -metadata album_artist="Various Artists" '
               f'-metadata album=\'Drumless (Lossless)\' "{output_file}"')
    else:
        cmd = (f'ffmpeg -y -i "{source_file}" -i "{audio_file}" -map_metadata 0 -map 1:a '
               f'-c copy -movflags use_metadata_tags -write_id3v2 1 "{output_file}"')

    success, _ = run_command(cmd)
    return success


def apply_replaygain_track(file_path):
    """Apply ReplayGain in track mode"""
    cmd = (f'rsgain custom --tagmode=i --loudness=-23 --clip-mode=p --max-peak=0 '
           f'--true-peak --id3v2-version=keep "{file_path}"')
    run_command(cmd)


def apply_replaygain_album(file_paths):
    """Apply ReplayGain in album mode"""
    files_str = " ".join([f'"{f}"' for f in file_paths])
    cmd = (f'rsgain custom --tagmode=i --loudness=-23 --clip-mode=p --max-peak=0 '
           f'--true-peak --id3v2-version=keep --album {files_str}')
    run_command(cmd)


def set_flac_tags(file_path, tags_dict):
    """Set tags on a FLAC file using mutagen"""
    try:
        audio = FLAC(file_path)
        for key, value in tags_dict.items():
            audio[key] = value
        audio.save()
        return True
    except Exception as e:
        print(f"Error setting tags on {file_path}: {e}")
        return False


def extract_pictures(source_file):
    """Extract artwork pictures from supported audio formats"""
    pictures = []
    try:
        ext = os.path.splitext(source_file)[1].lower()

        if ext == ".flac":
            audio = FLAC(source_file)
            pictures.extend(audio.pictures)
        elif ext == ".mp3":
            audio = MP3(source_file)
            if audio.tags:
                for apic in audio.tags.getall('APIC'):
                    pic = Picture()
                    pic.data = apic.data
                    pic.mime = apic.mime or 'application/octet-stream'
                    pic.type = apic.type
                    pic.desc = apic.desc or ''
                    pictures.append(pic)
        elif ext in {".m4a", ".mp4", ".alac"}:
            audio = MP4(source_file)
            if audio.tags and 'covr' in audio.tags:
                for cover in audio.tags['covr']:
                    pic = Picture()
                    if isinstance(cover, MP4Cover):
                        if cover.imageformat == MP4Cover.FORMAT_JPEG:
                            pic.mime = 'image/jpeg'
                        elif cover.imageformat == MP4Cover.FORMAT_PNG:
                            pic.mime = 'image/png'
                        else:
                            pic.mime = 'application/octet-stream'
                        pic.data = bytes(cover)
                    else:
                        pic.mime = 'application/octet-stream'
                        pic.data = cover
                    pic.type = 3  # Front cover
                    pic.desc = 'Cover'
                    pictures.append(pic)
        # WAV and other formats typically lack embedded artwork; skip silently
    except Exception as e:
        print(f"Warning: Unable to extract artwork from {source_file}: {e}")

    return pictures


def copy_artwork(source_file, dest_file):
    """Copy artwork from source to destination FLAC file"""
    try:
        dest_audio = FLAC(dest_file)

        # Clear existing pictures
        dest_audio.clear_pictures()

        source_pictures = extract_pictures(source_file)

        # Copy all pictures from source
        if source_pictures:
            for picture in source_pictures:
                dest_audio.add_picture(picture)
            dest_audio.save()
            return True
        else:
            print(f"No artwork found in {source_file}")
            return False
    except Exception as e:
        print(f"Error copying artwork: {e}")
        return False


def normalize_and_convert_to_mp3(source_flac, output_mp3, target_peak=-0.1):
    """
    Detect peak level, normalize to target peak using linear gain, and convert to MP3
    """
    # Detect current peak level
    peak_level = detect_file_peak_level(source_flac)

    if peak_level is None:
        print(f"Error: Could not detect peak level for {source_flac}")
        return False

    # Calculate gain adjustment needed to reach target peak
    gain_adjustment = target_peak - peak_level

    print(f"  Current peak: {peak_level:.2f}dB, Target: {target_peak:.2f}dB, Adjustment: {gain_adjustment:.2f}dB")

    # Convert to MP3 with normalization using volume filter (linear gain)
    cmd = (f'ffmpeg -y -i "{source_flac}" '
           f'-af "volume={gain_adjustment}dB" '
           f'-c:a libmp3lame -q:a 0 '
           f'"{output_mp3}"')

    success, _ = run_command(cmd)
    return success


def copy_metadata_flac_to_mp3(source_flac, dest_mp3):
    """Copy metadata and artwork from FLAC to MP3 using mutagen"""
    try:
        # Read source FLAC
        flac_audio = FLAC(source_flac)

        # Read destination MP3
        mp3_audio = MP3(dest_mp3)

        # Create ID3 tag if it doesn't exist
        if mp3_audio.tags is None:
            mp3_audio.add_tags()

        # Map common FLAC tags to ID3
        tag_mapping = {
            'title': TIT2,
            'album': TALB,
            'artist': TPE1,
            'albumartist': TPE2,
            'tracknumber': TRCK,
            'genre': TCON,
            'date': TDRC,
        }

        # Copy basic tags
        for flac_key, id3_frame in tag_mapping.items():
            if flac_key in flac_audio:
                value = flac_audio[flac_key][0]
                mp3_audio.tags.add(id3_frame(encoding=3, text=value))

        # Copy comment
        if 'comment' in flac_audio:
            mp3_audio.tags.add(COMM(encoding=3, lang='eng', desc='', text=flac_audio['comment'][0]))

        # Copy compilation tag
        if 'compilation' in flac_audio:
            mp3_audio.tags.add(TXXX(encoding=3, desc='COMPILATION', text=flac_audio['compilation'][0]))

        # Copy ReplayGain tags
        replaygain_tags = [
            'replaygain_reference_loudness',
            'replaygain_track_gain',
            'replaygain_track_peak',
            'replaygain_album_gain',
            'replaygain_album_peak',
            'replaygain_algorithm'
        ]

        for rg_tag in replaygain_tags:
            if rg_tag in flac_audio:
                mp3_audio.tags.add(TXXX(encoding=3, desc=rg_tag.upper(), text=flac_audio[rg_tag][0]))

        # Copy artwork
        if flac_audio.pictures:
            for picture in flac_audio.pictures:
                apic = APIC(
                    encoding=3,
                    mime=picture.mime,
                    type=picture.type,
                    desc=picture.desc,
                    data=picture.data
                )
                mp3_audio.tags.add(apic)

        mp3_audio.save()
        return True

    except Exception as e:
        print(f"Error copying metadata from {source_flac} to {dest_mp3}: {e}")
        return False


def process_normalization(final_files_list, is_compilation):
    """Process normalization and MP3 conversion for all output files"""
    print("\n\n=== Starting Normalization Process ===")

    mp3_files = []
    created_normalized_dirs = set()

    for flac_file in final_files_list:
        if not os.path.exists(flac_file):
            print(f"Warning: {flac_file} not found, skipping...")
            continue

        source_dir = os.path.dirname(flac_file) or "."
        normalized_dir = os.path.join(source_dir, "Normalised")

        if normalized_dir not in created_normalized_dirs:
            os.makedirs(normalized_dir, exist_ok=True)
            print(f"Created '{normalized_dir}' folder")
            created_normalized_dirs.add(normalized_dir)

        # Generate output filename
        filename_no_ext = os.path.splitext(os.path.basename(flac_file))[0]
        mp3_filename = os.path.join(normalized_dir, f"{filename_no_ext}.mp3")

        print(f"\nProcessing: {flac_file}")

        # Normalize and convert to MP3
        success = normalize_and_convert_to_mp3(flac_file, mp3_filename, target_peak=-0.1)

        if not success:
            print(f"Error: Failed to normalize and convert {flac_file}")
            continue

        # Copy metadata from FLAC to MP3
        metadata_success = copy_metadata_flac_to_mp3(flac_file, mp3_filename)

        if not metadata_success:
            print(f"Warning: Failed to copy metadata for {mp3_filename}")

        mp3_files.append(mp3_filename)
        print(f"Successfully created: {mp3_filename}")

    # Apply ReplayGain to all MP3 files
    if mp3_files:
        if is_compilation:
            # For compilations, apply track mode to each file individually
            print(f"\nApplying ReplayGain (track mode) to {len(mp3_files)} MP3 files...")
            for mp3_file in mp3_files:
                apply_replaygain_track(mp3_file)
        else:
            # For albums, apply album mode to all files together
            print(f"\nApplying ReplayGain (album mode) to {len(mp3_files)} MP3 files...")
            apply_replaygain_album(mp3_files)
        print("ReplayGain applied successfully")

        # Add the reference tags AFTER rsgain has run
        for mp3_file in mp3_files:
            try:
                mp3_audio = MP3(mp3_file)
                if mp3_audio.tags is None:
                    mp3_audio.add_tags()
                mp3_audio.tags.add(TXXX(encoding=3, desc='REPLAYGAIN_REFERENCE_LOUDNESS', text='-23 LUFS'))
                mp3_audio.tags.add(TXXX(encoding=3, desc='REPLAYGAIN_ALGORITHM', text='ITU-R BS.1770'))
                mp3_audio.save()
            except Exception as e:
                print(f"Warning: Failed to add ReplayGain reference tags to {mp3_file}: {e}")

    print("\n=== Normalization Process Complete ===")
    print(f"Created {len(mp3_files)} normalized MP3 files in 'Normalised' subfolders")


def main():
    print("\n\nWelcome to the automated Drumless folder Demuxer extraordinaire!")
    print("----------------------------------------------------------------\n")

    # Check dependencies
    print("Checking dependencies...")
    check_dependency("ffmpeg", "command")
    check_dependency("rsgain", "command")

    # Check Python modules with better error messages
    if not MUTAGEN_AVAILABLE:
        print("Error: Python module 'mutagen' is not installed.")
        print("Install it with: pip install mutagen")
        sys.exit(1)

    if not AUDIO_SEPARATOR_AVAILABLE:
        print("Error: Python module 'audio-separator' is not installed.")
        print("Install it with: pip install audio-separator")
        sys.exit(1)

    print("All dependencies found!\n")

    # Get user's model selection
    demucs_model = get_model_selection()

    # Initialize audio separator
    separator = Separator(
        output_format='WAV',
        output_dir='./separated'
    )
    separator.load_model(model_filename=demucs_model)

    # List to hold output files
    final_files_list = []

    # Ask if compilation
    is_compilation = get_compilation_input()

    # Ask if user wants normalized MP3 versions
    create_normalized = get_normalization_input()

    # Process each supported audio file
    audio_files = find_audio_files(".", SUPPORTED_INPUT_EXTENSIONS)

    if not audio_files:
        print("No supported audio files found in current directory or subdirectories.")
        return

    for file in audio_files:
        file_dir = os.path.dirname(file)
        filename = os.path.splitext(file)[0]
        wav_dir = f"separated"
        output_filename = f"{filename} - Drumless.flac"
        staging_dir = file_dir if file_dir else "."
        staging_file = os.path.join(staging_dir, "staging.flac")

        # Run separation
        print(f"Processing: {file}")

        output_names = {
            "Vocals": "vocals",
            "Guitar": "guitar",
            "Piano": "piano",
            "Drums": "drums",
            "Bass": "bass",
            "Other": "other"
        }

        try:
            output_files = separator.separate(file, output_names)
            success = True
        except Exception as e:
            print(f"\n\n\nError: Failed to execute the separation command for {file}: {e}\n\n\n")
            # Clean up separated directory if it exists
            if os.path.exists(wav_dir):
                shutil.rmtree(wav_dir)
            continue

        # Detect peak level
        peak_level = detect_peak_level(wav_dir)

        if peak_level is None:
            print(f"Error: Could not detect peak level for {file}")
            # Clean up separated directory
            if os.path.exists(wav_dir):
                shutil.rmtree(wav_dir)
            continue

        # Determine if gain adjustment is needed
        gain_db = None
        if peak_level > -0.1:
            gain_db = -(peak_level + 0.1)
            print(f"Peak detected at {peak_level}dB. Applying {gain_db}dB reduction to prevent clipping.")
        else:
            print(f"Peak at {peak_level}dB - no clipping protection needed.")

        # Merge audio files
        merge_success = merge_audio_files(wav_dir, staging_file, gain_db)

        if not merge_success:
            print(f"\n\n\nError: Failed to execute the merge files ffmpeg command for {file}.\n\n\n")
            # Clean up staging file if it was partially created
            if os.path.exists(staging_file):
                os.remove(staging_file)
            # Clean up separated directory
            if os.path.exists(wav_dir):
                shutil.rmtree(wav_dir)
            continue

        # Copy metadata
        metadata_success = copy_metadata(file, staging_file, output_filename, is_compilation)

        if not metadata_success:
            print(f"Error: Failed to copy metadata for {file}")
            if os.path.exists(staging_file):
                os.remove(staging_file)
            # Clean up separated directory
            if os.path.exists(wav_dir):
                shutil.rmtree(wav_dir)
            continue

        # Apply ReplayGain for compilation tracks
        if is_compilation:
            apply_replaygain_track(output_filename)

        final_files_list.append(output_filename)

        # Clean up staging file
        if os.path.exists(staging_file):
            os.remove(staging_file)

        # Remove separated wav files
        if os.path.exists(wav_dir):
            shutil.rmtree(wav_dir)

        # Copy artwork from supported sources
        copy_artwork(file, output_filename)

        # Set additional tags using mutagen
        tags_to_set = {
            'COMMENT': 'Drumless (Lossless)',
            'DESCRIPTION': f'Stem Separation Model = {demucs_model}',
            'REPLAYGAIN_REFERENCE_LOUDNESS': '-23 LUFS',
            'REPLAYGAIN_ALGORITHM': 'ITU-R BS.1770'
        }
        set_flac_tags(output_filename, tags_to_set)

    # Apply album-mode ReplayGain for non-compilation albums
    if not is_compilation and final_files_list:
        apply_replaygain_album(final_files_list)

        for album_file in final_files_list:
            tags_to_set = {
                'REPLAYGAIN_REFERENCE_LOUDNESS': '-23 LUFS',
                'REPLAYGAIN_ALGORITHM': 'ITU-R BS.1770'
            }
            set_flac_tags(album_file, tags_to_set)

    # Clean up separated folder
    if os.path.exists("separated"):
        shutil.rmtree("separated")

    print("\n\nMain processing complete!")

    # Process normalization if requested
    if create_normalized and final_files_list:
        process_normalization(final_files_list, is_compilation)

    print("\n\nAll processing complete!")


if __name__ == "__main__":
    main()
