import gradio as gr
import os
import shutil
import subprocess
import time

# --- 1. CONFIGURATION ---
UPSCALER_BIN = "./executable"
TEMP_BASE = "/app/temp_data"

# --- 2. WATI DESIGN SYSTEM CSS ---
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

# --- 4. IMAGE LOGIC (FIXED) ---
def process_images(files, model_name):
    # Error Handling: If something breaks, show it in the UI instead of crashing
    try:
        if not files: return None
        
        job_id = str(int(time.time()))
        upload_dir = f"{TEMP_BASE}/{job_id}/in"
        output_dir = f"{TEMP_BASE}/{job_id}/out"
        clean_path(upload_dir)
        clean_path(output_dir)

        # --- FIX: Handle file paths correctly for Gradio 4 ---
        for file_path in files:
            # Gradio sends the full temp path string (e.g. /tmp/gradio/image.jpg)
            filename = os.path.basename(file_path)
            shutil.copy(file_path, os.path.join(upload_dir, filename))
        
        # Run 24-Core Image Batch
        # We use explicit environment variables to force CPU usage here too
        env = os.environ.copy()
        env["VK_ICD_FILENAMES"] = "/usr/share/vulkan/icd.d/lvp_icd.x86_64.json"
        
        cmd = f"find {upload_dir} -type f | parallel -j 6 '{UPSCALER_BIN} -i {{}} -o {output_dir}/{{/.}}.png -n {model_name}'"
        subprocess.run(cmd, shell=True, env=env)
        
        # Zip Results
        zip_path = f"{TEMP_BASE}/{job_id}/results"
        shutil.make_archive(zip_path, 'zip', output_dir)
        return f"{zip_path}.zip"
    
    except Exception as e:
        raise gr.Error(f"System Error: {str(e)}")

# --- 5. VIDEO LOGIC ---
def process_video(video_file, model_name):
    try:
        if not video_file: return None
        
        job_id = str(int(time.time()))
        work_dir = f"{TEMP_BASE}/{job_id}"
        frames_in = f"{work_dir}/frames_in"
        frames_out = f"{work_dir}/frames_out"
        clean_path(frames_in)
        clean_path(frames_out)
        
        output_video = f"{work_dir}/upscaled_video.mp4"
        
        # Setup Env
        env = os.environ.copy()
        env["VK_ICD_FILENAMES"] = "/usr/share/vulkan/icd.d/lvp_icd.x86_64.json"

        # 1. Extract
        subprocess.run(f"ffmpeg -i {video_file} -q:v 2 {frames_in}/frame_%08d.jpg", shell=True)
        
        # 2. Upscale (Parallel)
        subprocess.run(f"find {frames_in} -name '*.jpg' | parallel -j 6 '{UPSCALER_BIN} -i {{}} -o {frames_out}/{{/.}}.png -n {model_name}'", shell=True, env=env)
        
        # 3. Stitch
        fps_cmd = f"ffprobe -v 0 -of csv=p=0 -select_streams v:0 -show_entries stream=r_frame_rate {video_file}"
        try:
            fps_raw = subprocess.check_output(fps_cmd, shell=True).decode().strip().split('/')
            fps = float(fps_raw[0]) / float(fps_raw[1]) if len(fps_raw) == 2 else 30
        except:
            fps = 30
            
        subprocess.run(f"ffmpeg -framerate {fps} -i {frames_out}/frame_%08d.png -i {video_file} -map 0:v -map 1:a -c:v libx264 -pix_fmt yuv420p -crf 23 -preset medium {output_video}", shell=True)
        
        return output_video
    except Exception as e:
        raise gr.Error(f"Video Error: {str(e)}")

# --- 6. UI ---
with gr.Blocks(css=wati_css, theme=gr.themes.Base()) as demo:
    with gr.Column(elem_classes="gradio-container"):
        gr.Markdown("# 🚀 Media Enhancement Studio")
        
    with gr.Tabs():
        # --- TAB 1: IMAGES ---
        with gr.TabItem("🖼️ Image Batch"):
            with gr.Column(elem_classes="group-container"):
                gr.Markdown("### Upload Images")
                # FIX: Explicitly set type="filepath" to get string paths
                img_input = gr.File(file_count="multiple", label="Upload Images", type="filepath") 
                model_sel = gr.Dropdown(["realesrgan-x4plus", "realesrgan-x4plus-anime"], value="realesrgan-x4plus", label="Model")
                btn_img = gr.Button("Upscale Images", variant="primary")
                out_zip = gr.File(label="Download Zip")
                btn_img.click(process_images, inputs=[img_input, model_sel], outputs=out_zip)

        # --- TAB 2: VIDEO ---
        with gr.TabItem("🎥 Video Upscaler"):
            with gr.Column(elem_classes="group-container"):
                gr.Markdown("### Upload Video (MP4)")
                # FIX: Explicitly set type="filepath"
                vid_input = gr.Video(label="Upload Video", format="mp4")
                model_sel_vid = gr.Dropdown(["realesrgan-x4plus", "realesrgan-x4plus-anime"], value="realesrgan-x4plus", label="Model")
                
                btn_vid = gr.Button("Start Video Upscale", variant="primary")
                out_vid = gr.Video(label="Download Result")
                
                btn_vid.click(process_video, inputs=[vid_input, model_sel_vid], outputs=out_vid)

# --- CRITICAL FIX: Enable Queue for Progress Bars & Long Tasks ---
if __name__ == "__main__":
    demo.queue()
    # We remove explicit arguments because we set them in Dockerfile ENV
    demo.launch(show_error=True)
