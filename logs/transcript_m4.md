**User:** /cook

**Rasoi:** Cook mode. Bolo — aaj kya banana hai?

**User:** aaj ka brief batao

**Tool:** get_daily_brief({'weekday': ''})

**Rasoi:** Aaj Mon. Sabse pehle Methi Thepla shuru karo. breakfast: Methi Thepla (5 servings, ~35 min) Phir lunch: Masoor Dal with Lemon (5 servings, ~25 min) Phir dinner: Dal Tadka (Jain-style) (5 servings, ~35 min).

**User:** tomato khatm ho gaya hai

**Tool:** report_disruption({'kind': 'missing_ingredient', 'detail': 'tomato', 'day': '', 'slot': ''})

**Rasoi:** Theek. lunch me Masoor Dal with Lemon ki jagah Curd Rice (30 min). Theek? tomato agli list me likh diya.

**User:** 4 mehman aa rahe hain dinner pe

**Tool:** report_disruption({'kind': 'extra_guests', 'detail': '4 guests', 'day': '', 'slot': 'dinner'})

**Rasoi:** Theek. dinner me 4 extra — total 9, 9 theek? Samaan agli list me jod diya.

**User:** cooker kharab ho gaya hai

**Tool:** report_disruption({'kind': 'equipment_broken', 'detail': 'cooker', 'day': '', 'slot': ''})

**Rasoi:** Theek. dinner me Dal Tadka (Jain-style) ki jagah Paneer Bhurji (25 min). Theek?

**User:** lunch bana diya, namak thoda zyada tha

**Tool:** log_cooked({'slot': 'lunch', 'status': 'cooked', 'note': 'namak thoda zyada tha'})

**Rasoi:** Note kar liya — Curd Rice cooked. Agli baar dhyan rakhungi.

**User:** kal ki taiyari batao

**Rasoi:** Kal Tue: Moong Dal Chilla (breakfast): soak moong 4 hours — 250g.

