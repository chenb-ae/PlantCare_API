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
            "npk": {"n": 7500.0, "p": 3000.0, "k": 7000.0}
        },
        "tolerable": {
            "temp_min": 15.0,
            "temp_max": 32.0,
            "soil_humidity_min": 65.0,
            "soil_humidity_max": 85.0,
            "npk": {"n_min": 6000.0, "p_min": 2400.0, "k_min": 5600.0}
        },
        "npk_decay_per_15min": {"n": 15.0, "p": 6.0, "k": 14.0},
        "npk_fertilizer_boost": {"n": 1000.0, "p": 400.0, "k": 900.0},
        "npk_max": {"n": 8000.0, "p": 3200.0, "k": 7500.0}
    },
    "cai_thia": {
        "label": "Cải thìa",
        "optimal": {
            "temp_min": 20.0,
            "temp_max": 30.0,
            "soil_humidity_min": 70.0,
            "soil_humidity_max": 80.0,
            "npk": {"n": 3000.0, "p": 1200.0, "k": 2760.0}
        },
        "tolerable": {
            "temp_min": 15.0,
            "temp_max": 35.0,
            "soil_humidity_min": 60.0,
            "soil_humidity_max": 85.0,
            "npk": {"n_min": 2400.0, "p_min": 960.0, "k_min": 2200.0}
        },
        "npk_decay_per_15min": {"n": 6.0, "p": 2.4, "k": 5.5},
        "npk_fertilizer_boost": {"n": 500.0, "p": 200.0, "k": 460.0},
        "npk_max": {"n": 3500.0, "p": 1400.0, "k": 3200.0}
    },
    "cai_ngot": {
        "label": "Cải ngọt",
        "optimal": {
            "temp_min": 20.0,
            "temp_max": 30.0,
            "soil_humidity_min": 70.0,
            "soil_humidity_max": 80.0,
            "npk": {"n": 3000.0, "p": 1200.0, "k": 2760.0}
        },
        "tolerable": {
            "temp_min": 15.0,
            "temp_max": 35.0,
            "soil_humidity_min": 60.0,
            "soil_humidity_max": 85.0,
            "npk": {"n_min": 2400.0, "p_min": 960.0, "k_min": 2200.0}
        },
        "npk_decay_per_15min": {"n": 6.0, "p": 2.4, "k": 5.5},
        "npk_fertilizer_boost": {"n": 500.0, "p": 200.0, "k": 460.0},
        "npk_max": {"n": 3500.0, "p": 1400.0, "k": 3200.0}
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
    "pest_control",
    "harvesting"
]

PLANT_TYPES = list(PLANT_PROFILES.keys())

PLACEMENTS = ["outdoor", "shaded"]
