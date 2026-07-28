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
            "npk": {"n": 60.0, "p": 35.0, "k": 45.0}
        },
        "tolerable": {
            "temp_min": 15.0,
            "temp_max": 32.0,
            "soil_humidity_min": 65.0,
            "soil_humidity_max": 85.0,
            "npk": {"n_min": 40.0, "p_min": 20.0, "k_min": 30.0}
        },
        "npk_decay_per_15min": {"n": 0.15, "p": 0.06, "k": 0.14},
        "npk_fertilizer_boost": {"n": 15.0, "p": 8.0, "k": 10.0},
        "npk_max": {"n": 90.0, "p": 50.0, "k": 65.0}
    },
    "cai_thia": {
        "label": "Cải thìa",
        "optimal": {
            "temp_min": 20.0,
            "temp_max": 30.0,
            "soil_humidity_min": 70.0,
            "soil_humidity_max": 80.0,
            "npk": {"n": 50.0, "p": 30.0, "k": 40.0}
        },
        "tolerable": {
            "temp_min": 15.0,
            "temp_max": 35.0,
            "soil_humidity_min": 60.0,
            "soil_humidity_max": 85.0,
            "npk": {"n_min": 35.0, "p_min": 20.0, "k_min": 25.0}
        },
        "npk_decay_per_15min": {"n": 0.1, "p": 0.04, "k": 0.08},
        "npk_fertilizer_boost": {"n": 12.0, "p": 6.0, "k": 8.0},
        "npk_max": {"n": 80.0, "p": 45.0, "k": 60.0}
    },
    "cai_ngot": {
        "label": "Cải ngọt",
        "optimal": {
            "temp_min": 20.0,
            "temp_max": 30.0,
            "soil_humidity_min": 70.0,
            "soil_humidity_max": 80.0,
            "npk": {"n": 55.0, "p": 32.0, "k": 42.0}
        },
        "tolerable": {
            "temp_min": 15.0,
            "temp_max": 35.0,
            "soil_humidity_min": 60.0,
            "soil_humidity_max": 85.0,
            "npk": {"n_min": 38.0, "p_min": 22.0, "k_min": 28.0}
        },
        "npk_decay_per_15min": {"n": 0.11, "p": 0.05, "k": 0.09},
        "npk_fertilizer_boost": {"n": 13.0, "p": 7.0, "k": 9.0},
        "npk_max": {"n": 85.0, "p": 48.0, "k": 62.0}
    },
    "rau_muong": {
        "label": "Rau muống",
        "optimal": {
            "temp_min": 25.0,
            "temp_max": 30.0,
            "soil_humidity_min": 75.0,
            "soil_humidity_max": 90.0,
            "npk": {"n": 77.5, "p": 12.9, "k": 8.6}
        },
        "tolerable": {
            "temp_min": 20.0,
            "temp_max": 38.0,
            "soil_humidity_min": 65.0,
            "soil_humidity_max": 95.0,
            "npk": {"n_min": 60.0, "p_min": 10.0, "k_min": 6.5}
        },
        "npk_decay_per_15min": {"n": 0.2, "p": 0.03, "k": 0.02},
        "npk_fertilizer_boost": {"n": 20.0, "p": 3.0, "k": 2.5},
        "npk_max": {"n": 95.0, "p": 16.0, "k": 11.0}
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
