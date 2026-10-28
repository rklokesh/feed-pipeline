# SarkariChart: who we write for, and the words they search

Working notes (28 Oct 2026). Real search volumes come from Google Search Console after launch; revisit this then.

## Ideal reader

- 18–32, Hindi belt first (UP, Bihar, Rajasthan, MP, Haryana, Uttarakhand, Delhi, Jharkhand), graduate or 12th pass.
- Phone-first, often on mobile data; reads Hindi, searches in English or Hinglish ("up police bharti 2026",
  "ssc gd admit card kab aayega"), sometimes in Devanagari ("यूपी पुलिस भर्ती").
- Wants four things fast: is it real (official), can I apply (eligibility, age), by when (last date), how (link).
- Lives on Telegram, WhatsApp, YouTube and Google. Distrusts sites full of ads and fake "expected vacancy" posts.

## How people search (patterns)

| Intent | English / Hinglish patterns | Hindi patterns |
|---|---|---|
| New job | `<board> <post> recruitment 2026`, `<post> vacancy 2026`, `<board> bharti 2026`, `<exam> notification 2026`, `<exam> online form 2026`, `apply online` | `<बोर्ड> <पद> भर्ती 2026`, `<पद> वैकेंसी 2026`, `ऑनलाइन फॉर्म` |
| Last date | `<exam> last date`, `last date extended` | `अंतिम तिथि`, `लास्ट डेट बढ़ी` |
| Admit card | `<exam> admit card 2026`, `hall ticket`, `call letter`, `exam city slip`, `admit card kab aayega`, `download link` | `एडमिट कार्ड`, `प्रवेश पत्र` |
| Answer key | `<exam> answer key 2026`, `objection link`, `final answer key` | `आंसर की`, `उत्तर कुंजी` |
| Result | `<exam> result 2026`, `cut off`, `merit list`, `final result`, `scorecard`, `marks` | `रिज़ल्ट`, `परिणाम`, `कट ऑफ`, `मेरिट लिस्ट` |
| Details | `<exam> eligibility`, `age limit`, `fees`, `salary`, `syllabus`, `exam pattern`, `selection process` | `योग्यता`, `आयु सीमा`, `शुल्क`, `वेतन`, `सिलेबस` |
| Brands | `sarkari result`, `sarkari naukri`, `rojgar samachar`, `employment news`, `free job alert` | `सरकारी नौकरी`, `सरकारी रिज़ल्ट`, `रोजगार समाचार` |

## Rules we apply

1. **Page title (H1)** starts with the board's common short name, then the exam/post, then the search word, then the
   year, then one hook: `RRB Station Master Recruitment 2026 – Apply Online for 1,215 Posts`,
   `SSC GD Admit Card 2026 Out – Exam City Slip Link`, `UPSC CSE Result 2026 – Cut Off and Final List`.
   Max ~65 characters so Google shows it whole. Use the words people search (Recruitment, Notification, Vacancy,
   Online Form, Admit Card, Answer Key, Result, Cut Off, Merit List, Last Date Extended).
2. **Browser title** = H1 + ` | SarkariChart` when it fits in ~70 characters, otherwise just the H1.
3. **Hindi title** uses the Hindi search words: भर्ती, वैकेंसी, एडमिट कार्ड, आंसर की, रिज़ल्ट, कट ऑफ, अंतिम तिथि.
4. **FAQs** answer the real questions: "last date kya hai", "admit card kab aayega", "age limit", "fees", "salary".
5. Never write "expected" or rumour titles. Facts only from the notice, which is our edge on trust.

## Later (after launch, from Search Console data)

- One page per exam (`/exam/ssc-cgl-2026/`) that collects its notification, admit card, answer key and result.
- Category pages people search: "12th pass govt jobs", "graduate govt jobs", state pages ("UP govt jobs 2026").
