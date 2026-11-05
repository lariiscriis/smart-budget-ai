from datetime import datetime
from io import BytesIO, StringIO
from pathlib import Path
import unicodedata
from zipfile import ZipFile

import pandas as pd
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models import Category
from app.schemas import ExpenseCreate


MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ROWS = 1000
REQUIRED_COLUMNS = {"categoria_id", "descricao", "data", "valor"}


def normalize_header(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value).strip().lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def normalize_date(value: str) -> str:
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), pattern).date().isoformat()
        except ValueError:
            continue

    raise ValueError("Data inválida. Use AAAA-MM-DD ou DD/MM/AAAA.")


def read_table(filename: str, content: bytes) -> pd.DataFrame:
    extension = Path(filename).suffix.lower()

    if extension not in {".csv", ".xlsx"}:
        raise ValueError("Formato não suportado. Envie CSV ou XLSX.")

    if not content:
        raise ValueError("O arquivo está vazio.")

    if len(content) > MAX_FILE_BYTES:
        raise ValueError("O arquivo ultrapassa o limite de 2 MB.")

    if extension == ".csv":
        text = content.decode("utf-8-sig")
        first_line = text.splitlines()[0]
        separator = ";" if ";" in first_line else ","

        frame = pd.read_csv(
            StringIO(text),
            sep=separator,
            dtype=str,
            keep_default_na=False,
            skip_blank_lines=False,
            nrows=MAX_ROWS + 1,
        )
    else:
        with ZipFile(BytesIO(content)) as archive:
            expanded_size = sum(item.file_size for item in archive.infolist())

            if expanded_size > 10 * 1024 * 1024:
                raise ValueError("O conteúdo descompactado do XLSX é muito grande.")

        frame = pd.read_excel(
            BytesIO(content),
            sheet_name=0,
            dtype=str,
            keep_default_na=False,
            engine="openpyxl",
            nrows=MAX_ROWS + 1,
        )

    if frame.empty:
        raise ValueError("A planilha não contém registros.")

    if len(frame) > MAX_ROWS:
        raise ValueError("A planilha ultrapassa o limite de 1.000 registros.")

    columns = [normalize_header(column) for column in frame.columns]

    if len(columns) != len(set(columns)):
        raise ValueError("Existem cabeçalhos repetidos após a padronização.")

    if set(columns) != REQUIRED_COLUMNS:
        raise ValueError(
            "Use exatamente as colunas: categoria_id, descricao, data, valor."
        )

    frame.columns = columns
    return frame


def preview_expenses(frame: pd.DataFrame, db: Session) -> dict:
    valid_rows = []
    errors = []
    duplicates = []
    seen = {}
    category_exists = {}

    for position, record in enumerate(frame.to_dict(orient="records"), start=2):
        try:
            expense = ExpenseCreate(
                category_id=record["categoria_id"],
                description=record["descricao"],
                expense_date=normalize_date(str(record["data"])),
                amount=str(record["valor"]).strip().replace(",", "."),
            )

            if expense.category_id not in category_exists:
                category = db.get(Category, expense.category_id)
                category_exists[expense.category_id] = (
                    category is not None and category.type == "expense"
                )

            if not category_exists[expense.category_id]:
                raise ValueError("Categoria de despesa não encontrada (tipo 'expense').")

            key = (
                expense.category_id,
                expense.description,
                expense.expense_date,
                expense.amount,
            )

            if key in seen:
                duplicates.append({
                    "row": position,
                    "same_as_row": seen[key],
                    "message": "Registro idêntico dentro deste arquivo.",
                })
                continue

            seen[key] = position

            valid_rows.append({
                "row": position,
                "data": expense.model_dump(mode="json"),
            })

        except ValidationError as error:
            messages = [
                f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
                for item in error.errors()
            ]
            errors.append({"row": position, "messages": messages})

        except ValueError as error:
            errors.append({"row": position, "messages": [str(error)]})

    return {
        "total_rows": len(frame),
        "valid_count": len(valid_rows),
        "invalid_count": len(errors),
        "duplicate_count": len(duplicates),
        "valid_rows": valid_rows,
        "errors": errors,
        "duplicates": duplicates,
        "saved": False,
    }
