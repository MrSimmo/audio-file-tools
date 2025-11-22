# Audio File Tools
This repo is my general storage for home-made quick and dirty scripts/tools to manipulate audio files.

Help yourself, hope they're useful. For these, I'll probably not update them with any requests so please don't log issues.

I tested on MacOS and Linux; I've not used Windows in >15 years so who knows if they'll work over there.

Essentially I wanted solutions to take input audio files, remove the drum track (so they can be played along to by drummers), then do stuff to make them function better with Roland's extremely limited V71 song player!


Here are some of the tools:

**bulk_convert_to_mp3.sh**

- This uses ffmpeg to convert a whole folder (and subfolders) full of audio files (FLAC, WAV, MP4 etc) to MP3.

= The reason I wrote this was that the Roland V71 only accepts WAV and MP3 files in the song player (sigh).


**normalise_audio_file_folder.sh**

- This uses fmpeg to normalise a whole folder (and subfolders) full of audio files (FLAC, WAV, MP4, MP3 etc).
- It normalises to -1db using ffmpeg's linear mode (i.e. reads the whole track and raise the volume for the whole track instead of parts)
- It also includes ffmpeg clipping protection feature so it doesn't normalise so loud it starts clipping.

= The reason I wrote this, is to set gain levels for each song in the Roland V71 is painful and the V71 doesn't read or use any replaygain
  tags (again sigh). This means that when you play back songs using the song player, they play at different volumes.


**drumless_demux.py**

A much improved version of the Drumless demuxer script. This version allows the use of the latest and highest quality stem separation models, now rivalling or sometimes beating commercial offerings on SDR/fullness/bleedless.

Changes are:

1. Changes the backend stem splitting tool to use python audio separator. This allows us to use the most up to date models such as BS-Roformer-SW for much improved quality and speed.

2. Now allows multiple and hi-res input file types.

3. Ported it to Python with improved error handling. This lays the ground work for a web based demuxer imterface. 

4. Decreased the amount of external tools in favour of python libraries. Note - I would shift the replaygain to ffmpeg but ffmpeg isn't as good as rsgain at this point for replaygain work.

5. Fixes a ffmpeg command error (I was amerging instead of amixing which resulted in muddied outputs)

6. Added recursive folder support.

7. Added extra support to output a second (mp3) file which is prepared to load straight into the Roland V71 drum module.

8. Fixed bugs in the quality settings so that the output now is much higher than before.





**OLD: (use the much newer python demuxer script!)... remove-drumtrack-using-demucs.sh**

- This is quite a complicated script. It removes the drum track from a folder of FLAC music files using HTDEMUCS. But it does
  other things too.

- Features include:
  1. Prompt the user to whether we're processing an entire album or a collection (compilation of songs)
  2. Uses HTDEMUCS in the highest quality setting (Demucs4_FT) and attempts to use Apple Silicon GPU encoding if possible
  3. Uses ffmpeg to copy the id3 tags from the source files to the destination and then add useful other info such as Drumless to comments and Demucs model used with kid3.
  4. Add compilation and album artist as Various Artists id3 if usr chose compilation in (1).
  5. Uses kid3 to copy the cover art/picture from the source files to the desintation.
  6. Uses ffmpeg to set id3 tags for Album or Compilation etc so music libraries can process them properly.
  7. Uses RSGAIN to calculate and set ReplayGain tags to the output files. Noting RSGAIN doesnt support all Replaygain tags properly so use kid3 to write those. Calcuate Album gain if the user chose album in (1)


= The reason I wrote this was that I have a large collection of purchased music files in FLAC formats. I'm also a drummer. I want to be
  able to play along to real backing music. I don't want to pay a hefty ongoing subscription to commercial services such as Moises, and the other
  tools are missing features that I want/need.
