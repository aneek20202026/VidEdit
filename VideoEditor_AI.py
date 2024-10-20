import streamlit as st
import requests
from moviepy.editor import VideoFileClip, AudioFileClip
import os
import io
from google.cloud import speech,texttospeech

uploaded_video=None

def AI_Editor(text,tot_time):
    azure_openai_key = "22ec84421ec24230a3638d1b51e3a7dc"
    azure_openai_endpoint = "https://internshala.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-08-01-preview"
    if azure_openai_key and azure_openai_endpoint:
        try:
            headers = {
                "Content-Type": "application/json",
                "api-key": azure_openai_key
            }
            prompt = (
                "The input provided is in SSML format. Please correct any grammatical errors and remove discrepancies, ensuring the overall time of the audio remains the same."
                "Convert the SSML format into plain text, adding appropriate punctuation to reflect the break times."
                "Each break should be represented by a suitable punctuation mark (such as a comma, period, ellipsis, or dash) to mimic the duration of the pauses."
                "Replace filler words such as 'umms' and 'hmms' with appropriate punctuation to reflect the length of those pauses."
                "If there is a pause before the voice starts, add suitable punctuation to reflect that time as well. Ensure the pauses and overall pacing of the speech remain intact."
                "Please ensure that the final text reflects the natural flow of speech, maintaining the original timing and pacing of the audio."
                "Do not use code block formatting.\n\n"
                f"Original audio: {text}"
                f"Overall duration: {tot_time}s"
            )
            data = {
                "messages": [
                    {"role": "system", "content": "You will receive SSML format text. The overall time will be mentioned. Correct the grammar and keep the overall time same."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 500 
            }
            
            response = requests.post(azure_openai_endpoint, headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                return f"Failed to connect or retrieve response: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Failed to connect or retrieve response: {str(e)}"
    else:
        st.warning("Please enter all the required details.")
    
def extract_audio_from_video(video_path):
    with VideoFileClip(video_path) as video:
        audio_path = os.path.join("temp", "temp_audio.wav")
        video.audio.write_audiofile(audio_path, codec="pcm_s16le", ffmpeg_params=["-ac", "1"])
        return audio_path

def speech_to_text(audio_path):
    client = speech.SpeechClient()
    with io.open(audio_path, "rb") as audio_file:
        content = audio_file.read()
        
    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        # sample_rate_hertz=16000,
        language_code="en-US",
        enable_word_time_offsets=True
    )

    response = client.recognize(config=config, audio=audio)
    transcript , timestamps, overall_time = "", [], 0.0

    for result in response.results:
        for alternative in result.alternatives:
            transcript += alternative.transcript            
            for word in alternative.words:
                timestamps.append({
                    "word":word.word,
                    "start_time":word.start_time.total_seconds(),
                    "end_time":word.end_time.total_seconds()
                })
                overall_time=word.end_time.total_seconds()
                
    formatted_text=timestamps_to_ssml(timestamps)

    return transcript, formatted_text,overall_time

def timestamps_to_ssml(timestamps):
    ssml_output = "<speak>"
    previous_end_time = 0.0

    for entry in timestamps:
        word = entry['word']
        start = entry['start_time']
        end = entry['end_time']
        if start > previous_end_time:
            gap = start - previous_end_time
            ssml_output += f"<break time='{gap:.1f}s'/>"
        ssml_output += f" {word}"
        previous_end_time = end

    ssml_output += " </speak>"
    return ssml_output

def text_to_speech(text, output_audio_path="temp/final_audio.mp3", model="en-US-Journey-F"):
    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        name=model,
        language_code="en-US",
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    with open(output_audio_path, "wb") as out:
        out.write(response.audio_content)
        
def replace_audio_in_video(video_path, new_audio_path="temp/final_audio.mp3", output_video_path="temp/final_video.mp4"):
    video_clip = VideoFileClip(video_path)
    new_audio = AudioFileClip(new_audio_path)
    final_video = video_clip.set_audio(new_audio)
    final_video.write_videofile(output_video_path, codec='libx264', audio_codec='aac')

    video_clip.close()
    new_audio.close()
    final_video.close()
    return output_video_path

def main():
    global uploaded_video
    st.title("Video-AI Voice Correction") 

    uploaded_video = st.file_uploader("Upload a video", type=["mp4", "mov", "avi"])
    
    if uploaded_video is not None:
        os.makedirs("temp",exist_ok=True)

        video_path = os.path.join("temp", uploaded_video.name)
        with open(video_path, "wb") as f:
            f.write(uploaded_video.read())

        st.video(uploaded_video)

        if st.button("Enhance audio"):
            audio_path = extract_audio_from_video(video_path)
            with st.spinner("Transcribing..."):
                transcript,format_text,tot_time = speech_to_text(audio_path)
            with st.spinner("Correcting..."):
                corr_script=AI_Editor(format_text,tot_time)
            # print(corr_script)
            with st.spinner("Converting to audio..."):
                text_to_speech(corr_script)
            with st.spinner("Replacing audio in the provided video..."):
                output_video_path=replace_audio_in_video(video_path)
            st.success("Audio replaced successfully!")
            st.video(output_video_path)

if __name__ == "__main__":
    main()