"""One country, whatever the source writes (#996): FEB gives the nationality in Spanish capitals (``ESPAÑA``), FIBA with its three-letter federation code (``ESP``, ``SLO``, ``GER``, ``LAT``).

A player with several passports is reported with ALL of them (decided 19/11/2026), so the same country written two ways has to be ONE nationality or everybody would look like a dual national.
``country`` returns the name in the style of FEB; what the table does not know is kept as it came (upper case, accents kept), never dropped and never merged by guess. Pure functions.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional
from src.utils.text import strip_accents

FIBA_CODES: Dict[str, str] = {
    "AFG": "AFGANISTÁN", "ALB": "ALBANIA", "ALG": "ARGELIA", "AND": "ANDORRA", "ANG": "ANGOLA", "ARG": "ARGENTINA", "ARM": "ARMENIA", "ARU": "ARUBA", "AUS": "AUSTRALIA", "AUT": "AUSTRIA",
    "AZE": "AZERBAIYÁN", "BAH": "BAHAMAS", "BAR": "BARBADOS", "BDI": "BURUNDI", "BEL": "BÉLGICA", "BEN": "BENÍN", "BER": "BERMUDAS", "BIH": "BOSNIA Y HERZEGOVINA", "BLR": "BIELORRUSIA",
    "BOL": "BOLIVIA", "BOT": "BOTSUANA", "BRA": "BRASIL", "BUL": "BULGARIA", "BUR": "BURKINA FASO", "CAF": "REPÚBLICA CENTROAFRICANA", "CAN": "CANADÁ", "CAY": "ISLAS CAIMÁN", "CHA": "CHAD",
    "CHI": "CHILE", "CHN": "CHINA", "CIV": "COSTA DE MARFIL", "CMR": "CAMERÚN", "COD": "REPÚBLICA DEMOCRÁTICA DEL CONGO", "COG": "CONGO", "COL": "COLOMBIA", "COM": "COMORAS",
    "CPV": "CABO VERDE", "CRC": "COSTA RICA", "CRO": "CROACIA", "CUB": "CUBA", "CYP": "CHIPRE", "CZE": "REPÚBLICA CHECA", "DEN": "DINAMARCA", "DJI": "YIBUTI", "DMA": "DOMINICA",
    "DOM": "REPÚBLICA DOMINICANA", "ECU": "ECUADOR", "EGY": "EGIPTO", "ENG": "INGLATERRA", "ESA": "EL SALVADOR", "ESP": "ESPAÑA", "EST": "ESTONIA", "ETH": "ETIOPÍA", "FIN": "FINLANDIA",
    "FRA": "FRANCIA", "FRO": "ISLAS FEROE", "GAB": "GABÓN", "GAM": "GAMBIA", "GBR": "GRAN BRETAÑA", "GBS": "GUINEA-BISÁU", "GEO": "GEORGIA", "GEQ": "GUINEA ECUATORIAL", "GER": "ALEMANIA",
    "GHA": "GHANA", "GIB": "GIBRALTAR", "GRE": "GRECIA", "GRN": "GRANADA", "GUA": "GUATEMALA", "GUI": "GUINEA", "GUY": "GUYANA", "HAI": "HAITÍ", "HKG": "HONG KONG", "HON": "HONDURAS",
    "HUN": "HUNGRÍA", "INA": "INDONESIA", "IND": "INDIA", "IRI": "IRÁN", "IRL": "IRLANDA", "IRQ": "IRAK", "ISL": "ISLANDIA", "ISR": "ISRAEL", "ITA": "ITALIA", "JAM": "JAMAICA",
    "JOR": "JORDANIA", "JPN": "JAPÓN", "KAZ": "KAZAJISTÁN", "KEN": "KENIA", "KGZ": "KIRGUISTÁN", "KOR": "COREA DEL SUR", "KOS": "KOSOVO", "KSA": "ARABIA SAUDÍ", "KUW": "KUWAIT",
    "LAO": "LAOS", "LAT": "LETONIA", "LBA": "LIBIA", "LBN": "LÍBANO", "LBR": "LIBERIA", "LCA": "SANTA LUCÍA", "LES": "LESOTO", "LIE": "LIECHTENSTEIN", "LTU": "LITUANIA", "LUX": "LUXEMBURGO",
    "MAC": "MACAO", "MAD": "MADAGASCAR", "MAR": "MARRUECOS", "MAS": "MALASIA", "MDA": "MOLDAVIA", "MDV": "MALDIVAS", "MEX": "MÉXICO", "MKD": "MACEDONIA DEL NORTE", "MLI": "MALÍ",
    "MLT": "MALTA", "MNE": "MONTENEGRO", "MNG": "MONGOLIA", "MOZ": "MOZAMBIQUE", "MRI": "MAURICIO", "MTN": "MAURITANIA", "MYA": "MYANMAR", "NAM": "NAMIBIA", "NCA": "NICARAGUA",
    "NED": "PAÍSES BAJOS", "NGR": "NIGERIA", "NIG": "NÍGER", "NIR": "IRLANDA DEL NORTE", "NOR": "NORUEGA", "NZL": "NUEVA ZELANDA", "OMA": "OMÁN", "PAK": "PAKISTÁN", "PAN": "PANAMÁ",
    "PAR": "PARAGUAY", "PER": "PERÚ", "PHI": "FILIPINAS", "PLE": "PALESTINA", "POL": "POLONIA", "POR": "PORTUGAL", "PUR": "PUERTO RICO", "QAT": "CATAR", "ROU": "RUMANÍA",
    "RSA": "SUDÁFRICA", "RUS": "RUSIA", "RWA": "RUANDA", "SCO": "ESCOCIA", "SEN": "SENEGAL", "SEY": "SEYCHELLES", "SLE": "SIERRA LEONA", "SLO": "ESLOVENIA", "SMR": "SAN MARINO",
    "SOM": "SOMALIA", "SRB": "SERBIA", "SSD": "SUDÁN DEL SUR", "STP": "SANTO TOMÉ Y PRÍNCIPE", "SUD": "SUDÁN", "SUI": "SUIZA", "SUR": "SURINAM", "SVK": "ESLOVAQUIA", "SWE": "SUECIA",
    "SWZ": "ESUATINI", "SYR": "SIRIA", "TAN": "TANZANIA", "TGA": "TONGA", "THA": "TAILANDIA", "TJK": "TAYIKISTÁN", "TKM": "TURKMENISTÁN", "TOG": "TOGO", "TPE": "TAIPÉI CHINO",
    "TTO": "TRINIDAD Y TOBAGO", "TUN": "TÚNEZ", "TUR": "TURQUÍA", "UAE": "EMIRATOS ÁRABES UNIDOS", "UGA": "UGANDA", "UKR": "UCRANIA", "URU": "URUGUAY", "USA": "ESTADOS UNIDOS",
    "UZB": "UZBEKISTÁN", "VEN": "VENEZUELA", "VIE": "VIETNAM", "VIN": "SAN VICENTE Y LAS GRANADINAS", "WAL": "GALES", "YEM": "YEMEN", "ZAM": "ZAMBIA", "ZIM": "ZIMBABUE",
}


def _plain(text: str) -> str:
    """Upper case without accents, with the blanks collapsed: what two writings of a country have in common."""
    return " ".join(strip_accents(text.upper()).split())


_BY_NAME = {_plain(name): name for name in FIBA_CODES.values()}


def country(raw: Optional[str]) -> Optional[str]:
    """The country in the style of FEB: a FIBA code or any writing of a known name gives the name; an unknown value stays as it came, in capitals; nothing says nothing."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = " ".join(raw.split())
    code = text.upper()
    if code in FIBA_CODES:
        return FIBA_CODES[code]
    return _BY_NAME.get(_plain(text), code)


def nationalities(values: Iterable[Optional[str]]) -> List[str]:
    """All the different nationalities of ``values`` in the order they come, each country once (two passports are two nationalities, never a conflict)."""
    out: List[str] = []
    for value in values:
        name = country(value)
        if name is not None and name not in out:
            out.append(name)
    return out
