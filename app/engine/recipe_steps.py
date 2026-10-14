"""Recipe Knowledge Base: items used, quantities, and step-by-step cooking process.
Supports tri-lingual instructions: English, Tamil (தமிழ்), and Hindi (हिंदी).
"""
from __future__ import annotations

from typing import Any
from app.engine.models import Recipe, Adaptation

# Tamil ingredient name translations
INGREDIENT_NAMES_TA: dict[str, str] = {
    "poha": "அவல் (Poha)",
    "onion": "வெங்காயம் (Onion)",
    "potato": "உருளைக்கிழங்கு (Potato)",
    "peanuts": "வேர்க்கடலை (Peanuts)",
    "oil": "எண்ணெய் (Oil)",
    "mustard_seeds": "கடுகு (Mustard seeds)",
    "turmeric": "மஞ்சள் தூள் (Turmeric)",
    "salt": "உப்பு (Salt)",
    "suji": "ரவை (Suji / Rava)",
    "water": "தண்ணீர் (Water)",
    "curry_leaves": "கறிவேப்பிலை (Curry leaves)",
    "green_peas": "பச்சை பட்டாணி (Green peas)",
    "french_beans": "பீன்ஸ் (French beans)",
    "idli_batter": "இட்லி மாவு (Idli batter)",
    "toor_dal": "துவரம் பருப்பு (Toor dal)",
    "lauki": "சுரைக்காய் (Bottle gourd)",
    "tomato": "தக்காளி (Tomato)",
    "sambar_powder": "சாம்பார் பொடி (Sambar powder)",
    "dosa_batter": "தோசை மாவு (Dosa batter)",
    "atta": "கோதுமை மாவு (Wheat flour)",
    "ghee": "நெய் (Ghee)",
    "ajwain": "ஓமம் (Ajwain)",
    "curd": "தயிர் (Curd)",
    "besan": "கடலை மாவு (Besan)",
    "green_chilli": "பச்சை மிளகாய் (Green chilli)",
    "green_moong": "பச்சை பயறு (Green moong)",
    "black_pepper": "மிளகு (Black pepper)",
    "methi_leaves": "வெந்தயக் கீரை (Methi)",
    "oats": "ஓட்ஸ் (Oats)",
    "milk": "பால் (Milk)",
    "sabudana": "ஜவ்வரிசி (Sabudana)",
    "sendha_salt": "இந்துப்பு (Sendha namak)",
    "lemon": "எலுமிச்சை (Lemon)",
    "kuttu_atta": "குட்டு மாவு (Buckwheat)",
    "rajma": "ராஜ்மா (Kidney beans)",
    "garam_masala": "கரம் மசாலா (Garam masala)",
    "rice": "பச்சரிசி (Rice)",
    "kabuli_chana": "வெள்ளை கொண்டைக்கடலை (Kabuli chana)",
    "chana_masala": "சென்னா மசாலா (Chana masala)",
    "cumin": "சீரகம் (Cumin)",
    "spinach": "பாலக் கீரை (Spinach)",
    "tamarind": "புளி (Tamarind)",
    "rasam_powder": "ரசம் பொடி (Rasam powder)",
    "whole_spices": "பட்டை கிராம்பு (Whole spices)",
    "moong_dal": "பாசிப் பருப்பு (Moong dal)",
    "chana_dal": "கடலை பருப்பு (Chana dal)",
    "cauliflower": "காலிஃபிளவர் (Cauliflower)",
    "amchur": "மாங்காய் தூள் (Amchur)",
    "bhindi": "வெண்டைக்காய் (Bhindi)",
    "brinjal": "கத்தரிக்காய் (Brinjal)",
    "paneer": "பன்னீர் (Paneer)",
    "butter": "வெண்ணெய் (Butter)",
    "cream": "கிரீம் (Fresh cream)",
    "mushroom": "காளான் (Mushroom)",
    "masoor_dal": "மசூர் பருப்பு (Masoor dal)",
    "chicken": "சிக்கன் (Chicken)",
    "chicken_masala": "சிக்கன் மசாலா (Chicken masala)",
    "fish_rohu": "ரோகு மீன் (Fish)",
    "mustard_oil": "கடுகு எண்ணெய் (Mustard oil)",
    "mustard_paste": "கடுகு விழுது (Mustard paste)",
    "egg": "முட்டை (Egg)",
    "capsicum": "குடைமிளகாய் (Capsicum)",
    "pav_bhaji_masala": "பாவ் பாஜி மசாலா (Pav bhaji masala)",
    "pav": "பாவ் பன் (Pav)",
    "matki_sprouts": "முளைகட்டிய பயறு (Sprouts)",
    "misal_masala": "மிசல் மசாலா (Misal masala)",
    "jaggery": "வெல்லம் (Jaggery)",
    "jowar_atta": "சோள மாவு (Jowar flour)",
    "eno": "ஈனோ (Eno)",
    "sugar": "சர்க்கரை (Sugar)",
    "sesame_seeds": "எள்ளு (Sesame seeds)",
    "bread": "பிரட் (Bread)",
    "cucumber": "வெள்ளரிக்காய் (Cucumber)",
    "green_chutney": "புதினா சட்னி (Green chutney)",
    "maida": "மைதா (Maida)",
    "apple": "ஆப்பிள் (Apple)",
    "banana": "வாழைப்பழம் (Banana)",
    "pomegranate": "மாதுளை (Pomegranate)",
    "chaat_masala": "சாட் மசாலா (Chaat masala)",
    "makhana": "தாமரை விதை (Makhana)",
    "samak_rice": "சாமை அரிசி (Samak rice)",
    "singhara_atta": "சிங்காடா மாவு (Singhara)",
    "cardamom": "ஏலக்காய் (Cardamom)",
    "cashew": "முந்திரி (Cashew)",
}

