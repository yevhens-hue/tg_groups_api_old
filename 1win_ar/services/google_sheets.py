# services/google_sheets.py
import os
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

import httpx
import structlog

logger = structlog.get_logger()

# Google Sheets API
GOOGLE_SHEETS_API_URL = "https://sheets.googleapis.com/v4/spreadsheets"
# Google Drive API
GOOGLE_DRIVE_API_URL = "https://www.googleapis.com/drive/v3/files"
# ID папки для всех скриншотов в Google Drive (общая папка, как в проекте 1win_STD)
DRIVE_SCREENSHOTS_FOLDER_ID = os.environ.get(
    "DRIVE_SCREENSHOTS_FOLDER_ID",
    "1wZeGXBkEoud0blwl06J7DEAHPTVAFaL4"
)

# Ссылка на папку со скриншотами в Google Drive
DRIVE_SCREENSHOTS_FOLDER_URL = f"https://drive.google.com/drive/u/1/folders/{DRIVE_SCREENSHOTS_FOLDER_ID}"


def extract_spreadsheet_id(url: str) -> str:
    """
    Извлечь ID таблицы из URL Google Sheets.
    
    Примеры:
    - https://docs.google.com/spreadsheets/d/1ubWNiixJEzQxu9kLO1GAosbdiXw1-kIGnsJjdwzFDJQ/edit
    -> 1ubWNiixJEzQxu9kLO1GAosbdiXw1-kIGnsJjdwzFDJQ
    """
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract spreadsheet ID from URL: {url}")


def extract_gid_from_url(url: str) -> Optional[int]:
    """
    Извлечь gid (ID вкладки) из URL Google Sheets.
    
    Примеры:
    - https://docs.google.com/spreadsheets/d/.../edit?gid=516142479#gid=516142479
    -> 516142479
    
    Args:
        url: URL Google Sheets
        
    Returns:
        gid или None если не найден
    """
    # Ищем gid в query параметрах или в hash
    match = re.search(r'[?&#]gid=(\d+)', url)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


