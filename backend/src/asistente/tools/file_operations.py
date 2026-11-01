"""Módulo reservado: tools/files. Maneja operaciones de archivos y carpetas."""

import os
import csv
import shutil
from pathlib import Path

def get_known_folder_path(location: str) -> Path | None:
    location = location.lower().strip()
    # Remove common conversational prefixes
    prefixes = ["en el ", "en la ", "en los ", "en las ", "en ", "el ", "la ", "los ", "las ", "mi ", "mis "]
    for prefix in prefixes:
        if location.startswith(prefix):
            location = location[len(prefix):]
    
    home = Path.home()
    if location in ["desktop", "escritorio"]:
        return home / "Desktop"
    elif location in ["documents", "documentos"]:
        return home / "Documents"
    elif location in ["downloads", "descargas"]:
        return home / "Downloads"
    elif location in ["pictures", "imagenes", "imágenes", "fotos"]:
        return home / "Pictures"
    elif location in ["videos", "vídeos", "videos"]:
        return home / "Videos"
    elif location in ["music", "musica", "música"]:
        return home / "Music"
    return None

def resolve_target_path(path_str: str) -> Path | None:
    # Remove surrounding quotes if any
    path_str = path_str.strip('\'"')
    p = Path(path_str)
    if p.is_absolute():
        return p
    
    parts = path_str.replace('\\', '/').split('/')
    first_part = parts[0]
    base_folder = get_known_folder_path(first_part)
    
    if base_folder:
        if len(parts) > 1:
            return base_folder.joinpath(*parts[1:])
        return base_folder
        
    known = get_known_folder_path(path_str)
    if known:
        return known
        
    return None

def is_safe_path(target_path: Path) -> bool:
    target = target_path.resolve()
    roots = [Path.home() / name for name in ("Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music")]
    return any(target != root.resolve() and target.is_relative_to(root.resolve()) for root in roots)


def check_invalid_chars(name: str) -> bool:
    invalid_chars = '<>:"/\\|?*'
    return (not name.strip() or name in (".", "..") or name.endswith((".", " "))
            or name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1,10)], *[f"LPT{i}" for i in range(1,10)]}
            or any(c in name for c in invalid_chars))

def create_folder_local(name: str, path_str: str) -> str:
    if check_invalid_chars(name):
        return f"El nombre '{name}' contiene caracteres que Windows no permite."
        
    target_base = resolve_target_path(path_str)
    if not target_base:
        return "No pude reconocer la ubicación donde quieres crear la carpeta."
        
    final_path = target_base / name
    
    if not is_safe_path(final_path):
        return "No tengo permiso para crear una carpeta en esa ubicación."
        
    if final_path.exists():
        return f"La carpeta '{name}' ya existe en esa ubicación."
        
    parent_exists = final_path.parent.exists()
    
    try:
        final_path.mkdir(parents=True, exist_ok=True)
        if not parent_exists:
            return f"Listo. He creado la estructura:\n{final_path}"
        else:
            return f"Listo, he creado la carpeta '{name}' en la ubicación indicada."
    except Exception as e:
        return "No tengo permiso para crear una carpeta en esa ubicación."

def generate_txt(path: Path, content: str):
    path.write_text(content, encoding="utf-8")

def generate_csv(path: Path, content: dict):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if "columns" in content:
            writer.writerow(content["columns"])
        if "rows" in content:
            writer.writerows(content["rows"])

def generate_xlsx(path: Path, content: dict):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    if "sheet" in content and content["sheet"]:
        ws.title = content["sheet"]
    if "columns" in content:
        ws.append(content["columns"])
    if "rows" in content:
        for row in content["rows"]:
            ws.append(row)
    wb.save(path)

def generate_docx(path: Path, content: dict | str):
    from docx import Document
    doc = Document()
    
    def add_text_with_newlines(p, text: str):
        lines = str(text).split('\n')
        for i, line in enumerate(lines):
            if i > 0:
                p.add_run().add_break()
            p.add_run(line)

    if isinstance(content, str):
        p = doc.add_paragraph()
        add_text_with_newlines(p, content)
    else:
        if "title" in content:
            doc.add_heading(content["title"], 0)
        if "sections" in content:
            for sec in content["sections"]:
                if "heading" in sec:
                    doc.add_heading(sec["heading"], level=1)
                if "paragraphs" in sec:
                    for text_para in sec["paragraphs"]:
                        p = doc.add_paragraph()
                        add_text_with_newlines(p, text_para)
                if "bullets" in sec:
                    for text_bullet in sec["bullets"]:
                        p = doc.add_paragraph(style='List Bullet')
                        add_text_with_newlines(p, text_bullet)
    doc.save(path)