# Hindi ingredient name translations
INGREDIENT_NAMES_HI: dict[str, str] = {
    "poha": "पोहा (Poha)",
    "onion": "प्याज (Pyaaz)",
    "potato": "आलू (Aloo)",
    "peanuts": "मूंगफली (Peanuts)",
    "oil": "तेल (Tel)",
    "mustard_seeds": "राई (Mustard seeds)",
    "turmeric": "हल्दी (Haldi)",
    "salt": "नमक (Namak)",
    "suji": "सूजी (Suji)",
    "water": "पानी (Paani)",
    "curry_leaves": "कढ़ी पत्ता (Curry leaves)",
    "green_peas": "मटर (Green peas)",
    "french_beans": "बीन्स (Beans)",
    "idli_batter": "इडली बैटर (Idli batter)",
    "toor_dal": "अरहर / तूर दाल (Toor dal)",
    "lauki": "लौकी (Lauki)",
    "tomato": "टमाटर (Tamatar)",
    "sambar_powder": "सांबर मसाला (Sambar powder)",
    "dosa_batter": "डोसा बैटर (Dosa batter)",
    "atta": "गेहूं का आटा (Atta)",
    "ghee": "घी (Ghee)",
    "ajwain": "अजवाइन (Ajwain)",
    "curd": "दही (Dahi)",
    "besan": "बेसन (Besan)",
    "green_chilli": "हरी मिर्च (Green chilli)",
    "green_moong": "साबुत मूंग (Green moong)",
    "black_pepper": "काली मिर्च (Black pepper)",
    "methi_leaves": "मेथी के पत्ते (Methi)",
    "oats": "ओट्स (Oats)",
    "milk": "दूध (Doodh)",
    "sabudana": "साबूदाना (Sabudana)",
    "sendha_salt": "सेंधा नमक (Sendha namak)",
    "lemon": "नींबू (Nimbu)",
    "kuttu_atta": "कुट्टू का आटा (Kuttu atta)",
    "rajma": "राजमा (Rajma)",
    "garam_masala": "गरम मसाला (Garam masala)",
    "rice": "चावल (Chawal)",
    "kabuli_chana": "काबुली चना / छोले (Chole)",
    "chana_masala": "चना मसाला (Chana masala)",
    "cumin": "जीरा (Jeera)",
    "spinach": "पालक (Palak)",
    "tamarind": "इमली (Imli)",
    "rasam_powder": "रसम पाउडर (Rasam powder)",
    "whole_spices": "खड़े मसाले (Whole spices)",
    "moong_dal": "मूंग दाल (Moong dal)",
    "chana_dal": "चना दाल (Chana dal)",
    "cauliflower": "गोभी (Gobhi)",
    "amchur": "आमचूर (Amchur)",
    "bhindi": "भिंडी (Bhindi)",
    "brinjal": "बैंगन (Baingan)",
    "paneer": "पनीर (Paneer)",
    "butter": "मक्खन (Butter)",
    "cream": "मलाई / क्रीम (Cream)",
    "mushroom": "मशरूम (Mushroom)",
    "masoor_dal": "मसूर दाल (Masoor dal)",
    "chicken": "चिकन (Chicken)",
    "chicken_masala": "चिकन मसाला (Chicken masala)",
    "fish_rohu": "रोहू मछली (Fish)",
    "mustard_oil": "सरसों का तेल (Mustard oil)",
    "mustard_paste": "सरसों का पेस्ट (Mustard paste)",
    "egg": "अंडा (Egg)",
    "capsicum": "शिमला मिर्च (Capsicum)",
    "pav_bhaji_masala": "पाव भाजी मसाला (Pav bhaji masala)",
    "pav": "पाव (Pav)",
    "matki_sprouts": "अंकुरित मोठ (Sprouts)",
    "misal_masala": "मिसल मसाला (Misal masala)",
    "jaggery": "गुड़ (Jaggery)",
    "jowar_atta": "ज्वार का आटा (Jowar atta)",
    "eno": "ईनो (Eno)",
    "sugar": "चीनी (Sugar)",
    "sesame_seeds": "तिल (Til)",
    "bread": "ब्रेड (Bread)",
    "cucumber": "खीरा (Kheera)",
    "green_chutney": "हरी चटनी (Green chutney)",
    "maida": "मैदा (Maida)",
    "apple": "सेब (Apple)",
    "banana": "केला (Kela)",
    "pomegranate": "अनार (Anaar)",
    "chaat_masala": "चाट मसाला (Chaat masala)",
    "makhana": "मखाना (Makhana)",
    "samak_rice": "समा के चावल (Samak rice)",
    "singhara_atta": "सिंघाड़े का आटा (Singhara atta)",
    "cardamom": "इलायची (Elaichi)",
    "cashew": "काजू (Kaju)",
}

