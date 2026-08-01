# Single source of truth for all locations.

GLOBAL_LOCATIONS = [

    # Europe
    {"City": "Paris",           "Country": "FR", "Lat": 48.8566,  "Lon":   2.3522},
    {"City": "Berlin",          "Country": "DE", "Lat": 52.5200,  "Lon":  13.4050},
    {"City": "Warsaw",          "Country": "PL", "Lat": 52.2297,  "Lon":  21.0122},
    {"City": "Kyiv",            "Country": "UA", "Lat": 50.4501,  "Lon":  30.5234},
    {"City": "Budapest",        "Country": "HU", "Lat": 47.4979,  "Lon":  19.0402},
    {"City": "Bucharest",       "Country": "RO", "Lat": 44.4268,  "Lon":  26.1025},
    {"City": "Helsinki",        "Country": "FI", "Lat": 60.1695,  "Lon":  24.9355},
    {"City": "Stockholm",       "Country": "SE", "Lat": 59.3293,  "Lon":  18.0686},
    {"City": "Oslo",            "Country": "NO", "Lat": 59.9139,  "Lon":  10.7522},
    {"City": "Copenhagen",      "Country": "DK", "Lat": 55.6761,  "Lon":  12.5683},
    {"City": "Vienna",          "Country": "AT", "Lat": 48.2082,  "Lon":  16.3738},
    {"City": "Prague",          "Country": "CZ", "Lat": 50.0755,  "Lon":  14.4378},
    {"City": "Rome",            "Country": "IT", "Lat": 41.9028,  "Lon":  12.4964},
    {"City": "Madrid",          "Country": "ES", "Lat": 40.4168,  "Lon":  -3.7038},

    # Africa
    {"City": "Nairobi",         "Country": "KE", "Lat":  -1.2921, "Lon":  36.8219},
    {"City": "Kampala",         "Country": "UG", "Lat":   0.3476, "Lon":  32.5825},
    {"City": "Accra",           "Country": "GH", "Lat":   5.6037, "Lon":  -0.1870},
    {"City": "Lagos",           "Country": "NG", "Lat":   6.5244, "Lon":   3.3792},
    {"City": "Addis Ababa",     "Country": "ET", "Lat":   9.0320, "Lon":  38.7469},
    {"City": "Dar es Salaam",   "Country": "TZ", "Lat":  -6.7924, "Lon":  39.2083},
    {"City": "Lusaka",          "Country": "ZM", "Lat": -15.4167, "Lon":  28.2833},
    {"City": "Harare",          "Country": "ZW", "Lat": -17.8252, "Lon":  31.0335},
    {"City": "Cairo",           "Country": "EG", "Lat":  30.0444, "Lon":  31.2357},
    {"City": "Casablanca",      "Country": "MA", "Lat":  33.5731, "Lon":  -7.5898},

    # Asia
    {"City": "Delhi",           "Country": "IN", "Lat":  28.6139, "Lon":  77.2090},
    {"City": "Dhaka",           "Country": "BD", "Lat":  23.8103, "Lon":  90.4125},
    {"City": "Hanoi",           "Country": "VN", "Lat":  21.0285, "Lon": 105.8542},
    {"City": "Bangkok",         "Country": "TH", "Lat":  13.7563, "Lon": 100.5018},
    {"City": "Islamabad",       "Country": "PK", "Lat":  33.6844, "Lon":  73.0479},
    {"City": "Tashkent",        "Country": "UZ", "Lat":  41.2995, "Lon":  69.2401},
    {"City": "Almaty",          "Country": "KZ", "Lat":  43.2220, "Lon":  76.8512},
    {"City": "Tokyo",           "Country": "JP", "Lat":  35.6762, "Lon": 139.6503},
    {"City": "Chengdu",         "Country": "CN", "Lat":  30.5728, "Lon": 104.0668},
    {"City": "Manila",          "Country": "PH", "Lat":  14.5995, "Lon": 120.9842},
    {"City": "Seoul",           "Country": "KR", "Lat":  37.5665, "Lon": 126.9780},

    # South America
    {"City": "Sao Paulo",       "Country": "BR", "Lat": -23.5505, "Lon": -46.6333},
    {"City": "Buenos Aires",    "Country": "AR", "Lat": -34.6037, "Lon": -58.3816},
    {"City": "Lima",            "Country": "PE", "Lat": -12.0464, "Lon": -77.0428},
    {"City": "Bogota",          "Country": "CO", "Lat":   4.7110, "Lon": -74.0721},
    {"City": "Santiago",        "Country": "CL", "Lat": -33.4489, "Lon": -70.6693},
    {"City": "Asuncion",        "Country": "PY", "Lat": -25.2867, "Lon": -57.6470},

    #  North America
    {"City": "Mexico City",     "Country": "MX", "Lat":  19.4326, "Lon": -99.1332},
    {"City": "Guadalajara",     "Country": "MX", "Lat":  20.6597, "Lon":-103.3496},
    {"City": "Des Moines",      "Country": "US", "Lat":  41.5868, "Lon": -93.6250},
    {"City": "Kansas City",     "Country": "US", "Lat":  39.0997, "Lon": -94.5786},
    {"City": "Fresno",          "Country": "US", "Lat":  36.7378, "Lon":-119.7871},
    {"City": "Winnipeg",        "Country": "CA", "Lat":  49.8951, "Lon": -97.1384},
    {"City": "Sacramento",      "Country": "US", "Lat":  38.5816, "Lon":-121.4944},

    # Oceania
    {"City": "Sydney",          "Country": "AU", "Lat": -33.8688, "Lon": 151.2093},
    {"City": "Perth",           "Country": "AU", "Lat": -31.9505, "Lon": 115.8605},
    {"City": "Auckland",        "Country": "NZ", "Lat": -36.8485, "Lon": 174.7633},

    # Middle East
    {"City": "Ankara",          "Country": "TR", "Lat":  39.9334, "Lon":  32.8597},
    {"City": "Tehran",          "Country": "IR", "Lat":  35.6892, "Lon":  51.3890},
    {"City": "Amman",           "Country": "JO", "Lat":  31.9454, "Lon":  35.9284},
]
