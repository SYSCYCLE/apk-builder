import os
import shutil
import lxml.etree as ET

def clean_directory(folder_path):
    """Bir klasörün içini temizler ama klasörü silmez."""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        return
        
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Dosya silinemedi {file_path}. Hata: {e}")

def update_manifest_package(manifest_path, new_package_name):
    """AndroidManifest.xml içindeki paket adını değiştirir."""
    parser = ET.XMLParser(remove_blank_text=False)
    tree = ET.parse(manifest_path, parser)
    root = tree.getroot()
    
    root.set("package", new_package_name)
    
    tree.write(manifest_path, encoding="utf-8", xml_declaration=True)

def update_app_name(strings_path, new_app_name):
    """strings.xml içindeki uygulama ismini değiştirir."""
    if not os.path.exists(strings_path):
        return

    parser = ET.XMLParser(remove_blank_text=False)
    tree = ET.parse(strings_path, parser)
    root = tree.getroot()
    
    found = False
    for string in root.findall("string"):
        if string.get("name") == "app_name":
            string.text = new_app_name
            found = True
            break
            
    if not found:
        new_elem = ET.SubElement(root, "string", name="app_name")
        new_elem.text = new_app_name

    tree.write(strings_path, encoding="utf-8", xml_declaration=True)
