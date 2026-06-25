import os
import xml.etree.ElementTree as ET
import csv
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

def generate_csv(root_dir):
    csv_path = Path(root_dir) / "Resolve_Timecode_Import.csv"
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['File Name', 'Start TC'])
        
        count = 0
        # Suche rekursiv nach allen XML Dateien
        for xml_file in Path(root_dir).rglob('*.XML'):
            # Ignoriere versteckte Dateien
            if xml_file.name.startswith('.'): continue
                
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                start_tc = None
                for elem in root.iter():
                    tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                    if tag_local == 'StartTimecode':
                        start_tc = elem.text
                        break
                
                if start_tc:
                    clip_name = xml_file.stem
                    video_dir = xml_file.parent.parent / "VIDEO"
                    
                    mxf_name_lower = f"{clip_name}.mxf"
                    mxf_name_upper = f"{clip_name}.MXF"
                    
                    final_name = mxf_name_lower
                    if (video_dir / mxf_name_upper).exists():
                        final_name = mxf_name_upper
                        
                    writer.writerow([final_name, start_tc])
                    count += 1
            except Exception as e:
                print(f"Fehler bei {xml_file.name}: {e}")
                
    return csv_path, count

def main():
    root = tk.Tk()
    root.withdraw()
    
    messagebox.showinfo(
        "Resolve TC Exporter", 
        "Bitte wähle den Ordner aus, in dem deine kopierten MXF/XML Dateien liegen.\n\nDas Tool sucht automatisch alle Timecodes zusammen und erstellt eine CSV für DaVinci Resolve."
    )
    
    target_dir = filedialog.askdirectory(title="Ingest-Ordner auswählen")
    if not target_dir:
        return
        
    csv_file, count = generate_csv(target_dir)
    
    if count > 0:
        messagebox.showinfo(
            "Fertig!", 
            f"Es wurden Timecodes für {count} Clips gefunden!\n\nDie Datei liegt hier:\n{csv_file}\n\nAnleitung für Resolve:\n1. Alle 42 Clips im Media Pool markieren\n2. Menü: File -> Import Metadata To -> Media Pool\n3. CSV auswählen und bei den Optionen 'Match using: File Name' einstellen."
        )
    else:
        messagebox.showwarning("Fehler", "Es konnten keine XML-Dateien mit Timecode in diesem Ordner gefunden werden.")

if __name__ == '__main__':
    main()