class GoogleSheetsClient:
    """
    Клиент для работы с Google Sheets API.
    Использует OAuth2 access token для аутентификации.
    """

    def __init__(self, access_token: Optional[str] = None):
        """
        Инициализация клиента.
        
        Args:
            access_token: OAuth2 access token (из .env или параметра)
        """
        self.access_token = access_token or os.getenv("GOOGLE_SHEETS_ACCESS_TOKEN")
        
        if not self.access_token:
            logger.warning("google_sheets_no_auth", message="GOOGLE_SHEETS_ACCESS_TOKEN not set")

    def _get_headers(self) -> Dict[str, str]:
        """Получить заголовки для запросов."""
        if not self.access_token:
            raise ValueError("Google Sheets access token is required")
        
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def append_rows(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: List[List[Any]],
    ) -> Dict[str, Any]:
        """
        Добавить строки в Google Sheet.
        
        Args:
            spreadsheet_id: ID таблицы
            range_name: Диапазон (например, "Sheet1!A:Z")
            values: Список строк (каждая строка - список значений)
        """
        url = f"{GOOGLE_SHEETS_API_URL}/{spreadsheet_id}/values/{range_name}:append"
        params = {
            "valueInputOption": "USER_ENTERED",
            "insertDataOption": "INSERT_ROWS",
        }

        body = {
            "values": values,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=self._get_headers(),
                    params=params,
                    json=body,
                )
                response.raise_for_status()
                result = response.json()
                logger.info(
                    "google_sheets_append_success",
                    spreadsheet_id=spreadsheet_id[:20],
                    rows_added=len(values),
                )
                return result
        except httpx.HTTPError as e:
            error_msg = str(e)
            if hasattr(e, "response") and e.response:
                try:
                    error_detail = e.response.json()
                    error_msg = error_detail.get("error", {}).get("message", str(e))
                except:
                    pass
            
            logger.error("google_sheets_append_error", error=error_msg)
            raise Exception(f"Google Sheets API error: {error_msg}") from e

    async def clear_range(
        self,
        spreadsheet_id: str,
        range_name: str,
    ) -> Dict[str, Any]:
        """Очистить диапазон в таблице."""
        url = f"{GOOGLE_SHEETS_API_URL}/{spreadsheet_id}/values/{range_name}:clear"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=self._get_headers(),
                    json={},
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            logger.error("google_sheets_clear_error", error=str(e))
            raise

    async def upload_file_to_drive(
        self,
        file_path: str,
        folder_id: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Загрузить файл в Google Drive.
        
        Args:
            file_path: Путь к локальному файлу
            folder_id: ID папки в Drive (по умолчанию DRIVE_SCREENSHOTS_FOLDER_ID)
            file_name: Имя файла в Drive (по умолчанию берется из file_path)
            
        Returns:
            webViewLink файла в Drive или None при ошибке
        """
        import json
        from pathlib import Path
        
        folder_id = folder_id or DRIVE_SCREENSHOTS_FOLDER_ID
        
        # Определяем имя файла
        if not file_name:
            file_path_obj = Path(file_path)
            file_name = file_path_obj.name
        
        # Читаем файл
        try:
            with open(file_path, 'rb') as f:
                file_content = f.read()
        except Exception as e:
            logger.error("drive_upload_file_read_error", error=str(e), file_path=file_path)
            return None
        
        # Метаданные файла
        metadata = {
            'name': file_name,
        }
        if folder_id:
            metadata['parents'] = [folder_id]
        
        # Загружаем файл используя правильный двухэтапный метод
        try:
            # Увеличиваем таймаут для больших файлов
            timeout = httpx.Timeout(120.0, connect=30.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                headers_auth = {
                    "Authorization": f"Bearer {self.access_token}",
                }
                
                # Метод 1: Сначала создаем пустой файл с метаданными
                logger.debug("drive_upload_creating_file", file_name=file_name, folder_id=folder_id)
                create_response = await client.post(
                    f"{GOOGLE_DRIVE_API_URL}?fields=id,webViewLink",
                    headers={**headers_auth, "Content-Type": "application/json"},
                    json=metadata,
                )
                create_response.raise_for_status()
                create_result = create_response.json()
                file_id = create_result.get('id')
                
                if not file_id:
                    raise ValueError("Failed to create file: no file ID returned")
                
                logger.debug("drive_upload_file_created", file_id=file_id)
                
                # Метод 2: Загружаем содержимое файла через PUT с uploadType=media
                # Для media upload НЕ указываем fields в URL, и используем PUT
                upload_url = f"{GOOGLE_DRIVE_API_URL}/{file_id}?uploadType=media"
                logger.debug("drive_upload_uploading_content", file_id=file_id, size=len(file_content))
                
                try:
                    upload_response = await client.put(
                        upload_url,
                        headers={**headers_auth, "Content-Type": "image/png"},
                        content=file_content,
                    )
                    
                    # Проверяем статус
                    if upload_response.status_code not in [200, 201]:
                        error_text = upload_response.text[:1000] if upload_response.text else "No error text"
                        logger.error("drive_upload_content_failed", 
                                    status=upload_response.status_code, 
                                    error=error_text[:200],
                                    file_id=file_id)
                        upload_response.raise_for_status()
                    
                    logger.debug("drive_upload_content_success", status=upload_response.status_code, file_id=file_id)
                except (httpx.ReadError, httpx.NetworkError) as read_err:
                    # Игнорируем ошибки чтения ответа - файл может быть загружен, но ответ не прочитан
                    # Это часто происходит с большими файлами
                    logger.warning("drive_upload_read_error_ignored", 
                                  error=str(read_err)[:100], 
                                  file_id=file_id,
                                  note="File may still be uploaded, checking...")
                except Exception as upload_err:
                    # Другие ошибки - логируем и пробуем продолжить
                    logger.warning("drive_upload_content_warning", 
                                  error=str(upload_err)[:200], 
                                  file_id=file_id,
                                  note="Will try to get file info anyway")
                
                # Для media upload ответ может быть пустым или содержать только file_id
                # Получаем информацию о файле отдельно для получения webViewLink
                upload_result = {"id": file_id}
                
                # Получаем webViewLink если его нет в ответе
                web_view_link = upload_result.get('webViewLink')
                if not web_view_link:
                    # Получаем информацию о файле для получения ссылки
                    try:
                        file_info_response = await client.get(
                            f"{GOOGLE_DRIVE_API_URL}/{file_id}?fields=id,webViewLink",
                            headers=headers_auth,
                        )
                        if file_info_response.status_code == 200:
                            file_info = file_info_response.json()
                            web_view_link = file_info.get('webViewLink') or f"https://drive.google.com/file/d/{file_id}/view"
                        else:
                            web_view_link = f"https://drive.google.com/file/d/{file_id}/view"
                    except Exception as info_e:
                        logger.warning("drive_upload_get_info_failed", error=str(info_e), file_id=file_id)
                        web_view_link = f"https://drive.google.com/file/d/{file_id}/view"
                
                logger.info(
                    "drive_upload_success",
                    file_name=file_name,
                    file_id=file_id,
                    link=web_view_link[:50] + "...",
                )
                return web_view_link
                
        except httpx.HTTPStatusError as e:
            # Более детальная обработка HTTP ошибок
            error_msg = str(e)
            error_code = None
            if hasattr(e, "response") and e.response:
                try:
                    error_detail = e.response.json()
                    error_msg = error_detail.get("error", {}).get("message", str(e))
                    error_code = error_detail.get("error", {}).get("code")
                except:
                    error_msg = e.response.text[:500] if e.response.text else str(e)
                    error_code = e.response.status_code
            
            logger.error("drive_upload_error", error=error_msg, error_code=error_code, file_path=file_path)
            return None
        except httpx.HTTPError as e:
            error_msg = str(e)
            error_code = None
            if hasattr(e, "response") and e.response:
                try:
                    error_detail = e.response.json()
                    error_msg = error_detail.get("error", {}).get("message", str(e))
                    error_code = error_detail.get("error", {}).get("code")
                except:
                    pass
            
            # Проверяем, связана ли ошибка с недостаточными правами
            if "insufficient authentication scopes" in error_msg.lower() or error_code == 403:
                logger.error(
                    "drive_upload_error_insufficient_scopes",
                    error=error_msg,
                    file_path=file_path,
                    solution="Запустите 'python3 get_google_token.py' для получения нового токена с правами для Drive API"
                )
            else:
                logger.error("drive_upload_error", error=error_msg, file_path=file_path, error_code=error_code)
            return None
        except Exception as e:
            logger.error("drive_upload_exception", error=str(e), file_path=file_path)
            return None


async def get_all_sheets_info(
    spreadsheet_id: str,
    access_token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Получить информацию о всех вкладках в таблице.
    
    Args:
        spreadsheet_id: ID таблицы
        access_token: OAuth2 access token
        
    Returns:
        Список словарей с информацией о вкладках: [{"title": "Sheet1", "sheetId": 0, "gid": ...}, ...]
    """
    client = GoogleSheetsClient(access_token=access_token)
    url = f"{GOOGLE_SHEETS_API_URL}/{spreadsheet_id}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.get(
                url,
                headers=client._get_headers(),
            )
            response.raise_for_status()
            data = response.json()
            
            sheets_info = []
            for sheet in data.get("sheets", []):
                props = sheet.get("properties", {})
                sheets_info.append({
                    "title": props.get("title"),
                    "sheetId": props.get("sheetId"),
                    "index": props.get("index", 0),
                })
            
            return sheets_info
    except Exception as e:
        logger.error("get_all_sheets_info_error", error=str(e))
        return []


