# Cấu hình thông số sinh học các loại cây trồng
# Dựa trên BÁO CÁO KỸ THUẬT: THÔNG SỐ NGƯỠNG TỐI ƯU TRONG CANH TÁC RAU ĂN LÁ QUY MÔ ĐÔ THỊ

PLANT_PROFILES = {
    "xa_lach": {
        "label": "Xà lách",
        "optimal": {
            "temp_min": 18.0,
            "temp_max": 25.0,
            "soil_humidity_min": 70.0,
            "soil_humidity_max": 80.0,
            "npk": {"n": 75.0, "p": 45.0, "k": 120.0}
        },
        "tolerable": {
            "temp_min": 12.0,
            "temp_max": 38.0,
            "soil_humidity_min": 40.0,
            "soil_humidity_max": 95.0,
            "npk": {"n_min": 25.0, "p_min": 15.0, "k_min": 40.0}
        },
        "npk_decay_per_15min": {"n": 0.25, "p": 0.15, "k": 0.35},
        "npk_fertilizer_boost": {"n": 15.0, "p": 10.0, "k": 20.0},
        "npk_max": {"n": 250.0, "p": 200.0, "k": 300.0}
    },
    "cai_thia": {
        "label": "Cải thìa",
        "optimal": {
            "temp_min": 20.0,
            "temp_max": 30.0,
            "soil_humidity_min": 70.0,
            "soil_humidity_max": 80.0,
            "npk": {"n": 80.0, "p": 50.0, "k": 130.0}
        },
        "tolerable": {
            "temp_min": 12.0,
            "temp_max": 40.0,
            "soil_humidity_min": 40.0,
            "soil_humidity_max": 95.0,
            "npk": {"n_min": 25.0, "p_min": 15.0, "k_min": 40.0}
        },
        "npk_decay_per_15min": {"n": 0.25, "p": 0.15, "k": 0.35},
        "npk_fertilizer_boost": {"n": 15.0, "p": 10.0, "k": 20.0},
        "npk_max": {"n": 250.0, "p": 200.0, "k": 300.0}
    },
    "cai_ngot": {
        "label": "Cải ngọt",
        "optimal": {
            "temp_min": 20.0,
            "temp_max": 30.0,
            "soil_humidity_min": 70.0,
            "soil_humidity_max": 80.0,
            "npk": {"n": 85.0, "p": 52.0, "k": 140.0}
        },
        "tolerable": {
            "temp_min": 12.0,
            "temp_max": 40.0,
            "soil_humidity_min": 40.0,
            "soil_humidity_max": 95.0,
            "npk": {"n_min": 25.0, "p_min": 15.0, "k_min": 40.0}
        },
        "npk_decay_per_15min": {"n": 0.25, "p": 0.15, "k": 0.35},
        "npk_fertilizer_boost": {"n": 15.0, "p": 10.0, "k": 20.0},
        "npk_max": {"n": 250.0, "p": 200.0, "k": 300.0}
    },
    "rau_muong": {
        "label": "Rau muống",
        "optimal": {
            "temp_min": 25.0,
            "temp_max": 30.0,
            "soil_humidity_min": 75.0,
            "soil_humidity_max": 90.0,
            "npk": {"n": 95.0, "p": 60.0, "k": 160.0}
        },
        "tolerable": {
            "temp_min": 15.0,
            "temp_max": 42.0,
            "soil_humidity_min": 45.0,
            "soil_humidity_max": 98.0,
            "npk": {"n_min": 30.0, "p_min": 18.0, "k_min": 50.0}
        },
        "npk_decay_per_15min": {"n": 0.30, "p": 0.18, "k": 0.40},
        "npk_fertilizer_boost": {"n": 15.0, "p": 10.0, "k": 20.0},
        "npk_max": {"n": 300.0, "p": 250.0, "k": 350.0}
    }
}

LOG_ACTIONS = [
    "watering",
    "fertilizing",
    "shade_covering",
    "sun_exposure",
    "harvesting"
]

PLANT_TYPES = list(PLANT_PROFILES.keys())

PLACEMENTS = ["outdoor", "shaded"]
