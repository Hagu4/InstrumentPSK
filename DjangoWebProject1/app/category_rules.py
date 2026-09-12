"""Initial rules for the 24 qualifying second-level catalog categories.

Keys are existing parent slugs, including the distinct hand/electric general
construction categories. Leaf slugs are local to a parent. Uncertain products
remain at that parent for review; there is no match-everything fallback.
"""

from .category_classification import LeafRule, ParentRule


MACHINE_ACCESSORIES = (
    "масло", "масла", "масел", "маслом", "цепь", "цепи", "цепей",
    "леск*", "диск", "диска", "диски", "дисков", "диском", "чехол", "чехлы",
    "чехла", "запчаст*", "запасная часть", "запасные части", "полотно для",
    "полотна для", "шина для", "шины для", "насадк*", "нож для", "ножи для",
)
BATTERY_ACCESSORIES = (
    "аккумулятор", "аккумуляторы", "аккумулятора", "аккумуляторов",
    "аккумуляторная батарея", "зарядное устройство", "зарядные устройства",
)
CART_ACCESSORIES = (
    "колес*", "камера", "камеры", "шина", "шины", "ручки для", "рукоятки для",
)


def _machine(slug, name, terms, *, exclude=(), priority=0):
    return LeafRule(slug, name, terms, exclude=MACHINE_ACCESSORIES + exclude, priority=priority)


