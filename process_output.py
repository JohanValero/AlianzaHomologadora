
import re
import nltk
import json
import pandas as pd

from typing import Dict, List, Set, Tuple, Optional, TypedDict, Union
from pandas._libs.missing import NAType
from nltk.corpus import stopwords
from pathlib import Path

nltk.download('stopwords')

def clean_concept(concept: str):
    if concept == "" or concept is None:
        return ""
    if (not isinstance(concept, str)):
        return str(concept)

    concept = concept.lower()
    tabla = str.maketrans(f"áäéëíïóöúü", "aaeeiioouu")
    concept = concept.translate(tabla)
    concept = re.sub(r'\(\s*[\d,.]+\s*%?\s*\)', '', concept)
    concept = re.sub(r'\b\d+\s*[xX]\s*\d+\b', '', concept)
    concept = re.sub(r'\b\d+(?:[.,]\d+)?\s*%', '', concept)
    meses: list[str] = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    pattern_meses = r'\b(?:' + '|'.join(meses) + r')\b'
    concept = re.sub(pattern_meses, 'mes', concept)
    concept = re.sub(r'\b\d+(?:[.,]\d+)?\b', '', concept)
    concept = re.sub(r'\s*[,.]\s*', ' ', concept)
    caracteres_especiales: str = '–-#()[]{}/:_*+.,~°";$&´='+"'"
    tabla = str.maketrans(caracteres_especiales, " " * len(caracteres_especiales))
    concept = concept.translate(tabla)
    concept = re.sub(r'\d+$', '', concept)
    concept = re.sub(r'[0-9]', ' ', concept)
    concept = re.sub(r'\s+', ' ', concept).strip()
    tokens = concept.split()
    tokens = [word for word in tokens if word not in STOP_WORDS and len(word) > 2]
    return " ".join(tokens)

STOP_WORDS: Set[str] = set(stopwords.words('spanish'))
INPUT_CONCEPTOS_PTESA: str = "./resources/input/Conceptos PTESA.xlsx"
INPUT_HOMOLOGA: str = "./resources/input/Tabla_homologación_2.xlsx"
INPUT_BACKUP_ANSWERS: str = "./resoureces/output/"

df_conceptos: pd.DataFrame = pd.read_excel(INPUT_CONCEPTOS_PTESA)
df_conceptos: pd.DataFrame = df_conceptos['Concepto'].astype(str).str.split('|').explode().to_frame()
df_conceptos["concepto_cleared"] = df_conceptos["Concepto"].apply(clean_concept)

def get_homologa_dict() -> Dict[str, str]:
    df_homologa: pd.DataFrame = pd.read_excel(INPUT_HOMOLOGA)
    df_keywords: pd.DataFrame = df_homologa[~df_homologa["KeyWords"].isna()].copy()
    dict_keyword_concept: Dict[str, str] = {}
    for ix, row in df_keywords.iterrows():
        cleared_keywords: List[str] = [clean_concept(kw) for kw in row["KeyWords"].split(",") if len(clean_concept(kw)) > 0]
        for kw in cleared_keywords:
            dict_keyword_concept[kw] = row["Concepto"]
    return dict_keyword_concept

homologa_dict: Dict[str, str] = get_homologa_dict()

def fast_category(concept: str) -> Tuple[Union[str, NAType], Union[str, NAType]]:
    """
    Analiza un concepto y retorna tanto la categoría como el tipo de algoritmo.
    
    Retorna:
        (categoria, algoritmo)
    """
    if not isinstance(concept, str) or len(concept) <= 3:
        return "CONCEPTO VACIO", "NO-DATA"
    for kw, cat in homologa_dict.items():
        if kw == concept or kw in concept:
            return cat, "KEYWORD"
    return pd.NA, pd.NA

df_conceptos[["categoria", "alg"]] = df_conceptos["concepto_cleared"].apply(lambda x: pd.Series(fast_category(x)))

class ClasificacionItem(TypedDict):
    concepto: str    # Concepto original (espejo del input para verificar integridad)
    categoria: str   # Uno de los valores de CONCEPTOS_TRIBUTARIOS
    explicacion: str # Justificación breve (máx ~40 palabras)

BACKUP_DIR: Path = Path("./resources/output/backup_llm_answer")
sessions: List[Path] = [d for d in BACKUP_DIR.iterdir() if d.is_dir()]
dict_conceptos: Dict[str, ClasificacionItem] = {}
for folder in sessions:
    files: List = [f for f in folder.iterdir() if f.is_file()]

    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            document: Dict[str, List] = json.loads(f.read())
            #input: List[str] = document["input"]
            output: Dict[str, ClasificacionItem] = {x["concepto"]:x for x in document["output_raw"]}
            dict_conceptos: Dict[str, ClasificacionItem]  = output | dict_conceptos

def clasifly_using_llm_answer(concept: str) -> Tuple[Union[str, NAType], Union[str, NAType], Union[str, NAType]]:
    if not isinstance(concept, str) or len(concept) <= 3:
        return ("CONCEPTO VACIO", "NO-DATA", pd.NA)
    for kw, cat in homologa_dict.items():
        if kw == concept or kw in concept:
            return (cat, "KEYWORD", pd.NA)
    if concept in dict_conceptos:
        return (dict_conceptos[concept]["categoria"], "gemini-3.1-flash-lite-preview", dict_conceptos[concept]["explicacion"])
    return (pd.NA, pd.NA, pd.NA)

print("Procesando LLM answers")
df_conceptos["categoria"] = pd.NA
df_conceptos["alg"] = pd.NA
df_conceptos["explicacion"] = pd.NA
df_conceptos[["categoria", "alg", "explicacion"]] = df_conceptos["concepto_cleared"].apply(lambda x: pd.Series(clasifly_using_llm_answer(x)))

df_conceptos.to_excel("./resources/output/result_llm.xlsx")