def generate_pptx(path: Path, content: dict):
    from pptx import Presentation
    prs = Presentation()
    title_slide_layout = prs.slide_layouts[0]
    bullet_slide_layout = prs.slide_layouts[1]
    
    if "title" in content:
        slide = prs.slides.add_slide(title_slide_layout)
        title = slide.shapes.title
        title.text = content["title"]
    
    if "slides" in content:
        for s_data in content["slides"]:
            slide = prs.slides.add_slide(bullet_slide_layout)
            shapes = slide.shapes
            if "title" in s_data:
                shapes.title.text = s_data["title"]
            if "bullets" in s_data:
                body_shape = shapes.placeholders[1]
                tf = body_shape.text_frame
                for i, b in enumerate(s_data["bullets"]):
                    if i == 0:
                        tf.text = b
                    else:
                        p = tf.add_paragraph()
                        p.text = b
    if not content or ("title" not in content and "slides" not in content):
        prs.slides.add_slide(title_slide_layout)
    prs.save(path)

def generate_pdf(path: Path, content: dict | str):
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("sys", "", "C:\\Windows\\Fonts\\arial.ttf")
    pdf.set_font("sys", size=12)
    if isinstance(content, str):
        pdf.multi_cell(0, 10, text=content)
    else:
        if "title" in content:
            pdf.set_font("sys", size=16)
            pdf.multi_cell(0, 10, text=content["title"], new_x="LMARGIN", new_y="NEXT", align='C')
            pdf.set_font("sys", size=12)
        if "sections" in content:
            for sec in content["sections"]:
                if "heading" in sec:
                    pdf.set_font("sys", size=14)
                    pdf.multi_cell(0, 10, text=sec["heading"], new_x="LMARGIN", new_y="NEXT")
                    pdf.set_font("sys", size=12)
                if "paragraphs" in sec:
                    for p in sec["paragraphs"]:
                        pdf.multi_cell(0, 10, text=p, new_x="LMARGIN", new_y="NEXT")
                if "bullets" in sec:
                    for b in sec["bullets"]:
                        pdf.multi_cell(0, 10, text=f"- {b}", new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))

def create_file_local(name: str, path_str: str, file_type: str, content: dict | str | None) -> str:
    ext = f".{file_type.lower()}"
    if not name.lower().endswith(ext):
        name = f"{name}{ext}"
        
    if check_invalid_chars(name):
        return f"El nombre '{name}' contiene caracteres que Windows no permite."
        
    target_base = resolve_target_path(path_str)
    if not target_base:
        return "No pude reconocer la ubicación donde quieres crear el archivo."
        
    final_path = target_base / name
    
    if not is_safe_path(final_path):
        return "No tengo permiso para crear un archivo en esa ubicación protegida."
        
    if final_path.exists():
        return "ALREADY_EXISTS"
        
    import uuid
    staging_path = final_path.with_name(f".{uuid.uuid4().hex}{final_path.suffix}")
    try:
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if not content:
            if file_type == "txt" or file_type == "csv":
                staging_path.write_text("", encoding="utf-8")
            elif file_type == "docx":
                generate_docx(staging_path, {})
            elif file_type == "xlsx":
                generate_xlsx(staging_path, {})
            elif file_type == "pptx":
                generate_pptx(staging_path, {})
            elif file_type == "pdf":
                generate_pdf(staging_path, "")
            else:
                staging_path.touch()
        else:
            if file_type == "txt":
                generate_txt(staging_path, content if isinstance(content, str) else str(content))
            elif file_type == "csv":
                generate_csv(staging_path, content if isinstance(content, dict) else {})
            elif file_type == "xlsx":
                generate_xlsx(staging_path, content if isinstance(content, dict) else {})
            elif file_type == "docx":
                generate_docx(staging_path, content if isinstance(content, dict) or isinstance(content, str) else str(content))
            elif file_type == "pptx":
                generate_pptx(staging_path, content if isinstance(content, dict) else {})
            elif file_type == "pdf":
                generate_pdf(staging_path, content)
            else:
                staging_path.write_text(str(content), encoding="utf-8")
                
        # Windows rename fails if another file appeared; never overwrite it.
        staging_path.rename(final_path)
        has_content = " con el contenido solicitado" if content else ""
        return f"Listo. He creado `{name}` en la ubicación indicada{has_content}."
    except Exception as e:
        staging_path.unlink(missing_ok=True)
        return f"No pude crear el archivo debido a un error técnico: {str(e)}"

