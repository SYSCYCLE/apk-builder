import os
import shutil
import subprocess
import uuid
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
import lxml.etree as ET

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def clean_up(folder_path):
    shutil.rmtree(folder_path, ignore_errors=True)

@app.post("/generate-apk")
async def generate_apk(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    icon: Optional[UploadFile] = File(None),
    app_name: str = Form(...),
    package_name: str = Form(...),
    min_sdk: str = Form("21"),
    target_sdk: str = Form("33")
):
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(TEMP_DIR, job_id)
    os.makedirs(job_dir)
    
    decoded_path = os.path.join(job_dir, "decoded")
    subprocess.run([
        "java", "-jar", os.path.join(BASE_DIR, "apktool.jar"),
        "d", os.path.join(TOOLS_DIR, "base.apk"),
        "-o", decoded_path,
        "-f"
    ], check=True)

    manifest_path = os.path.join(decoded_path, "AndroidManifest.xml")
    tree = ET.parse(manifest_path)
    root = tree.getroot()
    
    old_package = root.get("package")
    root.set("package", package_name)
    tree.write(manifest_path, encoding="utf-8", xml_declaration=True)

    yml_path = os.path.join(decoded_path, "apktool.yml")
    with open(yml_path, "r") as f:
        yml_content = f.read()
    
    with open(yml_path, "w") as f:
        f.write(yml_content)

    strings_path = os.path.join(decoded_path, "res", "values", "strings.xml")
    if os.path.exists(strings_path):
        stree = ET.parse(strings_path)
        sroot = stree.getroot()
        for string in sroot.findall("string"):
            if string.get("name") == "app_name":
                string.text = app_name
        stree.write(strings_path, encoding="utf-8", xml_declaration=True)

    assets_www = os.path.join(decoded_path, "assets", "www")

    os.makedirs(assets_www, exist_ok=True)
    
    for filename in os.listdir(assets_www):
        file_path = os.path.join(assets_www, filename)
        if os.path.isfile(file_path): os.unlink(file_path)
        elif os.path.isdir(file_path): shutil.rmtree(file_path)

    zip_path = os.path.join(job_dir, "upload.zip")
    with open(zip_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    shutil.unpack_archive(zip_path, assets_www)

    if icon:
        icon_path = os.path.join(decoded_path, "res", "mipmap-xxxhdpi", "ic_launcher.png")
        if os.path.exists(icon_path):
            with open(icon_path, "wb") as buffer:
                shutil.copyfileobj(icon.file, buffer)

    unsigned_apk = os.path.join(job_dir, "unsigned.apk")
    subprocess.run([
        "java", "-jar", os.path.join(BASE_DIR, "apktool.jar"),
        "b", decoded_path,
        "-o", unsigned_apk
    ], check=True)

    final_apk_name = f"{app_name.replace(' ', '_')}_{job_id}.apk"
    final_output = os.path.join(OUTPUT_DIR, final_apk_name)
    
    subprocess.run([
        "java", "-jar", os.path.join(BASE_DIR, "uber-apk-signer.jar"),
        "--apks", unsigned_apk,
        "--out", OUTPUT_DIR,
        "--renameManifestPackage"
    ], check=True)
    
    generated_file = os.path.join(OUTPUT_DIR, "unsigned-aligned-debugSigned.apk")
    target_file = os.path.join(OUTPUT_DIR, final_apk_name)
    if os.path.exists(generated_file):
        os.rename(generated_file, target_file)

    background_tasks.add_task(clean_up, job_dir)

    return FileResponse(target_file, filename=final_apk_name, media_type='application/vnd.android.package-archive')
