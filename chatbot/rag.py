"""RAG-based city/airport retrieval with fuzzy matching.

Combines:
1. Keyword matching (exact + alias) — fast, deterministic
2. Fuzzy string matching (Levenshtein distance) — handles typos
3. Phonetic matching (Soundex) — handles phonetic misspellings

This mitigates LLM hallucination by grounding city extraction in
the actual airport database, not LLM free-text generation.
"""
import re
from typing import Optional, List, Dict, Tuple
from difflib import SequenceMatcher


# ── Soundex Algorithm ──────────────────────────────────────────────────────

def _soundex(name: str) -> str:
    """Compute Soundex code for phonetic matching."""
    if not name:
        return ""

    name = re.sub(r'[^A-Za-z]', '', name).upper()
    if not name:
        return ""

    codes = {
        'B': '1', 'F': '1', 'P': '1', 'V': '1',
        'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
        'D': '3', 'T': '3',
        'L': '4',
        'M': '5', 'N': '5',
        'R': '6',
    }

    result = name[0]
    prev_code = codes.get(name[0], '0')

    for ch in name[1:]:
        code = codes.get(ch, '0')
        if code != '0' and code != prev_code:
            result += code
        if code == '0':
            prev_code = '0'
        else:
            prev_code = code

    result = (result + '000')[:4]
    return result


# ── Levenshtein Distance ───────────────────────────────────────────────────

def _levenshtein(a: str, b: str) -> int:
    """Compute edit distance between two strings."""
    if len(a) < len(b):
        a, b = b, a
    if len(b) == 0:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            ins = prev[j + 1] + 1
            dele = curr[j] + 1
            sub = prev[j] + (ca != cb)
            curr.append(min(ins, dele, sub))
        prev = curr

    return prev[-1]


def _similarity(a: str, b: str) -> float:
    """Normalized similarity score 0-1 using Levenshtein + SequenceMatcher."""
    if not a or not b:
        return 0.0
    lev = _levenshtein(a.lower(), b.lower())
    max_len = max(len(a), len(b))
    lev_score = 1.0 - (lev / max_len) if max_len > 0 else 0.0
    seq_score = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return (lev_score + seq_score) / 2.0


# ── City Database (loaded from airports at startup) ────────────────────────