# Standard step-by-step cooking instructions mapped by recipe id
RECIPE_STEPS_EN: dict[str, list[str]] = {
    "poha": [
        "Rinse poha in a colander under running water for 30 seconds; drain completely and rest for 5 minutes.",
        "Finely chop onions and dice potatoes into small 1/2-inch cubes.",
        "Heat oil in a kadai over medium flame; add mustard seeds and let them splutter.",
        "Add raw peanuts and fry for 1-2 minutes until crunchy and golden brown.",
        "Add chopped onions and potatoes; sauté on medium heat until potatoes turn tender (about 4-5 mins).",
        "Add turmeric powder and salt; mix well. Gently fold in the drained poha.",
        "Cover with a lid and steam on low flame for 2 minutes. Garnish with lemon juice and coriander; serve hot."
    ],
    "upma": [
        "Dry roast suji (semolina) in a pan on medium-low heat for 3-4 minutes until fragrant; set aside.",
        "Finely chop green peas and french beans.",
        "Heat oil in a pan; add mustard seeds and curry leaves. Let them crackle.",
        "Add the chopped vegetables and sauté for 2 minutes. Pour in water and add salt; bring to a rolling boil.",
        "Slowly pour in the roasted suji while whisking continuously to prevent lumps.",
        "Cover and cook on low heat for 3 minutes until all water is absorbed and upma is soft and fluffy.",
        "Turn off the heat, let it rest covered for 2 minutes, and serve warm."
    ],
    "idli_sambar": [
        "Grease idli plates with a few drops of oil. Pour fermented idli batter into moulds and steam for 10-12 minutes.",
        "In a pressure cooker, add rinsed toor dal, chopped lauki, tomatoes, salt, and water. Cook for 3-4 whistles.",
        "Once pressure releases, mash the dal and vegetables lightly with a ladle.",
        "Add sambar powder and simmer on medium flame for 5 minutes until aromatic.",
        "In a small tadka pan, heat oil, add mustard seeds and curry leaves; pour the tempering into the hot sambar.",
        "Demould warm soft idlis and serve accompanied by piping hot aromatic sambar."
    ],
    "masala_dosa": [
        "Boil potatoes until soft; peel and mash them roughly with a fork.",
        "Heat oil in a pan; splutter mustard seeds, add sliced onions and turmeric, and sauté until translucent.",
        "Add mashed potatoes and salt; mix thoroughly with 2 tablespoons of water to create the potato masala filling.",
        "Heat a seasoned cast-iron tawa. Pour a ladle of dosa batter and spread outward in circular motion into a thin crepe.",
        "Drizzle oil or ghee around the edges; cook on medium-high heat until the base turns golden and crisp.",
        "Place 2 tablespoons of warm potato masala in the center, fold the dosa over, and serve hot."
    ],
    "aloo_paratha": [
        "Boil and peel potatoes; mash smoothly with ajwain, finely chopped green chillies (optional), and salt.",
        "Knead wheat flour (atta) with water and a pinch of salt into a soft, pliable dough. Rest for 10 minutes.",
        "Divide dough and potato stuffing into equal medium-sized balls.",
        "Roll dough into a 4-inch circle, place potato ball in center, pleat edges to seal, and roll gently into a 7-inch paratha.",
        "Heat a tawa; cook paratha on both sides until brown spots appear, applying ghee generously.",
        "Serve piping hot with fresh curd (dahi) and butter."
    ],
    "dal_tadka": [
        "Wash toor dal thoroughly; pressure cook with water, turmeric, and salt for 3 whistles until soft and creamy.",
        "Whisk the cooked dal lightly with a spoon to achieve a smooth consistency.",
        "In a tadka pan, heat ghee; add cumin seeds and let them sizzle until fragrant.",
        "Add chopped tomatoes and ginger/green chilli; sauté until tomatoes turn mushy.",
        "Pour the hot ghee tempering directly into the simmering dal.",
        "Simmer for 2 minutes; garnish with fresh coriander and serve warm with steamed rice or phulkas."
    ],
    "rajma_chawal": [
        "Soak rajma (kidney beans) overnight in plenty of water for at least 8 hours.",
        "Pressure cook soaked rajma with fresh water and salt for 5-6 whistles until completely tender and melt-in-mouth.",
        "Heat ghee/oil in a pan; add cumin seeds, chopped onions, and ginger-garlic paste (skip for Jain). Sauté till golden.",
        "Add tomato puree, rajma masala, turmeric, and red chilli; cook until oil separates.",
        "Add boiled rajma along with its cooking broth; mash a few beans to thicken the gravy.",
        "Simmer on low heat for 15 minutes to allow flavours to meld. Serve hot with steamed basmati rice."
    ],
    "chana_masala": [
        "Soak kabuli chana overnight (8 hours); pressure cook with salt for 5-6 whistles until soft.",
        "Heat oil in a heavy-bottomed kadai; add whole cumin seeds and finely chopped onions. Sauté until deep brown.",
        "Add pureed tomatoes, chana masala powder, turmeric, and amchur powder; cook until oil releases from the masala.",
        "Add cooked chickpeas with broth; simmer covered on medium-low flame for 12 minutes.",
        "Gently mash a spoonful of chana against the side of the pot to thicken the rich gravy.",
        "Garnish with julienned ginger and freshly chopped coriander; serve with hot phulkas or puris."
    ],
    "paneer_butter_masala": [
        "Cut paneer into bite-sized cubes; soak in warm water for 10 minutes for extra softness.",
        "Heat butter in a pan; sauté whole spices, onions, and tomatoes until completely soft.",
        "Blend the tomato-onion mixture into a velvety smooth puree and strain back into the pan.",
        "Add turmeric, garam masala, salt, and a pinch of sugar; simmer on low heat for 5 minutes.",
        "Slide in paneer cubes and stir in fresh cream; cook gently for 2-3 minutes without boiling.",
        "Finish with crushed kasuri methi and serve hot with naan or jeera rice."
    ],
    "veg_pulao": [
        "Rinse basmati rice until water runs clear; soak for 20 minutes and drain.",
        "Heat ghee in a pressure cooker or heavy pot; add whole spices (bay leaf, cloves, cardamom, cinnamon).",
        "Add sliced onions, green peas, diced carrots, and french beans; sauté for 3 minutes.",
        "Add soaked rice and gently sauté for 1 minute so grains are coated with ghee.",
        "Pour in 2 cups of water per cup of rice and add salt; bring to a boil.",
        "Cover and cook on low flame for 10 minutes (or 1 whistle in pressure cooker). Rest for 5 minutes, fluff with fork, and serve."
    ],
    "curd_rice": [
        "Cook rice until very soft and slightly overcooked; mash while warm with the back of a ladle.",
        "Let the rice cool to room temperature; mix thoroughly with fresh curd, a splash of milk, and salt.",
        "In a small pan, heat oil; add mustard seeds, curry leaves, and green chillies; let them crackle.",
        "Pour the aromatic tempering over the curd rice and mix well.",
        "Optionally garnish with fresh pomegranate pearls or grated carrots; serve chilled or room temperature."
    ],
    "chicken_curry": [
        "Clean and cut chicken into curry-cut pieces; marinate with turmeric, salt, and curd for 20 minutes.",
        "Heat oil in a heavy pot; add whole spices and sliced onions; sauté on medium flame until deep golden brown.",
        "Add ginger-garlic paste and chopped tomatoes; sauté until tomatoes soften and oil releases.",
        "Add chicken masala, coriander powder, and chilli powder; sauté the masala for 2 minutes.",
        "Add marinated chicken pieces; sear on high flame for 5 minutes until chicken turns white on the outside.",
        "Pour 1 cup of warm water, cover with lid, and simmer on low heat for 18-20 minutes until chicken is tender and succulent.",
        "Garnish with freshly chopped coriander leaves and serve hot with rotis or rice."
    ],
    "kadhi_khichdi": [
        "Wash rice and moong dal together; pressure cook with turmeric, salt, and 3.5 cups water for 3 whistles until soft.",
        "In a bowl, whisk fresh curd with besan (gram flour), turmeric, salt, and water until completely lump-free.",
        "Pour curd mixture into a pot and bring to a gentle boil on low heat, stirring continuously so it does not curdle.",
        "In a small pan, heat ghee; crackle mustard seeds, cumin, curry leaves, and a pinch of hing.",
        "Pour tempering into the simmering kadhi; boil for 5 minutes.",
        "Serve hot comfort bowl: steaming moong khichdi topped with generous ladle of spiced kadhi."
    ],
    "aloo_gobhi": [
        "Cut cauliflower into florets and potatoes into wedges; rinse and pat completely dry.",
        "Heat oil in a kadai; shallow fry potato wedges and cauliflower florets for 5 minutes until half-cooked; remove.",
        "In the remaining oil, add cumin seeds, finely chopped ginger, and green chillies.",
        "Add turmeric, coriander powder, amchur powder, and salt; mix on low flame.",
        "Toss the fried potatoes and cauliflower in the spice mix until evenly coated.",
        "Cover and steam on low flame for 7-8 minutes until tender. Garnish with fresh coriander."
    ],
    "methi_thepla": [
        "Wash methi (fenugreek) leaves thoroughly and chop finely.",
        "In a wide mixing bowl, combine atta, chopped methi, curd, oil, turmeric, and salt.",
        "Knead into a soft, smooth dough using minimal water. Rest dough for 10 minutes.",
        "Divide into small balls and roll out thinly into 6-inch circles dusting with flour.",
        "Cook on a hot tawa with a few drops of oil on both sides until soft golden spots appear.",
        "Stack wrapped in a clean cloth to stay soft; serve warm with pickle and curd."
    ],
}

