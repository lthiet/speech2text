"""
https://stackoverflow.com/questions/62554058/subtitles-captions-with-microsoft-azure-speech-to-text-in-python
"""

import azure.cognitiveservices.speech as speechsdk
import time
import yaml
import datetime
import srt
import subprocess
import json

# Convert video to audio
command = "ffmpeg -i video.mp4 -ab 160k -ac 2 -ar 44100 -vn audio.wav"

subprocess.call(command, shell=True)

with open('cred.yaml', 'r') as f:
    cred = yaml.safe_load(f.read())

# Create SDK config
speech_key, service_region = cred["speech_key"], "westeurope"
speech_config = speechsdk.SpeechConfig(
    subscription=speech_key, region=service_region)

# Creates a recognizer with the given settings
speech_config.speech_recognition_language = "en-US"
speech_config.request_word_level_timestamps()

audio_config = speechsdk.audio.AudioConfig(filename="audio.wav")


speech_config.enable_dictation()  # TODO: is this really necessary?
speech_config.output_format = speechsdk.OutputFormat(1)
speech_recognizer = speechsdk.SpeechRecognizer(
    speech_config=speech_config, audio_config=audio_config)


all_results = []
results = []
transcript = []
words = []

done = False


def stop_cb(evt):
    print('CLOSING on {}'.format(evt))
    speech_recognizer.stop_continuous_recognition()
    global done
    done = True


def convertduration(t):
    x = t/10000
    return int((x / 1000)), (x % 1000)


transcript = []
index = 0
sec = 1
current_time = 0
last_duration = 0
last_start = 0
last_text = ""
last_offset = 0

# Timestamp from Microsoft Azure are actually too fast compared to the actual audio.
# This variable acts as some sort of slowing factor but more investigation is required.
# I suspect the duration field to be actually the time when their services
# actually finishes the computation, not the actual time stamp of the audio.
slow_factor = 16


def add_subtitle(evt):
    print(evt.result.json)
    global index
    global last_duration
    global last_start
    global last_text
    global last_offset

    data = json.loads((evt.result.json))
    if last_offset != data["Offset"]:
        last_start += last_duration
    current_duration = data["Duration"] + last_start

    start_s, start_ms = convertduration(last_duration*slow_factor)
    end_s, end_ms = convertduration(current_duration*slow_factor)

    transcript.append(srt.Subtitle(index, datetime.timedelta(
        seconds=start_s, milliseconds=start_ms), datetime.timedelta(seconds=end_s, milliseconds=end_ms), last_text))

    index += 1
    last_duration = current_duration
    last_text = data["Text"]
    last_offset = data["Offset"]


speech_recognizer.recognized.connect(
    lambda evt: print('RECOGNIZED'))
speech_recognizer.recognizing.connect(add_subtitle)
speech_recognizer.session_started.connect(
    lambda evt: print('SESSION STARTED: {}'.format(evt)))
speech_recognizer.session_stopped.connect(
    lambda evt: print('SESSION STOPPED {}'.format(evt)))
speech_recognizer.canceled.connect(
    lambda evt: print('CANCELED {}'.format(evt)))
speech_recognizer.session_stopped.connect(stop_cb)
speech_recognizer.canceled.connect(stop_cb)
speech_recognizer.start_continuous_recognition()
try:
    while not done:
        time.sleep(.5)

except KeyboardInterrupt:
    pass

subtitles = srt.compose(transcript)
with open("subtitle.srt", "w") as f:
    f.write(subtitles)
