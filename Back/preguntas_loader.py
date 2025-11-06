# preguntas_loader.py
# -*- coding: utf-8 -*-
import os
import re
from html import escape

# ---------------------------
# Carga y parseo de Preguntas.tex
# ---------------------------

def load_preguntas_from_latex(file_name: str):
    """
    Lee el archivo LaTeX y extrae preguntas definidas con el entorno question.
    Estructura de cada pregunta:
      {id}{tema(s)}{dif}{res(s)}{week}{enunciado con enumerate}
    Devuelve: dict[int] -> {
        'tema': str,
        'dif': int,
        'res': list[str],
        'week': int,
        'enunciado_html': str,
        'opts': dict[letra]=texto
    }
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, file_name)
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    pattern = r"\\begin\{question\}\{(\d+)\}\{([^\}]+)\}\{(\d+)\}\{([^\}]+)\}\{(\d+)\}\{([\s\S]+?)\}\s*\\end\{question\}"
    preguntas = {}
    matches = re.findall(pattern, content, re.DOTALL)

    for qid_str, tema, dif_str, res_str, week_str, body in matches:
        qid = int(qid_str)
        dif = int(dif_str)
        week = int(week_str)
        res_list = [r.strip() for r in res_str.split(',')]

        # Extraer opciones del enumerate
        opts = {}
        enum_match = re.search(r"\\begin\{enumerate\}([\s\S]+?)\\end\{enumerate\}", body)
        enum_src = enum_match.group(1) if enum_match else ""
        items = re.findall(r"\\item\s*([a-zA-Z])\)\s*([\s\S]*?)(?=(\\item|$))", enum_src)
        for letra, texto, _ in items:
            texto_clean = " ".join(texto.strip().split())
            opts[letra.lower()] = texto_clean

        # El enunciado sin el enumerate
        body_no_enum = re.sub(r"\\begin\{enumerate\}([\s\S]+?)\\end\{enumerate\}", "", body, flags=re.DOTALL).strip()
        body_no_enum = sanitize_latex_fragment(body_no_enum)

        # Render con Pandoc
        html = latex_to_html(body_no_enum)

        # Opciones (sin duplicar "a)")
        if opts:
            html += "<ol type='a' style='padding-left:1.5rem; margin-top:.5rem;'>\n"
            for k in sorted(opts.keys()):
                txt = re.sub(r'^[A-Za-z]\)\s*', '', opts[k]).strip()
                html += f"<li>{escape(txt)}</li>\n"
            html += "</ol>"

        preguntas[qid] = {
            "tema": ",".join([t.strip() for t in tema.split(",")]),
            "dif": dif,
            "res": res_list,
            "week": week,
            "enunciado_html": html,
            "opts": opts
        }
    return preguntas


def sanitize_latex_fragment(s: str) -> str:
    """
    Limpia fragmentos LaTeX típicos de banco de preguntas:
    - Normaliza saltos.
    - Elimina llaves de cierre sobrantes al final si hay desbalance.
    - Recorta cierres '}' finales repetidos (causa común del error de Pandoc).
    """
    s = s.replace("\r\n", "\n").strip()

    # Si termina con muchas '}', y hay más '}' que '{', recorta del final
    opens = s.count("{")
    closes = s.count("}")
    while closes > opens and s.endswith("}"):
        s = s[:-1].rstrip()
        closes -= 1

    # A veces queda '}}' al final del fragmento; recorta extra
    s = re.sub(r"\}{2,}\s*$", "}", s)

    return s


def latex_to_html(src: str) -> str:
    import subprocess, tempfile, os, re
    from html import escape

    try:
        with tempfile.NamedTemporaryFile(suffix=".tex", delete=False) as tf:
            tf.write(src.encode("utf-8"))
            tex_path = tf.name
        html_path = tex_path.replace(".tex", ".html")

        # Fragmento (sin -s) para no traer CSS global de Pandoc
        subprocess.run([
            "pandoc",
            tex_path,
            "-f", "latex",
            "-t", "html5",
            "--mathjax",
            "--quiet",
            "-o", html_path
        ], check=True)

        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Por defensa: quitar etiquetas de documento/estilos si se cuelan
        html_content = re.sub(r"</?(html|head|body)[^>]*>", "", html_content, flags=re.IGNORECASE)
        html_content = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", html_content, flags=re.IGNORECASE)

        os.remove(tex_path)
        os.remove(html_path)

        return html_content

    except Exception as e:
        # Fallback simple si Pandoc falla: evita romper la app
        s = src
        s = re.sub(r"\\textbf\{([^}]*)\}", r"<b>\1</b>", s)
        s = re.sub(r"\\textit\{([^}]*)\}", r"<i>\1</i>", s)
        s = s.replace("\\\\", "<br>")
        s = escape(s)
        return f"<p>Error al convertir con Pandoc ({str(e)}). Versión simple:<br>{s}</p>"


# Carga inmediata en import
Preguntas = load_preguntas_from_latex("Preguntas.tex")
