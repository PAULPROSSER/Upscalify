import gradio as gr
import os
import shutil
import subprocess
import time
import glob

# --- 1. CONFIGURATION ---
UPSCALER_BIN = "/app/executable" 
TEMP_BASE = "/app/temp_data"

# --- 2. STARTUP CHECKS ---
def configure_environment():
    # Force 8 threads for NCNN (Optimal for CPU scaling)
    os.environ["OMP_NUM_THREADS"] = "8"
    # Ensure the system uses the software renderer
    os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
    
    # Auto-detect driver path just in case
    drivers = glob.glob("/usr/share/vulkan/icd.d/*lvp*.json")
    if drivers:
        os.environ["VK_ICD_FILENAMES"] = drivers[0]
        print(f"🚀 Driver Activated: {drivers[0]}")
    else:
        print("⚠️ Warning: No LLVM software driver found. Upscaling may crash.")

configure_environment()
os.makedirs(TEMP_BASE, exist_ok=True)

# --- 3. CSS STYLING ---
wati_css = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
:root { --primary-main: #1BD760; --primary-dark: #0C9A3F; --primary-light: #D9F7E8; --ink-900: #111827; --radius-lg: 16px; --radius-pill: 999px; }
body, .gradio-container { font-family: 'Inter', sans-serif !important; background-color: #FFFFFF; color: var(--ink-900); }
.gradio-container { max-width: 1120px !important; margin: 0 auto; padding-top: 40px; }
h1 { font-weight: 800 !important; font-size: 40px !important; margin-bottom: 8px !important; }
.group-container { background: #FFFFFF; border: 1px solid rgba(15, 23, 42, 0.04); border-radius: var(--radius-lg); box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08); padding: 32px; margin-bottom: 24px; }
button.primary { background: var(--primary-main) !important; color: white !important; font-weight: 600 !important; border-radius: var(--radius-pill) !important; padding: 12px 32px !important; border: none !important; transition: all 0.2s; }
button.primary:hover { background: var(--primary-dark) !important; transform: translateY(-1px); }
"""

# --- 4. CLEANUP ---
def clean_path(path):
    if os.path.exists(path): shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)

# --- 5. IMAGE PROCESSING ---
def process_images(files, model_name):
    try:
        if not files: return None
        job_id = str(int(time.time()))
        upload_dir = f"{TEMP_BASE}/{job_id}/in"
        output_dir = f"{TEMP_BASE}/{job_id}/out"
        clean_path(upload_dir)
        clean_path(output_dir)

        for file_path in files:
            filename = os.path.basename(file_path)
            shutil.copy(file_path, os.path.join(upload_dir, filename))
        
        # NOTE: Removed "-g -1" so it uses the software driver (Device 0)
        cmd = f"find {upload_dir} -type f | parallel -j 4 '{UPSCALER_BIN} -i {{}} -o {output_dir}/{{/.}}.png -n {model_name}'"
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Engine Log: {result.stderr}")
            
        zip_path = f"{TEMP_BASE}/{job_id}/results"
        shutil.make_archive(zip_path, 'zip', output_dir)
        return f"{zip_path}.zip"
    except Exception as e:
        raise gr.Error(f"Error: {str(e)}")

# --- 6. VIDEO PROCESSING ---
def process_video(video_file, model_name):
    try:
        if not video_file: return None
        job_id = str(int(time.time()))
        work_dir = f"{TEMP_BASE}/{job_id}"
        frames_in = f"{work_dir}/frames_in"
        frames_out = f"{work_dir}/frames_out"
        clean_path(frames_in)
        clean_path(frames_out)
        output_video = f"{work_dir}/upscaled.mp4"
        
        # 1. Extract
        subprocess.run(f"ffmpeg -i {video_file} -q:v 2 {frames_in}/frame_%08d.jpg", shell=True, check=True)
        
        # 2. Upscale (Parallel)
        upscale_cmd = f"find {frames_in} -name '*.jpg' | parallel -j 4 '{UPSCALER_BIN} -i {{}} -o {frames_out}/{{/.}}.png -n {model_name}'"
        subprocess.run(upscale_cmd, shell=True, check=True)
        
        # 3. Stitch
        fps_cmd = f"ffprobe -v 0 -of csv=p=0 -select_streams v:0 -show_entries stream=r_frame_rate {video_file}"
        try:
            fps_raw = subprocess.check_output(fps_cmd, shell=True).decode().strip().split('/')
            fps = float(fps_raw[0]) / float(fps_raw[1]) if len(fps_raw) == 2 else 30
        except: fps = 30
            
        subprocess.run(f"ffmpeg -framerate {fps} -i {frames_out}/frame_%08d.png -i {video_file} -map 0:v -map 1:a -c:v libx264 -pix_fmt yuv420p -crf 23 -preset medium {output_video}", shell=True, check=True)
        
        return output_video
    except Exception as e:
        raise gr.Error(f"Video Error: {str(e)}")

# --- 7. UI LAUNCH ---
with gr.Blocks(theme=gr.themes.Base(), css=wati_css) as demo:
    with gr.Column(elem_classes="gradio-container"):
        gr.Markdown("# 🚀 Media Enhancement Studio")
        gr.Markdown("Powered by Debian 12 & LLVM 15+")
    with gr.Tabs():
        with gr.TabItem("🖼️ Image Batch"):
            with gr.Column(elem_classes="group-container"):
                img_input = gr.File(file_count="multiple", label="Upload Images", type="filepath", height=150)
                model_sel = gr.Dropdown(["realesrgan-x4plus", "realesrgan-x4plus-anime"], value="realesrgan-x4plus", label="Model")
                btn_img = gr.Button("Upscale Images", variant="primary")
                out_zip = gr.File(label="Download Results")
                btn_img.click(process_images, inputs=[img_input, model_sel], outputs=out_zip)
        with gr.TabItem("🎥 Video Upscaler"):
            with gr.Column(elem_classes="group-container"):
                vid_input = gr.Video(label="Upload Video", format="mp4")
                model_sel_vid = gr.Dropdown(["realesrgan-x4plus", "realesrgan-x4plus-anime"], value="realesrgan-x4plus", label="Model")
                btn_vid = gr.Button("Start Video Upscale", variant="primary")
                out_vid = gr.Video(label="Download Result")
                btn_vid.click(process_video, inputs=[vid_input, model_sel_vid], outputs=out_vid)

if __name__ == "__main__":
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=7860, allowed_paths=["/app/temp_data"], show_error=True)