async def get_sheet_name_by_gid(
    spreadsheet_id: str,
    gid: int,
    access_token: Optional[str] = None,
) -> Optional[str]:
    """
    Получить имя вкладки по gid через Google Sheets API.
    
    Внимание: gid из URL может не совпадать с sheetId в API напрямую.
    Эта функция пытается найти вкладку, сравнивая gid с sheetId.
    Если не найдена, возвращает None.
    
    Args:
        spreadsheet_id: ID таблицы
        gid: ID вкладки (gid из URL)
        access_token: OAuth2 access token
        
    Returns:
        Имя вкладки или None
    """
    sheets_info = await get_all_sheets_info(spreadsheet_id, access_token)
    
    # Пробуем найти по sheetId = gid
    for sheet_info in sheets_info:
        if sheet_info.get("sheetId") == gid:
            return sheet_info.get("title")
    
    # Если не нашли, логируем доступные вкладки для отладки
    if sheets_info:
        available_sheets = [s.get("title") for s in sheets_info]
        logger.warning(
            "sheet_name_not_found_by_gid",
            gid=gid,
            available_sheets=available_sheets,
            sheet_ids=[s.get("sheetId") for s in sheets_info],
        )
    
    return None


async def export_payment_data_to_sheets(
    payment_data: Dict[str, Any],
    spreadsheet_id_or_url: str,
    sheet_name: Optional[str] = None,
    clear_first: bool = False,
    access_token: Optional[str] = None,
    gid: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Экспортировать платежные данные в Google Sheets.
    
    Формат данных соответствует колонкам:
    Method | Type | Account | Date | Links | Screenshot | QR | Status | Bank | CVU
    
    Args:
        payment_data: Словарь с платежными данными (результат parse_payment_data_1win)
        spreadsheet_id_or_url: ID таблицы или URL (будет извлечен ID и gid если есть)
        sheet_name: Имя вкладки (будет получено по gid если указан gid, но не sheet_name)
        clear_first: Очистить диапазон перед записью
        access_token: OAuth2 access token (опционально, можно из .env)
        gid: ID вкладки (gid) - если не указан, будет извлечен из URL если возможно
        
    Returns:
        Результат операции записи
    """
    # Извлекаем ID и gid если передан URL
    original_url = spreadsheet_id_or_url if "/" in spreadsheet_id_or_url or "http" in spreadsheet_id_or_url else None
    
    if original_url:
        spreadsheet_id = extract_spreadsheet_id(original_url)
        # Извлекаем gid из URL если не был указан явно
        if gid is None:
            gid = extract_gid_from_url(original_url)
    else:
        spreadsheet_id = spreadsheet_id_or_url
    
    # Если указан gid и не указано имя вкладки, получаем имя вкладки
    if gid and not sheet_name:
        sheet_name_from_gid = await get_sheet_name_by_gid(
            spreadsheet_id=spreadsheet_id,
            gid=gid,
            access_token=access_token,
        )
        if sheet_name_from_gid:
            sheet_name = sheet_name_from_gid
    
    # Если имя вкладки все еще не найдено, получаем первую доступную
    if not sheet_name:
        sheets_info = await get_all_sheets_info(spreadsheet_id, access_token)
        if sheets_info:
            # Сортируем по index и берем первую
            sheets_info.sort(key=lambda x: x.get("index", 0))
            sheet_name = sheets_info[0].get("title", "Sheet1")
            logger.info("using_first_available_sheet", sheet_name=sheet_name, gid=gid)
        else:
            # Fallback на Sheet1
            sheet_name = "Sheet1"
            logger.warning("using_default_sheet_name", sheet_name=sheet_name)
    
    client = GoogleSheetsClient(access_token=access_token)
    
    # Формируем строку данных согласно структуре таблицы
    # Method | Type | Account | Date | Links | Screenshot | QR | Status | Bank | CVU
    # Формируем Links - включаем domain и url
    links_parts = []
    if payment_data.get("domain"):
        links_parts.append(f"Domain: {payment_data.get('domain')}")
    if payment_data.get("url"):
        links_parts.append(payment_data.get("url"))
    links_value = " | ".join(links_parts) if links_parts else ""
    
    # Загружаем скриншоты провайдера в Google Drive (в общую папку, как в проекте 1win_STD)
    provider_drive_link = ""
    provider_screenshot_path = payment_data.get("provider_screenshot_path")
    
    if provider_screenshot_path and os.path.exists(provider_screenshot_path):
        try:
            logger.info("uploading_provider_screenshot_to_drive", file_path=provider_screenshot_path, folder_id=DRIVE_SCREENSHOTS_FOLDER_ID)
            provider_drive_link = await client.upload_file_to_drive(
                provider_screenshot_path, 
                folder_id=DRIVE_SCREENSHOTS_FOLDER_ID  # Используем общую папку
            )
            if provider_drive_link:
                logger.info("provider_screenshot_uploaded_to_drive", link=provider_drive_link[:50] + "...", folder_id=DRIVE_SCREENSHOTS_FOLDER_ID)
            else:
                logger.warning(
                    "provider_screenshot_upload_failed", 
                    path=provider_screenshot_path,
                    folder_id=DRIVE_SCREENSHOTS_FOLDER_ID,
                    hint="Для загрузки в Drive запустите 'python3 get_google_token.py' для получения токена с правами Drive API"
                )
        except Exception as e:
            logger.warning(
                "provider_screenshot_upload_exception", 
                error=str(e), 
                path=provider_screenshot_path,
                hint="Скриншот провайдера сохранен локально. Для загрузки в Drive проверьте права токена."
            )
    
    # Формируем ссылку для колонки Screenshot: если файл загружен - ссылка на файл, иначе - ссылка на папку
    if provider_drive_link:
        screenshot_link = provider_drive_link  # Ссылка на загруженный файл
    else:
        screenshot_link = DRIVE_SCREENSHOTS_FOLDER_URL  # Ссылка на общую папку в Drive
        logger.info("using_screenshots_folder_link_in_sheet", folder_url=DRIVE_SCREENSHOTS_FOLDER_URL)
    
    # Если скриншота провайдера нет, всё равно добавляем ссылку на папку
    if not provider_screenshot_path:
        screenshot_link = DRIVE_SCREENSHOTS_FOLDER_URL
        logger.info("no_provider_screenshot_using_folder_link", folder_url=DRIVE_SCREENSHOTS_FOLDER_URL)
    
    row = [
        payment_data.get("method", ""),  # Method
        payment_data.get("payment_type", ""),  # Type
        payment_data.get("recipient", ""),  # Account
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Date
        links_value,  # Links (domain + url)
        screenshot_link,  # Screenshot (ссылка на общую папку в Drive или на файл, если загружен)
        "",  # QR (если есть)
        "Success" if payment_data.get("success") else "Failed",  # Status
        payment_data.get("bank", ""),  # Bank
        payment_data.get("cvu", ""),  # CVU
    ]
    
    range_name = f"{sheet_name}!A:J"
    
    # Очищаем если нужно (только новые строки, не заголовок)
    if clear_first:
        await client.clear_range(spreadsheet_id, f"{sheet_name}!A2:J1000")
    
    # Добавляем строку в конец таблицы
    result = await client.append_rows(
        spreadsheet_id=spreadsheet_id,
        range_name=range_name,
        values=[row],
    )
    
    logger.info(
        "payment_data_exported",
        spreadsheet_id=spreadsheet_id[:20],
        sheet_name=sheet_name,
        cvu=payment_data.get("cvu", "")[:10] + "..." if payment_data.get("cvu") else None,
    )
    
    return result