# Generic high-quality step template generator for recipes not explicitly customized above
def _generic_steps(recipe_name: str, meal_type: str, ingredients_list: list[str]) -> list[str]:
    prep_items = [i for i in ingredients_list if i not in ("water", "oil", "ghee", "salt", "turmeric")]
    return [
        f"Clean, wash, and prep all core ingredients: {', '.join(prep_items[:4])}.",
        "Heat oil or ghee in a pan or cooker over medium heat; add whole spices / mustard / cumin seeds and let them sizzle.",
        f"Add the prepared vegetables or base ingredients; sauté on medium flame for 4-5 minutes until aromatic.",
        "Add spices and salt; stir thoroughly on low heat so the flavours infuse evenly.",
        "Add measured water if required, cover with a tight lid, and simmer gently until cooked through and tender.",
        f"Turn off heat, garnish with fresh herbs, and serve hot {recipe_name}."
    ]


def get_recipe_steps_en(rec: Recipe) -> list[str]:
    if rec.id in RECIPE_STEPS_EN:
        return RECIPE_STEPS_EN[rec.id]
    ing_names = [i.item for i in rec.ingredients]
    return _generic_steps(rec.name, rec.meal_types[0] if rec.meal_types else "lunch", ing_names)


# Tamil cooking steps
RECIPE_STEPS_TA: dict[str, list[str]] = {
    "poha": [
        "படி 1: அவலை ஒரு வடிகட்டியில் போட்டு தண்ணீரில் 30 வினாடிகள் அலசி, உடனே தண்ணீரை முழுமையாக வடித்து 5 நிமிடங்கள் வைக்கவும்.",
        "படி 2: வெங்காயம் மற்றும் உருளைக்கிழங்கை பொடியாக நறுக்கி வைக்கவும்.",
        "படி 3: ஒரு கடாயில் எண்ணெய் ஊற்றி சூடானதும் கடுகு சேர்த்து வெடிக்க விடவும்.",
        "படி 4: வேர்க்கடலை சேர்த்து பொன்னிறமாகவும் மொறுமொறுப்பாகவும் மாறும் வரை 1-2 நிமிடங்கள் வறுக்கவும்.",
        "படி 5: நறுக்கிய வெங்காயம் மற்றும் உருளைக்கிழங்கு சேர்த்து, உருளைக்கிழங்கு வேகும் வரை மிதமான தீயில் வதக்கவும்.",
        "படி 6: மஞ்சள் தூள் மற்றும் உப்பு சேர்த்து நன்றாக கலக்கவும். பின் வடிகட்டிய அவலை சேர்த்து உடையாமல் மெதுவாக கிளறவும்.",
        "படி 7: கடாயை மூடி மிதமான தீயில் 2 நிமிடங்கள் ஆவியில் வேகவிடவும். எலுமிச்சை சாறு மற்றும் கொத்தமல்லி தூவி சூடாக பரிமாறவும்."
    ],
    "upma": [
        "படி 1: ரவையை ஒரு கடாயில் மிதமான தீயில் 3-4 நிமிடங்கள் வாசனை வரும் வரை வறுத்து தனியாக வைக்கவும்.",
        "படி 2: பச்சை பட்டாணி மற்றும் பீன்ஸை பொடியாக நறுக்கவும்.",
        "படி 3: கடாயில் எண்ணெய் ஊற்றி, கடுகு மற்றும் கறிவேப்பிலை சேர்த்து தாளிக்கவும்.",
        "படி 4: நறுக்கிய காய்கறிகளை சேர்த்து 2 நிமிடங்கள் வதக்கவும். பின் தேவையான தண்ணீர் மற்றும் உப்பு சேர்த்து கொதிக்க விடவும்.",
        "படி 5: தண்ணீர் கொதிக்கும் போது, வறுத்த ரவையை கட்டி பிடிக்காமல் மெதுவாக தூவி கொண்டே கிளறவும்.",
        "படி 6: கடாயை மூடி மிதமான தீயில் 3 நிமிடங்கள் வேக வைக்கவும். ரவை வெந்து மிருதுவானதும் இறக்கி சூடாக பரிமாறவும்."
    ],
    "idli_sambar": [
        "படி 1: இட்லி தட்டுகளில் சிறிது எண்ணெய் தடவி, இட்லி மாவை ஊற்றி 10-12 நிமிடங்கள் ஆவியில் வேக வைத்து எடுக்கவும்.",
        "படி 2: குக்கரில் துவரம் பருப்பு, நறுக்கிய சுரைக்காய், தக்காளி, உப்பு மற்றும் தண்ணீர் சேர்த்து 3-4 விசில் விட்டு வேக வைக்கவும்.",
        "படி 3: குக்கர் பிரஷர் அடங்கியதும், பருப்பு மற்றும் காய்கறிகளை கரண்டியால் மசித்து கொள்ளவும்.",
        "படி 4: சாம்பார் பொடி சேர்த்து 5 நிமிடங்கள் கொதிக்க விடவும்.",
        "படி 5: தாளிப்பு கரண்டியில் எண்ணெய் சூடாக்கி, கடுகு, கறிவேப்பிலை தாளித்து சாம்பாரில் கொட்டவும்.",
        "படி 6: பஞ்சு போன்ற மென்மையான இட்லியுடன் சுவையான சூடான சாம்பாரை பரிமாறவும்."
    ],
    "masala_dosa": [
        "படி 1: உருளைக்கிழங்கை வேகவைத்து தோலுரித்து மசித்து வைக்கவும்.",
        "படி 2: கடாயில் எண்ணெய் ஊற்றி கடுகு தாளித்து, நறுக்கிய வெங்காயம் மற்றும் மஞ்சள் தூள் சேர்த்து வதக்கவும்.",
        "படி 3: மசித்த உருளைக்கிழங்கு, உப்பு மற்றும் 2 ஸ்பூன் தண்ணீர் சேர்த்து நன்கு கலந்து மசாலா பூரணத்தை தயார் செய்யவும்.",
        "படி 4: தோசைக்கல்லை சூடாக்கி, ஒரு கரண்டி தோசை மாவை ஊற்றி வட்டமாக மெல்லியதாக தேய்க்கவும்.",
        "படி 5: சுற்றிலும் எண்ணெய் அல்லது நெய் ஊற்றி பொன்னிறமாக மொறுமொறுப்பாக வேகவிடவும்.",
        "படி 6: நடுவில் 2 கரண்டி உருளைக்கிழங்கு மசாலா வைத்து மடித்து, சூடான சாம்பார் சட்னியுடன் பரிமாறவும்."
    ],
    "aloo_paratha": [
        "படி 1: உருளைக்கிழங்கை வேகவைத்து மசித்து, அதனுடன் ஓமம், உப்பு சேர்த்து பூரணம் தயாரிக்கவும்.",
        "படி 2: கோதுமை மாவில் தண்ணீர் மற்றும் உப்பு சேர்த்து மென்மையான சப்பாத்தி மாவாக பிசைந்து 10 நிமிடங்கள் ஊற வைக்கவும்.",
        "படி 3: மாவை உருண்டைகளாக்கி சிறிய வட்டமாக தேய்த்து, நடுவில் உருளைக்கிழங்கு பூரணத்தை வைத்து விளிம்புகளை மூடி மெதுவாக பரோட்டாவாக தேய்க்கவும்.",
        "படி 4: தோசைக்கல்லை சூடாக்கி, பரோட்டாவை போட்டு இருபுறமும் நெய் தடவி பொன்னிறமாக வேக வைக்கவும்.",
        "படி 5: சூடான ஆலு பரோட்டாவை கெட்டி தயிர் மற்றும் வெண்ணெயுடன் பரிமாறவும்."
    ],
    "dal_tadka": [
        "படி 1: துவரம் பருப்பை கழுவி குக்கரில் மஞ்சள் தூள், உப்பு மற்றும் தண்ணீருடன் 3 விசில் விட்டு வேக வைக்கவும்.",
        "படி 2: வெந்த பருப்பை கரண்டியால் லேசாக கடைந்து கொள்ளவும்.",
        "படி 3: தாளிப்பு கரண்டியில் நெய் ஊற்றி சூடானதும் சீரகம் சேர்த்து பொரிய விடவும்.",
        "படி 4: நறுக்கிய தக்காளி மற்றும் பச்சை மிளகாய் சேர்த்து தக்காளி கரையும் வரை வதக்கவும்.",
        "படி 5: சூடான நெய் தாளிப்பை பருப்பில் ஊற்றி 2 நிமிடங்கள் கொதிக்க வைக்கவும்.",
        "படி 6: கொத்தமல்லி தழை தூவி சூடான சாதம் அல்லது சப்பாத்தியுடன் பரிமாறவும்."
    ],
    "curd_rice": [
        "படி 1: சாதத்தை நன்றாக குழைய வேகவைத்து, சூடாக இருக்கும் போதே கரண்டியின் பின்புறத்தால் மசித்து கொள்ளவும்.",
        "படி 2: சாதம் ஆறியதும் புதிய தயிர், சிறிதளவு பால் மற்றும் உப்பு சேர்த்து நன்றாக கலக்கவும்.",
        "படி 3: தாளிப்பு கரண்டியில் எண்ணெய் சூடாக்கி, கடுகு, கறிவேப்பிலை மற்றும் பச்சை மிளகாய் சேர்த்து தாளிக்கவும்.",
        "படி 4: தாளிப்பை தயிர் சாதத்தில் ஊற்றி நன்றாக கலக்கவும்.",
        "படி 5: விருப்பப்பட்டால் மாதுளை முத்துக்கள் தூவி குளிர்ச்சியாக பரிமாறவும்."
    ],
    "veg_pulao": [
        "படி 1: பாசுமதி அரிசியை கழுவி 20 நிமிடங்கள் ஊறவைத்து தண்ணீரை வடிக்கவும்.",
        "படி 2: குக்கரில் நெய் சூடாக்கி பட்டை, கிராம்பு, ஏலக்காய் உள்ளிட்ட வாசனைப் பொருட்களை சேர்க்கவும்.",
        "படி 3: நறுக்கிய வெங்காயம், பச்சை பட்டாணி, கேரட், பீன்ஸ் சேர்த்து 3 நிமிடங்கள் வதக்கவும்.",
        "படி 4: ஊறவைத்த அரிசியை சேர்த்து உடையாமல் 1 நிமிடம் வதக்கவும்.",
        "படி 5: ஒரு கப் அரிசிக்கு 2 கப் தண்ணீர் மற்றும் உப்பு சேர்த்து கொதிக்க விடவும்.",
        "படி 6: குக்கரை மூடி மிதமான தீயில் 1 விசில் விட்டு இறக்கவும். 5 நிமிடங்கள் கழித்து கிளறி சூடாக பரிமாறவும்."
    ],
}