class CityRetriever:
    """RAG-based city retrieval using airport database.

    Indexes cities by:
    - Exact name
    - Aliases (e.g., Bombay → Mumbai, Madras → Chennai)
    - IATA code (e.g., BLR, DEL, BOM)
    - Soundex code (phonetic)
    - Fuzzy similarity (for typos)
    """

    def __init__(self):
        self._cities: List[Dict] = []
        self._name_index: Dict[str, Dict] = {}
        self._alias_index: Dict[str, Dict] = {}
        self._code_index: Dict[str, Dict] = {}
        self._soundex_index: Dict[str, List[Dict]] = {}
        self._initialized = False

    def load_from_db(self, db_session=None) -> None:
        """Load airports from database. Falls back to hardcoded list if no DB."""
        cities = []

        if db_session:
            try:
                from models import Airport
                airports = db_session.query(Airport).all()
                for a in airports:
                    cities.append({
                        "city": a.city,
                        "code": a.code,
                        "name": a.name,
                        "country": a.country,
                    })
            except Exception:
                pass

        if not cities:
            # Fallback: hardcoded from seed data
            cities = [
                {"city": "Bangalore", "code": "BLR", "name": "Kempegowda International", "country": "India"},
                {"city": "Delhi", "code": "DEL", "name": "Indira Gandhi International", "country": "India"},
                {"city": "Mumbai", "code": "BOM", "name": "Chhatrapati Shivaji International", "country": "India"},
                {"city": "Chennai", "code": "MAA", "name": "Chennai International", "country": "India"},
                {"city": "Hyderabad", "code": "HYD", "name": "Rajiv Gandhi International", "country": "India"},
                {"city": "Kolkata", "code": "CCU", "name": "Netaji Subhas Chandra Bose", "country": "India"},
                {"city": "Goa", "code": "GOI", "name": "Dabolim Airport", "country": "India"},
                {"city": "Kochi", "code": "COK", "name": "Cochin International", "country": "India"},
                {"city": "Jaipur", "code": "JAI", "name": "Jaipur International", "country": "India"},
                {"city": "Ahmedabad", "code": "AMD", "name": "Sardar Vallabhbhai Patel", "country": "India"},
                {"city": "Coimbatore", "code": "CJB", "name": "Coimbatore International", "country": "India"},
                {"city": "Thiruvananthapuram", "code": "TRV", "name": "Trivandrum International", "country": "India"},
                {"city": "Pune", "code": "PNQ", "name": "Pune International", "country": "India"},
            ]

        # Aliases map
        aliases = {
            "bangalore": ["bengaluru", "blr"],
            "delhi": ["new delhi", "del", "indira gandhi"],
            "mumbai": ["bombay", "bom"],
            "chennai": ["madras", "maa"],
            "hyderabad": ["hyd"],
            "kolkata": ["calcutta", "ccu"],
            "goa": ["goi", "dabolim"],
            "kochi": ["cochin", "cok"],
            "jaipur": ["jai"],
            "ahmedabad": ["amd"],
            "coimbatore": ["cjb"],
            "thiruvananthapuram": ["trivandrum", "trv"],
            "pune": ["pnq"],
        }

        self._cities = cities
        self._name_index = {}
        self._alias_index = {}
        self._code_index = {}
        self._soundex_index = {}

        for c in cities:
            city_lower = c["city"].lower()
            self._name_index[city_lower] = c

            # Index by IATA code
            self._code_index[c["code"].lower()] = c

            # Index by aliases
            for alias in aliases.get(city_lower, []):
                self._alias_index[alias.lower()] = c

            # Index by soundex
            sx = _soundex(c["city"])
            if sx not in self._soundex_index:
                self._soundex_index[sx] = []
            self._soundex_index[sx].append(c)

        self._initialized = True

    def retrieve(self, query: str, threshold: float = 0.75) -> Optional[Dict]:
        """Retrieve the best-matching city for a query string.

        Uses a hybrid approach:
        1. Exact match (name, alias, or IATA code)
        2. Soundex phonetic match
        3. Fuzzy similarity match (if above threshold)

        Returns {"city": str, "code": str, "confidence": float, "method": str} or None.
        """
        if not self._initialized:
            self.load_from_db()

        if not query or not query.strip():
            return None

        q = query.lower().strip()

        # 1. Exact match — name
        if q in self._name_index:
            c = self._name_index[q]
            return {"city": c["city"], "code": c["code"], "confidence": 1.0, "method": "exact_name"}

        # 2. Exact match — alias
        if q in self._alias_index:
            c = self._alias_index[q]
            return {"city": c["city"], "code": c["code"], "confidence": 0.95, "method": "alias"}

        # 3. Exact match — IATA code
        if q in self._code_index:
            c = self._code_index[q]
            return {"city": c["city"], "code": c["code"], "confidence": 1.0, "method": "iata_code"}

        # 4. Substring match — "del" matches "delhi"
        for name, c in self._name_index.items():
            if q in name or name in q:
                if len(q) >= 3:
                    return {"city": c["city"], "code": c["code"], "confidence": 0.85, "method": "substring"}

        # 5. Soundex phonetic match (skip for very short queries — too many false positives)
        if len(q) >= 3:
            q_soundex = _soundex(q)
            if q_soundex and q_soundex in self._soundex_index:
                candidates = self._soundex_index[q_soundex]
                # Pick the one with highest similarity
                best = max(candidates, key=lambda c: _similarity(q, c["city"].lower()))
                sim = _similarity(q, best["city"].lower())
                if sim >= threshold * 0.7:
                    return {"city": best["city"], "code": best["code"], "confidence": sim * 0.8, "method": "phonetic"}

        # 6. Fuzzy similarity match
        best_match = None
        best_score = 0.0
        all_names = list(self._name_index.keys()) + list(self._alias_index.keys())
        for name in all_names:
            score = _similarity(q, name)
            if score > best_score:
                best_score = score
                best_match = name

        if best_match and best_score >= threshold:
            c = self._name_index.get(best_match) or self._alias_index.get(best_match)
            if c:
                return {"city": c["city"], "code": c["code"], "confidence": best_score, "method": "fuzzy"}

        return None

    def extract_cities(self, message: str) -> List[Dict]:
        """Extract all city mentions from a message.

        Returns list of {"city": str, "code": str, "confidence": float, "method": str, "position": int}.
        """
        if not self._initialized:
            self.load_from_db()

        results = []
        msg_lower = message.lower()

        # Check all known names and aliases
        all_keys = {}
        for name, c in self._name_index.items():
            all_keys[name] = c
        for alias, c in self._alias_index.items():
            all_keys[alias] = c
        for code, c in self._code_index.items():
            all_keys[code] = c

        found_positions = []
        for key, c in sorted(all_keys.items(), key=lambda x: len(x[0]), reverse=True):
            pattern = r'\b' + re.escape(key) + r'\b'
            match = re.search(pattern, msg_lower)
            if match:
                pos = match.start()
                # Avoid overlapping matches
                if not any(abs(pos - p) < 3 for p in found_positions):
                    found_positions.append(pos)
                    method = "alias" if key in self._alias_index else ("iata" if key in self._code_index else "name")
                    results.append({
                        "city": c["city"],
                        "code": c["code"],
                        "confidence": 1.0 if method == "name" else 0.95,
                        "method": method,
                        "position": pos,
                    })

        return sorted(results, key=lambda x: x["position"])

    def extract_route(self, message: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract departure and arrival cities from a message.

        Uses "from X to Y" pattern first, then falls back to positional extraction.
        Returns (departure_city, arrival_city) as canonical city names.
        """
        msg_lower = message.lower()

        # Pattern: "from X to Y"
        route_match = re.search(r'from\s+(.+?)\s+to\s+(.+?)(?:\s+(?:tomorrow|today|on|for|in|by|$)|[.,!?]|$)', msg_lower)
        if route_match:
            dep_raw = route_match.group(1).strip()
            arr_raw = route_match.group(2).strip()

            dep = self.retrieve(dep_raw)
            arr = self.retrieve(arr_raw)

            if dep and arr:
                return dep["city"], arr["city"]
            elif dep and not arr:
                # Try extracting arrival city from the raw text
                arr_cities = self.extract_cities(arr_raw)
                if arr_cities:
                    return dep["city"], arr_cities[0]["city"]
                # Try word-by-word match for misspellings
                for word in arr_raw.split():
                    r = self.retrieve(word)
                    if r:
                        return dep["city"], r["city"]
                return dep["city"], None
            elif arr and not dep:
                return None, arr["city"]

        # No "from X to Y" — extract all cities positionally
        cities = self.extract_cities(message)
        if len(cities) >= 2:
            return cities[0]["city"], cities[1]["city"]
        elif len(cities) == 1:
            return cities[0]["city"], None

        return None, None


# Singleton instance
city_retriever = CityRetriever()
