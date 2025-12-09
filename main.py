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
KEYSTORE_PATH = os.path.join(TOOLS_DIR, "keystore.jks")

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
    target_sdk: str = Form("33"),
    ks_pass: str = Form("fp5rqrbl"),
    ks_alias: str = Form("key0"),
    key_pass: str = Form("fp5rqrbl")
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
    root.set("package", package_name)
    tree.write(manifest_path, encoding="utf-8", xml_declaration=True)

    strings_path = os.path.join(decoded_path, "res", "values", "strings.xml")
    if os.path.exists(strings_path):
        stree = ET.parse(strings_path)
        sroot = stree.getroot()
        found = False
        for string in sroot.findall("string"):
            if string.get("name") == "app_name":
                string.text = app_name
                found = True
        if not found:
            new_elem = ET.SubElement(sroot, "string", name="app_name")
            new_elem.text = app_name
        stree.write(strings_path, encoding="utf-8", xml_declaration=True)

    assets_www = os.path.join(decoded_path, "assets", "www")
    if not os.path.exists(assets_www):
        assets_www = os.path.join(decoded_path, "assets")

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
        if not os.path.exists(os.path.dirname(icon_path)):
             icon_path = os.path.join(decoded_path, "res", "mipmap-hdpi", "ic_launcher.png")
             
        if os.path.exists(os.path.dirname(icon_path)):
            with open(icon_path, "wb") as buffer:
                shutil.copyfileobj(icon.file, buffer)

    unsigned_apk = os.path.join(job_dir, "unsigned.apk")
    subprocess.run([
        "java", "-jar", os.path.join(BASE_DIR, "apktool.jar"),
        "b", decoded_path,
        "-o", unsigned_apk
    ], check=True)

    final_apk_name = f"{app_name.replace(' ', '_')}_{job_id}.apk"
    
    signer_command = [
        "java", "-jar", os.path.join(BASE_DIR, "uber-apk-signer.jar"),
        "--apks", unsigned_apk,
        "--out", OUTPUT_DIR,
        "--renameManifestPackage"
    ]

    if os.path.exists(KEYSTORE_PATH):
        signer_command.extend([
            "--ks", KEYSTORE_PATH,
            "--ksAlias", ks_alias,
            "--ksPass", ks_pass,
            "--ksKeyPass", key_pass
        ])

    subprocess.run(signer_command, check=True)
    
    target_file = os.path.join(OUTPUT_DIR, final_apk_name)
    found_apk = None
    for f in os.listdir(OUTPUT_DIR):
        if f.endswith(".apk") and job_id not in f:
            found_apk = os.path.join(OUTPUT_DIR, f)
            break
            
    if found_apk:
        os.rename(found_apk, target_file)
    elif os.path.exists(unsigned_apk):
         shutil.copy(unsigned_apk, target_file)

    background_tasks.add_task(clean_up, job_dir)

    return FileResponse(target_file, filename=final_apk_name, media_type='application/vnd.android.package-archive')