_PARENTS = (
    ParentRule("instrument-dlya-razmetki", (
        LeafRule("pencils-markers", "Карандаши и маркеры", ("карандаш*", "маркер*")),
        LeafRule("cords-powders", "Шнуры и красящие порошки", ("шнур*", "порош*", "красящий мел")),
        LeafRule("punches-scribers", "Кернеры и чертилки", ("керн*", "чертил*")),
    )),
    ParentRule("malyarnyy-instrument", (
        LeafRule("brushes", "Кисти", ("кисть", "кисти", "кисточка", "макловиц*")),
        LeafRule("rollers", "Валики", ("валик*", "ролик малярный")),
        LeafRule("spatulas-scrapers", "Шпатели и скребки", ("шпател*", "скреб*")),
    )),
    ParentRule("obshchestroitelnyy-instrument", (
        LeafRule("installation", "Монтажный", ("монтажный", "заклепочник*", "степлер*", "пистолет*", "гвоздодер*", "лом", "монтировк*")),
        LeafRule("measurement-marking", "Измерительно-разметочный", ("рулетк*", "уровень", "угольник*", "линейк*", "отвес*", "разметочный")),
        LeafRule("auxiliary", "Вспомогательный", ("нож", "ножи", "лезви*", "ножниц*", "ведро", "ведра", "присоск*", "щетк*")),
    )),
    ParentRule("slesarno-stolyarnyy-instrument", (
        LeafRule("wrenches", "Ключи", ("ключ", "ключи", "ключей")),
        LeafRule("screwdrivers-bits", "Отвёртки и биты", ("отвертк*", "бита", "биты", "бит", "битодержател*")),
        LeafRule("hammers", "Молотки", ("молоток", "молотк*", "киянк*", "кувалд*")),
        LeafRule("pliers-cutters", "Плоскогубцы и кусачки", ("плоскогуб*", "пассатиж*", "кусач*", "бокорез*", "круглогуб*", "тонкогуб*", "длинногуб*")),
        LeafRule("clamps", "Струбцины", ("струбцин*",)),
        LeafRule("saws-files", "Пилы и напильники", ("пила", "пилы", "ножовк*", "напильник*", "надфил*", "рашпил*")),
    )),
    ParentRule("shtukaturno-otdelochnyy-instrument", (
        LeafRule("trowels", "Кельмы и гладилки", ("кельм*", "гладил*", "мастерок", "мастерк*")),
        LeafRule("spatulas", "Шпатели", ("шпател*",)),
        LeafRule("floats", "Тёрки", ("терка", "терки", "терок", "полутер*")),
        LeafRule("rules", "Правила", ("правило", "правила", "правилом")),
    )),
    ParentRule("niveliry-lazernye-i-postroiteli-ploskostey", (
        LeafRule("laser-levels", "Лазерные нивелиры", ("нивелир*", "лазерный уровень"), exclude=("построител*", "штатив*", "рейка", "держател*", "креплен*", "приемник*", "очки")),
        LeafRule("plane-builders", "Построители плоскостей", ("построител*",), exclude=("штатив*", "рейка", "держател*", "креплен*", "приемник*", "очки")),
        LeafRule("accessories", "Принадлежности", ("штатив*", "рейка", "держател*", "креплен*", "приемник*", "очки", "мишен*")),
    )),
    ParentRule("ruletki-mernye-lenty", (
        LeafRule("tape-measures", "Рулетки", ("рулетк*",), exclude=("геодезический", "мерная лента")),
        LeafRule("measuring-tapes", "Мерные ленты", ("мерная лента", "измерительная лента", "мерные ленты"), exclude=("геодезический",)),
        LeafRule("geodesic", "Геодезические рулетки", ("геодезический",)),
    )),
    ParentRule("urovni", (
        LeafRule("bubble", "Пузырьковые", ("пузырьковый", "уровень", "уровни"), exclude=("электронный", "цифровой", "магнитный")),
        LeafRule("electronic", "Электронные", ("электронный", "цифровой")),
        LeafRule("magnetic", "Магнитные", ("магнитный",), exclude=("электронный", "цифровой")),
    )),
    ParentRule("vozduhoduvki-i-opryskivateli-benzinovye", (
        _machine("blowers", "Воздуходувки", ("воздуходув*", "садовый пылесос")),
        _machine("sprayers", "Опрыскиватели", ("опрыскивател*", "мотоопрыскивател*")),
    )),
    ParentRule("gazonokosilki-motokosy-i-trimmery", (
        _machine("lawnmowers", "Газонокосилки", ("газонокосил*",)),
        _machine("brushcutters", "Мотокосы", ("мотокос*", "бензокос*")),
        _machine("trimmers", "Триммеры", ("триммер*", "электрокос*")),
    )),
    ParentRule("motonozhnitsy-elektronozhnitsy-kustorezy-vysotorezy", (
        _machine("hedge-trimmers", "Кусторезы", ("кусторез*",)),
        _machine("pole-saws", "Высоторезы", ("высоторез*",)),
        _machine("garden-shears", "Садовые ножницы", ("ножниц*", "мотоножниц*", "электроножниц*")),
    )),
    ParentRule("benzopily-i-pily-tsepnye-elektricheskie", (
        _machine("battery", "Аккумуляторные", ("аккумуляторный", "аккум")),
        _machine("petrol", "Бензиновые", ("бензиновый", "бензопил*")),
        _machine("electric", "Электрические", ("электрический", "электропил*", "сетевой")),
    )),
    ParentRule("perchatki", (
        LeafRule("work", "Рабочие", ("рабочий", "хлопчатобумажный", "х б", "трикотажный"), exclude=("утепленный", "зимний", "морозостойкий", "защитный", "диэлектрический", "нитриловый", "латексный")),
        LeafRule("protective", "Защитные", ("защитный", "диэлектрический", "нитриловый", "латексный", "краги"), exclude=("утепленный", "зимний", "морозостойкий")),
        LeafRule("insulated", "Утеплённые", ("утепленный", "зимний", "морозостойкий")),
    )),
    ParentRule("sredstva-zashchity-golovyzreniyasluha", (
        LeafRule("helmets", "Каски", ("каска", "каски", "каскетк*")),
        LeafRule("glasses-shields", "Очки и щитки", ("очки", "щиток", "щитки", "маска сварщика")),
        LeafRule("ear-protection", "Наушники и беруши", ("наушник*", "беруш*")),
    )),
    ParentRule("sredstva-zashchity-organov-dyhaniya", (
        LeafRule("respirators", "Респираторы", ("респиратор*",), exclude=("фильтр", "фильтры", "фильтра", "картридж*")),
        LeafRule("masks", "Маски", ("маска", "маски", "полумаск*"), exclude=("респиратор*", "фильтр", "фильтры", "фильтра", "картридж*")),
        LeafRule("filters-cartridges", "Фильтры и картриджи", ("фильтр", "фильтры", "фильтра", "картридж*")),
    )),
    ParentRule("tachki-i-telezhki", (
        LeafRule("wheelbarrows", "Тачки", ("тачка", "тачки", "тачек"), exclude=CART_ACCESSORIES),
        LeafRule("platform-carts", "Платформенные тележки", ("платформенный",), exclude=CART_ACCESSORIES),
        LeafRule("cargo-carts", "Грузовые тележки", ("тележка", "тележки", "грузовой"), exclude=CART_ACCESSORIES + ("платформенный", "тачка", "тачки")),
    )),
    ParentRule("elektrostantsii", (
        _machine("petrol", "Бензиновые генераторы", ("бензиновый", "бензогенератор*"), exclude=("инверторный",)),
        _machine("diesel", "Дизельные генераторы", ("дизельный", "дизельгенератор*"), exclude=("инверторный",)),
        _machine("inverter", "Инверторные генераторы", ("инверторный",)),
    )),
    ParentRule("akkumulyatornaya-tehnika", (
        _machine("drills", "Дрели-шуруповёрты", ("дрель", "дрели", "шуруповерт*"), exclude=BATTERY_ACCESSORIES),
        _machine("impact-wrenches", "Гайковёрты", ("гайковерт*",), exclude=BATTERY_ACCESSORIES),
        _machine("saws", "Пилы", ("пила", "пилы", "лобзик*", "электропил*"), exclude=BATTERY_ACCESSORIES),
        _machine("grinders", "Шлифмашины", ("шлифмашин*", "углошлифмашин*", "ушм"), exclude=BATTERY_ACCESSORIES),
        _machine("rotary-hammers", "Перфораторы", ("перфоратор*",), exclude=BATTERY_ACCESSORIES),
        LeafRule("batteries-chargers", "Аккумуляторы и зарядные устройства", BATTERY_ACCESSORIES),
    )),
    ParentRule("derevoobrabotka", (
        _machine("planers", "Рубанки", ("рубанок", "рубанк*", "электрорубан*")),
        _machine("routers", "Фрезеры", ("фрезер", "фрезеры", "фрезерный")),
        _machine("wood-saws", "Деревообрабатывающие пилы", ("пила", "пилы", "лобзик*", "распиловочный")),
    )),
    ParentRule("metalloobrabotka", (
        _machine("metal-shears", "Ножницы по металлу", ("ножниц*", "электроножниц*")),
        _machine("threading-tools", "Резьбонарезной инструмент", ("резьбонарезной", "резьборез*", "метчик*", "плашк*", "клупп*")),
        _machine("metal-cutting-machines", "Металлорежущие машины", ("металлорежущий", "отрезной", "монтажная пила", "ленточная пила")),
    )),
    ParentRule("obrabotka-betona", (
        _machine("rotary-hammers", "Перфораторы", ("перфоратор*",)),
        _machine("demolition-hammers", "Отбойные молотки", ("отбойный", "бетонолом*")),
        _machine("diamond-drilling", "Алмазное сверление", ("алмазный", "установка сверления"), exclude=("коронка", "коронки")),
    )),
    ParentRule("obshchestroitelnyy-instrument-2109", (
        _machine("mixers", "Миксеры", ("миксер*",)),
        _machine("heat-guns", "Фены", ("фен", "фены", "термовоздуходув*")),
        _machine("guns", "Пистолеты", ("пистолет*", "краскораспылител*")),
        _machine("other-construction-tools", "Прочий строительный электроинструмент", ("гравер*", "реноватор*", "дрель", "шуруповерт*", "углошлифмашин*", "штроборез*", "окрасочный аппарат"), exclude=("миксер*",)),
    )),
    ParentRule("pilenie", (
        _machine("circular", "Дисковые", ("дисковый", "циркулярный"), exclude=("торцовочный",)),
        _machine("reciprocating", "Сабельные", ("сабельный",)),
        _machine("jigsaws", "Лобзики", ("лобзик*", "электролобзик*")),
        _machine("miter", "Торцовочные", ("торцовочный",)),
    )),
    ParentRule("shlifovanie-i-polirovka", (
        _machine("angle", "Угловые", ("угловой", "углошлифмашин*", "ушм")),
        _machine("belt", "Ленточные", ("ленточный",)),
        _machine("eccentric", "Эксцентриковые", ("эксцентриковый", "орбитальный")),
        _machine("polishing", "Полировальные", ("полировальный",)),
    )),
)

CATEGORY_RULES: dict[str, ParentRule] = {rule.parent_slug: rule for rule in _PARENTS}
