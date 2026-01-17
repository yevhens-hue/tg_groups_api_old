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

    async def batch_update(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: List[List[Any]],
    ) -> Dict[str, Any]:
        """
        Обновить диапазон в таблице (заменить существующие данные).
        
        Args:
            spreadsheet_id: ID таблицы
            range_name: Диапазон (например, "Sheet1!A2:Z")
            values: Список строк для записи
        """
        url = f"{GOOGLE_SHEETS_API_URL}/{spreadsheet_id}/values/{range_name}"

        body = {
            "values": values,
        }

        params = {
            "valueInputOption": "USER_ENTERED",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.put(
                    url,
                    headers=self._get_headers(),
                    params=params,
                    json=body,
                )
                response.raise_for_status()
                result = response.json()
                logger.info(
                    "google_sheets_update_success",
                    spreadsheet_id=spreadsheet_id[:20],
                    rows_updated=len(values),
                )
                return result
        except httpx.HTTPError as e:
            error_msg = str(e)
            status_code = None
            if hasattr(e, "response") and e.response:
                status_code = e.response.status_code
                try:
                    error_detail = e.response.json()
                    error_msg = error_detail.get("error", {}).get("message", str(e))
                except:
                    pass
            
            logger.error(
                "google_sheets_update_error",
                error=error_msg,
                status_code=status_code,
            )
            raise Exception(f"Google Sheets API error: {error_msg}") from e

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


async def export_mirrors_to_sheets(
    mirrors: List[Any],
    spreadsheet_id: str,
    range_name: str = "Sheet1!A2:Z",
    clear_first: bool = False,
    access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Экспортировать зеркала в Google Sheets.
    
    Args:
        mirrors: Список объектов Mirror из БД
        spreadsheet_id: ID таблицы (или URL, будет извлечен ID)
        range_name: Диапазон для записи
        clear_first: Очистить диапазон перед записью
        access_token: OAuth2 access token (опционально, можно из .env)
    """
    # Извлекаем ID если передан URL
    if "/" in spreadsheet_id or "http" in spreadsheet_id:
        spreadsheet_id = extract_spreadsheet_id(spreadsheet_id)
    
    client = GoogleSheetsClient(access_token=access_token)

    # Преобразуем зеркала в строки для таблицы
    # Порядок колонок: merchant, country, keyword, source_url, source_domain, 
    #                  final_url, final_domain, is_redirector, is_mirror, cta_found, 
    #                  first_seen_at, last_seen_at
    rows = []
    for mirror in mirrors:
        row = [
            mirror.merchant,
            mirror.country,
            mirror.keyword,
            mirror.source_url,
            mirror.source_domain,
            mirror.final_url or "",
            mirror.final_domain or "",
            "TRUE" if mirror.is_redirector else "FALSE",
            "TRUE" if mirror.is_mirror else "FALSE",
            "TRUE" if mirror.cta_found else "FALSE",
            mirror.first_seen_at.isoformat() if mirror.first_seen_at else "",
            mirror.last_seen_at.isoformat() if mirror.last_seen_at else "",
        ]
        rows.append(row)

    if not rows:
        logger.warning("google_sheets_no_data", message="No mirrors to export")
        return {"updatedCells": 0, "updatedRows": 0}

    # Очищаем если нужно
    if clear_first:
        await client.clear_range(spreadsheet_id, range_name)

    # Записываем данные
    result = await client.batch_update(spreadsheet_id, range_name, rows)

    return result


def extract_sheet_name_from_url(url: str, default: str = "Sheet1") -> str:
    """
    Извлечь имя вкладки из URL Google Sheets или использовать gid.
    
    Args:
        url: URL Google Sheets
        default: Имя вкладки по умолчанию
        
    Returns:
        Имя вкладки для использования в range_name
    """
    # Если в URL есть указание на имя вкладки через #gid=, 
    # мы не можем напрямую получить имя из URL
    # Но можно попробовать извлечь из range_name или использовать API
    # Для простоты, если gid указан, используем Sheet1 или можно получить через API
    return default


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
    
    # Формируем путь к скриншоту - приоритет у provider_screenshot_path, потом screenshot_path
    screenshot_path_value = payment_data.get("provider_screenshot_path") or payment_data.get("screenshot_path") or ""
    
    row = [
        payment_data.get("method", ""),  # Method
        payment_data.get("payment_type", ""),  # Type
        payment_data.get("recipient", ""),  # Account
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Date
        links_value,  # Links (domain + url)
        screenshot_path_value,  # Screenshot (путь к файлу)
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
