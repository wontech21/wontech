"""
Merchant name normalization for bank statement transaction descriptions.
Maps raw merchant strings to standardized names.
"""

import re


def get_merchant_normalization_map():
    """Return a dictionary mapping merchant name patterns to standardized names."""
    return {
        # Grocery Stores
        'MARKET BASKET': 'Market Basket',
        'WHOLE FOODS': 'Whole Foods Market',
        'TRADER JOE': "Trader Joe's",
        'TRADER JOES': "Trader Joe's",
        'STOP SHOP': 'Stop & Shop',
        'STOP & SHOP': 'Stop & Shop',
        'SHAWS': "Shaw's",
        'STAR MARKET': 'Star Market',
        'WEGMANS': 'Wegmans',
        'PUBLIX': 'Publix',
        'KROGER': 'Kroger',
        'SAFEWAY': 'Safeway',
        'ALBERTSONS': 'Albertsons',
        'FOOD LION': 'Food Lion',
        'GIANT FOOD': 'Giant Food',
        'GIANT EAGLE': 'Giant Eagle',
        'HANNAFORD': 'Hannaford',
        'PRICE CHOPPER': 'Price Chopper',
        'BIG Y': 'Big Y',
        'ALDI': 'ALDI',
        'LIDL': 'Lidl',
        'COSTCO': 'Costco Wholesale',
        "SAM'S CLUB": "Sam's Club",
        'SAMS CLUB': "Sam's Club",
        "BJ'S": "BJ's Wholesale Club",
        'BJS': "BJ's Wholesale Club",
        'TARGET': 'Target',
        'WALMART': 'Walmart',
        'WAL MART': 'Walmart',
        'WAL-MART': 'Walmart',

        # Restaurant/Food Service
        'RESTAURANT DEPOT': 'Restaurant Depot',
        'SYSCO': 'Sysco',
        'US FOODS': 'US Foods',
        'MCDONALD': "McDonald's",
        'MCDONALDS': "McDonald's",
        'BURGER KING': 'Burger King',
        "WENDY'S": "Wendy's",
        'WENDYS': "Wendy's",
        'SUBWAY': 'Subway',
        'DUNKIN': "Dunkin'",
        'DUNKIN DONUTS': "Dunkin'",
        'STARBUCKS': 'Starbucks',
        'CHIPOTLE': 'Chipotle',
        'PANERA': 'Panera Bread',
        'PANERA BREAD': 'Panera Bread',

        # Hardware/Home Improvement
        'HOME DEPOT': 'The Home Depot',
        'HOMEDEPOT': 'The Home Depot',
        'LOWES': "Lowe's",
        "LOWE'S": "Lowe's",
        'ACE HARDWARE': 'Ace Hardware',
        'TRUE VALUE': 'True Value',
        'MENARDS': 'Menards',
        'HARBOR FREIGHT': 'Harbor Freight Tools',

        # Discount/Dollar Stores
        'DOLLAR TREE': 'Dollar Tree',
        'DOLLAR GENERAL': 'Dollar General',
        'FAMILY DOLLAR': 'Family Dollar',
        '99 CENT': '99 Cents Only',
        'FIVE BELOW': 'Five Below',

        # Office Supplies
        'STAPLES': 'Staples',
        'OFFICE DEPOT': 'Office Depot',
        'OFFICEDEPOT': 'Office Depot',
        'OFFICE MAX': 'OfficeMax',
        'OFFICEMAX': 'OfficeMax',

        # Gas Stations/Fuel
        'SHELL': 'Shell',
        'SHELL OIL': 'Shell',
        'EXXON': 'Exxon',
        'MOBIL': 'Mobil',
        'EXXONMOBIL': 'ExxonMobil',
        'CHEVRON': 'Chevron',
        'BP': 'BP',
        'GULF': 'Gulf',
        'GULF OIL': 'Gulf',
        'SUNOCO': 'Sunoco',
        'CITGO': 'Citgo',
        'VALERO': 'Valero',
        'SPEEDWAY': 'Speedway',
        '7-ELEVEN': '7-Eleven',
        '7 ELEVEN': '7-Eleven',
        'CIRCLE K': 'Circle K',

        # Pharmacies
        'CVS': 'CVS Pharmacy',
        'WALGREENS': 'Walgreens',
        'WALGREEN': 'Walgreens',
        'RITE AID': 'Rite Aid',
        'RITE-AID': 'Rite Aid',
        'DUANE READE': 'Duane Reade',

        # Auto Parts/Service
        'AUTOZONE': 'AutoZone',
        'AUTO ZONE': 'AutoZone',
        'ADVANCE AUTO': 'Advance Auto Parts',
        'ADVANCE AUTO PARTS': 'Advance Auto Parts',
        "O'REILLY": "O'Reilly Auto Parts",
        'OREILLY': "O'Reilly Auto Parts",
        'NAPA': 'NAPA Auto Parts',
        'NAPA AUTO': 'NAPA Auto Parts',
        'PEP BOYS': 'Pep Boys',
        'JIFFY LUBE': 'Jiffy Lube',
        'VALVOLINE': 'Valvoline Instant Oil Change',
        'FIRESTONE': 'Firestone Complete Auto Care',
        'GOODYEAR': 'Goodyear Auto Service',
        'MIDAS': 'Midas',
        'MEINEKE': 'Meineke Car Care',
        'MAACO': 'MAACO',

        # Uniforms/Apparel
        'UNIFIRST': 'UniFirst',
        'UNI FIRST': 'UniFirst',
        'CINTAS': 'Cintas',

        # Payment Types
        'PAYROLL': 'Payroll',
        'ACH': 'ACH Transfer',
        'WIRE TRANSFER': 'Wire Transfer',
        'ATM WITHDRAWAL': 'ATM Withdrawal',
        'CHECK': 'Check',
    }