def get_recipe_steps_ta(rec: Recipe) -> list[str]:
    if rec.id in RECIPE_STEPS_TA:
        return RECIPE_STEPS_TA[rec.id]
    steps_en = get_recipe_steps_en(rec)
    return [f"படி {i+1}: " + s for i, s in enumerate(steps_en)]


# Hindi cooking steps
RECIPE_STEPS_HI: dict[str, list[str]] = {
    "poha": [
        "स्टेप 1: पोहा को छलनी में 30 सेकंड पानी से धोकर तुरंत पानी निथार लें और 5 मिनट अलग रखें।",
        "स्टेप 2: प्याज और आलू को बारीक टुकड़ों में काट लें।",
        "स्टेप 3: कड़ाही में तेल गरम करें, राई डालें और चटकने दें।",
        "स्टेप 4: कच्ची मूंगफली डालकर 1-2 मिनट तक कुरकुरी और सुनहरी होने तक भूनें।",
        "स्टेप 5: कटा प्याज और आलू डालें, आलू नरम होने तक मध्यम आंच पर भूनें।",
        "स्टेप 6: हल्दी और नमक डालकर अच्छी तरह मिलाएं। फिर भीगा हुआ पोहा डालकर हल्के हाथ से मिलाएं।",
        "स्टेप 7: ढककर 2 मिनट धीमी आंच पर भाप दें। हरा धनिया और नींबू का रस डालकर गरमा-गरम परोसें।"
    ],
    "upma": [
        "स्टेप 1: सूजी को कढ़ाई में धीमी आंच पर 3-4 मिनट खुशबू आने तक सूखा भूनकर अलग निकाल लें।",
        "स्टेप 2: मटर और बीन्स को बारीक काट लें।",
        "स्टेप 3: कड़ाही में तेल गरम करें, राई और कढ़ी पत्ता डालकर तड़कने दें।",
        "स्टेप 4: कटी सब्जियां डालकर 2 मिनट भूनें, फिर पानी और नमक डालकर उबाल आने दें।",
        "स्टेप 5: पानी उबलने पर भुनी सूजी धीरे-धीरे डालते हुए लगातार चलाएं ताकि गांठें न पड़ें।",
        "स्टेप 6: ढककर धीमी आंच पर 3 मिनट पकाएं जब तक सूजी सारा पानी सोखकर खिली-खिली न हो जाए। गरमा-गरम परोसें।"
    ],
    "dal_tadka": [
        "स्टेप 1: तूर दाल को धोकर कुकर में हल्दी, नमक और पानी के साथ 3 सीटी आने तक पकाएं।",
        "स्टेप 2: पकी दाल को कलछी से हल्का घोंट लें।",
        "स्टेप 3: तड़का पैन में घी गरम करें, जीरा डालकर तड़कने दें।",
        "स्टेप 4: कटे टमाटर और हरी मिर्च डालकर टमाटर के गलने तक भूनें।",
        "स्टेप 5: गरम घी का तड़का उबलती दाल में डालें और 2 मिनट पकाएं।",
        "स्टेप 6: हरा धनिया डालकर गरमा-गरम चावल या रोटी के साथ परोसें।"
    ]
}

