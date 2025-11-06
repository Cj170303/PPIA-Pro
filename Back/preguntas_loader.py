# preguntas_loader.py
# -*- coding: utf-8 -*-
import os
import re
from html import escape

# ---------------------------
# Carga y parseo de Preguntas.tex
# ---------------------------

import unicodedata

def _strip_accents(s: str) -> str:
    """Quita acentos para comparar en minúsculas."""
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


# Mapa MANUAL de canónicos (puedes ampliarlo cuando quieras).
# La clave se guarda sin acentos y en minúsculas.
THEMES_CANON = {
    # conjuntos
    "conjunto": "Conjuntos",
    "conjuntos": "Conjuntos",

    # lógica y cercanos
    "logica": "Lógica",
    "lógica": "Lógica",   # por si acaso viene ya con acento

    # proposiciones
    "proposiciones": "Proposiciones",
    "proposiciones2": "Proposiciones",

    # otros comunes (ajusta libremente)
    "argumentos": "Argumentación",
    "argumentación": "Argumentación",
    "argumentacion": "Argumentación",
    "cuantificadores": "Cuantificadores",
    "demostraciones": "Demostraciones",
    "exploracion": "Exploración",
    "exploración": "Exploración",
    "funciones": "Funciones",
    "implicaciones": "Implicaciones",
    "indices": "Índices",
    "índices": "Índices",
    "sumatorias": "Sumatorias",
    "traducciones": "Traducciones",
    "preferencias": "Preferencias",
    "utilidad": "Utilidad",
}

def canon_tema(raw: str) -> str:
    """
    Devuelve el nombre de tema canónico para mostrar/almacenar.
    - recorta espacios
    - baja a minúsculas sin acentos para buscar en el mapa
    - si no está en el mapa, devuelve 'Title Case' del texto original limpio
    """
    s = (raw or "").strip()
    if not s:
        return ""
    key = _strip_accents(s).lower()
    if key in THEMES_CANON:
        return THEMES_CANON[key]
    # Fallback: lo dejamos en formato Título a partir del original
    return s[:1].upper() + s[1:].lower()

def load_preguntas_from_latex(file_name: str):
    """
    Lee el archivo LaTeX y extrae preguntas definidas con el entorno question.
    Estructura de cada pregunta:
      {id}{tema(s)}{dif}{res(s)}{week}{enunciado con enumerate}
    Devuelve: dict[int] -> {
        'tema': str,                 # <-- temáticas YA CANONIZADAS y unificadas
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

        # ---- CANONIZACIÓN DE TEMAS ----
        raw_topics = [t.strip() for t in tema.split(",") if t.strip()]
        canon_set = set()
        for t in raw_topics:
            ct = canon_tema(t)
            if ct:
                canon_set.add(ct)
        canon_topics = ",".join(sorted(canon_set))  # orden consistente

        # -------- Opciones del enumerate (sin duplicar letras) --------
        # Captura el bloque interno de enumerate
        enum_match = re.search(r"\\begin\{enumerate\}([\s\S]+?)\\end\{enumerate\}", body)
        enum_src = enum_match.group(1) if enum_match else ""

        # Soporta "\item a) ..." y toma el texto hasta el siguiente \item
        items = re.findall(r"\\item\s*([A-Za-z])\)\s*([\s\S]*?)(?=(\\item|$))", enum_src)

        # Guardamos también el texto “original” de cada opción por si lo necesitas
        opts = {}

        # --- utilitaria: arregla $...$ y $$...$$ para que MathJax/Pandoc no sufran
        def _fix_inline_dollars(tex: str) -> str:
            tex = tex.strip()
            # Normaliza $$...$$ a \[...\] (bloque)
            tex = re.sub(r"\$\$([\s\S]*?)\$\$", r"\\[\1\\]", tex)

            # Si queda un número impar de '$', recorta un $ colgante al final (defensa)
            if tex.count("$") % 2 == 1:
                tex = tex.rstrip("$")

            # Reemplaza $...$ (inline) por \( ... \)
            tex = re.sub(r"\$([^$]+)\$", r"\\(\1\\)", tex)
            return tex

        # --- Enunciado sin el enumerate (como ya lo tenías)
        body_no_enum = re.sub(r"\\begin\{enumerate\}([\s\S]+?)\\end\{enumerate\}", "", body, flags=re.DOTALL).strip()
        body_no_enum = sanitize_latex_fragment(body_no_enum)
        html = latex_to_html(body_no_enum)

        # --- Construye el <ol> de opciones renderizando cada li con Pandoc
        if items:
            html += "<ol type='a' class='options-list' style='padding-left:1.5rem; margin-top:.5rem;'>\n"
            for letra, texto, _ in items:
                # elimina "a)" inicial si vino duplicado en el banco
                txt = re.sub(r'^[A-Za-z]\)\s*', '', texto).strip()
                opts[letra.lower()] = " ".join(txt.split())

                # prepara el LaTeX del li
                txt = _fix_inline_dollars(txt)
                txt = sanitize_latex_fragment(txt)

                # convierte con Pandoc para que quede igual de “bonito” que el enunciado
                li_html = latex_to_html(txt).strip()

                # Si Pandoc envolvió en <p>...</p>, lo quitamos para no anidar párrafos en <li>
                li_html = re.sub(r'^<p>([\s\S]*?)</p>\s*$', r'\1', li_html)

                html += f"<li>{li_html}</li>\n"
            html += "</ol>\n"

        # --- Guarda estructura
        preguntas[qid] = {
            "tema": canon_topics,   # <-- YA UNIFICADO
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