def normalize_merchant_name(description):
    """Normalize merchant name using known patterns and locations."""
    merchant_map = get_merchant_normalization_map()
    desc_upper = description.upper()

    # Remove common location indicators (city names, state abbreviations)
    location_pattern = r'\s+[A-Z]{2,}(\s+[A-Z]{2})?$'
    desc_no_location = re.sub(location_pattern, '', desc_upper).strip()

    # Try to match against known merchants
    for merchant_key, merchant_name in merchant_map.items():
        if merchant_key in desc_no_location:
            return merchant_name

    # If no match found, do basic title casing
    words = description.split()
    cleaned_words = []
    for word in words:
        if len(word) == 2 and word.isupper():
            continue
        cleaned_words.append(word.title())

    return ' '.join(cleaned_words) if cleaned_words else description


def clean_merchant_description(description):
    """Clean up merchant description to extract just the merchant name.

    Removes common noise patterns like POS, TERMINAL, card numbers, transaction IDs.
    """
    desc_upper = description.upper()

    # Handle "MERCHANT PURCHASE TERMINAL" pattern
    if "MERCHANT PURCHASE TERMINAL" in desc_upper:
        match = re.search(r'MERCHANT\s+PURCHASE\s+TERMINAL', desc_upper)
        if match:
            after_terminal = description[match.end():].strip()
            cleaned = re.sub(r'^[\d\s\-\.]+', '', after_terminal).strip()
            capital_words = re.findall(r'\b[A-Z][A-Z\s]+\b', cleaned)
            if capital_words:
                result = ' '.join(capital_words)
                result = re.sub(r'\s+', ' ', result).strip()
                return normalize_merchant_name(result)

    # Remove common noise patterns from description
    cleaned = description
    noise_patterns = [
        r'\bPOS\b', r'\bPOSAP\b', r'\bPURCHASE\b', r'\bTERMINAL\b',
        r'\bDEBIT\s*CARD\b', r'\bCREDIT\s*CARD\b', r'\bMERCHANT\b',
        r'\bDEBITPOSAP\b', r'\bDBCRDPURAP\b', r'\bDBCRDPMTAP\b',
    ]
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    # Remove masked card numbers
    cleaned = re.sub(r'\*{3,}\d+', '', cleaned)
    cleaned = re.sub(r'[xX]{4,}\d*', '', cleaned)

    # Remove transaction codes (mixed letters/numbers)
    cleaned = re.sub(r'\b[A-Z]*\d{6,}[A-Z]*\d*[A-Z]*\b', '', cleaned)
    cleaned = re.sub(r'\b\d{6,}\b', '', cleaned)

    # Clean up
    cleaned = re.sub(r',+', ',', cleaned)
    cleaned = cleaned.strip(',').strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)

    if not cleaned or len(cleaned.strip()) < 3:
        return normalize_merchant_name(description)

    return normalize_merchant_name(cleaned)


def normalize_transaction_name(text):
    """Extract and normalize transaction names by extracting ALL capital letter sequences."""
    if not isinstance(text, str):
        return str(text)

    capital_words = re.findall(r'\b[A-Z][A-Z]+\b', text)
    if capital_words:
        return ' '.join(capital_words)

    return text.strip()
