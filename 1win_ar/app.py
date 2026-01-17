#!/usr/bin/env python3
"""
FastAPI приложение для парсера платежных данных 1win Аргентина.
"""
import os
from typing import Optional

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.payment_parser_ar import parse_payment_data_1win
from services.google_sheets import export_payment_data_to_sheets, extract_gid_from_url

# Настройка логирования
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger()

app = FastAPI(
    title="1win AR Payment Parser",
    description="Парсер платежных данных для 1win.lat (Аргентина)",
    version="1.0.0",
)


class ParsePaymentDataRequest(BaseModel):
    """
    Запрос для парсинга платежных данных с 1win.lat для Аргентины.
    """
    email: str = Field(..., description="Email для входа на сайт")
    password: str = Field(..., description="Пароль для входа на сайт")
    base_url: str = Field(default="https://1win.lat/", description="Базовый URL сайта")
    spreadsheet_url: Optional[str] = Field(default=None, description="URL Google Sheets для экспорта данных")
    sheet_name: Optional[str] = Field(default=None, description="Имя вкладки (если не указано, будет получено по gid)")
    clear_first: bool = Field(default=False, description="Очистить данные перед записью")
    access_token: Optional[str] = Field(default=None, description="Google OAuth2 access token")
    wait_seconds: int = Field(default=15, ge=5, le=60, description="Время ожидания для загрузки страниц")
    use_persistent_context: bool = Field(default=True, description="Использовать persistent context для сохранения cookies/session (позволяет сохранить авторизацию)")
    skip_login: bool = Field(default=False, description="Пропустить логин (если уже авторизован через persistent context)")


@app.get("/")
async def root():
    """Корневой эндпоинт."""
    return {
        "service": "1win AR Payment Parser",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check эндпоинт."""
    return {"status": "healthy"}


@app.post(
    "/parse_payment_data_ar",
    summary="Parse Payment Data for Argentina (1win.lat)",
)
async def parse_payment_data_ar_endpoint(req: ParsePaymentDataRequest):
    """
    Парсит платежные данные с сайта 1win.lat для Аргентины.
    
    Процесс:
    1. Логинится на сайт с указанными учетными данными
    2. Переходит на страницу депозита
    3. Выбирает метод оплаты Claro Pay (Fiat)
    4. Извлекает данные платежной формы (CVU, Recipient, Bank, Amount)
    5. Экспортирует данные в Google Sheets (если указан spreadsheet_url)
    
    Возвращает результат парсинга и информацию об экспорте.
    """
    try:
        # Парсим платежные данные
        logger.info("payment_parser_starting", email=req.email, base_url=req.base_url)
        payment_data = await parse_payment_data_1win(
            email=req.email,
            password=req.password,
            base_url=req.base_url,
            wait_seconds=req.wait_seconds,
            use_persistent_context=req.use_persistent_context,
            skip_login=req.skip_login,
        )
        
        if not payment_data.get("success"):
            logger.warning(
                "payment_parser_failed",
                error=payment_data.get("error"),
                cvu_found=payment_data.get("cvu") is not None,
            )
            return {
                "ok": False,
                "message": "Payment data parsing failed",
                "payment_data": payment_data,
                "export": None,
            }
        
        # Экспортируем в Google Sheets (опционально - если есть токен)
        export_result = None
        if req.spreadsheet_url and (req.access_token or os.getenv("GOOGLE_SHEETS_ACCESS_TOKEN")):
            try:
                logger.info("payment_parser_exporting_to_sheets", spreadsheet_url=req.spreadsheet_url[:50])
                
                # Извлекаем gid из URL если есть
                gid = extract_gid_from_url(req.spreadsheet_url)
                
                export_result = await export_payment_data_to_sheets(
                    payment_data=payment_data,
                    spreadsheet_id_or_url=req.spreadsheet_url,
                    sheet_name=req.sheet_name,
                    clear_first=req.clear_first,
                    access_token=req.access_token,
                    gid=gid,
                )
                
                logger.info(
                    "payment_parser_export_completed",
                    rows_added=export_result.get("updates", {}).get("updatedRows", 0),
                )
            except ValueError as e:
                logger.warning("payment_parser_export_skipped", error=str(e))
                export_result = {"error": str(e)}
            except Exception as e:
                logger.warning("payment_parser_export_failed", error=str(e))
                export_result = {"error": str(e)}
        else:
            logger.info("payment_parser_export_skipped_no_token", 
                       has_url=bool(req.spreadsheet_url),
                       has_token=bool(req.access_token or os.getenv("GOOGLE_SHEETS_ACCESS_TOKEN")))
        
        logger.info(
            "payment_parser_completed",
            success=True,
            domain=payment_data.get("domain"),
            method=payment_data.get("method"),
            url=payment_data.get("url"),
            export_success=export_result is not None and "error" not in export_result if export_result else False,
        )
        
        return {
            "ok": True,
            "message": "Payment data parsed successfully" + (" and exported" if export_result and "error" not in export_result else ""),
            "payment_data": {
                "domain": payment_data.get("domain"),
                "method": payment_data.get("method"),
                "payment_type": payment_data.get("payment_type"),
                "bank": payment_data.get("bank"),
                "cvu": payment_data.get("cvu"),
                "recipient": payment_data.get("recipient"),
                "amount": payment_data.get("amount"),
                "url": payment_data.get("url"),
                "provider_screenshot": payment_data.get("provider_screenshot"),
                "provider_screenshot_path": payment_data.get("provider_screenshot_path"),
                "screenshot": payment_data.get("screenshot"),
                "screenshot_path": payment_data.get("screenshot_path"),
                "success": payment_data.get("success"),
            },
            "export": {
                "spreadsheet_id": export_result.get("spreadsheetId", "") if export_result and "error" not in export_result else None,
                "updated_range": export_result.get("updates", {}).get("updatedRange", "") if export_result and "error" not in export_result else None,
                "updated_rows": export_result.get("updates", {}).get("updatedRows", 0) if export_result and "error" not in export_result else 0,
                "error": export_result.get("error") if export_result and "error" in export_result else None,
            } if export_result else None,
        }
        
    except ValueError as e:
        logger.error("payment_parser_validation_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("payment_parser_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Payment parser error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8011)
