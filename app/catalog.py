"""Initial seed catalog — 20 well-known books across genres.

This is the starter set; the system is designed to scale to many more.
Summaries are generated on demand and cached in the DB.
"""

SEED_BOOKS = [
    {
        "title": "Atomic Habits",
        "author": "James Clear",
        "year": 2018,
        "genre": "Self-Help",
        "description": "A framework for building tiny habits that compound into remarkable results.",
    },
    {
        "title": "Sapiens: A Brief History of Humankind",
        "author": "Yuval Noah Harari",
        "year": 2011,
        "genre": "History",
        "description": "Sweeping account of how Homo sapiens came to dominate the planet.",
    },
    {
        "title": "Thinking, Fast and Slow",
        "author": "Daniel Kahneman",
        "year": 2011,
        "genre": "Psychology",
        "description": "Two systems of thought — fast/intuitive and slow/deliberate — and how they shape us.",
    },
    {
        "title": "The Lean Startup",
        "author": "Eric Ries",
        "year": 2011,
        "genre": "Business",
        "description": "Build-measure-learn methodology for startups operating under uncertainty.",
    },
    {
        "title": "Deep Work",
        "author": "Cal Newport",
        "year": 2016,
        "genre": "Productivity",
        "description": "The case for focused, distraction-free work as a 21st-century superpower.",
    },
    {
        "title": "The Pragmatic Programmer",
        "author": "Andy Hunt & Dave Thomas",
        "year": 1999,
        "genre": "Technology",
        "description": "Timeless principles for software craftsmanship.",
    },
    {
        "title": "1984",
        "author": "George Orwell",
        "year": 1949,
        "genre": "Fiction",
        "description": "A dystopia of surveillance, language control, and totalitarian power.",
    },
    {
        "title": "To Kill a Mockingbird",
        "author": "Harper Lee",
        "year": 1960,
        "genre": "Fiction",
        "description": "A child's view of racial injustice in 1930s Alabama.",
    },
    {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "year": 1925,
        "genre": "Fiction",
        "description": "Jazz Age tragedy of wealth, longing, and the American Dream.",
    },
    {
        "title": "Brave New World",
        "author": "Aldous Huxley",
        "year": 1932,
        "genre": "Fiction",
        "description": "A pleasure-drugged dystopia where conformity is engineered, not imposed.",
    },
    {
        "title": "Meditations",
        "author": "Marcus Aurelius",
        "year": 180,
        "genre": "Philosophy",
        "description": "Personal notes from a Roman emperor on self-discipline and Stoic virtue.",
    },
    {
        "title": "Man's Search for Meaning",
        "author": "Viktor E. Frankl",
        "year": 1946,
        "genre": "Philosophy",
        "description": "A psychiatrist's account of finding meaning in Nazi concentration camps.",
    },
    {
        "title": "The Selfish Gene",
        "author": "Richard Dawkins",
        "year": 1976,
        "genre": "Science",
        "description": "Evolution reframed from the gene's eye view.",
    },
    {
        "title": "A Brief History of Time",
        "author": "Stephen Hawking",
        "year": 1988,
        "genre": "Science",
        "description": "Cosmology from the Big Bang to black holes, made accessible.",
    },
    {
        "title": "The Power of Habit",
        "author": "Charles Duhigg",
        "year": 2012,
        "genre": "Psychology",
        "description": "Why we do what we do, and how to change it.",
    },
    {
        "title": "Zero to One",
        "author": "Peter Thiel",
        "year": 2014,
        "genre": "Business",
        "description": "Notes on startups, or how to build the future from nothing.",
    },
    {
        "title": "The Innovator's Dilemma",
        "author": "Clayton M. Christensen",
        "year": 1997,
        "genre": "Business",
        "description": "Why great companies fail in the face of disruptive technology.",
    },
    {
        "title": "Educated",
        "author": "Tara Westover",
        "year": 2018,
        "genre": "Memoir",
        "description": "A woman escapes a survivalist family and discovers formal education at 17.",
    },
    {
        "title": "The Body Keeps the Score",
        "author": "Bessel van der Kolk",
        "year": 2014,
        "genre": "Psychology",
        "description": "How trauma reshapes the brain and body — and the paths to recovery.",
    },
    {
        "title": "Crime and Punishment",
        "author": "Fyodor Dostoevsky",
        "year": 1866,
        "genre": "Fiction",
        "description": "A student's moral disintegration after a calculated murder.",
    },
]


# Languages we offer translation + TTS for. Codes match gTTS / common ISO usage.
SUPPORTED_LANGUAGES = [
    {"code": "en",    "name": "English"},
    {"code": "es",    "name": "Spanish"},
    {"code": "fr",    "name": "French"},
    {"code": "de",    "name": "German"},
    {"code": "it",    "name": "Italian"},
    {"code": "pt",    "name": "Portuguese"},
    {"code": "ru",    "name": "Russian"},
    {"code": "zh-CN", "name": "Chinese (Simplified)"},
    {"code": "ja",    "name": "Japanese"},
    {"code": "ko",    "name": "Korean"},
    {"code": "ar",    "name": "Arabic"},
    {"code": "hi",    "name": "Hindi"},
    {"code": "nl",    "name": "Dutch"},
    {"code": "vi",    "name": "Vietnamese"},
    {"code": "id",    "name": "Indonesian"},
    {"code": "tr",    "name": "Turkish"},
    {"code": "pl",    "name": "Polish"},
    {"code": "th",    "name": "Thai"},
]

LANG_NAME = {l["code"]: l["name"] for l in SUPPORTED_LANGUAGES}