def search_items_local(query: str) -> list[Path]:
    import unicodedata
    def remove_accents(s: str) -> str:
        return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8')
    
    query_lower = remove_accents(query.lower())
    results = []
    
    # We build safe_locations here to avoid cyclic imports
    home = Path.home()
    safe_locations = [
        home / "Desktop", home / "Documents", home / "Downloads",
        home / "Pictures", home / "Videos", home / "Music"
    ]
    
    for base_path in safe_locations:
        if not base_path.exists(): continue
        try:
            for root, dirs, files in os.walk(base_path):
                for d in [".git", "node_modules", ".venv", "venv", "AppData"]:
                    if d in dirs: dirs.remove(d)
                
                for f in files:
                    if query_lower in remove_accents(f.lower()):
                        results.append(Path(root) / f)
                
                for d in dirs:
                    if query_lower in remove_accents(d.lower()):
                        results.append(Path(root) / d)
                        
                if len(results) >= 10:
                    return results
        except OSError:
            pass
    return results

def get_source_path(source: str) -> Path | list[Path] | str:
    p = resolve_target_path(source)
    if p and p.exists():
        return p
    
    matches = search_items_local(source)
    if not matches:
        return f"No encontré ningún archivo o carpeta que coincida con '{source}'."
    if len(matches) == 1:
        return matches[0]
    
    return matches

def move_item_local(source: str, destination: str) -> str:
    src = get_source_path(source)
    if isinstance(src, str): return src 
    if isinstance(src, list):
        lines = [f"Encontré varios elementos que coinciden con '{source}':"]
        for i, match in enumerate(src):
            lines.append(f"{i+1}. {match}")
        lines.append("¿Cuál ruta exacta quieres mover?")
        return "\n".join(lines)
        
    dest_base = resolve_target_path(destination)
    if not dest_base:
        return f"No pude reconocer la ubicación de destino '{destination}'."
        
    if dest_base.is_dir():
        final_dest = dest_base / src.name
    else:
        final_dest = dest_base
        
    if not is_safe_path(final_dest) or not is_safe_path(src):
        return "No tengo permiso para realizar esta operación en ubicaciones protegidas."
        
    if final_dest.exists():
        return f"No pude mover el elemento porque ya existe otro llamado '{src.name}' en la carpeta destino."
        
    try:
        final_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(final_dest))
        return f"Listo, moví `{src.name}` a la ubicación indicada."
    except Exception as e:
        return f"Ocurrió un error al intentar mover el elemento: {str(e)}"

def copy_item_local(source: str, destination: str) -> str:
    src = get_source_path(source)
    if isinstance(src, str): return src
    if isinstance(src, list):
        lines = [f"Encontré varios elementos que coinciden con '{source}':"]
        for i, match in enumerate(src):
            lines.append(f"{i+1}. {match}")
        lines.append("¿Cuál ruta exacta quieres copiar?")
        return "\n".join(lines)
        
    dest_base = resolve_target_path(destination)
    if not dest_base:
        return f"No pude reconocer la ubicación de destino '{destination}'."
        
    if dest_base.is_dir():
        final_dest = dest_base / src.name
    else:
        final_dest = dest_base
        
    if not is_safe_path(final_dest) or not is_safe_path(src):
        return "No tengo permiso para realizar esta operación en ubicaciones protegidas."
        
    if final_dest.exists():
        return f"No pude copiar el elemento porque ya existe otro llamado '{src.name}' en la carpeta destino."
        
    try:
        final_dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, final_dest)
        else:
            shutil.copy2(src, final_dest)
        return f"Listo, copié `{src.name}` a la ubicación indicada."
    except Exception as e:
        return f"Ocurrió un error al intentar copiar el elemento: {str(e)}"

def rename_item_local(source: str, new_name: str) -> str:
    src = get_source_path(source)
    if isinstance(src, str): return src
    if isinstance(src, list):
        lines = [f"Encontré varios elementos que coinciden con '{source}':"]
        for i, match in enumerate(src):
            lines.append(f"{i+1}. {match}")
        lines.append("¿Cuál ruta exacta quieres renombrar?")
        return "\n".join(lines)
        
    if check_invalid_chars(new_name):
        return f"El nombre '{new_name}' contiene caracteres que Windows no permite."
        
    final_dest = src.parent / new_name
    
    if not is_safe_path(final_dest) or not is_safe_path(src):
        return "No tengo permiso para realizar esta operación en ubicaciones protegidas."
        
    if final_dest.exists():
        return f"No pude renombrar el elemento porque ya existe otro llamado '{new_name}' en esa carpeta."
        
    try:
        src.rename(final_dest)
        return f"Listo, renombré `{src.name}` como `{new_name}`."
    except Exception as e:
        return f"Ocurrió un error al intentar renombrar el elemento: {str(e)}"