def get_recipe_steps_hi(rec: Recipe) -> list[str]:
    if rec.id in RECIPE_STEPS_HI:
        return RECIPE_STEPS_HI[rec.id]
    steps_en = get_recipe_steps_en(rec)
    return [f"कदम {i+1}: " + s for i, s in enumerate(steps_en)]


def format_recipe_instructions(
    recipe: Recipe,
    servings: int = 4,
    lang: str = "en-IN",
    adaptations: list[Adaptation] | None = None,
) -> str:
    """Format full recipe instructions with scaled ingredient quantities and step-by-step process."""
    servings = max(1, servings)
    lines: list[str] = []

    # 1. Header
    if lang == "ta-IN":
        lines.append(f"🍲 {recipe.name} — {servings} நபர்களுக்கான அளவு ({servings} portions)")
        lines.append(f"⏱️ தயாரிப்பு நேரம்: {recipe.prep_min} நிமிடங்கள் | சமையல் நேரம்: {recipe.cook_min} நிமிடங்கள்")
        lines.append("")
        lines.append("📦 தேவையான பொருட்கள் மற்றும் அளவுகள் (Items Used & Quantity):")
    elif lang == "hi-IN":
        lines.append(f"🍲 {recipe.name} — {servings} लोगों के लिए ({servings} portions)")
        lines.append(f"⏱️ तैयारी समय: {recipe.prep_min} मिनट | पकाने का समय: {recipe.cook_min} मिनट")
        lines.append("")
        lines.append("📦 आवश्यक सामग्री और मात्रा (Items Used & Quantity):")
    else:
        lines.append(f"🍲 {recipe.name} — {servings} portions")
        lines.append(f"⏱️ Prep Time: {recipe.prep_min} mins | Cooking Time: {recipe.cook_min} mins")
        lines.append("")
        lines.append("📦 Items Used & Exact Quantities:")

    # 2. Scaled Ingredients
    for ing in recipe.ingredients:
        if ing.item == "water":
            continue
        total_q = ing.qty * servings
        # Format quantity cleanly (e.g. 2 instead of 2.0)
        q_str = f"{total_q:g}"
        unit_str = ing.unit

        if lang == "ta-IN":
            item_name = INGREDIENT_NAMES_TA.get(ing.item, ing.item.replace("_", " ").title())
            lines.append(f"• {item_name}: {q_str} {unit_str}")
        elif lang == "hi-IN":
            item_name = INGREDIENT_NAMES_HI.get(ing.item, ing.item.replace("_", " ").title())
            lines.append(f"• {item_name}: {q_str} {unit_str}")
        else:
            item_name = ing.item.replace("_", " ").title()
            lines.append(f"• {item_name}: {q_str} {unit_str}")

    # 3. Step-by-Step Cooking Process
    lines.append("")
    if lang == "ta-IN":
        lines.append("👨‍🍳 செய்முறை படி படியாக (Step-by-Step Cooking Process):")
        steps = get_recipe_steps_ta(recipe)
        for s in steps:
            lines.append(s)
    elif lang == "hi-IN":
        lines.append("👨‍🍳 पकाने की विधि क्रमवार (Step-by-Step Cooking Process):")
        steps = get_recipe_steps_hi(recipe)
        for s in steps:
            lines.append(s)
    else:
        lines.append("👨‍🍳 Step-by-Step Cooking Process:")
        steps = get_recipe_steps_en(recipe)
        for i, s in enumerate(steps, 1):
            lines.append(f"Step {i}: {s}")

    # 4. Adaptations and dietary notes
    notes: list[str] = []
    if adaptations:
        for a in adaptations:
            notes.append(f"{a.member}: {a.change}")
    if recipe.substitutions:
        notes.extend(recipe.substitutions)

    if notes:
        lines.append("")
        if lang == "ta-IN":
            lines.append("💡 சிறப்பு குறிப்புகள் (Special Notes & Adaptations):")
        elif lang == "hi-IN":
            lines.append("💡 विशेष निर्देश और बदलाव (Special Notes & Adaptations):")
        else:
            lines.append("💡 Special Notes & Dietary Adaptations:")
        for n in notes:
            lines.append(f"• {n}")

    return "\n".join(lines)
