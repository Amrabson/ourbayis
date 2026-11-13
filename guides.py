# -*- coding: utf-8 -*-
"""Bilingual guide articles served at /guides and /guides/<slug>.

Kept out of i18n.py deliberately: these are long-form editorial blocks, not UI
strings, and mixing them in would make `T_EN`/`T_HE` unreadable. Same rule
applies though — every English string has a Hebrew twin (`*_he`), and the
renderer falls back to English if a Hebrew field is ever left empty.

Content rules (2026-09-22 review): describe only what we can stand behind.
Anything that varies by product, store or posek is phrased as "check" /
"ask", never as a guarantee. Nothing here claims customs, warranty or
halachic rulings.

Shape of a guide:
    slug      URL segment (also the anchor used in the index)
    icon      <symbol> id already present in base.html's sprite
    updated   ISO date shown as "Updated <date>" and used for dateModified
    title / summary (+ _he)
    sections  [{h, h_he, p: [...], p_he: [...], list: [...], list_he: [...]}]
              `p` are paragraphs, `list` an optional bullet list after them.
    cta       key into _CTAS below (button at the end of the article)
"""

_CTAS = {
    "start": ("signup", "cta_start"),
    "catalog": ("catalog_page", "cta_explore"),
    "sample": ("sample", "cta_sample"),
    "shana": ("shana", "shana_intro_cta"),
}

