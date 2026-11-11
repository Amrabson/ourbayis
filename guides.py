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
]

BY_SLUG = {g["slug"]: g for g in GUIDES}


def pick(guide_or_section, field, lang):
    """Bilingual field with an English fallback (same contract as app.pick)."""
    if lang == "he":
        he = guide_or_section.get(field + "_he")
        if he:
            return he
    return guide_or_section.get(field, "")
