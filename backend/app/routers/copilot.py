import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from google.genai import errors
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.copilot_schemas import CopilotRequest, CopilotResponse
from app.dependencies import get_db
from app.services.copilot import ask_copilot

from pydantic import ValidationError

router = APIRouter(prefix="/copilot", tags=["Copilot"])
logger = logging.getLogger(__name__)

DbSession = Annotated[Session, Depends(get_db)]


@router.post("/chat", response_model=CopilotResponse)
def chat(payload: CopilotRequest, db: DbSession):
    try:
        return ask_copilot(db, payload)
    
    except ValidationError as error:
        details = [
            {
                "location": list(item["loc"]),
                "type": item["type"],
            }
            for item in error.errors()
        ]

        print("Detalhes da validação do copiloto:", details)

        raise HTTPException(
            status_code=503,
            detail="Resposta inválida no copiloto. Confira o terminal do backend.",
        ) from error
    
    except errors.APIError as error:
        from app.config import settings

        key = (
            settings.gemini_api_key.get_secret_value()
            if settings.gemini_api_key
            else ""
        )
        message = str(error.message)
        if key:
            message = message.replace(key, "[CHAVE OCULTA]")

        logger.error(
            "Erro Gemini — código=%s; mensagem=%s",
            error.code,
            message,
        )

        if error.code == 429:
            raise HTTPException(
                status_code=429,
                detail="Cota ou limite do Gemini atingido. Aguarde ou utilize o modo mock.",
            ) from None

        raise HTTPException(
            status_code=502,
            detail=(
                "O Gemini recusou a solicitação. Confira a chave, "
                "o modelo e a disponibilidade no projeto."
            ),
        ) from None

    except (RuntimeError, ValidationError) as error:
        logger.warning("Falha de configuração ou protocolo: %s", type(error).__name__)
        raise HTTPException(
            status_code=503,
            detail=(
                "Copiloto indisponível ou resposta de ferramenta inválida. "
                "Confira a configuração ou utilize o modo mock."
            ),
        ) from None

    except Exception:
        logger.error("Falha inesperada no copiloto.")
        raise HTTPException(
            status_code=503,
            detail="Não foi possível concluir a consulta. Tente novamente.",
        ) from None

    