GUIDES = [
    {
        "slug": "first-apartment-checklist",
        "icon": "i-house",
        "updated": "2026-09-22",
        "title": "What a first apartment in Israel actually needs",
        "title_he": "מה דירה ראשונה בישראל באמת צריכה",
        "summary": "A room-by-room starting list for couples setting up a home in Israel — what to "
                   "buy first, what can wait, and what an Israeli apartment needs that a list from "
                   "abroad usually misses.",
        "summary_he": "רשימת פתיחה חדר-חדר לזוגות שמקימים בית בישראל — מה לקנות קודם, מה יכול לחכות, "
                      "ומה דירה ישראלית צריכה שרשימות מחו״ל בדרך כלל מפספסות.",
        "sections": [
            {
                "h": "The first week",
                "h_he": "השבוע הראשון",
                "p": ["You do not need a finished apartment on day one. You need to be able to sleep, "
                      "eat, make Shabbos and clean up afterwards. Almost everything else can wait for "
                      "the second month, when you know how you actually live in the space.",
                      "If you are building a registry, put this group at the top and mark it as most "
                      "wanted — guests genuinely want to know what matters first."],
                "p_he": ["אתם לא צריכים דירה גמורה ביום הראשון. אתם צריכים לישון, לאכול, לעשות שבת "
                         "ולנקות אחר כך. כמעט כל השאר יכול לחכות לחודש השני, כשכבר תדעו איך אתם באמת "
                         "חיים בדירה.",
                         "אם אתם בונים רשימת מתנות, שימו את הקבוצה הזו למעלה וסמנו אותה כהכי רצויה — "
                         "אורחים באמת רוצים לדעת מה חשוב קודם."],
                "list": ["Bed, mattress protector, one sheet set, duvet and pillows",
                         "Towels for two, plus a bath mat",
                         "A platta (Shabbos hot plate) and an urn or hot water pump",
                         "Basic milchig and fleishig plates, bowls and cutlery",
                         "One pot, one frying pan, a cutting board and a sharp knife",
                         "An electric kettle",
                         "A sponja set — squeegee, stick, cloths and a bucket",
                         "A netilas yadayim cup",
                         "Bin, bin bags, cleaning basics, a few light bulbs and a screwdriver"],
                "list_he": ["מיטה, מגן מזרן, סט מצעים אחד, שמיכה וכריות",
                            "מגבות לשניים ושטיחון אמבטיה",
                            "פלטת שבת ומיחם או תרמוס משאבה",
                            "צלחות, קערות וסכו״ם בסיסיים — חלבי ובשרי",
                            "סיר אחד, מחבת אחת, קרש חיתוך וסכין חדה",
                            "קומקום חשמלי",
                            "סט ספונג׳ה — מגב, מקל, סמרטוטים ודלי",
                            "נטלה",
                            "פח, שקיות, חומרי ניקוי בסיסיים, כמה נורות ומברג"],
            },
            {
                "h": "What usually comes with the apartment — and what doesn't",
                "h_he": "מה בדרך כלל מגיע עם הדירה — ומה לא",
                "p": ["Israeli rentals vary enormously. Some come with a fridge, oven, washing machine "
                      "and air conditioning; others come with bare walls and a kitchen counter. Before "
                      "you buy or register for a large appliance, ask the landlord in writing what stays "
                      "in the apartment, and whether it works.",
                      "This is also worth writing on your registry: a one-line note saying “our "
                      "apartment already has a fridge and oven” saves a relative from buying a "
                      "second one."],
                "p_he": ["דירות בישראל שונות מאוד זו מזו. חלקן מגיעות עם מקרר, תנור, מכונת כביסה "
                         "ומזגן; אחרות עם קירות חשופים ושיש. לפני שקונים או מוסיפים לרשימה מוצר חשמלי "
                         "גדול, בקשו מבעל הדירה בכתב מה נשאר בדירה — והאם זה עובד.",
                         "כדאי לכתוב את זה גם ברשימה: שורה אחת כמו ״בדירה שלנו כבר יש מקרר ותנור״ "
                         "חוסכת לקרוב משפחה קנייה כפולה."],
            },
            {
                "h": "The things people forget",
                "h_he": "הדברים ששוכחים",
                "p": ["These are the items couples tend to buy twice — once badly in the first week, "
                      "once properly a month later. Putting them on a registry early usually means "
                      "buying them once."],
                "p_he": ["אלה הפריטים שזוגות נוטים לקנות פעמיים — פעם אחת בחיפזון בשבוע הראשון, ופעם "
                         "שנייה כמו שצריך אחרי חודש. אם מוסיפים אותם לרשימה מוקדם, בדרך כלל קונים "
                         "אותם פעם אחת."],
                "list": ["A drying rack — many apartments have no dryer",
                         "A folding table and chairs for Shabbos guests",
                         "Storage: hangers, closet organisers, storage boxes",
                         "A step stool — Israeli kitchens build upwards",
                         "Fans or a space heater, depending on the season you arrive in",
                         "A basic tool kit and a first-aid kit",
                         "Bentchers, a challah board and cover, candlesticks and a kiddush cup"],
                "list_he": ["מתקן ייבוש כביסה — בהרבה דירות אין מייבש",
                            "שולחן מתקפל וכיסאות לאורחי שבת",
                            "אחסון: קולבים, מסדרים לארון, קופסאות אחסון",
                            "שרפרף — מטבחים בישראל בנויים לגובה",
                            "מאווררים או תנור חימום, לפי העונה שבה אתם מגיעים",
                            "ערכת כלי עבודה וערכת עזרה ראשונה",
                            "ברכונים, מגש וכיסוי לחלה, פמוטים וגביע קידוש"],
            },
        ],
        "cta": "catalog",
    },
    {
        "slug": "giving-from-abroad",
        "icon": "i-gift",
        "updated": "2026-09-22",
        "title": "Giving a gift to a couple in Israel from abroad",
        "title_he": "לתת מתנה לזוג בישראל מחו״ל",
        "summary": "You are in New York, London or Johannesburg and they are moving into an apartment "
                   "in Yerushalayim. Here is how to give something that actually arrives — and what "
                   "the buttons on a registry mean.",
        "summary_he": "אתם בניו יורק, בלונדון או ביוהנסבורג, והם נכנסים לדירה בירושלים. ככה נותנים "
                      "מתנה שבאמת מגיעה — ומה המשמעות של הכפתורים ברשימת המתנות.",
        "sections": [
            {
                "h": "Two ways to give",
                "h_he": "שתי דרכים לתת",
                "p": ["On an OurBayis registry every gift has one or two routes, and the card tells you "
                      "which. Either you buy the item yourself from the store the couple linked to, or "
                      "you send the couple the money for it through their own payment link and they "
                      "order it.",
                      "Both are direct. OurBayis never takes or holds your money: a store purchase "
                      "happens on the store's own checkout, and a cash gift goes to the couple's own "
                      "PayPal, Stripe, Bit or PayBox link."],
                "p_he": ["בכל רשימה ב-OurBayis לכל מתנה יש דרך אחת או שתיים, והכרטיס אומר איזו. או "
                         "שאתם קונים את הפריט בעצמכם מהחנות שהזוג קישר אליה, או ששולחים לזוג את הכסף "
                         "דרך קישור התשלום שלהם והם מזמינים.",
                         "שתי הדרכים ישירות. OurBayis אף פעם לא לוקח או מחזיק את הכסף שלכם: קנייה "
                         "בחנות מתבצעת בקופה של החנות, ומתנה כספית מגיעה לקישור ה-PayPal, Stripe, Bit "
                         "או PayBox של הזוג עצמם."],
            },
            {
                "h": "Why buying from an Israeli store is usually simpler",
                "h_he": "למה בדרך כלל פשוט יותר לקנות מחנות ישראלית",
                "p": ["Shipping a kettle from abroad means freight, possible customs handling and a "
                      "plug that may not match the socket. Ordering the same kettle from a store that "
                      "delivers inside Israel skips all three. That is why the catalog links to Israeli "
                      "retailers.",
                      "If you prefer to send something personal from home — a photo album, a piece of "
                      "jewellery, a sefer — send it as a package and use the registry for the practical "
                      "things."],
                "p_he": ["לשלוח קומקום מחו״ל זה משלוח בינלאומי, אולי טיפול מכס, ותקע שאולי לא מתאים "
                         "לשקע. הזמנה של אותו קומקום מחנות שמשלחת בתוך ישראל חוסכת את שלושת אלה. "
                         "בגלל זה הקטלוג מקשר לחנויות ישראליות.",
                         "אם בא לכם לשלוח משהו אישי מהבית — אלבום תמונות, תכשיט, ספר — שלחו אותו "
                         "כחבילה, והשתמשו ברשימה לדברים המעשיים."],
            },
            {
                "h": "What the prices and “approx.” amounts mean",
                "h_he": "מה אומרים המחירים והסכומים המשוערים",
                "p": ["Prices are set in shekels, because that is what the store charges. The smaller "
                      "“≈ $59” next to a price is an estimate from a published reference "
                      "rate on the date shown — it is there so you know roughly what you are spending, "
                      "not what your card will be billed. Your bank or payment provider uses its own "
                      "rate and may add a fee.",
                      "“Price checked” on a card means someone opened that store page on that "
                      "date and saw that price. Shops change prices and run sales; treat it as a guide, "
                      "and the store page as the truth."],
                "p_he": ["המחירים נקובים בשקלים, כי זה מה שהחנות גובה. ה-״≈ $59״ הקטן ליד המחיר הוא "
                         "הערכה לפי שער חליפין מפורסם בתאריך המצוין — הוא שם כדי שתדעו בערך כמה אתם "
                         "מוציאים, לא כמה יחויב הכרטיס. הבנק או ספק התשלום שלכם משתמשים בשער שלהם "
                         "ועשויים להוסיף עמלה.",
                         "״המחיר נבדק״ על כרטיס אומר שמישהו פתח את עמוד החנות באותו תאריך וראה את "
                         "המחיר. חנויות משנות מחירים ועושות מבצעים; תתייחסו לזה כאל הכוונה, ולעמוד "
                         "החנות כאל האמת."],
            },
            {
                "h": "Reserve, then tell them",
                "h_he": "לשריין, ואז לעדכן",
                "p": ["Reserving a gift holds it so nobody buys the same thing twice. It is not a "
                      "purchase — nothing is charged and nothing is ordered on your behalf. After you "
                      "reserve you get a private link of your own; when you have actually bought or sent "
                      "the gift, open it and tap “I've bought / sent it” so the couple knows "
                      "what is coming.",
                      "Reservations are held for 14 days. If you change your mind, cancel from that same "
                      "link so someone else can give it. Save the link — it is the only way back to your "
                      "reservation, and we cannot resend it."],
                "p_he": ["שריון מתנה שומר אותה כדי שאף אחד לא יקנה את אותו דבר פעמיים. זו לא רכישה — "
                         "לא מחויב שום סכום ולא מוזמן שום דבר בשמכם. אחרי השריון תקבלו קישור פרטי משלכם; "
                         "כשבאמת קניתם או שלחתם, פתחו אותו ולחצו ״קניתי / שלחתי״ כדי שהזוג ידע מה בדרך.",
                         "שריון נשמר 14 יום. אם שיניתם דעתכם, בטלו מאותו קישור כדי שמישהו אחר יוכל לתת. "
                         "שמרו את הקישור — זו הדרך היחידה לחזור לשריון, ואנחנו לא יכולים לשלוח אותו שוב."],
            },
        ],
        "cta": "sample",
    },
    {
        "slug": "kosher-kitchen-basics",
        "icon": "i-pot",
        "updated": "2026-09-22",
        "title": "Setting up a kosher kitchen in a new home",
        "title_he": "להקים מטבח כשר בבית חדש",
        "summary": "The practical side of a first kosher kitchen: two sets of everything, how couples "
                   "keep them apart, and the Shabbos equipment an Israeli kitchen is built around.",
        "summary_he": "הצד המעשי של מטבח כשר ראשון: שני סטים מכל דבר, איך זוגות מפרידים ביניהם, "
                      "והציוד לשבת שמטבח ישראלי בנוי סביבו.",
        "sections": [
            {
                "h": "Two of everything — and a way to tell them apart",
                "h_he": "שניים מכל דבר — ודרך להבדיל ביניהם",
                "p": ["A kosher kitchen needs separate milchig and fleishig sets: plates, cutlery, pots, "
                      "boards, sponges and dish racks. The most common way couples keep it simple is "
                      "colour: one colour for milchig, another for fleishig, chosen once and used for "
                      "everything from the cutting boards to the dish towels.",
                      "Write your two colours on your registry. Guests buying a pot or a set of towels "
                      "will get the right one, and you will not end up with three blue colanders.",
                      "Questions about what needs separating, what can be kashered and how to handle a "
                      "shared oven or dishwasher are halachic questions — ask your rav rather than a "
                      "website."],
                "p_he": ["מטבח כשר צריך סטים נפרדים לחלבי ולבשרי: צלחות, סכו״ם, סירים, קרשים, ספוגים "
                         "ומתקני ייבוש. הדרך הנפוצה לפשט את זה היא צבע: צבע אחד לחלבי, אחר לבשרי, "
                         "נבחרים פעם אחת ומשמשים לכול — מקרשי החיתוך ועד מגבות המטבח.",
                         "כתבו את שני הצבעים ברשימת המתנות שלכם. אורחים שקונים סיר או סט מגבות יביאו "
                         "את הנכון, ולא תישארו עם שלושה מסננים כחולים.",
                         "שאלות על מה צריך להפריד, מה אפשר להכשיר ואיך מתנהלים עם תנור או מדיח משותף "
                         "הן שאלות הלכתיות — שאלו את הרב שלכם, לא אתר אינטרנט."],
            },
            {
                "h": "The Shabbos shelf",
                "h_he": "מדף השבת",
                "p": ["An Israeli kitchen is built around Shabbos, and a handful of appliances do most "
                      "of the work. They are cheap relative to their use and they are the first thing "
                      "worth putting on a registry."],
                "p_he": ["מטבח ישראלי בנוי סביב שבת, וקומץ מכשירים עושים את רוב העבודה. הם זולים ביחס "
                         "לשימוש שלהם, וכדאי לשים אותם ראשונים ברשימה."],
                "list": ["A platta — a flat hot plate that keeps food warm from before Shabbos",
                         "An urn, or a smaller hot water pump pot if the kitchen is tight",
                         "A slow cooker for cholent",
                         "Tablecloths you do not mind washing weekly",
                         "A challah board, a challah knife and a cover",
                         "Candlesticks, and a set of bentchers for guests"],
                "list_he": ["פלטה — משטח חימום שמשאיר אוכל חם מלפני שבת",
                            "מיחם, או תרמוס משאבה קטן יותר אם המטבח צפוף",
                            "סיר לבישול איטי לצ׳ולנט",
                            "מפות שולחן שלא אכפת לכם לכבס כל שבוע",
                            "מגש חלה, סכין חלה וכיסוי",
                            "פמוטים וסט ברכונים לאורחים"],
            },
            {
                "h": "Buy once, not twice",
                "h_he": "לקנות פעם אחת, לא פעמיים",
                "p": ["Where couples regret saving money: a knife that cannot cut, a thin pot that burns "
                      "everything, and a cheap platta replaced within a year. Where saving money makes "
                      "sense: serving platters, extra glassware, anything you use twice a year.",
                      "A registry is good at this. Put the two or three things worth doing properly at "
                      "the top and let several guests contribute the smaller items around them."],
                "p_he": ["איפה זוגות מתחרטים שחסכו: סכין שלא חותכת, סיר דק ששורף הכול, ופלטה זולה "
                         "שמתחלפת תוך שנה. איפה חיסכון הגיוני: מגשי הגשה, כוסות נוספות, כל מה שמשתמשים "
                         "בו פעמיים בשנה.",
                         "רשימת מתנות טובה בדיוק בזה. שימו למעלה את שניים-שלושה הדברים ששווה לעשות "
                         "כמו שצריך, ותנו לכמה אורחים להביא סביבם את הפריטים הקטנים."],
            },
        ],
        "cta": "start",
    },
    {
        "slug": "sizes-plugs-delivery",
        "icon": "i-plug",
        "updated": "2026-09-22",
        "title": "Before you buy: sizes, plugs and delivery in Israel",
        "title_he": "לפני שקונים: מידות, תקעים ומשלוחים בישראל",
        "summary": "The three things that turn a good gift into a returned one — the wrong bed size, a "
                   "plug that doesn't fit, and a delivery nobody is home for.",
        "summary_he": "שלושת הדברים שהופכים מתנה טובה למתנה שמוחזרת — מידת מיטה לא נכונה, תקע שלא "
                      "מתאים, ומשלוח שאין מי שיקבל.",
        "sections": [
            {
                "h": "Electricity and plugs",
                "h_he": "חשמל ותקעים",
                "p": ["Israel's mains supply is 230 volts at 50 Hz, and wall sockets take the Israeli "
                      "three-pin plug (type H); modern sockets also accept the round two-pin europlug "
                      "(type C). Appliances bought from an Israeli store are sold for that supply.",
                      "An appliance brought from a country on 110–120 V is a different matter: a "
                      "travel adapter changes the plug shape only, not the voltage, and a transformer "
                      "is an extra box to buy, place and trip over. Check the label on the appliance "
                      "itself — many modern electronics are marked 100–240 V and are fine anywhere, "
                      "while motors and heating elements usually are not.",
                      "If you are unsure about a specific product, the store's own page is the place to "
                      "check, not a general rule."],
                "p_he": ["רשת החשמל בישראל היא 230 וולט ב-50 הרץ, והשקעים מתאימים לתקע הישראלי "
                         "תלת-פיני (סוג H); שקעים מודרניים מקבלים גם תקע אירופי עגול דו-פיני (סוג C). "
                         "מוצרי חשמל שנקנים בחנות ישראלית נמכרים עבור הרשת הזו.",
                         "מכשיר שמביאים ממדינה עם 110–120 וולט זה סיפור אחר: מתאם נסיעות משנה רק את "
                         "צורת התקע, לא את המתח, ושנאי הוא עוד קופסה לקנות, למקם ולהיתקל בה. בדקו את "
                         "התווית על המכשיר עצמו — הרבה מוצרי אלקטרוניקה מודרניים מסומנים 100–240 וולט "
                         "ועובדים בכל מקום, ומנועים וגופי חימום בדרך כלל לא.",
                         "אם אתם לא בטוחים לגבי מוצר מסוים, עמוד החנות הוא המקום לבדוק — לא כלל כללי."],
            },
            {
                "h": "Beds and linen",
                "h_he": "מיטות ומצעים",
                "p": ["Bed sizes sold in Israel do not match American or British names, and “double” "
                      "means different things in different shops. The sizes couples here usually choose "
                      "from are roughly 90×190 for a single, 140×190 for a standard double, "
                      "160×200 for a queen and 180×200 for a king — but manufacturers vary by a "
                      "few centimetres, and linen is cut to fit the mattress, not the name.",
                      "So measure the mattress before buying sheets, and write the measurement on your "
                      "registry. If you have not moved in yet and cannot measure, say so — a guest can "
                      "give towels now and linen later."],
                "p_he": ["מידות מיטות בישראל לא תואמות לשמות האמריקאיים או הבריטיים, ו״זוגית״ אומר "
                         "דברים שונים בחנויות שונות. המידות שזוגות כאן בדרך כלל בוחרים מהן הן בערך "
                         "90×190 ליחיד, 140×190 לזוגית סטנדרטית, 160×200 לקווין ו-180×200 לקינג — אבל "
                         "יצרנים נבדלים בכמה סנטימטרים, ומצעים נתפרים למזרן, לא לשם.",
                         "אז מדדו את המזרן לפני שקונים מצעים, וכתבו את המידה ברשימה. אם עוד לא נכנסתם "
                         "ואי אפשר למדוד — כתבו את זה; אורח יכול לתת מגבות עכשיו ומצעים אחר כך."],
            },
            {
                "h": "Delivery, and being there for it",
                "h_he": "משלוח, ולהיות שם בשבילו",
                "p": ["Large items are delivered on a scheduled window, often to the building entrance "
                      "rather than up the stairs, and often with an SMS the morning of. Someone has to "
                      "be there. Before a fridge or a couch is ordered, decide who is receiving it.",
                      "If you are still abroad, do not schedule big deliveries for the week you land — "
                      "you will be at the misrad hapnim, not at home. Either push them a week later, or "
                      "ask whoever holds the keys to receive them.",
                      "Assembly is usually separate from delivery. Flat-pack furniture arrives in boxes; "
                      "appliance installation, where it is offered at all, is normally an extra line on "
                      "the order. Check both when you buy."],
                "p_he": ["פריטים גדולים מגיעים בחלון זמן מתואם, לא פעם עד כניסת הבניין ולא במעלה "
                         "המדרגות, ולרוב עם SMS באותו בוקר. צריך שמישהו יהיה שם. לפני שמזמינים מקרר או "
                         "ספה, תחליטו מי מקבל.",
                         "אם אתם עדיין בחו״ל, אל תתאמו משלוחים גדולים לשבוע שאתם נוחתים — תהיו במשרד "
                         "הפנים, לא בבית. או שתדחו בשבוע, או שתבקשו ממי שמחזיק את המפתחות לקבל.",
                         "הרכבה היא בדרך כלל נפרדת מהמשלוח. רהיטים מגיעים בקרטונים; התקנה של מוצרי "
                         "חשמל, אם בכלל מוצעת, היא בדרך כלל שורה נוספת בהזמנה. בדקו את שניהם בקנייה."],
            },
        ],
        "cta": "shana",
    },
    {
        "slug": "building-your-registry",
        "icon": "i-star",
        "updated": "2026-10-22",
        "title": "How to build a registry when you're moving to Israel",
        "title_he": "איך בונים רשימת מתנות כשעוברים לגור בישראל",
        "summary": "Your guests are in three countries and your apartment is still empty. A practical way "
                   "to choose what goes on the list, so it fits both the home and the people giving.",
        "summary_he": "האורחים שלכם בשלוש מדינות והדירה עדיין ריקה. דרך מעשית לבחור מה נכנס לרשימה, "
                      "כך שתתאים גם לבית וגם לאנשים שנותנים.",
        "sections": [
            {
                "h": "Start with the first month",
                "h_he": "מתחילים מהחודש הראשון",
                "p": ["Before anything decorative, list what you will reach for in the first weeks: a "
                      "kettle, something to cook in, plates and cutlery for milchig and fleishig, sheets "
                      "that fit the bed, towels, and what you need for Shabbos — a platta, an urn, "
                      "candlesticks.",
                      "Check the apartment first. A furnished rental may already have a fridge, a washing "
                      "machine and beds, and Israeli bed sizes are not the ones you know from abroad — "
                      "measure the mattress before anyone buys linen for it."],
                "p_he": ["לפני כל דבר נוי, רשמו את מה שתושיטו אליו יד בשבועות הראשונים: קומקום, משהו "
                         "לבשל בו, צלחות וסכו״ם לחלבי ולבשרי, מצעים שמתאימים למיטה, מגבות, ומה שצריך "
                         "לשבת — פלטה, מיחם, פמוטים.",
                         "קודם בודקים את הדירה. בדירה מרוהטת אולי כבר יש מקרר, מכונת כביסה ומיטות, "
                         "ומידות המיטות בישראל שונות ממה שמכירים בחו״ל — מודדים את המזרן לפני שמישהו "
                         "קונה לו מצעים."],
            },
            {
                "h": "Give every guest something to choose",
                "h_he": "שלכל אורח יהיה מה לבחור",
                "p": ["A list made only of big appliances leaves most guests with nothing in their range, "
                      "and a list of small things leaves the people who want to give something "
                      "substantial without a way to do it. Aim for a spread:"],
                "p_he": ["רשימה שכולה מוצרי חשמל גדולים משאירה את רוב האורחים בלי משהו בטווח שלהם, "
                         "ורשימה של דברים קטנים משאירה את מי שרוצה לתת משהו משמעותי בלי דרך לעשות "
                         "את זה. כדאי לפזר:"],
                "list": ["small gifts under about ₪150 — kitchen tools, towels, a challah cover",
                         "a middle band of ₪150–₪600 — a platta, an urn, dinnerware, a good pot set",
                         "a few large items — a fridge, a washing machine, a couch — for parents or "
                         "close family",
                         "a quantity above one where you really need several — two sheet sets, four towels"],
                "list_he": ["מתנות קטנות עד כ-₪150 — כלי מטבח, מגבות, כיסוי חלה",
                            "טווח ביניים של ₪150–₪600 — פלטה, מיחם, סט צלחות, סט סירים טוב",
                            "כמה פריטים גדולים — מקרר, מכונת כביסה, ספה — להורים או "
                            "למשפחה קרובה",
                            "כמות גדולה מאחת כשבאמת צריך כמה — שני סטים של מצעים, ארבע מגבות"],
            },
            {
                "h": "Think about where your guests are",
                "h_he": "לחשוב איפה האורחים נמצאים",
                "p": ["Relatives abroad usually find it easiest to order from an Israeli store that "
                      "delivers here, or to send money through your payment link and let you buy. "
                      "Guests in Israel may prefer Bit or PayBox. Adding each link you have gives every "
                      "guest a familiar way to give.",
                      "Write a delivery note: your address, a phone number for the courier, or where to "
                      "send things if you have not moved in yet. Guests see it only after they reserve "
                      "a gift, on their private page — it is never shown on the public list."],
                "p_he": ["לקרובים בחו״ל בדרך כלל הכי קל להזמין מחנות ישראלית שמשלחת לכאן, או לשלוח "
                         "כסף דרך קישור התשלום שלכם ולתת לכם לקנות. אורחים בארץ אולי יעדיפו Bit או "
                         "PayBox. כשמוסיפים כל קישור שיש לכם, לכל אורח יש דרך מוכרת לתת.",
                         "כתבו הערת משלוח: הכתובת שלכם, טלפון לשליח, או לאן לשלוח אם עוד לא נכנסתם "
                         "לדירה. האורחים רואים אותה רק אחרי ששריינו מתנה, בעמוד הפרטי שלהם — היא אף פעם "
                         "לא מוצגת ברשימה הציבורית."],
            },
            {
                "h": "Share it early and keep it current",
                "h_he": "לשתף מוקדם ולעדכן",
                "p": ["Put the link on the invitation or send it with the first WhatsApp message about "
                      "the wedding — guests who plan ahead like to give early. Mark the few things you "
                      "want most so they show first.",
                      "Come back to it as gifts arrive: confirm what reached you, write your thank-yous "
                      "while you still remember who sent what, and add a few more items if the list runs "
                      "out — the last guests to look should still find something to give."],
                "p_he": ["שימו את הקישור על ההזמנה או שלחו אותו עם הודעת הוואטסאפ הראשונה על החתונה — "
                         "אורחים שמתכננים מראש אוהבים לתת מוקדם. סמנו את הדברים הבודדים שהכי חשובים "
                         "לכם, כדי שיופיעו ראשונים.",
                         "חזרו לרשימה כשמתנות מגיעות: אשרו מה הגיע, כתבו תודות כל עוד אתם זוכרים מי "
                         "שלח מה, והוסיפו עוד כמה פריטים אם הרשימה נגמרת — גם האורחים האחרונים שנכנסים "
                         "צריכים למצוא מה לתת."],
            },
        ],
        "cta": "start",
    },
    {
        "slug": "appliances-from-abroad-or-buy-in-israel",
        "icon": "i-plug",
        "updated": "2026-11-10",
        "title": "Bringing appliances to Israel, or buying them here",
        "title_he": "להביא מכשירי חשמל לישראל או לקנות כאן",
        "summary": "What actually works on Israel's 230 V supply with just a plug adapter, what needs a "
                   "transformer and why that is rarely worth it, and how couples usually split the list "
                   "between suitcase and store.",
        "summary_he": "מה באמת עובד ברשת של 230 וולט עם מתאם תקע בלבד, מה דורש שנאי ולמה זה כמעט אף "
                      "פעם לא משתלם, ואיך זוגות בדרך כלל מחלקים את הרשימה בין המזוודה לחנות.",
        "sections": [
            {
                "h": "What the supply is, and what the label tells you",
                "h_he": "מה הרשת, ומה כתוב על התווית",
                "p": ["Israel runs on 230 V at 50 Hz. North America is 120 V at 60 Hz, so both numbers "
                      "differ. The UK is 230 V at 50 Hz, so British appliances match the supply and "
                      "only need a plug adapter. The plug itself is a separate question: Israeli "
                      "sockets are type H (three pins), and newer ones also take the two-pin europlug "
                      "(type C).",
                      "The rating label on the appliance or its power brick is the thing to read. "
                      "Look for “Input” followed by a voltage range and a frequency. “100-240 V, 50/60 "
                      "Hz” means it adapts by itself. A single figure such as “120 V, 60 Hz” means it "
                      "does not."],
                "p_he": ["ישראל פועלת על 230 וולט ב-50 הרץ. בצפון אמריקה זה 120 וולט ב-60 הרץ, כך ששני "
                         "המספרים שונים. בבריטניה זה 230 וולט ב-50 הרץ, ולכן מכשירים בריטיים מתאימים "
                         "לרשת וצריכים רק מתאם תקע. התקע עצמו הוא שאלה נפרדת: השקעים בישראל הם סוג H "
                         "(שלושה פינים), ושקעים חדשים יותר מקבלים גם תקע אירופי דו-פיני (סוג C).",
                         "מה שצריך לקרוא הוא תווית הנתונים על המכשיר או על המשנאי הקטן שלו. חפשו "
                         "Input ואחריו טווח מתח ותדר. ״100-240 V, 50/60 Hz״ אומר שהמכשיר מסתגל לבד. "
                         "מספר בודד כמו ״120 V, 60 Hz״ אומר שלא."],
            },
            {
                "h": "What works with just an adapter",
                "h_he": "מה עובד עם מתאם בלבד",
                "p": ["Anything electronic with a rating of 100-240 V is fine with a plug adapter and "
                      "nothing else. In practice that is most things with a small power brick. Check "
                      "each one rather than assuming, but these are usually marked this way:"],
                "p_he": ["כל מוצר אלקטרוני עם דירוג של 100-240 וולט מתאים עם מתאם תקע בלבד ושום דבר "
                         "נוסף. בפועל זה רוב המוצרים עם משנאי קטן. בדקו כל אחד ואל תניחו, אבל לרוב "
                         "הם מסומנים כך:"],
                "list": ["Phone, tablet and laptop chargers",
                         "Camera and e-reader chargers, power banks",
                         "Many electric toothbrush and shaver chargers",
                         "Many small speakers, routers and game consoles with an external power brick",
                         "A short extension strip with its own plug is often more convenient than "
                         "five separate adapters"],
                "list_he": ["מטענים של טלפון, טאבלט ומחשב נייד",
                            "מטענים של מצלמה וקורא ספרים אלקטרוני, וסוללות גיבוי",
                            "הרבה מטענים של מברשות שיניים ומכונות גילוח",
                            "הרבה רמקולים קטנים, ראוטרים וקונסולות משחקים עם משנאי חיצוני",
                            "מפצל חשמל קצר עם תקע ישראלי נוח הרבה יותר מחמישה מתאמים נפרדים"],
            },
            {
                "h": "What needs a transformer, and why it is usually not worth it",
                "h_he": "מה דורש שנאי, ולמה בדרך כלל זה לא משתלם",
                "p": ["A 120 V appliance that is not marked for 230 V needs a step-down transformer, "
                      "and the transformer has to be rated well above the appliance's wattage. Heating "
                      "appliances draw a lot: kettles, toasters, hair dryers, irons, hot plates, "
                      "coffee makers. A transformer big enough for them is heavy, costs money and is "
                      "one more box on the counter. These appliances are cheap to replace here, so "
                      "most people leave them behind.",
                      "Motors are a separate problem. Even with a transformer, a motor built for 60 Hz "
                      "can run slower and hotter on 50 Hz, and the manufacturer may not support that "
                      "use. Stand mixers, blenders, food processors and vacuum cleaners are the usual "
                      "examples. Anything that keeps time from the mains frequency has the same issue: "
                      "plug-in clocks, some older timers and some old record players.",
                      "Whether a particular model tolerates 50 Hz is for the manufacturer to say. If "
                      "you love the appliance, ask them before you pack it."],
                "p_he": ["מכשיר של 120 וולט שלא מסומן גם ל-230 וולט צריך שנאי מוריד מתח, והשנאי חייב "
                         "להיות מדורג בהרבה מעל הספק המכשיר. מכשירי חימום צורכים הרבה: קומקומים, טוסטרים, "
                         "מייבשי שיער, מגהצים, פלטות, מכונות קפה. שנאי שמספיק גדול בשבילם כבד, עולה "
                         "כסף והוא עוד קופסה על השיש. את המכשירים האלה קל וזול להחליף כאן, ולכן רוב "
                         "האנשים משאירים אותם מאחור.",
                         "מנועים הם בעיה נפרדת. גם עם שנאי, מנוע שנבנה ל-60 הרץ עלול לעבוד לאט יותר "
                         "ולהתחמם יותר ב-50 הרץ, והיצרן אולי לא תומך בשימוש כזה. מיקסרים, בלנדרים, "
                         "מעבדי מזון ושואבי אבק הם הדוגמאות הרגילות. כל מה שמודד זמן לפי תדר הרשת "
                         "סובל מאותה בעיה: שעוני קיר חשמליים, חלק מהטיימרים הישנים וחלק מפטיפונים ישנים.",
                         "אם דגם מסוים מתאים ל-50 הרץ, זו שאלה ליצרן. אם אתם אוהבים את המכשיר, שאלו "
                         "אותו לפני שאתם אורזים."],
            },
            {
                "h": "Warranty and service",
                "h_he": "אחריות ושירות",
                "p": ["A warranty from the country where you bought something often covers only that "
                      "country, and service centers here may not have parts or manuals for a model "
                      "sold elsewhere. Read the warranty terms before you decide, and do not assume "
                      "one carries over.",
                      "An appliance bought from an Israeli importer or store comes with its own "
                      "warranty and a local service line, which is a real advantage the first time "
                      "something breaks. Look at the product page or the box for who the importer is "
                      "and how to reach them."],
                "p_he": ["אחריות ממדינה שבה קניתם מכשיר מכסה לא פעם רק את אותה מדינה, ולמוקדי שירות "
                         "בארץ אולי אין חלפים או מדריכים לדגם שנמכר במקום אחר. קראו את תנאי האחריות "
                         "לפני שמחליטים, ואל תניחו שהיא עוברת איתכם.",
                         "מכשיר שנקנה מיבואן או מחנות ישראלית מגיע עם אחריות משלו ועם מוקד שירות "
                         "מקומי, וזה יתרון אמיתי בפעם הראשונה שמשהו מתקלקל. בדפי המוצר ועל האריזה "
                         "מופיע מי היבואן ואיך מגיעים אליו."],
            },
            {
                "h": "How couples usually split it",
                "h_he": "איך זוגות בדרך כלל מחלקים",
                "p": ["There is no single rule, but a sensible split is: bring "
                      "what is small, personal and universal, buy what heats, spins or is big. Fridges, "
                      "washing machines and ovens are bought here because they are sized for Israeli "
                      "kitchens and delivered and serviced locally."],
                "p_he": ["אין כלל אחד, אבל חלוקה הגיונית היא: מביאים את מה שקטן, אישי ואוניברסלי, "
                         "וקונים את מה שמחמם, מסתובב או גדול. מקררים, מכונות כביסה ותנורים נקנים כאן "
                         "כי הם בגודל שמתאים למטבחים בישראל, ומגיעים עם משלוח ושירות מקומיים."],
                "list": ["Usually brought: chargers, laptops, cameras, e-readers, small dual-voltage "
                         "electronics, hand tools without motors",
                         "Usually bought here: kettle, toaster oven, mixer, blender, iron, hair dryer, "
                         "vacuum, platta, urn",
                         "Always bought here: fridge, oven, washing machine, air conditioner"],
                "list_he": ["בדרך כלל מביאים: מטענים, מחשבים ניידים, מצלמות, קוראי ספרים, אלקטרוניקה "
                            "קטנה דו-מתחית, כלי יד בלי מנוע",
                            "בדרך כלל קונים כאן: קומקום, תנור משולב, מיקסר, בלנדר, מגהץ, מייבש שיער, "
                            "שואב אבק, פלטה, מיחם",
                            "תמיד קונים כאן: מקרר, תנור, מכונת כביסה, מזגן"],
            },
        ],
        "cta": "catalog",
    },
    {
        "slug": "israeli-bed-mattress-and-linen-sizes",
        "icon": "i-bed",
        "updated": "2026-11-10",
        "title": "Israeli bed, mattress and linen sizes for Americans and Brits",
        "title_he": "מידות מיטות, מזרנים ומצעים בישראל, לדוברי אנגלית",
        "summary": "Israeli beds are sold in centimetres and the names do not line up with Twin, Full, "
                   "Queen or UK single, double and king. Here is how the sizes map, why American sheets "
                   "often do not fit, and what to buy for two single beds.",
        "summary_he": "מיטות בישראל נמכרות בסנטימטרים, והשמות לא מתיישרים עם Twin, Full, Queen או "
                      "single, double ו-king הבריטיים. כך המידות מתאימות זו לזו, למה סדינים אמריקאיים "
                      "בדרך כלל לא מתאימים, ומה לקנות לשתי מיטות נפרדות.",
        "sections": [
            {
                "h": "The sizes you will see in Israel",
                "h_he": "המידות שתראו בישראל",
                "p": ["Israeli shops list bed bases and mattresses by width and length in centimetres. "
                      "The sizes couples usually shop from are below. Manufacturers vary by a few "
                      "centimetres, and a retailer may mention a tolerance on the product page, so "
                      "treat these as approximate and check the exact figure.",
                      "Hebrew names are also loose. A bed of 120 cm is often called a “mitah va-chetzi” "
                      "(a bed and a half), and 140 cm is the standard “zugit” (double), but the same "
                      "word is used a little differently in different shops. The centimetres are the "
                      "reliable part."],
                "p_he": ["חנויות בישראל מציגות בסיסי מיטה ומזרנים לפי רוחב ואורך בסנטימטרים. המידות "
                         "שזוגות בדרך כלל בוחרים מהן מופיעות ברשימה. יצרנים נבדלים בכמה סנטימטרים, "
                         "ולעיתים הקמעונאי מציין סטייה מותרת בדף המוצר, אז תתייחסו לזה כמשוער ובדקו "
                         "את המידה המדויקת.",
                         "גם השמות בעברית גמישים. מיטה של 120 ס״מ נקראת לרוב מיטה וחצי, ו-140 ס״מ היא "
                         "הזוגית הסטנדרטית, אבל אותה מילה משמשת קצת אחרת בחנויות שונות. הסנטימטרים הם "
                         "החלק האמין."],
                "list": ["80×190 or 90×190 (sometimes 90×200): single",
                         "120×190: a bed and a half, a large single",
                         "140×190: standard double",
                         "160×200: large double, close to a queen in width",
                         "180×200: king-sized double"],
                "list_he": ["80×190 או 90×190 (לפעמים 90×200): יחיד",
                            "120×190: מיטה וחצי, יחיד רחב",
                            "140×190: זוגית סטנדרטית",
                            "160×200: זוגית גדולה, קרובה לקווין ברוחב",
                            "180×200: זוגית בגודל קינג"],
            },
            {
                "h": "How they compare to US and UK sizes",
                "h_he": "איך זה מתאים למידות בארה״ב ובבריטניה",
                "p": ["The US sizes in centimetres are roughly: Twin 97×191, Full 137×191, Queen "
                      "152×203, King 193×203. UK nominal sizes are: single 90×190, small double "
                      "120×190, double 135×190, king 150×200, super king 180×200.",
                      "So an Israeli 90×190 is very close to a UK single and slightly narrower than a "
                      "Twin. A 140×190 sits near a US Full or a UK double. A 160×200 is wider but "
                      "shorter than a US Queen, and a 180×200 is narrower and shorter than a US King. "
                      "None is an exact match, and that is the point of the next section."],
                "p_he": ["המידות האמריקאיות בסנטימטרים הן בערך: Twin ‏97×191, Full ‏137×191, Queen "
                         "‏152×203, King ‏193×203. המידות הנומינליות הבריטיות: single ‏90×190, small "
                         "double ‏120×190, double ‏135×190, king ‏150×200, super king ‏180×200.",
                         "כלומר 90×190 ישראלי קרוב מאוד ל-single בריטי ומעט צר מ-Twin. 140×190 קרוב ל-Full "
                         "אמריקאי או ל-double בריטי. 160×200 רחב יותר אך קצר יותר מ-Queen אמריקאי, ו-180×200 "
                         "צר וקצר יותר מ-King אמריקאי. אף אחת מהן לא התאמה מדויקת, וזה העניין של הסעיף "
                         "הבא."],
            },
            {
                "h": "Why American fitted sheets often do not fit",
                "h_he": "למה סדינים מצויידים אמריקאיים בדרך כלל לא מתאימים",
                "p": ["A fitted sheet is cut to the mattress, so a size that is a few centimetres out "
                      "either strains the corners or sags. A US Queen sheet on a 160×200 mattress will "
                      "be too short at the head and foot, for example. Pocket depth matters as well: "
                      "American mattresses are often thick, and sheets for them have deep pockets that "
                      "can look baggy on a thinner one.",
                      "The simple rule is to measure the mattress itself, width, length and height, "
                      "before buying any linen, and to buy from a retailer that states the dimensions "
                      "and the pocket depth. If you bring sheets from abroad, check them against the "
                      "actual mattress rather than the name."],
                "p_he": ["סדין מצויד נחתך לפי המזרן, ולכן מידה שסוטה בכמה סנטימטרים או מותחת את "
                         "הפינות או נשארת רפויה. סדין Queen אמריקאי על מזרן של 160×200 יהיה קצר מדי "
                         "בראש וברגליים, למשל. גם עומק הכיס משנה: מזרנים אמריקאיים לרוב עבים, וסדינים "
                         "שלהם עם כיסים עמוקים נראים רפויים על מזרן דק יותר.",
                         "הכלל הפשוט הוא למדוד את המזרן עצמו, רוחב, אורך וגובה, לפני שקונים מצעים, "
                         "ולקנות מקמעונאי שמציין את המידות ואת עומק הכיס. אם מביאים סדינים מחו״ל, "
                         "בדקו אותם מול המזרן ולא מול השם."],
            },
            {
                "h": "Two single beds",
                "h_he": "שתי מיטות נפרדות",
                "p": ["Many frum couples sleep in two single beds, sometimes pushed together during "
                      "the weeks they are permitted and apart otherwise. Customs and practice differ "
                      "between families and communities, so choose what suits you and ask your rav if "
                      "you have a question. This guide is only about what to buy for it.",
                      "The practical consequence is that you buy everything twice: two 90×190 mattresses "
                      "(or 90×200), two mattress protectors, two fitted sheets, and a duvet and "
                      "pillows for each bed. A single bedspread over both beds is the usual way to make "
                      "the room look like one piece."],
                "p_he": ["הרבה זוגות חרדים ודתיים ישנים בשתי מיטות נפרדות, לפעמים צמודות בשבועות "
                         "שמותר ופרודות בשאר הזמן. המנהגים וההנהגה שונים בין משפחות וקהילות, אז בחרו "
                         "מה שמתאים לכם ושאלו את הרב שלכם אם יש לכם שאלה. המדריך הזה עוסק רק במה לקנות.",
                         "התוצאה המעשית היא שקונים הכול פעמיים: שני מזרנים של 90×190 (או 90×200), שני "
                         "מגני מזרן, שני סדינים מצוידים, ושמיכה וכריות לכל מיטה. כיסוי מיטה אחד על שתיהן "
                         "הוא הדרך הרגילה לגרום לחדר להיראות כמקשה אחת."],
                "list": ["Two single fitted sheets, sized to the mattress",
                         "Two single duvets and duvet covers",
                         "Two or four pillows with covers",
                         "Two mattress protectors, one per bed",
                         "If the beds will be placed together, ask the shop about a connector or a "
                         "single wide topper for the pair"],
                "list_he": ["שני סדינים מצוידים ליחיד, לפי מידת המזרן",
                            "שתי שמיכות ושני ציפות ליחיד",
                            "שתיים או ארבע כריות עם ציפיות",
                            "שני מגני מזרן, אחד לכל מיטה",
                            "אם המיטות יוצמדו, שאלו בחנות על מחבר או על טופר רחב אחד לשתיהן"],
            },
            {
                "h": "Duvets and pillows",
                "h_he": "שמיכות וכריות",
                "p": ["Duvet and pillow sizes follow the European pattern more than the American one. "
                      "A single duvet in Europe is commonly about 140×200, a double about 200×200, and a "
                      "larger double about 220×240. A pillow is often about 50×70, a little different "
                      "from the US standard pillow. Israeli shops and brands vary, so check the "
                      "dimensions listed rather than relying on Twin, Queen or King.",
                      "Buy the cover to match the duvet's stated size, not the bed's name. And if you "
                      "register for linen, write the mattress measurements on the registry so a guest "
                      "can pick the right set without guessing."],
                "p_he": ["מידות שמיכות וכריות קרובות יותר לדפוס האירופי מאשר לאמריקאי. שמיכה ליחיד "
                         "באירופה היא לרוב בערך 140×200, לזוגית בערך 200×200, ולזוגית גדולה בערך "
                         "220×240. כרית היא לרוב בערך 50×70, מעט שונה מכרית הסטנדרט האמריקאית. חנויות "
                         "ומותגים בישראל שונים זה מזה, אז בדקו את המידות הרשומות ואל תסתמכו על Twin, "
                         "Queen או King.",
                         "קנו את הציפה לפי המידה הרשומה של השמיכה, לא לפי שם המיטה. ואם אתם רושמים "
                         "מצעים ברשימה, כתבו שם את מידות המזרן כדי שאורח יוכל לבחור את הסט הנכון בלי "
                         "לנחש."],
            },
        ],
        "cta": "sample",
    },
    {
        "slug": "shabbos-kitchen-equipment-buying-guide",
        "icon": "i-candles",
        "updated": "2026-11-10",
        "title": "Shabbos kitchen equipment: what to look for when buying",
        "title_he": "ציוד מטבח לשבת: על מה להסתכל כשקונים",
        "summary": "Platta, urn or Shabbos kettle, Shabbos clock, slow cooker and lamp: sizes, wattage and "
                   "safety marks worth checking, and what suits a couple compared with a household "
                   "that hosts.",
        "summary_he": "פלטה, מיחם או קומקום שבת, שעון שבת, סיר בישול איטי ומנורה: גדלים, הספק וסימוני "
                      "בטיחות שכדאי לבדוק, ומה מתאים לזוג לעומת בית שמארח.",
        "sections": [
            {
                "h": "Before you buy: what this guide covers",
                "h_he": "לפני שקונים: על מה המדריך הזה",
                "p": ["This is about the appliances themselves: size, power, build and how long they "
                      "last. How each one may be used on Shabbos, and what a given household does "
                      "with it, differs between families and communities. Those are questions for your "
                      "own rav, and we do not answer them here.",
                      "If you read the kitchen basics guide first, this one goes one level deeper "
                      "into what to compare in the shop."],
                "p_he": ["המדריך הזה עוסק במכשירים עצמם: גודל, הספק, בנייה וכמה זמן הם מחזיקים. איך "
                         "מותר להשתמש בכל אחד מהם בשבת, ומה בית מסוים עושה איתו, שונה בין משפחות "
                         "וקהילות. אלה שאלות לרב שלכם, ואנחנו לא עונים עליהן כאן.",
                         "אם קראתם קודם את מדריך יסודות המטבח הכשר, המדריך הזה יורד רמה אחת לעומק "
                         "ומסביר מה להשוות בחנות."],
            },
            {
                "h": "The platta (hot plate)",
                "h_he": "הפלטה",
                "p": ["Plattas are sold as a flat sheet of metal or glass-ceramic with a control, and "
                      "the main differences are size, material and how the heat is spread. Think in "
                      "terms of the pots you actually own: the surface has to hold them with room "
                      "around each. A larger platta gives more flexibility but needs more counter "
                      "space and draws more power, so look at the wattage on the label and at the "
                      "circuit you will plug it into.",
                      "Cheaper plattas tend to heat unevenly and are the item couples mention replacing "
                      "within a year. Metal-surface models are easier to wipe; glass surfaces look "
                      "cleaner but can be damaged by dragging pots."],
                "p_he": ["פלטות נמכרות כמשטח של מתכת או קרמיקת זכוכית עם בקרה, וההבדלים העיקריים הם "
                         "גודל, חומר ואיך החום מתפזר. תחשבו על הסירים שיש לכם בפועל: המשטח צריך להכיל "
                         "אותם עם מקום סביב כל אחד. פלטה גדולה יותר נותנת גמישות אבל דורשת יותר מקום "
                         "על השיש וצורכת יותר חשמל, אז הסתכלו על ההספק בתווית ועל המעגל שאליו "
                         "תחברו אותה.",
                         "פלטות זולות נוטות להתחמם בצורה לא אחידה, והן הפריט שזוגות מספרים שהחליפו "
                         "תוך שנה. דגמים עם משטח מתכת קלים יותר לניגוב; משטחי זכוכית נראים נקיים יותר "
                         "אבל אפשר לפגוע בהם בגרירת סירים."],
            },
            {
                "h": "Urn (meicham) or Shabbos kettle",
                "h_he": "מיחם או קומקום שבת",
                "p": ["An urn is a large insulated hot water container that holds water hot for a long "
                      "time, usually with a tap. A Shabbos kettle or a hot water pump pot is smaller "
                      "and often has a pump-action spout. Capacity is listed in litres on the product "
                      "page, and the practical question is how much hot water you use: a couple who "
                      "has Shabbos meals alone is fine with a smaller one, and hosting a table of "
                      "guests is where a bigger one helps.",
                      "Compare the weight when full, the stability of the base, and whether the tap or "
                      "pump is easy to clean. Where space is tight, the smaller pot is the practical "
                      "choice."],
                "p_he": ["מיחם הוא מיכל גדול ומבודד למים חמים שמחזיק את המים חמים זמן רב, בדרך כלל עם "
                         "ברז. קומקום שבת או תרמוס משאבה קטנים יותר ולרוב עם פיה שפועלת בלחיצה. "
                         "הקיבולת רשומה בליטרים בדף המוצר, והשאלה המעשית היא כמה מים חמים אתם צורכים: "
                         "זוג שאוכל סעודות שבת לבד מסתדר עם קטן יותר, ובית שמארח שולחן אורחים נהנה "
                         "מגדול יותר.",
                         "השוו משקל כשהוא מלא, יציבות הבסיס, והאם הברז או המשאבה קלים לניקוי. כשהמקום "
                         "צר, הסיר הקטן הוא הבחירה המעשית."],
            },
            {
                "h": "Shabbos clock, slow cooker and lamp",
                "h_he": "שעון שבת, סיר בישול איטי ומנורה",
                "p": ["A Shabbos clock is a plug-in timer. Look at the maximum load printed on it, in "
                      "amps or watts, and make sure it is higher than the appliance you plan to run "
                      "through it. Mechanical and digital types are both sold; both are cheap enough to "
                      "have a spare. A 60 Hz timer from abroad may not keep correct time on Israel's "
                      "50 Hz, which is one more reason to buy it here.",
                      "A slow cooker for cholent is about capacity. A smaller one, around 3 to 4 "
                      "litres, suits two people; a hosting household usually wants closer to 6 litres "
                      "or more. A removable ceramic insert is easier to clean than a fixed one.",
                      "A Shabbos lamp is a bedside lamp that stays on, with a shade you slide or "
                      "twist closed to cover the light. Check that the cover closes fully, that "
                      "the base is stable, and which bulb it takes so you can replace it."],
                "p_he": ["שעון שבת הוא טיימר שמחברים לשקע. הסתכלו על העומס המרבי המודפס עליו, באמפר "
                         "או בוואט, וודאו שהוא גבוה מהמכשיר שאתם מתכוונים לחבר דרכו. נמכרים סוגים "
                         "מכניים ודיגיטליים, ושניהם זולים מספיק כדי שיהיה אחד רזרבי. טיימר של 60 הרץ "
                         "מחו״ל אולי לא ישמור זמן נכון ברשת של 50 הרץ בישראל, ועוד סיבה לקנות אותו כאן.",
                         "סיר בישול איטי לצ׳ולנט הוא עניין של נפח. סיר קטן, בערך 3 עד 4 ליטר, מתאים "
                         "לשניים; בית שמארח בדרך כלל רוצה קרוב ל-6 ליטר ומעלה. תבנית קרמית נשלפת קלה "
                         "יותר לניקוי מתבנית קבועה.",
                         "מנורת שבת היא מנורת לילה שנשארת דולקת, עם כיסוי שמזיזים או מסובבים כדי "
                         "להסתיר את האור. בדקו שהכיסוי נסגר עד הסוף, שהבסיס יציב, ואיזו נורה "
                         "מתאימה לה כדי שתוכלו להחליף."],
            },
            {
                "h": "Safety marks and cords",
                "h_he": "סימוני בטיחות וכבלים",
                "p": ["Many household electrical appliances have to meet an Israeli standard before "
                      "they can be sold here. When you compare, prefer an appliance sold through an "
                      "Israeli importer, check the product page or the box for the Israeli standard "
                      "mark or the importer's details, and ask the shop if it is not shown. Avoid "
                      "unbranded imports with no importer listed.",
                      "Whatever you buy, plug heavy appliances like the platta and the urn directly "
                      "into a wall socket if the manufacturer says so, and use an extension only if "
                      "its rating is higher than the appliance. Check the instructions rather than "
                      "relying on us for any particular model."],
                "p_he": ["הרבה מכשירי חשמל ביתיים חייבים לעמוד בתקן ישראלי לפני שמותר למכור אותם כאן. "
                         "כשמשווים, העדיפו מכשיר שנמכר דרך יבואן ישראלי, בדקו בדף המוצר או על האריזה "
                         "אם מופיע תו תקן ישראלי או פרטי היבואן, ושאלו בחנות אם לא רשום. הימנעו "
                         "מיבוא פרטי ללא מותג וללא יבואן מצוין.",
                         "מה שלא תקנו, חברו מכשירים כבדים כמו פלטה ומיחם ישירות לשקע בקיר אם היצרן "
                         "אומר כך, והשתמשו במאריך רק אם הדירוג שלו גבוה מזה של המכשיר. קראו את "
                         "ההוראות ואל תסמכו עלינו לגבי דגם מסוים."],
            },
            {
                "h": "A short list by household",
                "h_he": "רשימה קצרה לפי סוג הבית",
                "p": ["The right size depends more on how often you host than on how big the apartment "
                      "is."],
                "p_he": ["הגודל הנכון תלוי יותר בתדירות האירוח מאשר בגודל הדירה."],
                "list": ["A couple at home most Shabbosos: a platta that holds two or three pots, a "
                         "smaller urn or hot water pump pot, a 3 to 4 litre slow cooker, one Shabbos "
                         "clock",
                         "A couple who hosts every few weeks: a larger platta, a bigger urn, a 6 litre "
                         "slow cooker, two clocks",
                         "Either way: a spare Shabbos clock, since they are the part most likely to "
                         "fail"],
                "list_he": ["זוג שבבית רוב השבתות: פלטה שמכילה שניים-שלושה סירים, מיחם קטן יותר או "
                            "תרמוס משאבה, סיר בישול איטי של 3 עד 4 ליטר, שעון שבת אחד",
                            "זוג שמארח כל כמה שבועות: פלטה גדולה יותר, מיחם גדול יותר, סיר בישול "
                            "איטי של 6 ליטר, שני שעונים",
                            "בכל מקרה: שעון שבת רזרבי, כי הוא החלק שהכי סביר שייכשל"],
            },
        ],
        "cta": "catalog",
    },
    {
        "slug": "wedding-gifts-israel-guests-from-abroad",
        "icon": "i-gift",
        "updated": "2026-11-10",
        "title": "Wedding gifts in Israel: what to give and how to send it",
        "title_he": "מתנות חתונה בישראל: מה לתת ואיך לשלוח",
        "summary": "In Israel most wedding guests give money, not a household item. A tactful look at "
                   "that custom, how family and friends abroad can send a gift, and what to know about "
                   "currency, fees and giving in multiples of 18.",
        "summary_he": "בישראל רוב אורחי החתונה נותנים כסף ולא חפץ לבית. מבט עדין על המנהג, איך משפחה "
                      "וחברים בחו״ל יכולים לשלוח מתנה, ומה כדאי לדעת על מטבע, עמלות ונתינה בכפולות של 18.",
        "sections": [
            {
                "h": "What Israelis usually give",
                "h_he": "מה ישראלים בדרך כלל נותנים",
                "p": ["At an Israeli wedding the common custom is to give money, often in an envelope "
                      "handed over at the event or in a box near the entrance. This is different from "
                      "the habit in many countries abroad of buying something from a registry. Both are "
                      "normal. They are two different gifting cultures, and a couple with guests from "
                      "both is usually glad to receive either.",
                      "Some couples and families see the gift as helping the couple start their home. "
                      "Others, especially in secular circles, think of it partly as covering the guest's "
                      "share of the evening. Practice varies a lot between communities, so there is no "
                      "single rule to follow."],
                "p_he": ["בחתונה ישראלית המנהג הנפוץ הוא לתת כסף, לרוב במעטפה שמוסרים באירוע או "
                         "בקופסה ליד הכניסה. זה שונה מהרגל בהרבה מדינות בחו״ל לקנות משהו מרשימת מתנות. "
                         "שניהם נורמליים. אלה שתי תרבויות נתינה שונות, וזוג עם אורחים משתיהן בדרך כלל "
                         "שמח לקבל כל אחת.",
                         "יש זוגות ומשפחות שרואים בתשורה עזרה לזוג להקים בית. אחרים, במיוחד בחוגים "
                         "חילוניים, חושבים עליה גם כעל כיסוי חלקו של האורח בערב. המנהגים שונים מאוד "
                         "בין קהילות, ולכן אין כלל אחד שאפשר לפעול לפיו."],
            },
            {
                "h": "How much",
                "h_he": "כמה",
                "p": ["We do not give a figure, because there is no honest one. You will see ranges "
                      "quoted in the Israeli press and on forums, and they differ by how close you are "
                      "to the couple, which community the wedding is in, which city, and whether you "
                      "are a couple or a family attending. These are commonly cited ranges, not norms "
                      "anyone has to follow.",
                      "A better guide is your own situation. Give what you can comfortably give, and "
                      "ask a relative or friend who knows the family and the community if you are "
                      "unsure. A thoughtful gift that is within your means is welcome in any amount."],
                "p_he": ["אנחנו לא נותנים מספר, כי אין מספר ישר. תראו טווחים שמצוטטים בעיתונות "
                         "הישראלית ובפורומים, והם משתנים לפי הקרבה לזוג, באיזו קהילה החתונה, באיזו עיר, "
                         "והאם מגיע זוג או משפחה. אלה טווחים שמצוטטים בדרך כלל, לא נורמות שמישהו חייב "
                         "לעמוד בהן.",
                         "מדריך טוב יותר הוא המצב שלכם. תנו מה שנוח לכם לתת, ושאלו קרוב משפחה או חבר "
                         "שמכיר את המשפחה ואת הקהילה אם אתם לא בטוחים. מתנה מחושבת שבהישג ידכם מתקבלת "
                         "בברכה בכל סכום."],
            },
            {
                "h": "Giving in multiples of 18",
                "h_he": "נתינה בכפולות של 18",
                "p": ["Many people give in multiples of 18, since the Hebrew letters chet and yud spell "
                      "chai, life, and have the numerical value 18. It is a custom and not a rule. "
                      "Some families follow it closely, some do not mention it at all, and in a mixed "
                      "crowd nobody will notice either way.",
                      "If you want to follow it, round to the nearest multiple in your own currency "
                      "or in shekels. Whatever you choose, the sincerity of the gift matters more "
                      "than the number."],
                "p_he": ["הרבה אנשים נותנים בכפולות של 18, כי האותיות חית ויוד מרכיבות את המילה חי "
                         "וערכן המספרי 18. זה מנהג ולא חובה. יש משפחות שמקפידות, יש שלא מזכירות את "
                         "זה בכלל, ובקהל מעורב אף אחד לא ישים לב כך או כך.",
                         "אם רוצים לנהוג כך, מעגלים לכפולה הקרובה במטבע שלכם או בשקלים. מה שלא תבחרו, "
                         "הכנות של המתנה חשובה יותר מהמספר."],
            },
            {
                "h": "Sending a gift from abroad",
                "h_he": "לשלוח מתנה מחו״ל",
                "p": ["The options for family and friends abroad are the same as for any gift, and "
                      "the couple chooses which they want. You can use the couple's own payment link, "
                      "usually PayPal; buy a registry item from an Israeli store that delivers in "
                      "Israel, which saves shipping and customs; or send a personal item by post.",
                      "Bit and PayBox are Israeli apps that are generally set up around Israeli "
                      "phone numbers and bank accounts, so they are mainly for guests who live in "
                      "Israel. If you are abroad, ask whether the couple has a PayPal link or can "
                      "accept a bank transfer, and do not send an envelope of cash by post."],
                "p_he": ["האפשרויות לקרובים ולחברים בחו״ל זהות לכל מתנה, והזוג בוחר מה הוא מעדיף. "
                         "אפשר להשתמש בקישור התשלום של הזוג, בדרך כלל PayPal; לקנות פריט מהרשימה "
                         "מחנות ישראלית שמשלחת בישראל, וכך חוסכים משלוח ומכס; או לשלוח חפץ אישי בדואר.",
                         "Bit ו-PayBox הן אפליקציות ישראליות שבדרך כלל מוגדרות סביב מספרי טלפון "
                         "וחשבונות בנק ישראליים, ולכן הן בעיקר לאורחים שחיים בארץ. אם אתם בחו״ל, שאלו "
                         "אם לזוג יש קישור PayPal או שהוא יכול לקבל העברה בנקאית, ואל תשלחו מעטפה עם "
                         "מזומן בדואר."],
                "list": ["Use the link the couple gave, not one passed along second-hand",
                         "Ask them first; do not guess which method they accept",
                         "Keep a screenshot or confirmation so you can tell them it was sent"],
                "list_he": ["השתמשו בקישור שהזוג נתן, לא בקישור שהועבר דרך אחרים",
                            "שאלו אותם קודם ואל תנחשו באיזו שיטה הם מקבלים",
                            "שמרו צילום מסך או אישור כדי שתוכלו לספר להם שנשלח"],
            },
            {
                "h": "Currency and fees",
                "h_he": "מטבע ועמלות",
                "p": ["Your gift is probably in dollars, pounds or another currency, and the couple "
                      "will spend it in shekels. Somewhere in the chain the money is converted, and "
                      "that costs something: a conversion margin, a transfer fee, or both. The amounts "
                      "depend on the service, the size of the gift and the route, and they change, so "
                      "compare before you send.",
                      "Ask yourself two things: who pays the fee, and which rate is used? Some "
                      "services show the receiving amount before you confirm. A larger gift sent less "
                      "often is usually cheaper than several small ones if the fee has a fixed part. "
                      "OurBayis never touches the money; it goes straight from you to the couple."],
                "p_he": ["המתנה שלכם כנראה בדולרים, בלירות שטרלינג או במטבע אחר, והזוג יוציא אותה "
                         "בשקלים. איפשהו בדרך הכסף מומר, וזה עולה: מרווח המרה, עמלת העברה או שניהם. "
                         "הסכומים תלויים בשירות, בגודל המתנה ובמסלול, והם משתנים, אז השוו לפני "
                         "ששולחים.",
                         "שאלו שני דברים: מי משלם את העמלה, ובאיזה שער? יש שירותים שמראים את הסכום "
                         "שיתקבל לפני האישור. מתנה גדולה יותר שנשלחת פחות פעמים בדרך כלל זולה יותר מכמה "
                         "קטנות אם יש עמלה עם חלק קבוע. OurBayis אף פעם לא נוגע בכסף; הוא עובר ישירות "
                         "מכם לזוג."],
            },
            {
                "h": "Writing the card",
                "h_he": "לכתוב את הברכה",
                "p": ["Whatever you send, add a short note. A couple opening a lot of envelopes and "
                      "payment notifications will remember who wrote a few warm lines. If you gave "
                      "through a registry, your private page tells the couple what is coming, and a "
                      "note on top of that is the personal part."],
                "p_he": ["מה שלא שולחים, הוסיפו ברכה קצרה. זוג שפותח הרבה מעטפות והתראות תשלום "
                         "יזכור מי כתב כמה שורות חמות. אם נתתם דרך רשימת מתנות, העמוד הפרטי שלכם "
                         "מספר לזוג מה בדרך, וברכה מעל זה היא החלק האישי."],
            },
        ],
        "cta": "sample",
    },
    {
        "slug": "where-to-shop-for-a-home-in-israel",
        "icon": "i-house",
        "updated": "2026-11-10",
        "title": "Where to shop for a home in Israel",
        "title_he": "איפה קונים לבית בישראל",
        "summary": "An orientation to the kinds of stores couples use, how delivery and installation "
                   "usually work, and what Israeli consumer law says about returns. No rankings, "
                   "just how the landscape is laid out.",
        "summary_he": "היכרות עם סוגי החנויות שזוגות משתמשים בהן, איך משלוח והתקנה בדרך כלל עובדים, "
                      "ומה חוק הגנת הצרכן אומר על החזרות. בלי דירוגים, רק איך המפה בנויה.",
        "sections": [
            {
                "h": "Electronics and appliance chains",
                "h_he": "רשתות אלקטרוניקה ומוצרי חשמל",
                "p": ["For large and small appliances, the names you will meet most are KSP and "
                      "Machsanei Chashmal, alongside a long tail of local electrical-goods stores. "
                      "Fridges, washing machines, ovens, air conditioners and kitchen appliances are "
                      "all sold through them, and most also sell online and deliver.",
                      "These chains have different ranges and promotions, and they change. We make no "
                      "ranking: compare the same model across two or three of them, and use the "
                      "importer's warranty details on the product page to see who stands behind it."],
                "p_he": ["למוצרי חשמל קטנים וגדולים, השמות שתפגשו הכי הרבה הם KSP ומחסני חשמל, "
                         "לצד שובל ארוך של חנויות חשמל מקומיות. מקררים, מכונות כביסה, תנורים, מזגנים "
                         "ומכשירי מטבח נמכרים בכולן, ורובן מוכרות גם אונליין ומשלחות.",
                         "לרשתות האלה יש מגוון ומבצעים שונים, והם משתנים. אנחנו לא מדרגים: השוו את "
                         "אותו דגם בשתיים-שלוש מהן, והשתמשו בפרטי האחריות של היבואן בדף המוצר כדי "
                         "לראות מי עומד מאחוריו."],
            },
            {
                "h": "Home, kitchen and linen stores",
                "h_he": "חנויות לבית, למטבח ולמצעים",
                "p": ["For everything that is not an appliance there are several well-known "
                      "chains: Home Center and IKEA Israel for furniture and household goods, Fox Home "
                      "and Golf & Co for home and kitchen items, Naaman for tableware and kitchenware, "
                      "and Vardinon for textiles and home goods. Each has its own mix, and the "
                      "selection and prices move with the season.",
                      "Check the current website or the nearest branch before planning a trip, since "
                      "branch lists and what each chain stocks change from year to year."],
                "p_he": ["לכל מה שאינו מכשיר חשמלי יש כמה רשתות מוכרות: הום סנטר ואיקאה ישראל "
                         "לרהיטים ולמוצרי בית, פוקס הום וגולף ושות׳ לפריטי בית ומטבח, נעמן לכלי שולחן "
                         "ומטבח, וורדינון לטקסטיל ולמוצרי בית. לכל אחת תמהיל משלה, והמגוון והמחירים "
                         "משתנים לפי העונה.",
                         "בדקו את האתר העדכני או את הסניף הקרוב לפני שמתכננים נסיעה, כי רשימת הסניפים "
                         "ומה שכל רשת מחזיקה משתנים משנה לשנה."],
            },
            {
                "h": "Judaica, local shops and second-hand",
                "h_he": "יודאיקה, חנויות שכונתיות ויד שנייה",
                "p": ["Judaica and seforim shops, which you will find in religious neighbourhoods and "
                      "town centres, are the usual place for candlesticks, a kiddush cup, a challah "
                      "board, a netilas yadayim cup and bentchers. Small neighbourhood housewares "
                      "shops (klei bayis) often have the odd thing a chain does not.",
                      "For second-hand furniture and appliances, many people use Yad2 and community "
                      "groups, especially for a first apartment. Check anything electrical before "
                      "you take it, and ask whether the seller has a warranty or receipt."],
                "p_he": ["חנויות יודאיקה וספרים, שתמצאו בשכונות דתיות ובמרכזי ערים, הן המקום הרגיל "
                         "לפמוטים, גביע קידוש, מגש חלה, נטלה וברכונים. חנויות כלי בית שכונתיות קטנות "
                         "מחזיקות לא פעם את הפריט המיוחד שלרשת אין.",
                         "לרהיטים ומכשירי חשמל יד שנייה, הרבה אנשים משתמשים ביד2 ובקבוצות קהילה, "
                         "במיוחד לדירה ראשונה. בדקו כל דבר חשמלי לפני שלוקחים אותו, ושאלו אם למוכר יש "
                         "אחריות או קבלה."],
            },
            {
                "h": "Comparing prices",
                "h_he": "השוואת מחירים",
                "p": ["Zap (zap.co.il) is a price-comparison site that lists the same product across "
                      "many stores, with a recorded range. It is a useful starting point, but check "
                      "the store's own page before you buy: the price, the stock and the delivery "
                      "terms may differ from the comparison listing.",
                      "A cheaper price from a seller you have never heard of can mean no local "
                      "warranty or a slower return. Compare the whole offer: delivery, installation, "
                      "warranty and who the importer is."],
                "p_he": ["Zap‏ (zap.co.il) הוא אתר להשוואת מחירים שמציג את אותו מוצר ברבות מהחנויות, "
                         "עם טווח מחירים. זו נקודת פתיחה שימושית, אבל בדקו את עמוד החנות עצמה לפני "
                         "שקונים: המחיר, המלאי ותנאי המשלוח עשויים להיות שונים מהרישום בהשוואה.",
                         "מחיר זול יותר ממוכר שלא שמעתם עליו יכול להעיד על חוסר אחריות מקומית או "
                         "החזרה איטית יותר. השוו את ההצעה כולה: משלוח, התקנה, אחריות ומי היבואן."],
            },
            {
                "h": "Delivery and installation",
                "h_he": "משלוח והתקנה",
                "p": ["Large items come by scheduled delivery (hovala) in a time window. Ask "
                      "before ordering what floor the delivery goes to, whether the price includes "
                      "carrying it upstairs when there is no elevator, and whether the crew takes away "
                      "the old unit. Floor and elevator access are common reasons for extra charges.",
                      "Installation (hatkana) is a separate service for items such as air conditioners, "
                      "ovens, dishwashers and wall-mounted TVs. In some cases it is included or "
                      "available as an add-on, and in others you hire your own technician. Ask for it "
                      "in writing, and find out who is responsible if something is damaged."],
                "p_he": ["פריטים גדולים מגיעים בהובלה בחלון זמן מתואם. שאלו לפני ההזמנה לאיזו קומה "
                         "המשלוח מגיע, האם המחיר כולל נשיאה במעלה המדרגות כשאין מעלית, והאם הצוות "
                         "לוקח את המכשיר הישן. קומה וגישה למעלית הן סיבות נפוצות לתוספת תשלום.",
                         "התקנה היא שירות נפרד לפריטים כמו מזגנים, תנורים, מדיחים וטלוויזיות תלויות. "
                         "לעיתים היא כלולה או זמינה כתוספת, ולעיתים שוכרים טכנאי משלכם. בקשו אותה "
                         "בכתב, ובררו מי אחראי אם משהו ניזוק."],
            },
            {
                "h": "Returns under Israeli consumer law",
                "h_he": "החזרות לפי חוק הגנת הצרכן",
                "p": ["For purchases made remotely, such as online or by phone, the Consumer "
                      "Protection Law generally lets you cancel within 14 days, with the seller allowed "
                      "to charge a cancellation fee of up to 5 percent of the price or ₪100, whichever "
                      "is lower. There are exceptions, for example for made-to-order goods, and in some "
                      "cases the period is longer for olim, people with disabilities and people over "
                      "65. Check the exact conditions with the Ministry of Justice or Kol Zchut "
                      "before relying on them.",
                      "In a physical shop, the law does not generally give you a right to return a "
                      "product that works and that you simply changed your mind about. Returns there "
                      "depend on the store's own policy, which is often posted and may be generous, so "
                      "ask before buying and keep the receipt. A defective product is a different "
                      "matter and you are entitled to a remedy."],
                "p_he": ["בקניות שנעשות מרחוק, כמו באינטרנט או בטלפון, חוק הגנת הצרכן מאפשר בדרך "
                         "כלל לבטל תוך 14 יום, כשהמוכר רשאי לגבות דמי ביטול של עד 5 אחוזים ממחיר "
                         "העסקה או ₪100, לפי הנמוך מביניהם. יש חריגים, למשל מוצרים שנעשו בהזמנה "
                         "אישית, ובמקרים מסוימים התקופה ארוכה יותר לעולים חדשים, לאנשים עם מוגבלות "
                         "ולבני 65 ומעלה. בדקו את התנאים המדויקים באתר משרד המשפטים או בכל זכות לפני "
                         "שמסתמכים עליהם.",
                         "בחנות פיזית, החוק בדרך כלל לא נותן זכות להחזיר מוצר שעובד ושסתם התחרטתם עליו. "
                         "ההחזרה שם תלויה במדיניות של החנות, שלעיתים מפורסמת ויכולה להיות נדיבה, אז "
                         "שאלו לפני הקנייה ושמרו את הקבלה. מוצר פגום הוא עניין אחר, ומגיע לכם תיקון "
                         "או פתרון."],
            },
        ],
        "cta": "catalog",
    },
    {
        "slug": "first-yom-tov-year-in-a-new-home",
        "icon": "i-star",
        "updated": "2026-11-10",
        "title": "Your first year of Yom Tov in a new home: a checklist by season",
        "title_he": "שנת החגים הראשונה בבית חדש: רשימה לפי עונה",
        "summary": "What a couple tends to need as the year goes round, from Rosh Hashanah and "
                   "Sukkos through Chanukah, Purim, Pesach and Shavuos, so nothing is a surprise the "
                   "week before.",
        "summary_he": "מה זוג נוטה להזדקק לו ככל שהשנה מתגלגלת, מראש השנה וסוכות דרך חנוכה, פורים, "
                      "פסח ושבועות, כך שדבר לא יהיה הפתעה בשבוע שלפני.",
        "sections": [
            {
                "h": "Rosh Hashanah and the days after",
                "h_he": "ראש השנה והימים שאחריו",
                "p": ["The first Yom Tov in a new home is usually Rosh Hashanah, and it comes with a "
                      "full table. Most of what you need is already on the Shabbos list, plus a few "
                      "items for the simanim and for hosting. Questions about shofar and which customs "
                      "to follow go to your rav."],
                "p_he": ["החג הראשון בבית החדש הוא לרוב ראש השנה, והוא מגיע עם שולחן מלא. רוב מה "
                         "שצריך כבר ברשימת השבת, ועוד כמה פריטים לסימנים ולאירוח. שאלות על שופר ועל "
                         "איזה מנהגים לנהוג מופנות לרב שלכם."],
                "list": ["Machzorim, one per person at the table",
                         "A honey dish and a round challah board or cover",
                         "Serving plates for the simanim, and a small apple-and-honey set",
                         "A larger table or folding extension and chairs for guests",
                         "Enough platta space and hot water for a full holiday table"],
                "list_he": ["מחזורים, אחד לכל אדם בשולחן",
                            "קערת דבש ומגש או כיסוי עגול לחלה",
                            "צלחות הגשה לסימנים וסט קטן של תפוח בדבש",
                            "שולחן גדול יותר או הרחבה מתקפלת וכיסאות לאורחים",
                            "מספיק מקום על הפלטה ומים חמים לשולחן חג מלא"],
            },
            {
                "h": "Sukkos",
                "h_he": "סוכות",
                "p": ["The sukkah is the big decision. Many apartments have a sukkah balcony, and in "
                      "others the building has a shared spot. Ask your landlord and the building "
                      "committee in good time, and measure the space before choosing a kit. Which "
                      "schach and which sukkah materials to use is a halachic question for your rav. "
                      "Sukkah kits and schach are sold in the weeks before Sukkos by Judaica shops and "
                      "larger chains.",
                      "The arba minim are usually bought separately, a few weeks before, and a lot "
                      "of people ask their rav or a trusted seller about which set to choose."],
                "p_he": ["הסוכה היא ההחלטה הגדולה. בהרבה דירות יש מרפסת סוכה, ובאחרות לבניין יש "
                         "מקום משותף. שאלו את בעל הדירה ואת ועד הבית בזמן, ומדדו את המקום לפני שבוחרים "
                         "ערכה. איזה סכך ואילו חומרי סוכה להשתמש הן שאלות הלכתיות לרב שלכם. ערכות "
                         "סוכה וסכך נמכרות בשבועות שלפני סוכות בחנויות יודאיקה וברשתות גדולות.",
                         "ארבעת המינים נקנים בדרך כלל בנפרד, כמה שבועות לפני, והרבה אנשים שואלים את "
                         "הרב או מוכר אמין איזו ערכה לבחור."],
                "list": ["Sukkah frame or kit, and schach (check with your rav)",
                         "Decorations, string and hooks that hold in the wind",
                         "A lulav holder (koishel) and a box for the esrog",
                         "A sukkah table, benches and a light with a weatherproof cord",
                         "A way to carry food out: a trolley or trays"],
                "list_he": ["שלד או ערכת סוכה וסכך (בדקו עם הרב)",
                            "קישוטים, חוט וווים שמחזיקים ברוח",
                            "נרתיק ללולב וקופסה לאתרוג",
                            "שולחן סוכה, ספסלים ותאורה עם כבל עמיד למזג אוויר",
                            "דרך לשאת אוכל החוצה: עגלה או מגשים"],
            },
            {
                "h": "Chanukah and Purim",
                "h_he": "חנוכה ופורים",
                "p": ["For Chanukah you need a chanukiah and a supply of oil with wicks or candles, "
                      "whichever your family uses. Match the candles to the holders, and put the "
                      "chanukiah on a tray that catches the drips. Where and how you light is "
                      "something to ask your rav, and it differs between homes.",
                      "Purim is mostly the mishloach manos season. Baskets, boxes and cellophane are "
                      "sold in the weeks before, and a Megillah, a costume and a table for the seudah "
                      "round it out."],
                "p_he": ["לחנוכה צריך חנוכייה ומלאי שמן עם פתילות או נרות, לפי מה שהמשפחה נוהגת. "
                         "התאימו את הנרות לבתים, והעמידו את החנוכייה על מגש שתופס טיפות. איפה ואיך "
                         "מדליקים הוא עניין לשאול את הרב, והוא שונה בין בתים.",
                         "פורים הוא בעיקר עונת משלוחי מנות. סלים, קופסאות וצלופן נמכרים בשבועות שלפני, "
                         "ומגילה, תחפושת ושולחן לסעודה משלימים."],
                "list": ["A chanukiah and a tray",
                         "Oil and wicks, or candles that fit the holders",
                         "Mishloach manos baskets or boxes, ribbon and tags",
                         "A Megillah, one per person if you can",
                         "A table or serving trays for the seudah"],
                "list_he": ["חנוכייה ומגש",
                            "שמן ופתילות, או נרות שמתאימים לבתים",
                            "סלים או קופסאות למשלוחי מנות, סרט ותוויות",
                            "מגילה, אחת לכל אדם אם אפשר",
                            "שולחן או מגשי הגשה לסעודה"],
            },
            {
                "h": "Pesach",
                "h_he": "פסח",
                "p": ["Pesach is the biggest purchase of the year, because many families keep a "
                      "separate set of dishes, pots and cutlery. A first Pesach in a new home is often "
                      "where couples ask for help, since it is a second kitchen in miniature. Some "
                      "families also keep one set for milchig and another for fleishig, which doubles "
                      "the list.",
                      "What can be kashered, what must be replaced and what each family does are "
                      "questions for your rav. Raise them well before the holiday, since shops and "
                      "rabbanim are both very busy in the weeks before."],
                "p_he": ["פסח הוא הקנייה הגדולה של השנה, כי הרבה משפחות מחזיקות סט נפרד של כלים, "
                         "סירים וסכו״ם. פסח ראשון בבית חדש הוא לעיתים המקום שבו זוגות מבקשים עזרה, "
                         "כי זה מטבח שני בקטן. יש משפחות שמחזיקות גם סט אחד לחלבי ואחד לבשרי, מה "
                         "שמכפיל את הרשימה.",
                         "מה אפשר להכשיר, מה חייבים להחליף ומה כל משפחה עושה, אלה שאלות לרב שלכם. "
                         "העלו אותן הרבה לפני החג, כי בשבועות שלפני גם החנויות וגם הרבנים עמוסים מאוד."],
                "list": ["Pesach dishes, glasses and cutlery",
                         "Pesach pots, a pan and a baking sheet",
                         "A seder plate, a Kos Eliyahu cup and wine cups",
                         "Matzah cover and a Haggadah for every guest",
                         "Storage boxes so the set can be packed away for eleven months"],
                "list_he": ["כלים, כוסות וסכו״ם לפסח",
                            "סירי פסח, מחבת ותבנית אפייה",
                            "קערת סדר, גביע אליהו וכוסות יין",
                            "כיסוי מצות והגדה לכל אורח",
                            "קופסאות אחסון כדי שאפשר יהיה לארוז את הסט לאחד עשר חודשים"],
            },
            {
                "h": "Shavuos",
                "h_he": "שבועות",
                "p": ["Shavuos is the lightest holiday to equip for. The custom of eating dairy "
                      "means a cheesecake pan or two, a cheese board, a blintz pan if you make them, "
                      "and flowers or greenery for the table, which many families like to have.",
                      "If you keep to the milchig colour you chose when you set up the kitchen, the "
                      "dairy meal will use your existing set. That is one more reason to settle the "
                      "two colours early."],
                "p_he": ["שבועות הוא החג הקל ביותר להתכונן אליו. המנהג לאכול חלבי אומר תבנית אחת "
                         "או שתיים לעוגת גבינה, מגש גבינות, מחבת לבלינצ׳ס אם מכינים, ופרחים או "
                         "ירק לשולחן, שהרבה משפחות אוהבות.",
                         "אם אתם שומרים על צבע החלבי שבחרתם כשהקמתם את המטבח, הסעודה החלבית תשתמש "
                         "בסט הקיים שלכם. זו עוד סיבה להחליט על שני הצבעים מוקדם."],
            },
        ],
        "cta": "start",
    },
    {
        "slug": "helping-your-children-set-up-a-home-in-israel",
        "icon": "i-house",
        "updated": "2026-11-12",
        "title": "For parents abroad: helping your children set up a home in Israel",
        "title_he": "להורים בחו״ל: לעזור לילדים להקים בית בישראל",
        "summary": "Your son or daughter is setting up an apartment in Israel and you are an ocean away. "
                   "What helps most from a distance, and what tends to cause more work than it saves.",
        "summary_he": "הבן או הבת שלכם מקימים דירה בישראל ואתם רחוקים מעבר לים. מה עוזר הכי הרבה "
                      "מרחוק, ומה נוטה ליצור יותר עבודה ממה שהוא חוסך.",
        "sections": [
            {
                "h": "Agree the plan before anyone buys anything",
                "h_he": "להסכים על התוכנית לפני שמישהו קונה משהו",
                "p": ["The most useful conversation happens early and costs nothing: what is the "
                      "overall budget, what will you cover, and what will the couple cover or leave to "
                      "other relatives. Parents who say “we would like to buy the big appliances” or "
                      "“we will cover the bed and linen” give the couple something to plan around. "
                      "Parents who just say “let us know what you need” often get a long list later, "
                      "or silence out of politeness.",
                      "Decide who owns each decision. If the couple is choosing the fridge, let them "
                      "choose it, and treat your role as paying for it, not picking it. They are the "
                      "ones who know the kitchen, the lift and the landlord."],
                "p_he": ["השיחה הכי שימושית קורית מוקדם ולא עולה כלום: מה התקציב הכולל, מה אתם "
                         "מכסים, ומה הזוג מכסה בעצמו או משאיר לקרובים אחרים. הורים שאומרים ״נשמח "
                         "לקנות את המכשירים הגדולים״ או ״אנחנו נכסה את המיטה והמצעים״ נותנים לזוג משהו "
                         "לתכנן סביבו. הורים שאומרים רק ״תגידו לנו מה אתם צריכים״ מקבלים לא פעם רשימה "
                         "ארוכה מאוחר יותר, או שתיקה מתוך נימוס.",
                         "החליטו של מי כל החלטה. אם הזוג בוחר את המקרר, תנו להם לבחור, והתפקיד שלכם "
                         "הוא לשלם עליו ולא לבחור אותו. הם אלה שמכירים את המטבח, את המעלית ואת בעל "
                         "הדירה."],
                "list": ["Agree a total, and whether it is a gift, a loan or a mix",
                         "Split by category, such as big appliances, bed and linen, kitchen, Shabbos",
                         "Say plainly what you are not planning to buy, so nobody waits for it",
                         "Revisit it once the apartment is chosen, since the lease changes the list"],
                "list_he": ["סכמו על סכום כולל, והאם זו מתנה, הלוואה או שילוב",
                            "חלקו לפי קטגוריות, כמו מכשירים גדולים, מיטה ומצעים, מטבח, שבת",
                            "אמרו בפשטות מה אתם לא מתכננים לקנות, כדי שאף אחד לא יחכה לזה",
                            "חזרו לזה אחרי שנבחרה הדירה, כי החוזה משנה את הרשימה"],
            },
            {
                "h": "A registry, so relatives do not double up",
                "h_he": "רשימת מתנות, כדי שקרובים לא יקנו כפול",
                "p": ["When aunts, grandparents and family friends all want to help, someone buys a "
                      "kettle and someone else buys the same kettle. A single shared list that shows "
                      "what has been taken ends that. It also gives relatives who ask “what do they "
                      "need?” a link to send instead of a guess.",
                      "Help the couple make the list useful: a spread of small and large items, the "
                      "mattress measurements before anyone buys linen, and a note on what the apartment "
                      "already has. Our guide on building a registry covers how to choose what goes on "
                      "it."],
                "p_he": ["כשדודות, סבים וחברי משפחה כולם רוצים לעזור, מישהו קונה קומקום ומישהו אחר "
                         "קונה את אותו קומקום. רשימה משותפת אחת שמראה מה כבר נלקח מסיימת את זה. היא "
                         "גם נותנת לקרובים ששואלים ״מה הם צריכים?״ קישור לשלוח במקום ניחוש.",
                         "עזרו לזוג להפוך את הרשימה לשימושית: פיזור של פריטים קטנים וגדולים, מידות "
                         "המזרן לפני שמישהו קונה מצעים, והערה על מה שכבר יש בדירה. המדריך שלנו על "
                         "בניית רשימת מתנות מסביר איך בוחרים מה נכנס אליה."],
            },
            {
                "h": "Paying Israeli stores from abroad",
                "h_he": "לשלם לחנויות ישראליות מחו״ל",
                "p": ["Many Israeli online stores accept foreign credit cards, but not all do, and "
                      "some checkouts are only in Hebrew. Some may also ask for an Israeli ID number or "
                      "an Israeli phone number for delivery updates, which a parent abroad does not "
                      "have. We have not tested every store, so do not assume.",
                      "The practical approach is to try the checkout before the day you need it, and "
                      "if it will not accept your card, you have two easy ways round it. You can send "
                      "the money to the couple and let them order, or ask the couple to put their own "
                      "phone number and delivery details on the order. Your bank may also add a "
                      "foreign-currency fee, so a larger single payment is often less hassle than "
                      "several small ones."],
                "p_he": ["הרבה חנויות אונליין ישראליות מקבלות כרטיסי אשראי זרים, אבל לא כולן, ובחלק "
                         "מהקופות הכול רק בעברית. חלקן גם עשויות לבקש מספר תעודת זהות ישראלי או מספר "
                         "טלפון ישראלי לעדכוני משלוח, ולהורה בחו״ל אין. לא בדקנו כל חנות, אז אל "
                         "תניחו.",
                         "הגישה המעשית היא לנסות את הקופה הרבה לפני היום שבו צריך, ואם היא לא מקבלת "
                         "את הכרטיס שלכם, יש שתי דרכים קלות לעקוף. אפשר לשלוח את הכסף לזוג ולתת להם "
                         "להזמין, או לבקש מהם לרשום בהזמנה את הטלפון ופרטי המשלוח שלהם. הבנק שלכם אולי "
                         "גם יוסיף עמלת מט״ח, ולכן תשלום אחד גדול יותר הוא לרוב פחות טרחה מכמה קטנים."],
            },
            {
                "h": "Delivery before the couple arrives",
                "h_he": "משלוח לפני שהזוג מגיע",
                "p": ["If you want the bed and fridge in place before they land, someone has to be "
                      "there to receive them. Ask whether a relative, a friend or the landlord can "
                      "hold the keys on the delivery day, and confirm the time window with the store "
                      "the week before. Our guide on sizes, plugs and delivery explains what to ask a "
                      "store.",
                      "Big deliveries often arrive in boxes, and assembly is usually separate. Arriving "
                      "to an apartment full of flat-pack boxes is not always the welcome you imagined, "
                      "so ask the store about assembly, or arrange it with the couple."],
                "p_he": ["אם אתם רוצים שהמיטה והמקרר יהיו במקום לפני שהם נוחתים, מישהו חייב להיות "
                         "שם לקבל אותם. שאלו אם קרוב משפחה, חבר או בעל הדירה יכולים להחזיק את המפתחות "
                         "ביום המשלוח, ואשרו את חלון הזמן מול החנות שבוע לפני. המדריך שלנו על מידות, "
                         "תקעים ומשלוחים מסביר מה לשאול חנות.",
                         "משלוחים גדולים מגיעים לא פעם בקרטונים, וההרכבה בדרך כלל נפרדת. להגיע לדירה "
                         "מלאה בקרטונים של רהיטים לא תמיד מרגיש כמו קבלת הפנים שדמיינתם, אז שאלו את "
                         "החנות על הרכבה, או תאמו אותה עם הזוג."],
            },
            {
                "h": "What not to ship",
                "h_he": "מה לא לשלוח",
                "p": ["Shipping from abroad costs freight, may involve customs handling, and the "
                      "goods may not suit Israeli electricity or sizes. For most household things it "
                      "is simpler to buy in Israel. Our guide on bringing appliances or buying them "
                      "here goes through the electricity side in detail.",
                      "Keep the suitcase for what is small, personal and hard to find here."],
                "p_he": ["משלוח מחו״ל עולה בהובלה, עשוי לכלול טיפול במכס, והמוצרים אולי לא מתאימים "
                         "לחשמל או למידות בישראל. לרוב דברי הבית פשוט יותר לקנות בארץ. המדריך שלנו על "
                         "להביא מכשירי חשמל או לקנות כאן עובר על עניין החשמל בפירוט.",
                         "השאירו את המזוודה למה שקטן, אישי וקשה למצוא כאן."],
                "list": ["Large appliances and anything with a heating element or a motor",
                         "Bed linen and mattresses, whose sizes differ here",
                         "Heavy or breakable items that cost more to send than to buy locally",
                         "Anything you have not checked against the apartment, such as a lamp for a "
                         "different socket",
                         "Food, unless you have asked the family first, since kashrus standards differ"],
                "list_he": ["מכשירי חשמל גדולים וכל מה שיש בו גוף חימום או מנוע",
                            "מצעים ומזרנים, שהמידות שלהם כאן שונות",
                            "פריטים כבדים או שבירים ששליחתם עולה יותר מקנייתם כאן",
                            "כל דבר שלא בדקתם מול הדירה, כמו מנורה לשקע אחר",
                            "אוכל, אלא אם שאלתם קודם את המשפחה, כי רמות הכשרות שונות"],
            },
            {
                "h": "Two things OurBayis offers",
                "h_he": "שני דברים ש-OurBayis מציע",
                "p": ["OurBayis is a registry where each gift can be bought at an Israeli store or "
                      "paid for through the couple's own payment link. The site never holds the "
                      "money.",
                      "There is also a separate Shana Rishonah setup service, for couples arriving in "
                      "Israel: the basics are ordered and delivered to the apartment before they "
                      "land, for a quoted price. Details are on its own page."],
                "p_he": ["OurBayis הוא רשימת מתנות שבה כל מתנה אפשר לקנות בחנות ישראלית או לשלם "
                         "עליה דרך קישור התשלום של הזוג עצמו. האתר אף פעם לא מחזיק את הכסף.",
                         "יש גם שירות נפרד, הקמה לשנה ראשונה, לזוגות שמגיעים לארץ: הדברים "
                         "הבסיסיים מוזמנים ומגיעים לדירה לפני הנחיתה, לפי הצעת מחיר. הפרטים בעמוד שלו."],
            },
        ],
        "cta": "start",
    },
    {
        "slug": "eight-week-timeline-engagement-to-working-apartment",
        "icon": "i-star",
        "updated": "2026-11-12",
        "title": "An eight-week timeline: from engagement to a working apartment",
        "title_he": "ציר זמן של שמונה שבועות: מהאירוסין לדירה שעובדת",
        "summary": "A week-by-week order of work for the weeks between finding an apartment and "
                   "living in it, so the long-lead items start early and the last week is only "
                   "cleaning and food.",
        "summary_he": "סדר עבודה שבוע אחר שבוע לשבועות שבין מציאת דירה לחיים בה, כך שהפריטים עם זמן "
                      "אספקה ארוך מתחילים מוקדם והשבוע האחרון הוא רק ניקיון ואוכל.",
        "sections": [
            {
                "h": "How to use this",
                "h_he": "איך להשתמש בזה",
                "p": ["Eight weeks is a frame, not a rule. If you have longer, spread it out; if you "
                      "have less, do the first two steps at once. The order matters more than the "
                      "dates: the apartment decides the list, and the biggest items take the longest "
                      "to arrive.",
                      "This guide is only the order of work. For what goes in each room, see our "
                      "first apartment checklist."],
                "p_he": ["שמונה שבועות זו מסגרת ולא כלל. אם יש לכם יותר זמן, פזרו; אם פחות, עשו "
                         "את שני השלבים הראשונים במקביל. הסדר חשוב יותר מהתאריכים: הדירה קובעת את "
                         "הרשימה, והפריטים הגדולים לוקחים הכי הרבה זמן להגיע.",
                         "המדריך הזה הוא רק סדר העבודה. מה נכנס לכל חדר מופיע ברשימת הציוד לדירה "
                         "ראשונה שלנו."],
            },
            {
                "h": "Weeks 8 and 7: the lease and the measurements",
                "h_he": "שבועות 8 ו-7: החוזה והמידות",
                "p": ["Sign the lease, then ask the landlord in writing what stays: fridge, oven, "
                      "washing machine, air conditioning, curtains, lights. Check that each works. "
                      "Everything on that answer changes what you buy.",
                      "Measure while you can still get in: the kitchen gaps for a fridge and a "
                      "washing machine, the width of the door and the stairwell or lift, the "
                      "mattress if the beds stay, and the balcony if you plan a sukkah. Write the "
                      "numbers somewhere you will find them."],
                "p_he": ["חתמו על החוזה, ואז שאלו את בעל הדירה בכתב מה נשאר: מקרר, תנור, מכונת "
                         "כביסה, מיזוג, וילונות, תאורה. בדקו שכל אחד עובד. כל מה שבתשובה הזו משנה "
                         "מה קונים.",
                         "מדדו כל עוד אפשר להיכנס: הנישות במטבח למקרר ולמכונת כביסה, רוחב הדלת "
                         "וחדר המדרגות או המעלית, המזרן אם המיטות נשארות, והמרפסת אם מתכננים סוכה. "
                         "רשמו את המספרים במקום שתמצאו."],
                "list": ["Fridge, oven and washing machine: what stays and what you buy",
                         "Gap widths and heights for each appliance",
                         "Door, stairwell and lift widths for large items",
                         "Mattress size, if beds stay"],
                "list_he": ["מקרר, תנור ומכונת כביסה: מה נשאר ומה קונים",
                            "רוחב וגובה הנישה לכל מכשיר",
                            "רוחב דלת, חדר מדרגות ומעלית לפריטים גדולים",
                            "מידת המזרן, אם המיטות נשארות"],
            },
            {
                "h": "Weeks 6 and 5: big appliances and their lead times",
                "h_he": "שבועות 6 ו-5: מכשירים גדולים וזמני אספקה",
                "p": ["Order the large items now. Delivery can take a week or more depending on the "
                      "store, the item and the season, so ask the store for the actual window rather "
                      "than assuming. If you want installation, ask whether it is included and who "
                      "does it. Where is the right place to buy? Our guide on where to shop for a home "
                      "in Israel gives the landscape.",
                      "Decide who will be in the apartment on delivery day. If you are not in Israel "
                      "yet, this is the week to line up a relative or a friend."],
                "p_he": ["הזמינו עכשיו את הפריטים הגדולים. אספקה יכולה לקחת שבוע או יותר, תלוי "
                         "בחנות, בפריט ובעונה, אז שאלו את החנות מה החלון בפועל ואל תניחו. אם אתם "
                         "רוצים התקנה, שאלו אם היא כלולה ומי עושה אותה. איפה קונים? המדריך שלנו על "
                         "איפה קונים לבית בישראל נותן את המפה.",
                         "החליטו מי יהיה בדירה ביום המשלוח. אם אתם עוד לא בארץ, זה השבוע לסדר קרוב "
                         "משפחה או חבר."],
            },
            {
                "h": "Week 4: the registry and telling guests",
                "h_he": "שבוע 4: רשימת המתנות והודעה לאורחים",
                "p": ["With the apartment known, build the registry: the first-week items at the "
                      "top, a spread of prices, and a note on what you already have. Then send the "
                      "link. See our guide on telling guests about a registry for wording.",
                      "Guests who plan ahead like to buy early, and some items on the list need time "
                      "to arrive, so a link sent in week four helps both sides."],
                "p_he": ["כשהדירה ידועה, בנו את הרשימה: פריטי השבוע הראשון למעלה, פיזור של מחירים, "
                         "והערה על מה שכבר יש לכם. ואז שלחו את הקישור. נוסח אפשרי מופיע במדריך שלנו "
                         "על איך מספרים לאורחים על רשימת מתנות.",
                         "אורחים שמתכננים מראש אוהבים לקנות מוקדם, ופריטים מסוימים ברשימה צריכים זמן "
                         "להגיע, אז קישור שנשלח בשבוע הרביעי עוזר לשני הצדדים."],
            },
            {
                "h": "Week 3 and week 2: kitchen, Shabbos and linen",
                "h_he": "שבוע 3 ושבוע 2: מטבח, שבת ומצעים",
                "p": ["In week three, settle the kitchen: your two colours, the pots and knives "
                      "worth doing properly, and the Shabbos basics such as a platta, an urn and a "
                      "Shabbos clock. If you are bringing a set from home, ask your rav about it now, "
                      "not the night before Shabbos. Our guides on the kosher kitchen and Shabbos "
                      "equipment cover the choices.",
                      "In week two, once you know the bed size and the mattress, buy the linen: "
                      "fitted sheets to the measurement, a mattress protector, duvet, pillows and "
                      "towels. Buying earlier risks sheets that do not fit."],
                "p_he": ["בשבוע השלישי סוגרים את המטבח: שני הצבעים שלכם, הסירים והסכינים ששווה "
                         "לעשות כמו שצריך, והבסיס לשבת כמו פלטה, מיחם ושעון שבת. אם מביאים סט מהבית, "
                         "שאלו את הרב עכשיו ולא בליל שבת. המדריכים שלנו על מטבח כשר ועל ציוד מטבח "
                         "לשבת מסבירים את האפשרויות.",
                         "בשבוע השני, כשמידת המיטה והמזרן ידועה, קונים את המצעים: סדינים מצוידים לפי "
                         "המידה, מגן מזרן, שמיכה, כריות ומגבות. קנייה מוקדמת יותר מסכנת סדינים שלא "
                         "מתאימים."],
                "list": ["Kitchen: pots, a pan, knives, plates and cutlery in both colours",
                         "Shabbos: platta, urn, clock, candlesticks, challah board",
                         "Linen: fitted sheets, protector, duvet, pillows, towels"],
                "list_he": ["מטבח: סירים, מחבת, סכינים, צלחות וסכו״ם בשני הצבעים",
                            "שבת: פלטה, מיחם, שעון, פמוטים, מגש חלה",
                            "מצעים: סדינים מצוידים, מגן מזרן, שמיכה, כריות, מגבות"],
            },
            {
                "h": "The last week: clean, stock up, set up",
                "h_he": "השבוע האחרון: מנקים, ממלאים מלאי, מסדרים",
                "p": ["Clean before the boxes arrive, while the rooms are empty. Then stock the "
                      "basics: cleaning supplies, bin bags, light bulbs, toilet paper, a first-aid "
                      "kit, and food for the first week such as bread, eggs, oil, tea and whatever "
                      "you cook from without thinking.",
                      "Remind yourselves of the set-up jobs that do not happen by themselves: "
                      "internet, electricity, water and arnona accounts, and the gas if there is "
                      "any. Ask the landlord who the account holder is and what the previous tenant "
                      "closed. Do not assume any of it is transferred."],
                "p_he": ["מנקים לפני שהקרטונים מגיעים, כשהחדרים ריקים. אחר כך ממלאים מלאי בסיסי: "
                         "חומרי ניקוי, שקיות אשפה, נורות, נייר טואלט, ערכת עזרה ראשונה, ואוכל לשבוע "
                         "הראשון כמו לחם, ביצים, שמן, תה ומה שמבשלים ממנו בלי לחשוב.",
                         "תזכירו לעצמכם את סידורי ההקמה שלא קורים לבד: אינטרנט, חשמל, מים וארנונה, "
                         "וגז אם יש. שאלו את בעל הדירה על שם מי החשבונות ומה הדייר הקודם סגר. אל "
                         "תניחו שמשהו מזה עובר מעצמו."],
                "list": ["Cleaning supplies, bin bags, bulbs, toilet paper",
                         "First-week food and Shabbos food",
                         "Internet, electricity, water and arnona: who holds each account",
                         "Keys, building committee contact and the lift or parking arrangements"],
                "list_he": ["חומרי ניקוי, שקיות אשפה, נורות, נייר טואלט",
                            "אוכל לשבוע הראשון ואוכל לשבת",
                            "אינטרנט, חשמל, מים וארנונה: על שם מי כל חשבון",
                            "מפתחות, איש קשר בוועד הבית והסדרי מעלית או חניה"],
            },
        ],
        "cta": "start",
    },
    {
        "slug": "how-to-tell-guests-about-a-registry",
        "icon": "i-gift",
        "updated": "2026-11-12",
        "title": "How to tell guests about a registry without it feeling awkward",
        "title_he": "איך מספרים לאורחים על רשימת מתנות בלי שזה יהיה מביך",
        "summary": "Registries are more familiar in some communities than others. How to share one "
                   "kindly, who should say it, example wording, and how to handle guests who would "
                   "rather give their own gift.",
        "summary_he": "רשימות מתנות מוכרות יותר בקהילות מסוימות מאחרות. איך משתפים אחת בעדינות, מי "
                      "צריך להגיד את זה, נוסחים לדוגמה, ואיך מתנהלים עם אורחים שמעדיפים לתת מתנה משלהם.",
        "sections": [
            {
                "h": "Why it can feel awkward, and why it usually is not",
                "h_he": "למה זה יכול להרגיש מביך, ולמה בדרך כלל זה לא",
                "p": ["In many families abroad, a registry is routine and guests often ask for one. "
                      "In Israel, most guests give money, and some may not have seen a registry "
                      "before. Neither habit is wrong. The awkwardness usually comes from guessing "
                      "what the other side expects.",
                      "A registry is an offer, not an instruction. Guests who like it will use it, "
                      "and guests who do not will give as they always would. Practice differs between "
                      "families and communities, so what follows are suggestions and not rules."],
                "p_he": ["במשפחות רבות בחו״ל רשימת מתנות היא שגרה, ואורחים מבקשים אחת לא פעם. "
                         "בישראל רוב האורחים נותנים כסף, וחלקם אולי לא ראו רשימה קודם. אף אחד מההרגלים "
                         "אינו שגוי. המבוכה באה בדרך כלל מניחוש של מה שהצד השני מצפה לו.",
                         "רשימה היא הצעה, לא הוראה. אורחים שאוהבים אותה ישתמשו בה, ואורחים שלא "
                         "ייתנו כמו שהם תמיד נותנים. המנהגים שונים בין משפחות וקהילות, ולכן מה "
                         "שכתוב כאן הוא הצעות ולא כללים."],
            },
            {
                "h": "Who tells whom",
                "h_he": "מי מספר למי",
                "p": ["Often the gentlest route is through someone other than the couple. Parents "
                      "can mention it to relatives who ask what the couple needs, and a sibling or "
                      "friend organising a shower or a Shabbos kallah can include the link in the "
                      "invitation. Hearing it from a third person who says “they set one up in case "
                      "it helps” is easier than a couple asking for gifts directly.",
                      "When guests ask you directly, that is the easiest moment of all. Answering a "
                      "question is not asking for something."],
                "p_he": ["לא פעם הדרך העדינה ביותר היא דרך מישהו אחר ולא הזוג. הורים יכולים להזכיר "
                         "את זה לקרובים ששואלים מה הזוג צריך, ואח, אחות או חברה שמארגנים מקלחת מתנות "
                         "או שבת כלה יכולים לכלול את הקישור בהזמנה. לשמוע את זה מצד שלישי שאומר ״הם "
                         "הקימו רשימה למקרה שזה עוזר״ קל יותר מזוג שמבקש מתנות ישירות.",
                         "כשאורחים שואלים אתכם ישירות, זה הרגע הקל מכולם. להשיב לשאלה זה לא לבקש "
                         "משהו."],
            },
            {
                "h": "Wording that has worked for others",
                "h_he": "נוסחים שאנשים משתמשים בהם",
                "p": ["Keep it short, warm and optional. Put the thanks and the invitation first and "
                      "the link last. Here are three examples to adapt, one for a WhatsApp message to "
                      "friends abroad, one for an invitation insert, and one for word of mouth in "
                      "Israel."],
                "p_he": ["שמרו על קצר, חם ולא מחייב. שימו את התודה וההזמנה קודם ואת הקישור בסוף. "
                         "הנה שלוש דוגמאות להתאמה, אחת להודעת וואטסאפ לחברים בחו״ל, אחת לדף הוספה "
                         "להזמנה, ואחת לשיחה בעל פה בישראל."],
                "list": ["WhatsApp, abroad: “So happy you will be with us. Several people asked what "
                         "we need, so we made a small list at this link. Completely optional, and "
                         "your being there is the real gift.”",
                         "Invitation insert: “For those who have asked, we have set up a gift list "
                         "at the address below. Cash gifts are equally welcome.”",
                         "In person, in Israel: “If you want to help us set up, we put together a "
                         "list of what we still need. And if you prefer to give in the usual way, "
                         "that is wonderful too.”"],
                "list_he": ["וואטסאפ, בחו״ל: ״כל כך שמחים שתהיו איתנו. כמה אנשים שאלו מה אנחנו "
                            "צריכים, אז הכנו רשימה קטנה בקישור הזה. זה לגמרי אופציונלי, והנוכחות שלכם "
                            "היא המתנה האמיתית.״",
                            "דף הוספה להזמנה: ״למי ששאל, הקמנו רשימת מתנות בכתובת שלמטה. מתנות "
                            "בכסף מתקבלות באותה שמחה.״",
                            "בעל פה, בישראל: ״אם בא לכם לעזור לנו להקים את הבית, הכנו רשימה של מה "
                            "שעוד חסר לנו. ואם אתם מעדיפים לתת כמו שנהוג, זה מצוין גם כן.״"],
            },
            {
                "h": "Cash and registry, side by side",
                "h_he": "כסף ורשימה, זה לצד זה",
                "p": ["You do not have to pick one. Many couples welcome cash and also keep a "
                      "registry for the guests who like a specific item. Saying so plainly takes the "
                      "pressure off: guests who prefer to give money will not feel they are doing the "
                      "wrong thing.",
                      "If you will use cash for something particular, such as a fridge, you can say "
                      "so. Guests who give toward it see where it goes. That is a decision for you "
                      "and for your family, and there is no wrong answer."],
                "p_he": ["אין חובה לבחור אחד. הרבה זוגות מקבלים בשמחה כסף ושומרים גם רשימה לאורחים "
                         "שאוהבים פריט מסוים. להגיד את זה בפשטות מוריד לחץ: אורחים שמעדיפים לתת כסף "
                         "לא ירגישו שהם עושים משהו לא נכון.",
                         "אם תשתמשו בכסף למשהו מסוים, כמו מקרר, אפשר להגיד את זה. אורחים שנותנים "
                         "לקראתו רואים לאן זה הולך. זו החלטה שלכם ושל המשפחה, ואין תשובה לא נכונה."],
            },
            {
                "h": "Guests who prefer their own gift",
                "h_he": "אורחים שמעדיפים מתנה משלהם",
                "p": ["Some guests will bring something they chose themselves, such as a sefer, a "
                      "set of candlesticks, a painting or a family item. Receive it with thanks. "
                      "A registry is not a ban on everything else.",
                      "If you worry about duplicates, a quiet note is enough, for example by marking "
                      "something as already received. Do not return or exchange a personal gift "
                      "without being sure the giver would not mind."],
                "p_he": ["חלק מהאורחים יביאו משהו שבחרו בעצמם, כמו ספר, פמוטים, ציור או פריט "
                         "משפחתי. קבלו אותו בתודה. רשימה היא לא איסור על כל השאר.",
                         "אם אתם חוששים מכפילויות, די בהערה שקטה, למשל לסמן פריט כמי שכבר התקבל. "
                         "אל תחזירו ואל תחליפו מתנה אישית בלי להיות בטוחים שהנותן לא יפגע."],
            },
            {
                "h": "Saying thank you",
                "h_he": "להגיד תודה",
                "p": ["Write thank-yous soon after, while you still remember who gave what, and name "
                      "the gift. Guests abroad in particular like to know it arrived. A few lines is "
                      "enough, and a photo of the item in use is a pleasant extra.",
                      "For cash or a transfer, a short thanks that says what you plan to do with it "
                      "is warmer than only acknowledging the amount."],
                "p_he": ["כתבו תודות זמן קצר אחרי, כל עוד אתם זוכרים מי נתן מה, וציינו את המתנה "
                         "בשמה. במיוחד אורחים בחו״ל אוהבים לדעת שהיא הגיעה. כמה שורות מספיקות, ותמונה "
                         "של הפריט בשימוש היא תוספת נעימה.",
                         "על כסף או העברה, תודה קצרה שאומרת מה מתכננים לעשות איתו חמה יותר "
                         "מאישור של הסכום בלבד."],
            },
        ],
        "cta": "sample",
    },
    {
        "slug": "registry-when-you-already-have-hand-me-downs",
        "icon": "i-pot",
        "updated": "2026-11-12",
        "title": "What to put on a registry when you already have hand-me-downs",
        "title_he": "מה לשים ברשימת מתנות כשכבר קיבלתם דברים יד שנייה מהמשפחה",
        "summary": "Parents, grandparents and friends have handed you plates, pots and a bed frame. "
                   "How to take stock, what is worth buying new, what is fine as it is, and how to "
                   "build a list around the gaps.",
        "summary_he": "הורים, סבים וחברים נתנו לכם צלחות, סירים ומסגרת מיטה. איך עושים מלאי, מה כדאי "
                      "לקנות חדש, מה בסדר כמו שהוא, ואיך בונים רשימה סביב החסרים.",
        "sections": [
            {
                "h": "Take stock first",
                "h_he": "קודם עושים מלאי",
                "p": ["Before adding anything to a registry, put everything you have been given in one "
                      "place and go room by room. Note what works, what is worn, and what is missing "
                      "entirely. A short written inventory takes an hour and prevents a lot of "
                      "duplicates.",
                      "Include the date and who gave it, if you can. You may want to thank them "
                      "later, and it helps when a relative asks what you still need."],
                "p_he": ["לפני שמוסיפים משהו לרשימה, שימו את כל מה שקיבלתם במקום אחד ועברו חדר "
                         "חדר. רשמו מה עובד, מה בלוי, ומה חסר לגמרי. מלאי כתוב קצר לוקח שעה וחוסך "
                         "הרבה כפילויות.",
                         "הוסיפו תאריך ומי נתן, אם אפשר. אולי תרצו להודות להם אחר כך, וזה עוזר "
                         "כשקרוב שואל מה עוד חסר לכם."],
                "list": ["Walk through the kitchen, bathroom, bedroom and living area",
                         "Mark each item as good, worn or missing",
                         "Write down sizes for anything that must fit, such as mattresses",
                         "Keep the list handy for relatives who ask"],
                "list_he": ["עברו על המטבח, האמבטיה, חדר השינה והסלון",
                            "סמנו כל פריט כטוב, בלוי או חסר",
                            "רשמו מידות לכל מה שצריך להתאים, כמו מזרנים",
                            "שמרו את הרשימה בהישג יד לקרובים ששואלים"],
            },
            {
                "h": "What is worth buying new",
                "h_he": "מה כדאי לקנות חדש",
                "p": ["The usual advice is to buy new what touches your body or gets used every day, "
                      "and what wears out. Things people tend to replace include:"],
                "p_he": ["העצה הרגילה היא לקנות חדש את מה שנוגע בגוף או משמש כל יום, ואת מה "
                         "שמתבלה. דברים שאנשים נוטים להחליף כוללים:"],
                "list": ["Mattress protectors and pillows",
                         "Towels and sheets in the right sizes",
                         "A good chef's knife and a sharpener",
                         "The one or two pots and a pan you will use daily",
                         "Any pan with a scratched or flaking non-stick coating",
                         "Sponges, scrubbers and cutting boards that have seen heavy use"],
                "list_he": ["מגני מזרן וכריות",
                            "מגבות ומצעים במידות הנכונות",
                            "סכין שף טובה ומשחיז",
                            "סיר אחד או שניים ומחבת שמשתמשים בהם כל יום",
                            "כל מחבת עם ציפוי נון-סטיק שרוט או מתקלף",
                            "ספוגים, מקרצפים וקרשי חיתוך שעברו שימוש קשה"],
            },
            {
                "h": "What is fine second-hand",
                "h_he": "מה בסדר יד שנייה",
                "p": ["Plenty of things last for decades and lose nothing by being used: solid "
                      "furniture, a table and chairs, baking trays, glass and ceramic dishes, a "
                      "platter, cast iron, a bookcase. These are worth keeping even if they do not "
                      "match.",
                      "Be more careful with electrical items. Test them before you rely on them, "
                      "check the voltage on the label if they came from abroad, and ask whether the "
                      "giver has a receipt or a warranty. Our guide on bringing appliances from abroad "
                      "covers voltage."],
                "p_he": ["הרבה דברים מחזיקים עשרות שנים ולא מפסידים משימוש: רהיטים מוצקים, שולחן "
                         "וכיסאות, תבניות אפייה, כלי זכוכית וקרמיקה, מגש הגשה, ברזל יצוק, ארון ספרים. "
                         "שווה לשמור אותם גם אם הם לא תואמים.",
                         "היזהרו יותר עם מוצרי חשמל. בדקו אותם לפני שמסתמכים עליהם, בדקו את המתח "
                         "בתווית אם הגיעו מחו״ל, ושאלו אם לנותן יש קבלה או אחריות. המדריך שלנו על "
                         "מכשירי חשמל מחו״ל עוסק במתח."],
            },
            {
                "h": "A mixed kitchen set",
                "h_he": "סט מטבח מעורב",
                "p": ["If you inherit dishes or pots from a family that kept kosher differently, or "
                      "that used the same set for everything, you may end up with items whose history "
                      "you do not know. Whether they can be used, kashered, or must be set aside is a "
                      "halachic question. Ask your rav before you use or register around any of it.",
                      "The two-set question also affects the registry. If you will use two colours for "
                      "milchig and fleishig, check what each inherited item already is, and list only "
                      "what is missing in each colour. Our kosher kitchen guide explains the colour "
                      "system."],
                "p_he": ["אם ירשתם כלים או סירים ממשפחה ששמרה כשרות בצורה אחרת, או שהשתמשה באותו סט "
                         "לכול, אולי יש לכם פריטים שההיסטוריה שלהם לא ידועה לכם. אם אפשר להשתמש בהם, "
                         "להכשיר אותם או שצריך לשים אותם בצד, זו שאלה הלכתית. שאלו את הרב שלכם לפני "
                         "שמשתמשים או בונים סביבם את הרשימה.",
                         "שאלת שני הסטים משפיעה גם על הרשימה. אם תשתמשו בשני צבעים לחלבי ולבשרי, "
                         "בדקו מה כל פריט שירשתם כבר, ורשמו רק מה שחסר בכל צבע. מדריך המטבח הכשר "
                         "שלנו מסביר את שיטת הצבעים."],
            },
            {
                "h": "Balance the price points",
                "h_he": "לאזן את טווחי המחירים",
                "p": ["Once you know the gaps, you may find the list is mostly small things. That "
                      "is fine, but remember that some guests want to give something larger. Keep "
                      "a few mid-range and bigger items so that every guest finds something that fits "
                      "their budget and closeness.",
                      "Quantities help too. If you need four towels, list four, so more than one "
                      "guest can give toward it."],
                "p_he": ["אחרי שאתם יודעים מה חסר, אולי תגלו שהרשימה היא בעיקר דברים קטנים. זה "
                         "בסדר, אבל זכרו שחלק מהאורחים רוצים לתת משהו גדול יותר. השאירו כמה פריטים "
                         "בינוניים וגדולים יותר, כדי שכל אורח ימצא משהו שמתאים לתקציב ולקרבה שלו.",
                         "גם כמויות עוזרות. אם צריך ארבע מגבות, רשמו ארבע, כדי שיותר מאורח אחד "
                         "יוכל לתת מהן."],
            },
            {
                "h": "Big items as group gifts or funds",
                "h_he": "פריטים גדולים כמתנה קבוצתית או קרן",
                "p": ["A bed, a couch or a washing machine is a lot for one guest. Offering it as "
                      "something several relatives can contribute to, or as a general home fund "
                      "through your own payment link, lets people give what they can toward it. "
                      "Be clear in the description what the fund is for.",
                      "Because the site never holds the money, a contribution goes straight to your "
                      "payment link. Keep track of what has come in so you know when you can order."],
                "p_he": ["מיטה, ספה או מכונת כביסה זה הרבה לאורח אחד. להציע אותם כמשהו שכמה "
                         "קרובים יכולים לתרום אליו, או כקרן כללית לבית דרך קישור התשלום שלכם, נותן "
                         "לאנשים לתת מה שהם יכולים. כתבו בתיאור בבירור למה הקרן מיועדת.",
                         "מכיוון שהאתר לא מחזיק את הכסף, תרומה עוברת ישירות לקישור התשלום שלכם. "
                         "עקבו אחרי מה שהגיע כדי לדעת מתי אפשר להזמין."],
            },
        ],
        "cta": "catalog",
    },
    {
        "slug": "chanukas-habayis-and-aliyah-gifts",
        "icon": "i-candles",
        "updated": "2026-11-12",
        "title": "Chanukas habayis and aliyah gifts: what to bring a family in a new home",
        "title_he": "חנוכת בית ומתנות לעולים: מה מביאים למשפחה בבית חדש",
        "summary": "For guests and friends: useful gifts for a family who has just moved in, customs "
                   "people mention, how to give from abroad, and a note for families who have just "
                   "made aliyah.",
        "summary_he": "לאורחים ולחברים: מתנות שימושיות למשפחה שזה עתה נכנסה, מנהגים שאנשים מזכירים, "
                      "איך לתת מחו״ל, והערה למשפחות שזה עתה עלו.",
        "sections": [
            {
                "h": "Useful beats decorative",
                "h_he": "שימושי עדיף על קישוטי",
                "p": ["A family in a new home usually has more ornaments than they can place and "
                      "fewer practical things than they need. Something they will use this week is "
                      "usually more welcome than something for a shelf. If you can, ask a family "
                      "member or the couple what is missing. If they have a registry, it will tell "
                      "you.",
                      "Keep in mind that a kosher home often has two of many things, so check which "
                      "colour or set before buying kitchenware. A general item such as a platter or "
                      "a challah cover is an easier choice than a pot, and Shabbos equipment is best "
                      "bought after asking."],
                "p_he": ["למשפחה בבית חדש יש בדרך כלל יותר קישוטים ממה שהיא מצליחה למקם ופחות דברים "
                         "מעשיים ממה שהיא צריכה. משהו שישתמשו בו השבוע מתקבל לרוב טוב יותר ממשהו "
                         "למדף. אם אפשר, שאלו בן משפחה או את הזוג מה חסר. אם יש להם רשימת מתנות, היא "
                         "תגיד לכם.",
                         "זכרו שבבית כשר יש לא פעם שניים מדברים רבים, אז בדקו איזה צבע או סט לפני "
                         "שקונים כלי מטבח. פריט כללי כמו מגש הגשה או כיסוי חלה הוא בחירה קלה יותר מסיר, "
                         "ואת ציוד השבת עדיף לקנות אחרי ששואלים."],
            },
            {
                "h": "Customs people mention",
                "h_he": "מנהגים שאנשים מזכירים",
                "p": ["Some people bring bread and salt, or honey, or a bottle of wine or juice, to "
                      "a new home. Others bring a plant, or a sefer or a mezuzah. These are customs "
                      "that vary from community to community, and some families will not know them "
                      "at all.",
                      "If you want to follow a custom, do it simply and with a few kind words. If you "
                      "are not sure what the family would appreciate, a practical gift with a warm "
                      "note is always fine. A mezuzah is a question for the family and their rav, "
                      "since it has to be a kosher one and be put up in a certain way."],
                "p_he": ["יש אנשים שמביאים לחם ומלח, או דבש, או בקבוק יין או מיץ, לבית חדש. אחרים "
                         "מביאים צמח, או ספר או מזוזה. אלה מנהגים שמשתנים בין קהילות, ויש משפחות "
                         "שלא מכירות אותם בכלל.",
                         "אם רוצים לנהוג לפי מנהג, עושים את זה בפשטות ועם כמה מילים טובות. אם אתם "
                         "לא בטוחים מה המשפחה תעריך, מתנה מעשית עם ברכה חמה תמיד בסדר. מזוזה היא "
                         "שאלה למשפחה ולרב שלהם, כי היא חייבת להיות כשרה ולהיות מוצבת בדרך מסוימת."],
                "list": ["Bread and salt, honey, or a bottle of wine or juice",
                         "A plant or flowers, if the family keeps a garden or a balcony",
                         "A sefer or a framed blessing, if you know the family well",
                         "Always check that food and drink carry a hechsher the family accepts"],
                "list_he": ["לחם ומלח, דבש, או בקבוק יין או מיץ",
                            "צמח או פרחים, אם למשפחה יש גינה או מרפסת",
                            "ספר או ברכה ממוסגרת, אם אתם מכירים את המשפחה היטב",
                            "תמיד בדקו שמאכלים ומשקאות עם הכשר שהמשפחה מקבלת"],
            },
            {
                "h": "Practical gifts by budget",
                "h_he": "מתנות מעשיות לפי תקציב",
                "p": ["We do not give prices, because what feels right depends on your closeness to "
                      "the family and your own situation. In general terms, here is how the choices "
                      "tend to group."],
                "p_he": ["אנחנו לא נותנים מחירים, כי מה שנכון תלוי בקרבה שלכם למשפחה ובמצב שלכם. "
                         "באופן כללי, כך האפשרויות נוטות להתקבץ."],
                "list": ["Smaller: a dish towel set, a challah cover, a spice rack, a plant, a "
                         "well-chosen sefer, or food for the first Shabbos",
                         "Middle: a good serving platter, a cutting board, a set of baking trays, "
                         "a lamp, a set of glasses",
                         "Larger, usually together with others: a platta, an urn, a small appliance "
                         "the family has asked for, or a contribution toward a big item",
                         "Anywhere in the range: a gift card for a store they use, if you are unsure"],
                "list_he": ["קטן: סט מגבות מטבח, כיסוי חלה, מתקן תבלינים, צמח, ספר שנבחר היטב, או "
                            "אוכל לשבת הראשונה",
                            "בינוני: מגש הגשה טוב, קרש חיתוך, סט תבניות אפייה, מנורה, סט כוסות",
                            "גדול, בדרך כלל יחד עם אחרים: פלטה, מיחם, מכשיר קטן שהמשפחה ביקשה, או "
                            "תרומה לפריט גדול",
                            "בכל טווח: שובר לחנות שהם משתמשים בה, אם אינכם בטוחים"],
            },
            {
                "h": "Giving from abroad",
                "h_he": "לתת מחו״ל",
                "p": ["If you live abroad, an Israeli store that delivers in Israel is usually "
                      "simpler than shipping something yourself. Ask the family for a delivery address "
                      "and a phone number for the courier, and check the store accepts your card, since "
                      "some checkouts are in Hebrew only. Our guide on giving a gift to a couple in "
                      "Israel from abroad explains the routes.",
                      "Or send a transfer through whatever method the family tells you they use, and "
                      "add a note. Money is always a practical gift in a new home."],
                "p_he": ["אם אתם גרים בחו״ל, חנות ישראלית שמשלחת בישראל היא לרוב פשוטה יותר ממשלוח "
                         "עצמאי. בקשו מהמשפחה כתובת למשלוח וטלפון לשליח, ובדקו שהחנות מקבלת את הכרטיס "
                         "שלכם, כי חלק מהקופות רק בעברית. המדריך שלנו על לתת מתנה לזוג בישראל מחו״ל "
                         "מסביר את הדרכים.",
                         "או שלחו העברה בכל שיטה שהמשפחה אומרת שהיא משתמשת בה, והוסיפו ברכה. כסף הוא "
                         "תמיד מתנה מעשית בבית חדש."],
            },
            {
                "h": "A note for a family that has just made aliyah",
                "h_he": "הערה למשפחה שזה עתה עלתה",
                "p": ["A family that has just arrived may not yet have its lift, the shipping "
                      "container with its belongings, which can arrive weeks or more after they do. "
                      "In the meantime they may be living with very little. Things that help right "
                      "away tend to be better than anything for later: a few days of food, basic "
                      "bedding, towels, a kettle, cleaning supplies, and an invitation for Shabbos.",
                      "Ask what they actually have before you buy. Do not bring things that would "
                      "duplicate a container full of belongings. Your time, a ride, help with a "
                      "form, or a seat at your table is often worth more than an object."],
                "p_he": ["משפחה שזה עתה הגיעה אולי עדיין אין לה את הליפט, המכולה עם החפצים שלה, "
                         "שיכולה להגיע שבועות או יותר אחריה. בינתיים היא אולי חיה עם מעט מאוד. דברים "
                         "שעוזרים מיד טובים יותר מכל דבר למאוחר: אוכל לכמה ימים, מצעים בסיסיים, מגבות, "
                         "קומקום, חומרי ניקוי, והזמנה לשבת.",
                         "שאלו מה יש להם בפועל לפני שקונים. אל תביאו דברים שיכפילו מכולה מלאה "
                         "בחפצים. הזמן שלכם, טרמפ, עזרה עם טופס או מקום ליד השולחן שלכם שווים לא פעם "
                         "יותר מחפץ."],
            },
            {
                "h": "Before you visit",
                "h_he": "לפני שמגיעים",
                "p": ["Check the time with the family, and keep Shabbos and Yom Tov in mind. A new "
                      "home may still be full of boxes, so a short visit, or leaving the gift with a "
                      "word and a smile, is often appreciated.",
                      "Bring a note that says who it is from, since gifts arrive from many people in "
                      "the first weeks and it is easy to lose track."],
                "p_he": ["תאמו עם המשפחה שעה, ושימו לב לשבת ולחג. בבית חדש עדיין יכולים להיות "
                         "קרטונים, אז ביקור קצר, או השארת המתנה עם מילה וחיוך, מתקבלים לא פעם "
                         "בהערכה.",
                         "הביאו פתק שאומר ממי זה, כי מתנות מגיעות מהרבה אנשים בשבועות הראשונים וקל "
                         "לאבד את הספירה."],
            },
        ],
        "cta": "catalog",
    },
]

BY_SLUG = {g["slug"]: g for g in GUIDES}


def pick(guide_or_section, field, lang):
    """Bilingual field with an English fallback (same contract as app.pick)."""
    if lang == "he":
        he = guide_or_section.get(field + "_he")
        if he:
            return he
    return guide_or_section.get(field, "")
