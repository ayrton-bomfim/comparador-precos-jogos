"""
Coleta o catálogo público de estúdios do Indústria de Jogos (IDJ).

Modo padrão: somente simulação, sem gravar no banco.
Para persistir: python -m backend.scripts.importar_estudios_idj --apply

A rotina coleta os registros das páginas de listagem. Não importa jogos e
não altera a tabela `jogos`.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text

try:
    from backend.config import settings
except ImportError:
    # Permite execução direta a partir da raiz do projeto.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from backend.config import settings


BASE_URL = "https://www.industriadejogos.com.br/estudio/"
SOURCE = "idj"
USER_AGENT = "Mozilla/5.0 (compatible; DESCTRL-StudioCatalog/1.0)"
TIMEOUT_SECONDS = 25
DEFAULT_DELAY = 1.5
MAX_PAGES_SAFETY = 100


def normalize_name(name: str) -> str:
    """Normalização estável para deduplicação; preserva nome original separado."""
    value = unicodedata.normalize("NFKD", name or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\s+", " ", value).strip().casefold()
    return value


def page_url(page: int) -> str:
    if page <= 1:
        return BASE_URL
    return f"{BASE_URL}?page={page}"


def fetch_soup(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    if "text/html" not in response.headers.get("Content-Type", "").lower():
        raise RuntimeError(f"Resposta não parece HTML: {url}")
    return BeautifulSoup(response.text, "html.parser")


def is_studio_href(href: str | None) -> bool:
    if not href:
        return False
    absolute = urljoin(BASE_URL, href)
    parsed = urlparse(absolute)
    if parsed.netloc and not parsed.netloc.endswith("industriadejogos.com.br"):
        return False
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2 or parts[0] not in {"estudio", "studio"}:
        return False
    # Rotas de navegação/ações não são páginas individuais de estúdios.
    if parts[1].casefold() in {"cadastrar", "cadastro", "page", "novo"}:
        return False
    return True


def find_page_count(soup: BeautifulSoup) -> int:
    pages = [1]
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        parsed = urlparse(urljoin(BASE_URL, href))
        query = parse_qs(parsed.query)
        for raw in query.get("page", []):
            try:
                pages.append(int(raw))
            except ValueError:
                pass
    # Fallback para paginação por texto caso o site mude os links.
    for element in soup.select("a, button"):
        label = element.get_text(" ", strip=True)
        if label.isdigit():
            value = int(label)
            if 1 < value < MAX_PAGES_SAFETY:
                pages.append(value)
    return min(max(pages), MAX_PAGES_SAFETY)


def extract_card_text(anchor) -> str:
    # Os cartões podem variar de estrutura. Sobe até encontrar um contêiner
    # razoável com nome, localidade e status, sem capturar a página inteira.
    node = anchor
    best = anchor.get_text(" ", strip=True)
    for _ in range(5):
        parent = getattr(node, "parent", None)
        if not parent:
            break
        text_value = parent.get_text(" ", strip=True)
        if len(text_value) > 0:
            best = text_value
        if parent.name in {"article", "li"}:
            return text_value
        node = parent
    return best


def parse_listing_page(soup: BeautifulSoup) -> list[dict]:
    records_by_slug: dict[str, dict] = {}

    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if not is_studio_href(href):
            continue

        url = urljoin(BASE_URL, href).split("#", 1)[0].rstrip("/") + "/"
        slug = urlparse(url).path.strip("/").split("/")[-1]
        if not slug:
            continue

        # A tabela do catálogo apresenta nome, localidade e status na mesma linha.
        # Extrair a linha inteira evita depender apenas do link de imagem, que não tem texto.
        row = anchor.find_parent("tr")
        cells = row.find_all(["td", "th"], recursive=False) if row else []
        name = ""
        locality = None
        active = None

        if cells:
            # Primeiro tenta o texto do link e depois o conteúdo da primeira célula.
            name = anchor.get_text(" ", strip=True)
            if not name and cells:
                name = cells[0].get_text(" ", strip=True)

            # A segunda coluna é Localidade na tabela pública da IDJ.
            if len(cells) >= 2:
                locality_text = cells[1].get_text(" ", strip=True)
                if locality_text and locality_text not in {"-", "—", "–"}:
                    locality = locality_text[:255]

            for cell in cells:
                status_text = cell.get_text(" ", strip=True).casefold()
                if status_text == "ativo":
                    active = True
                elif status_text == "inativo":
                    active = False
        else:
            # Fallback para eventual mudança de tabela para cartões.
            name = anchor.get_text(" ", strip=True)
            if not name and anchor.parent:
                name = anchor.parent.get_text(" ", strip=True)

        # Limpa aliases que aparecem junto ao nome principal.
        name = re.split(r"\bTambém conhecido como\b", name, maxsplit=1, flags=re.IGNORECASE)[0]
        name = re.sub(r"\s+", " ", name).strip()
        invalid_names = {
            "cadastrar estúdio", "cadastrar estudio", "visualizar",
            "ver estúdio", "ver estudio", "ativo", "inativo",
        }
        if not name or name.casefold() in invalid_names or name.casefold().startswith("cadastrar "):
            continue

        record = {
            "nome": name[:255],
            "nome_normalizado": normalize_name(name),
            "slug": slug[:255],
            "url_fonte": url[:1000],
            "localidade": locality,
            "ativo": active,
            "origem": SOURCE,
        }

        previous = records_by_slug.get(slug)
        if previous is None:
            records_by_slug[slug] = record
        else:
            # Consolida os links repetidos do mesmo estúdio, aproveitando os campos conhecidos.
            if (not previous.get("nome") or previous["nome"].casefold() == "visualizar") and record.get("nome"):
                previous["nome"] = record["nome"]
                previous["nome_normalizado"] = record["nome_normalizado"]
            if not previous.get("localidade") and record.get("localidade"):
                previous["localidade"] = record["localidade"]
            if previous.get("ativo") is None and record.get("ativo") is not None:
                previous["ativo"] = record["ativo"]

    return list(records_by_slug.values())


def get_total_from_page(soup: BeautifulSoup) -> int | None:
    text_content = soup.get_text(" ", strip=True)
    patterns = [
        r"Exibindo\s+\d+\s+estúdios\s+de\s+([\d.]+)",
        r"Exibindo\s+\d+\s+estudios\s+de\s+([\d.]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_content, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1).replace(".", ""))
            except ValueError:
                pass
    return None


def collect(session: requests.Session, delay: float, max_pages: int | None) -> list[dict]:
    all_records: list[dict] = []
    empty_pages = 0
    page_limit = max_pages if max_pages is not None else MAX_PAGES_SAFETY
    seen_page_signatures: set[tuple[str, ...]] = set()

    for page in range(1, page_limit + 1):
        url = BASE_URL if page == 1 else page_url(page)
        soup = fetch_soup(session, url)
        if page == 1 and max_pages is None:
            total = get_total_from_page(soup)
            pagination_last_page = find_page_count(soup)

            if total:
                # O catálogo costuma exibir 30 estúdios por página.
                total_pages = (total + 29) // 30
                page_limit = min(total_pages, MAX_PAGES_SAFETY)
                print(
                    f"Total informado pela IDJ: {total} estúdios; "
                    f"páginas previstas pelo total: {page_limit}"
                )
            elif pagination_last_page > 1:
                # Fallback: usa o maior número de página encontrado nos links
                # reais de paginação, em vez de continuar até o limite de segurança.
                page_limit = min(pagination_last_page, MAX_PAGES_SAFETY)
                print(
                    "Total de estúdios não identificado no texto; "
                    f"última página detectada na paginação: {page_limit}"
                )
            else:
                # Último fallback seguro para este catálogo: não seguir páginas
                # indefinidamente se a IDJ repetir conteúdo em páginas inexistentes.
                page_limit = 56
                print(
                    "Paginação não identificada no HTML; usando limite de 56 páginas "
                    "observado no catálogo da IDJ."
                )
        records = parse_listing_page(soup)
        page_signature = tuple(sorted(record["slug"] for record in records))

        if records and page_signature in seen_page_signatures:
            print(
                f"Página {page}: conteúdo repetido de outra página; "
                "encerrando a coleta para evitar duplicações."
            )
            break

        if records:
            seen_page_signatures.add(page_signature)
            empty_pages = 0
            all_records.extend(records)
            print(f"Página {page}: {len(records)} estúdios; total bruto: {len(all_records)}")
        else:
            empty_pages += 1
            print(f"Página {page}: nenhum estúdio identificado ({empty_pages}/2 páginas vazias consecutivas).")
            if empty_pages >= 2:
                break

        if page < page_limit:
            time.sleep(delay)

    deduped: dict[str, dict] = {}
    for item in all_records:
        key = item["slug"] or item["nome_normalizado"]
        previous = deduped.get(key)
        if previous is None:
            deduped[key] = item
        else:
            if previous.get("ativo") is None and item.get("ativo") is not None:
                previous["ativo"] = item["ativo"]

    if not deduped:
        raise RuntimeError(
            "Nenhum estúdio foi identificado. O HTML pode ter mudado; nada foi gravado."
        )
    return list(deduped.values())


DDL = """
CREATE TABLE IF NOT EXISTS estudios_brasileiros (
    id BIGSERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    nome_normalizado VARCHAR(255) NOT NULL UNIQUE,
    slug VARCHAR(255),
    url_fonte VARCHAR(1000),
    localidade VARCHAR(255),
    ativo BOOLEAN,
    origem VARCHAR(20) NOT NULL DEFAULT 'idj',
    ultima_coleta TIMESTAMPTZ,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_estudios_brasileiros_origem CHECK (origem IN ('idj', 'manual'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_estudios_brasileiros_slug
ON estudios_brasileiros (slug) WHERE slug IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_estudios_brasileiros_ativo
ON estudios_brasileiros (ativo);
"""


UPSERT = text("""
INSERT INTO estudios_brasileiros
    (nome, nome_normalizado, slug, url_fonte, localidade, ativo, origem, ultima_coleta, atualizado_em)
VALUES
    (:nome, :nome_normalizado, :slug, :url_fonte, :localidade, :ativo, :origem, :ultima_coleta, NOW())
ON CONFLICT (nome_normalizado) DO UPDATE SET
    nome = EXCLUDED.nome,
    slug = COALESCE(EXCLUDED.slug, estudios_brasileiros.slug),
    url_fonte = COALESCE(EXCLUDED.url_fonte, estudios_brasileiros.url_fonte),
    localidade = COALESCE(EXCLUDED.localidade, estudios_brasileiros.localidade),
    ativo = COALESCE(EXCLUDED.ativo, estudios_brasileiros.ativo),
    ultima_coleta = EXCLUDED.ultima_coleta,
    atualizado_em = NOW()
WHERE estudios_brasileiros.origem = 'idj'
   OR estudios_brasileiros.url_fonte IS NULL
""")


def main() -> int:
    parser = argparse.ArgumentParser(description="Coleta estúdios do IDJ para o DESCTRL.")
    parser.add_argument("--apply", action="store_true", help="Grava no PostgreSQL. Sem esta opção, apenas simula.")
    parser.add_argument("--max-pages", type=int, default=None, help="Limita páginas para teste (ex.: --max-pages 2).")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help=f"Intervalo entre páginas em segundos (padrão: {DEFAULT_DELAY}).")
    parser.add_argument("--output", default="estudios_idj_coletados.csv", help="CSV de saída.")
    args = parser.parse_args()

    if args.max_pages is not None and args.max_pages < 1:
        parser.error("--max-pages precisa ser >= 1")
    if args.delay < 0:
        parser.error("--delay não pode ser negativo")

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    try:
        records = collect(session, args.delay, args.max_pages)
    except Exception as exc:
        print(f"ERRO na coleta: {exc}", file=sys.stderr)
        return 2

    if not records:
        print("Nenhum registro coletado; banco não foi alterado.")
        return 2

    import csv
    output_path = Path(args.output)
    fieldnames = ["nome", "nome_normalizado", "slug", "url_fonte", "localidade", "ativo", "origem"]
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"\nCSV salvo: {output_path.resolve()}")
    print(f"Registros únicos coletados: {len(records)}")
    print(f"Com status ativo conhecido: {sum(r['ativo'] is True for r in records)}")
    print(f"Com status inativo conhecido: {sum(r['ativo'] is False for r in records)}")
    print(f"Sem status conhecido: {sum(r['ativo'] is None for r in records)}")

    if not args.apply:
        print("\nSIMULAÇÃO: nada foi gravado no PostgreSQL.")
        print("Revise o CSV e execute novamente com --apply para persistir.")
        return 0

    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    timestamp = datetime.now(timezone.utc)
    payload = [{**r, "ultima_coleta": timestamp} for r in records]
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(DDL)
            result = connection.execute(UPSERT, payload)
        print(f"\nImportação concluída. Linhas afetadas pelo PostgreSQL: {result.rowcount}")
        print("A tabela `jogos` não foi alterada.")
    except Exception as exc:
        print(f"ERRO na gravação; transação revertida: {exc}", file=sys.stderr)
        return 3
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
