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
]

BY_SLUG = {g["slug"]: g for g in GUIDES}


def pick(guide_or_section, field, lang):
    """Bilingual field with an English fallback (same contract as app.pick)."""
    if lang == "he":
        he = guide_or_section.get(field + "_he")
        if he:
            return he
    return guide_or_section.get(field, "")
