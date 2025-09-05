#!/bin/bash

# needs ffmpeg installed in the path (maybe https://www.osxexperts.net)
# assumes facebookresearchdemucs is installed in the python3 path (https://github.com/facebookresearch/demucs)
# assumes python3 is installed
# needs kid3 installed https://kid3.kde.org
# needs rsgain installed and in path https://github.com/complexlogic/rsgain
# wrote and tested on MacOS Sequoia, may work on others, may not


demucsmodel="htdemucs_ft"
# alternative model could be mdx_extra instead of htdemucs_ft
# note - using the GPU flag -d mps ; on models other than htdemucs or htdemucs_ft causes silent tiny files to be outputted


echo "\n\nWelcome to the automated Drumless folder Demuxer extraordinaire!"
echo     "----------------------------------------------------------------\n"

# check for dependencies
if ! which "ffmpeg" &> /dev/null; then
    echo "Error: 'ffmpeg' not found in PATH."
    exit 1
fi
if ! which "rsgain" &> /dev/null; then
    echo "Error: 'rsgain' not found in PATH."
    exit 1
fi
if [[ ! -f "/Applications/kid3.app/Contents/MacOS/kid3-cli" ]]; then
    echo "Error: File '/Applications/kid3.app/Contents/MacOS/kid3-cli' does not exist."
    exit 1
fi
if ! python3 -c "import demucs" 2>/dev/null; then
    echo "Error: Python module 'demucs' is not installed."
    exit 1
fi



# create an array to hold the output files list
finalfileslist=()



# better version of the below question with error checking
while true; do
    read -r -n 1 -p 'Is this a compilation rather than one artist? y/n or Y/N ' compilation
    echo ""  # Print a newline
    if [[ "$compilation" =~ ^[YyNn]$ ]]; then
        break
    else
        echo "Invalid input. Please enter y/Y or n/N."
    fi
done


#read -r -n 1 -p 'Is this a compilation rather than one artist? y/n or Y/N ' compilation

for file in *.flac; do
#  echo "\n\n\nDemuxing the source file... $file"
#  echo "\n\n\n"
  if python3 -m demucs -n "$demucsmodel" -d mps "$file"; then
    filename="${file%.*}"
    wav_dir="separated/$demucsmodel/$filename"
    filenameout="$filename - Drumless.${file##*.}"
    stagingfile="staging.flac"

    wav_files=()
    for f in "$wav_dir"/*.wav; do
      if [[ $f != *"drums.wav" ]]; then
        wav_files+=("-i" "$f")
      fi
    done

 #   echo "\n\n\nCreating a new FLAC file from the split audio, minus the drums...\n\n\n"

    if ffmpeg "${wav_files[@]}" -compression_level 8 -filter_complex "amerge=inputs=$(ls "$wav_dir"/*.wav | grep -v "drums.wav" | wc -l)" -ac 2 "$stagingfile"; then

 #     echo "\n\n\nCopying the id3 tag information from the source file to the final FLAC file...\n\n\n"
      if [[ "$compilation" = "y" || "$compilation" == "Y" ]]; then
        ffmpeg -y -i "$file" -i "$stagingfile" -map_metadata 0 -map 1:a -c copy -movflags use_metadata_tags -write_id3v2 1 -metadata compilation="1" -metadata album_artist="Various Artists" -metadata album='Drumless (Lossless)' "$filenameout"
         rsgain custom --tagmode=i --loudness=-23 --clip-mode=p --max-peak=0 --true-peak --id3v2-version=keep "$filenameout" 
      else
        ffmpeg -y -i "$file" -i "$stagingfile" -map_metadata 0 -map 1:a -c copy -movflags use_metadata_tags -write_id3v2 1 "$filenameout"
#         rsgain custom --tagmode=i --loudness=-23 --clip-mode=p --max-peak=0 --true-peak --id3v2-version=keep --album *"- Drumless.flac"  
      fi

      finalfileslist+=("$filenameout")

    else
      echo "\n\n\nError: Failed to execute the merge files ffmpeg command.\n\n\n"
      continue
    fi
  else
    echo "\n\n\nError: Failed to execute the demucs command.\n\n\n"
    continue
  fi
  sleep 1s

#  echo "\n\n\nRemoving temporary files...\n\n\n"
  rm "$stagingfile"

 # comment out the next line if you want to keep the separated wav files
  rm -rf "$wav_dir"


# copy and set other id3tags
#  echo "Copying artwork tag"
  /Applications/kid3.app/Contents/MacOS/kid3-cli -c "get picture:'./artworktemp.jpg'" "$file"
  /Applications/kid3.app/Contents/MacOS/kid3-cli -c "set picture:'./artworktemp.jpg' 'artwork.jpg'"  "$filenameout"
  rm "./artworktemp.jpg"

# echo "Settings misc tags"
/Applications/kid3.app/Contents/MacOS/kid3-cli -c "set Comment 'Drumless (Lossless)'" "$filenameout" 
/Applications/kid3.app/Contents/MacOS/kid3-cli -c "set Description 'Demucs Model = $demucsmodel'" "$filenameout" 
/Applications/kid3.app/Contents/MacOS/kid3-cli -c "set REPLAYGAIN_REFERENCE_LOUDNESS '-23 LUFS'" "$filenameout" 
/Applications/kid3.app/Contents/MacOS/kid3-cli -c "set REPLAYGAIN_ALGORITHM 'ITU-R BS.1770'" "$filenameout" 




 # echo "\n\n\nDone demuxing $file"
 # echo "\n\n\n"


#uncomment to delete the source file
#rm -rfv $file

done

# if the album option was set - run rsgain album mode on it
     if [[ "$compilation" = "n" || "$compilation" == "N" ]]; then
       rsgain custom --tagmode=i --loudness=-23 --clip-mode=p --max-peak=0 --true-peak --id3v2-version=keep --album "${finalfileslist[@]}"

     for albumfile in "${finalfileslist[@]}"; do
      # Execute kid3-cli with the file
       /Applications/kid3.app/Contents/MacOS/kid3-cli -c "set REPLAYGAIN_REFERENCE_LOUDNESS '-23 LUFS'" "$albumfile"
       /Applications/kid3.app/Contents/MacOS/kid3-cli -c "set REPLAYGAIN_ALGORITHM 'ITU-R BS.1770'" "$albumfile"
     done

     fi


 # comment out the next line if you want to keep the separated folder
  rm -rf "separated"
