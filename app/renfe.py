from typing import List, Optional, Tuple
from pydantic import BaseModel
from datetime import datetime

from playwright.async_api import async_playwright

RENFE_HOME = "https://www.renfe.com/es/es"


class TrainModel(BaseModel):
    service: str
    departure: str
    arrival: str
    duration: str
    fare_from: Optional[float] = None
    currency: Optional[str] = None


async def _fill_search_form(
    page,
    origin: str,
    destination: str,
    date_out: str,
    date_return: Optional[str],
    adults: int,
) -> None:
    await page.goto(RENFE_HOME)

    # Accept cookies if banner appears
    try:
        accept_selector = 'button:has-text("Aceptar")'
        if await page.is_visible(accept_selector):
            await page.click(accept_selector)
    except Exception:
        pass

    # Fill origin
    await page.get_by_label("ORIGEN").click()
    await page.keyboard.type(origin)
    await page.wait_for_timeout(400)
    await page.keyboard.press("Enter")

    # Fill destination
    await page.get_by_label("DESTINO").click()
    await page.keyboard.type(destination)
    await page.wait_for_timeout(400)
    await page.keyboard.press("Enter")

    # Dates
    await page.get_by_text("FECHA IDA").click()
    await _pick_date(page, date_out)

    if date_return:
        await page.get_by_text("FECHA VUELTA").click()
        await _pick_date(page, date_return)

    # Passengers
    await page.get_by_text("PASAJEROS").click()
    current = 1
    if adults > current:
        for _ in range(adults - current):
            await page.locator('button[aria-label="Aumentar adultos"]').click()
    elif adults < current:
        for _ in range(current - adults):
            await page.locator('button[aria-label="Disminuir adultos"]').click()
    await page.keyboard.press("Escape")

    # Submit
    await page.get_by_role("button", name="Buscar billete").click()


async def _pick_date(page, date_str: str) -> None:
    target = datetime.strptime(date_str, "%Y-%m-%d")
    day_str = str(target.day)

    for _ in range(24):
        calendar_header = page.locator(
            '[class*="calendar"] [class*="month"], .ui-datepicker-title'
        )
        text = (
            await calendar_header.first().text_content()
            if await calendar_header.count() > 0
            else ""
        )
        if (
            text
            and str(target.year) in text
            and _month_name_es(target.month) in text.lower()
        ):
            day_cell = page.locator(f'button[aria-label*=" {day_str} "]')
            if await day_cell.count() == 0:
                day_cell = page.locator(f'td:has(button) >> text="{day_str}"')
            await day_cell.first().click()
            await page.wait_for_timeout(200)
            return
        next_btn = page.locator(
            'button[aria-label*="Siguiente"], button:has-text("Siguiente")'
        )
        if await next_btn.count() == 0:
            next_btn = page.locator('button[aria-label="Next"]')
        await next_btn.first().click()
        await page.wait_for_timeout(150)


def _month_name_es(month: int) -> str:
    names = [
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    return names[month - 1]


async def _extract_results(page) -> List[TrainModel]:
    trains: List[TrainModel] = []
    await page.wait_for_load_state("networkidle")
    cards = page.locator(
        '[data-testid*="result"], article:has([class*="hora"]) , .trayecto, .result-item'
    )
    count = await cards.count()
    for i in range(count):
        card = cards.nth(i)
        try:
            service = (
                await card.locator(
                    ':text("AVE"), :text("Avlo"), :text("Alvia"), :text("Intercity"), :text("MD")'
                )
                .first()
                .text_content()
            ) or "tren"
        except Exception:
            service = "tren"
        try:
            dep = (
                await card.locator(':text("Salida"), [class*="salida"], time')
                .first()
                .text_content()
            )
            arr = (
                await card.locator(':text("Llegada"), [class*="llegada"], time')
                .nth(1)
                .text_content()
            )
        except Exception:
            dep = arr = ""
        try:
            duration = (
                await card.locator(
                    ':text("Duración"), [class*="duracion"], [class*="duration"]'
                )
                .first()
                .text_content()
            )
        except Exception:
            duration = ""
        price_text = None
        try:
            price_text = (
                await card.locator(':text("€"), [class*="precio"], [class*="price"]')
                .first()
                .text_content()
            )
        except Exception:
            pass
        fare = None
        currency = None
        if price_text:
            txt = price_text.replace(" ", "").replace(",", ".")
            if "€" in txt:
                currency = "EUR"
                try:
                    import re

                    m = re.search(r"(\d+\.?\d*)", txt)
                    if m:
                        fare = float(m.group(1))
                except Exception:
                    pass
        trains.append(
            TrainModel(
                service=service.strip(),
                departure=dep.strip(),
                arrival=arr.strip(),
                duration=duration.strip(),
                fare_from=fare,
                currency=currency,
            )
        )
    return trains


async def search_trains(
    origin: str,
    destination: str,
    date_out: str,
    date_return: Optional[str],
    adults: int,
) -> Tuple[List[TrainModel], Optional[List[TrainModel]]]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="es-ES")
        page = await context.new_page()

        await _fill_search_form(
            page, origin, destination, date_out, date_return, adults
        )

        trains_out = await _extract_results(page)
        trains_ret: Optional[List[TrainModel]] = None

        if date_return:
            try:
                await page.get_by_role("tab", name="Vuelta").click()
                await page.wait_for_timeout(300)
                trains_ret = await _extract_results(page)
            except Exception:
                trains_ret = None

        await context.close()
        await browser.close()

        return trains_out, trains_ret
