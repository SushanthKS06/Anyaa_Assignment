**User:** Namaste

**Rasoi:** Namaste! Main Rasoi — tumhare ghar ka khana sambhalungi. Ghar me kaun kaun hai, aur koi parhez ya allergy?

**User:** Ghar me 4 log hain — Dadi Jain hain aur Thursday ko fast rakhti hain, Papa diabetic hain, Beta teen hai jo weekend pe nonveg khata hai, aur Chhotu 2 saal ka hai

**Rasoi:** Theek. Hafte ka grocery budget kitna rakhu?

**User:** 7 din ka plan banao, budget 6000 ka hai

**Tool:** generate_plan({'days': 7, 'seed': 42})

**Rasoi:** Plan ready — 7 din, 21 meals. Pehle 2 din suno: Mon — breakfast: Methi Thepla; lunch: Dal Tadka (Jain-style); dinner: Moong Dal Khichdi | Tue — breakfast: Moong Dal Chilla; lunch: Moong Dal Khichdi; dinner: Dal Tadka (Jain-style) Aur? (aur bolo)

**User:** haan nahi wait, budget 5000 hai

**Rasoi:** Theek — budget Rs.5000 Grocery total isi hisab se banegi.

**User:** Tuesday dopahar ko paneer nahi, aloo gobhi bana do

**Tool:** swap_meal({'day': 'Tue', 'slot': 'lunch', 'new_dish': ''})

**Rasoi:** Done — Tue lunch: Moong Dal Khichdi ki jagah Aloo Gobhi. (Dadi ke liye alag) Kuch aur?

**User:** yeh kyun choose kiya?

**Tool:** explain_meal({'day': 'Tue', 'slot': 'lunch'})

**Rasoi:** Aloo Gobhi — no repeat in 3-day window; leftover-friendly.

**User:** aur

**Rasoi:** Wed — breakfast: Khaman Dhokla; lunch: Masoor Dal with Lemon; dinner: Paneer Bhurji | Thu — breakfast: Vegetable Upma (Dadi ke liye vrat plate); lunch: Sambar Sadam (Dadi ke liye vrat plate, Beta ke liye alag); dinner: Masoor Dal with Lemon (Dadi ke liye vrat plate, Beta ke liye alag) Aur? (aur bolo)

**User:** grocery list banao

**Tool:** build_grocery_list({})

**Rasoi:** List ready — 37 items, total Rs.3457. Budget Rs.5000. 3 cheez out of stock hai (capsicum, french_beans, kuttu_atta). Order karu ya WhatsApp pe bheju?

**User:** order karo

**Rasoi:** List ready — 37 items, total Rs.3457. Budget Rs.5000. 3 cheez out of stock hai (capsicum, french_beans, kuttu_atta). Pakka order karu? 'Haan' bolo.

**User:** haan, order karo

**Tool:** place_order({'confirm': True})

**Rasoi:** Order ho gaya! ID SM-ORD-0042-2824, 46 min me aayega (simulated). Kal se cook ko plan de dungi.

