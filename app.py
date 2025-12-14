import gradio as gr
import os
import shutil
import subprocess
import time

# --- 1. CONFIGURATION ---
UPSCALER_BIN = "./executable"
TEMP_BASE = "/app/temp_data"

# --- 2. WATI DESIGN SYSTEM CSS (Same as before) ---
wati_css = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
:root { --primary-main: #1BD760; --primary-dark: #0C9A3F; --primary-light: #D9F7E8; --ink-900: #111827; --radius-lg: 16px; --radius-pill: 999px; }
body, .gradio-container { font-family: 'Inter', sans-serif !important; background-color: #FFFFFF; color: var(--ink-900); }
.gradio-container { max-width: 1120px !important; margin: 0 auto; padding-top: 40px; }
h1 { font-weight: 800 !important; font-size: 40px !important; }
.group-container { background: #FFFFFF; border: 1px solid rgba(15, 23, 42, 0.04); border-radius: var(--radius-lg); box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08); padding: 32px; margin-bottom: 24px; }
button.primary { background: var(--primary-main) !important; color: white !important; font-weight: 600 !important; border-radius: var(--radius-pill) !important; padding: 12px 32px !important; border: none !important; }
button.primary:hover { background: var(--primary-dark) !important; }
"""

# --- 3. HELPER FUNCTIONS ---
def clean_path(path):
    if os.path.exists(path): shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)

# --- 4. IMAGE LOGIC ---
def process_images(files, model_name):
    job_id = str(int(time.time()))
    upload_dir = f"{TEMP_BASE}/{job_id}/in"
    output_dir = f"{TEMP_BASE}/{job_id}/out"
    clean_path(upload_dir)
    clean_path(output_dir)

    # Save Uploads
    for file in files: shutil.copy(file.name, upload_dir)
    
    # Run 24-Core Image Batch
    cmd = f"find {upload_dir} -type f | parallel -j 6 '{UPSCALER_BIN} -i {{}} -o {output_dir}/{{/.}}.png -n {model_name}'"
    subprocess.run(cmd, shell=True)
    
    # Zip Results
    zip_path = f"{TEMP_BASE}/{job_id}/results"
    shutil.make_archive(zip_path, 'zip', output_dir)
    return f"{zip_path}.zip"

# --- 5. VIDEO LOGIC (The New Part) ---
def process_video(video_file, model_name):
    if not video_file: return None
    
    job_id = str(int(time.time()))
    work_dir = f"{TEMP_BASE}/{job_id}"
    frames_in = f"{work_dir}/frames_in"
    frames_out = f"{work_dir}/frames_out"
    clean_path(frames_in)
    clean_path(frames_out)
    
    output_video = f"{work_dir}/upscaled_video.mp4"
    
    # Step A: Extract Frames
    # We use -q:v 2 for high quality frame extraction
    extract_cmd = f"ffmpeg -i {video_file} -q:v 2 {frames_in}/frame_%08d.jpg"
    subprocess.run(extract_cmd, shell=True)
    
    # Step B: Upscale Frames (Parallel)
    # Using 6 threads to saturate your 24 cores
    upscale_cmd = f"find {frames_in} -name '*.jpg' | parallel -j 6 '{UPSCALER_BIN} -i {{}} -o {frames_out}/{{/.}}.png -n {model_name}'"
    subprocess.run(upscale_cmd, shell=True)
    
    # Step C: Get Framerate
    fps_cmd = f"ffprobe -v 0 -of csv=p=0 -select_streams v:0 -show_entries stream=r_frame_rate {video_file}"
    try:
        fps = subprocess.check_output(fps_cmd, shell=True).decode().strip().eval()
    except:
        fps = 30 # Fallback
        
    # Step D: Stitch Video
    stitch_cmd = f"ffmpeg -framerate 30 -i {frames_out}/frame_%08d.png -i {video_file} -map 0:v -map 1:a -c:v libx264 -pix_fmt yuv420p -crf 23 -preset medium {output_video}"
    subprocess.run(stitch_cmd, shell=True)
    
    return output_video

# --- 6. UI ---
with gr.Blocks(css=wati_css, theme=gr.themes.Base()) as demo:
    with gr.Column(elem_classes="gradio-container"):
        gr.Markdown("# 🚀 Media Enhancement Studio")
        
    with gr.Tabs():
        # --- TAB 1: IMAGES ---
        with gr.TabItem("🖼️ Image Batch"):
            with gr.Column(elem_classes="group-container"):
                gr.Markdown("### Upload Images")
                img_input = gr.File(file_count="multiple", label="Upload Images")
                model_sel = gr.Dropdown(["realesrgan-x4plus", "realesrgan-x4plus-anime"], value="realesrgan-x4plus", label="Model")
                btn_img = gr.Button("Upscale Images", variant="primary")
                out_zip = gr.File(label="Download Zip")
                btn_img.click(process_images, inputs=[img_input, model_sel], outputs=out_zip)

        # --- TAB 2: VIDEO (NEW) ---
        with gr.TabItem("🎥 Video Upscaler"):
            with gr.Column(elem_classes="group-container"):
                gr.Markdown("### Upload Video (MP4)")
                gr.Markdown("*Note: This splits the video into frames and uses all 24 Cores. A 1-minute video may take 10-20 mins.*")
                
                vid_input = gr.Video(label="Upload Video", format="mp4")
                model_sel_vid = gr.Dropdown(["realesrgan-x4plus", "realesrgan-x4plus-anime"], value="realesrgan-x4plus", label="Model")
                
                btn_vid = gr.Button("Start Video Upscale", variant="primary")
                out_vid = gr.Video(label="Download Result")
                
                btn_vid.click(process_video, inputs=[vid_input, model_sel_vid], outputs=out_vid)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)