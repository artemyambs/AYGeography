from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WaterRegion:
    key: str
    name: str
    kind: str
    longitude: float
    latitude: float
    radius_x: float
    radius_y: float


WATER_REGIONS = [
    WaterRegion("atlantic", "Атлантический океан", "Океан", -35, 5, 28, 38),
    WaterRegion("pacific_w", "Тихий океан", "Океан", 165, 0, 30, 38),
    WaterRegion("pacific_e", "Тихий океан", "Океан", -135, 0, 30, 38),
    WaterRegion("indian", "Индийский океан", "Океан", 80, -25, 27, 25),
    WaterRegion("arctic", "Северный Ледовитый океан", "Океан", 20, 76, 60, 11),
    WaterRegion("southern", "Южный океан", "Океан", 20, -67, 100, 10),
    WaterRegion("mediterranean", "Средиземное море", "Море", 18, 36, 13, 4),
    WaterRegion("black", "Чёрное море", "Море", 34, 43, 5, 3),
    WaterRegion("baltic", "Балтийское море", "Море", 19, 58, 4, 4),
    WaterRegion("red", "Красное море", "Море", 39, 21, 3, 8),
    WaterRegion("arabian", "Аравийское море", "Море", 64, 15, 10, 8),
    WaterRegion("caribbean", "Карибское море", "Море", -75, 16, 11, 6),
    WaterRegion("bering", "Берингово море", "Море", -175, 58, 8, 7),
    WaterRegion("north", "Северное море", "Море", 3, 56, 4, 4),
    WaterRegion("japan", "Японское море", "Море", 135, 40, 4, 6),
    WaterRegion("okhotsk", "Охотское море", "Море", 150, 53, 8, 7),
    WaterRegion("south_china", "Южно-Китайское море", "Море", 114, 13, 8, 9),
    WaterRegion("coral", "Коралловое море", "Море", 155, -20, 9, 10),
    WaterRegion("adriatic", "Адриатическое море", "Море", 15, 43, 2.5, 4),
    WaterRegion("aegean", "Эгейское море", "Море", 25, 38, 3, 3),
    WaterRegion("azov", "Азовское море", "Море", 37, 46, 2, 1.5),
    WaterRegion("barents", "Баренцево море", "Море", 40, 74, 15, 7),
    WaterRegion("beaufort", "Море Бофорта", "Море", -140, 73, 12, 7),
    WaterRegion("chukchi", "Чукотское море", "Море", -170, 69, 9, 6),
    WaterRegion("east_siberian", "Восточно-Сибирское море", "Море", 155, 72, 14, 6),
    WaterRegion("laptev", "Море Лаптевых", "Море", 120, 76, 12, 6),
    WaterRegion("kara", "Карское море", "Море", 75, 73, 13, 7),
    WaterRegion("norwegian", "Норвежское море", "Море", 3, 67, 9, 8),
    WaterRegion("greenland", "Гренландское море", "Море", -5, 75, 10, 6),
    WaterRegion("labrador", "Море Лабрадор", "Море", -55, 58, 9, 8),
    WaterRegion("sargasso", "Саргассово море", "Море", -55, 28, 14, 11),
    WaterRegion("scotia", "Море Скоша", "Море", -40, -57, 12, 7),
    WaterRegion("weddell", "Море Уэдделла", "Море", -40, -70, 18, 7),
    WaterRegion("ross", "Море Росса", "Море", 175, -72, 13, 7),
    WaterRegion("tasman", "Тасманово море", "Море", 155, -40, 12, 11),
    WaterRegion("timor", "Тиморское море", "Море", 126, -11, 6, 4),
    WaterRegion("arafura", "Арафурское море", "Море", 135, -9, 7, 4),
    WaterRegion("java", "Яванское море", "Море", 112, -5, 6, 3),
    WaterRegion("banda", "Море Банда", "Море", 128, -5, 5, 4),
    WaterRegion("celebes", "Море Сулавеси", "Море", 123, 3, 5, 5),
    WaterRegion("sulu", "Море Сулу", "Море", 120, 9, 4, 4),
    WaterRegion("philippine", "Филиппинское море", "Море", 132, 22, 10, 12),
    WaterRegion("yellow", "Жёлтое море", "Море", 124, 35, 4, 4),
    WaterRegion("east_china", "Восточно-Китайское море", "Море", 126, 29, 5, 5),
    WaterRegion("andaman", "Андаманское море", "Море", 95, 10, 5, 7),
    WaterRegion("irish", "Ирландское море", "Море", -5, 54, 2, 2.5),
    WaterRegion("marmara", "Мраморное море", "Море", 28, 41, 1.5, 1),
    WaterRegion("ionian", "Ионическое море", "Море", 19, 37, 4, 4),
    WaterRegion("ligurian", "Лигурийское море", "Море", 9, 43, 2, 2),
    WaterRegion("tyrrhenian", "Тирренское море", "Море", 12, 39, 4, 4),
]
