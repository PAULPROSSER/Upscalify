import gradio as gr
import os
import shutil
import subprocess
import time

# --- 1. CONFIGURATION ---
# We use absolute path to match the Dockerfile location
UPSCALER_BIN = "/app/executable" 
TEMP_BASE = "/app/temp_data"

# Ensure temp directories exist at startup
os.makedirs(TEMP_BASE, exist_ok=True)

# --- 2. WATI DESIGN SYSTEM CSS ---
wati_css = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
:root { 
    --primary-main: #1BD760; 
    --primary-dark: #0C9A3F; 
    --primary-light: #D9F7E8; 
    --ink-900: #111827; 
    --radius-lg: 16px; 
    --radius-pill: 999px; 
}
body, .gradio-container { 
    font-family: 'Inter', sans-serif !important; 
    background-color: #FFFFFF; 
    color: var(--ink-900); 
}
.gradio-container { 
    max-width: 1120px !important; 
    margin: 0 auto; 
    padding-top: 40px; 
}
h1 { 
    font-weight: 800 !important; 
    font-size: 40px !important; 
    margin-bottom: 8px !important;
}
.subtitle {
    font-size: 18px;
    color: #4B5563;
    margin-bottom: 32px;
}
.group-container { 
    background: #FFFFFF; 
    border: 1px solid rgba(15, 23, 42, 0.04); 
    border-radius: var(--radius-lg); 
    box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08); 
    padding: 32px; 
    margin-bottom: 24px; 
}
button.primary { 
    background: var(--primary-main) !important; 
    color: white !important; 
    font-weight: 600 !important; 
    border-radius: var(--radius-pill) !important; 
    padding: 12px 32px !important; 
    border: none !important; 
    transition: all 0.2s;
}
button.primary:hover { 
    background: var(--primary-dark) !important; 
    transform: translateY(-1px);
}
"""

# --- 3. HELPER FUNCTIONS ---
def clean_path(path):
    if os.path.exists(path): 
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)

# --- 4. IMAGE LOGIC ---
def process_images(files, model_name):
    # Error Handling Block
    try:
        if not files: return None
        
        job_id = str(int(time.time()))
        upload_dir = f"{TEMP_BASE}/{job_id}/in"
        output_dir = f"{TEMP_BASE}/{job_id}/out"
        clean_path(upload_dir)
        clean_path(output_dir)

        # Handle Files (Gradio 4 passes paths as strings now)
        for file_path in files:
            filename = os.path.basename(file_path)
            shutil.copy(file_path, os.path.join(upload_dir, filename))
        
        # CPU Environment Variables (Crucial for Netcup)
        env = os.environ.copy()
        env["VK_ICD_FILENAMES"] = "/usr/share/vulkan/icd.d/lvp_icd.x86_64.json"
        
        # 24-Core Parallel Command
        cmd = f"find {upload_dir} -type f | parallel -j 6 '{UPSCALER_BIN} -i {{}} -o {output_dir}/{{/.}}.png -n {model_name}'"
        
        # Run process
        result = subprocess.run(cmd, shell=True, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Upscaling failed: {result.stderr}")
        
        # Zip Results
        zip_path = f"{TEMP_BASE}/{job_id}/results"
        shutil.make_archive(zip_path, 'zip', output_dir)
        return f"{zip_path}.zip"
    
    except Exception as e:
        raise gr.Error(f"Error processing images: {str(e)}")

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
        
        env = os.environ.copy()
        env["VK_ICD_FILENAMES"] = "/usr/share/vulkan/icd.d/lvp_icd.x86_64.json"

        # 1. Extract Frames
        subprocess.run(f"ffmpeg -i {video_file} -q:v 2 {frames_in}/frame_%08d.jpg", shell=True, check=True)
        
        # 2. Upscale (Parallel)
        upscale_cmd = f"find {frames_in} -name '*.jpg' | parallel -j 6 '{UPSCALER_BIN} -i {{}} -o {frames_out}/{{/.}}.png -n {model_name}'"
        subprocess.run(upscale_cmd, shell=True, env=env, check=True)
        
        # 3. Get Framerate
        fps_cmd = f"ffprobe -v 0 -of csv=p=0 -select_streams v:0 -show_entries stream=r_frame_rate {video_file}"
        try:
            fps_raw = subprocess.check_output(fps_cmd, shell=True).decode().strip().split('/')
            fps = float(fps_raw[0]) / float(fps_raw[1]) if len(fps_raw) == 2 else 30
        except:
            fps = 30
            
        # 4. Stitch Video
        stitch_cmd = f"ffmpeg -framerate {fps} -i {frames_out}/frame_%08d.png -i {video_file} -map 0:v -map 1:a -c:v libx264 -pix_fmt yuv420p -crf 23 -preset medium {output_video}"
        subprocess.run(stitch_cmd, shell=True, check=True)
        
        return output_video
    except Exception as e:
        raise gr.Error(f"Video Error: {str(e)}")

# --- 6. UI LAYOUT ---
# We pass theme/css here to avoid warnings
with gr.Blocks(theme=gr.themes.Base(), css=wati_css) as demo:
    
    with gr.Column(elem_classes="gradio-container"):
        gr.Markdown("# 🚀 Media Enhancement Studio")
        gr.Markdown('<div class="subtitle">High-performance 24-core upscaling engine.</div>')
        
    with gr.Tabs():
        # --- TAB 1: IMAGES ---
        with gr.TabItem("🖼️ Image Batch"):
            with gr.Column(elem_classes="group-container"):
                gr.Markdown("### Upload Images")
                # CRITICAL FIX: type="filepath" ensures we get string paths, not objects
                img_input = gr.File(
                    file_count="multiple", 
                    label="Upload Images", 
                    type="filepath",
                    height=150
                )
                model_sel = gr.Dropdown(
                    ["realesrgan-x4plus", "realesrgan-x4plus-anime"], 
                    value="realesrgan-x4plus", 
                    label="Model"
                )
                btn_img = gr.Button("Upscale Images", variant="primary")
                out_zip = gr.File(label="Download Results")
                
                btn_img.click(process_images, inputs=[img_input, model_sel], outputs=out_zip)

        # --- TAB 2: VIDEO ---
        with gr.TabItem("🎥 Video Upscaler"):
            with gr.Column(elem_classes="group-container"):
                gr.Markdown("### Upload Video (MP4)")
                # CRITICAL FIX: type="filepath"
                vid_input = gr.Video(
                    label="Upload Video", 
                    format="mp4"
                )
                model_sel_vid = gr.Dropdown(
                    ["realesrgan-x4plus", "realesrgan-x4plus-anime"], 
                    value="realesrgan-x4plus", 
                    label="Model"
                )
                
                btn_vid = gr.Button("Start Video Upscale", variant="primary")
                out_vid = gr.Video(label="Download Result")
                
                btn_vid.click(process_video, inputs=[vid_input, model_sel_vid], outputs=out_vid)

# --- 7. LAUNCH ---
if __name__ == "__main__":
    # Queue is essential for heavy tasks to avoid timeouts
    demo.queue()
    # We use 0.0.0.0 to bind to all interfaces for Docker
    # We allow all paths in /app/temp_data so downloading the zip works
    demo.launch(
        server_name="0.0.0.0", 
        server_port=7860, 
        allowed_paths=["/app/temp_data"],
        show_error=True
    )
