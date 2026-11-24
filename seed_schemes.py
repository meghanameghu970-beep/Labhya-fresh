import json
from database import get_connection, init_db, utc_now


VERIFIED_SCHEMES = [
    {
        "id": "gruha-lakshmi",
        "slug": "gruha-lakshmi",
        "name": "Gruha Lakshmi Scheme",
        "description": "Monthly financial assistance of ₹2,000 to women heads of households in Karnataka via Direct Benefit Transfer (DBT).",
        "level": "KARNATAKA_STATE",
        "category": "Women and child welfare",
        "department": "Women and Child Development Department, Government of Karnataka",
        "target_beneficiaries": "Women heads of households listed on Antyodaya, BPL, or APL ration cards in Karnataka.",
        "application_portal": "https://sevasindhugs.karnataka.gov.in/",
        "notification_ref": "WCD Karnataka Guarantee Scheme Guidelines",
        "deadline": None,
        "verification_status": "VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": "2023-08-30",
        "last_verified_date": "2026-10-22",
        "benefits": [
            ("Cash Transfer (DBT)", "₹2,000 per month (₹24,000/year)", "Monthly", "Aadhaar-linked Bank DBT", "Credited directly to the woman head of household")
        ],
        "rules": [
            ("residency", "AND", "state", "eq", "Karnataka", 0, 1, "Applicant must be a resident of Karnataka"),
            ("gender", "AND", "gender", "eq", "Female", 0, 1, "Applicant must be a woman"),
            ("ration", "AND", "ration_card_type", "in", ["BPL", "APL", "Antyodaya"], 0, 1, "Household must hold a valid Antyodaya, BPL, or APL Ration Card"),
            ("excl_tax", "AND", "is_taxpayer", "is_true", None, 1, 1, "Applicant or spouse must not be an Income Tax / GST payer"),
        ],
        "documents": [
            ("Aadhaar Card", 1, "Linked with mobile number and bank account"),
            ("Ration Card (Antyodaya / BPL / APL)", 1, "Showing woman as head of family"),
            ("Bank Account Passbook", 1, "Aadhaar-seeded bank account"),
            ("Residence Proof in Karnataka", 0, "If required during verification"),
        ],
        "sources": [
            ("myScheme - Griha Lakshmi Scheme", "https://www.myscheme.gov.in/schemes/gls", "OFFICIAL_PORTAL", "2026-09-18"),
            ("Vikaspedia - Gruha Lakshmi Scheme Karnataka", "https://schemes.vikaspedia.in/viewcontent/schemesall/state-specific-schemes/welfare-schemes-of-karnataka/gruha-lakshmi-scheme-karnataka?lgn=en", "GOVT_KNOWLEDGE_PORTAL", "2026-10-22"),
        ],
        "faqs": [
            ("Who is excluded from Gruha Lakshmi?", "Women or their spouses who pay Income Tax or file GST returns are not eligible.")
        ],
    },
    {
        "id": "yuva-nidhi",
        "slug": "yuva-nidhi",
        "name": "Yuva Nidhi Scheme",
        "description": "Monthly unemployment financial assistance for eligible Karnataka-domicile graduates and diploma holders for up to 2 years.",
        "level": "KARNATAKA_STATE",
        "category": "Youth and employment",
        "department": "Department of Skill Development, Entrepreneurship and Livelihood, Government of Karnataka",
        "target_beneficiaries": "Unemployed graduates and diploma holders domiciled in Karnataka.",
        "application_portal": "https://sevasindhugs.karnataka.gov.in/",
        "notification_ref": "Karnataka Skill Development GO (Yuva Nidhi)",
        "deadline": None,
        "verification_status": "VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": "2024-01-12",
        "last_verified_date": "2026-09-06",
        "benefits": [
            ("Unemployment Allowance (Graduates)", "₹3,000 per month", "Monthly (up to 24 months)", "Bank DBT", "For eligible degree holders until employed"),
            ("Unemployment Allowance (Diploma)", "₹1,500 per month", "Monthly (up to 24 months)", "Bank DBT", "For eligible diploma holders until employed"),
        ],
        "rules": [
            ("residency", "AND", "state", "eq", "Karnataka", 0, 1, "Applicant must be domiciled in Karnataka"),
            ("edu", "AND", "education", "in", ["Graduate", "Diploma", "College", "Postgraduate"], 0, 1, "Applicant must hold a recognised Degree or Diploma"),
            ("occ", "AND", "occupation", "in", ["Unemployed", "Student"], 0, 1, "Applicant must not be currently employed"),
        ],
        "documents": [
            ("Aadhaar Card", 1, "For identity and DBT seeding"),
            ("Degree / Diploma Certificate & Marks Cards", 1, "From a recognised institution"),
            ("Domicile / Residence Certificate", 1, "Proof of Karnataka residency"),
            ("Bank Account Passbook", 1, "Aadhaar-linked bank account"),
        ],
        "sources": [
            ("Vikaspedia - Yuva Nidhi Scheme Karnataka", "https://schemes.vikaspedia.in/viewcontent/schemesall/state-specific-schemes/welfare-schemes-of-karnataka/yuva-nidhi-scheme-karnataka?lgn=en", "GOVT_KNOWLEDGE_PORTAL", "2026-09-06"),
            ("Bangalore Rural District Skill Development", "https://bangalorerural.nic.in/en/district-skill-development-office-2/", "DISTRICT_GOV_SITE", "2025-07-24"),
        ],
        "faqs": [
            ("Who is excluded from Yuva Nidhi?", "Individuals pursuing higher education, receiving apprenticeship stipends, employed, or availing other unemployment benefits are excluded.")
        ],
    },
    {
        "id": "shakti-karnataka",
        "slug": "shakti-karnataka",
        "name": "Shakti Scheme (Free Bus Travel)",
        "description": "100% zero-fare travel for women and transgender persons domiciled in Karnataka on eligible state-run non-luxury RTC buses.",
        "level": "KARNATAKA_STATE",
        "category": "Women and child welfare",
        "department": "Transport Department, Government of Karnataka",
        "target_beneficiaries": "Women, girls (6+ years), and transgender persons domiciled in Karnataka.",
        "application_portal": "https://sevasindhugs.karnataka.gov.in/",
        "notification_ref": "Karnataka Transport Department Shakti Guidelines",
        "deadline": None,
        "verification_status": "VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": "2023-06-11",
        "last_verified_date": "2026-11-11",
        "benefits": [
            ("Free Public Transport", "100% zero-fare travel on non-luxury KSRTC/BMTC/NWKRTC/KKRTC buses within Karnataka", "Per Trip", "Zero-fare Ticket / Shakti Smart Card", "Valid only on intra-state non-luxury buses")
        ],
        "rules": [
            ("residency", "AND", "state", "eq", "Karnataka", 0, 1, "Applicant must be domiciled in Karnataka"),
            ("gender", "AND", "gender", "in", ["Female", "Other"], 0, 1, "Applicable to women and transgender persons"),
            ("age", "AND", "age", "gte", 6, 0, 1, "Beneficiary must be aged 6 years or above"),
        ],
        "documents": [
            ("Government Photo ID (Aadhaar / Voter ID / Driving License)", 1, "Showing Karnataka address for conductor verification"),
        ],
        "sources": [
            ("Karnataka.com - Shakti Scheme Guide", "https://www.karnataka.com/govt/shakti-scheme-karnataka/", "STATE_INFO_PORTAL", "2026-11-11"),
        ],
        "faqs": [
            ("Is Shakti valid on interstate buses?", "No, free travel applies only to state-run non-luxury bus services operating within Karnataka.")
        ],
    },
    {
        "id": "sandhya-suraksha",
        "slug": "sandhya-suraksha",
        "name": "Sandhya Suraksha Yojana",
        "description": "Monthly social security pension of ₹1,200 for senior citizens aged 65 and above in Karnataka.",
        "level": "KARNATAKA_STATE",
        "category": "Social security and pensions",
        "department": "Revenue Department (Directorate of Social Security and Pensions), Government of Karnataka",
        "target_beneficiaries": "Senior citizens aged 65+ residing in Karnataka with combined annual income up to ₹1,20,000.",
        "application_portal": "https://sevasindhu.karnataka.gov.in/",
        "notification_ref": "Karnataka Revenue Department Social Security Pension",
        "deadline": None,
        "verification_status": "VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": "2007-07-01",
        "last_verified_date": "2026-11-21",
        "benefits": [
            ("Monthly Pension", "₹1,200 per month", "Monthly", "Bank / Post Office DBT", "For eligible senior citizens")
        ],
        "rules": [
            ("residency", "AND", "state", "eq", "Karnataka", 0, 1, "Applicant must be a resident of Karnataka"),
            ("age", "AND", "age", "gte", 65, 0, 1, "Applicant must be at least 65 years old"),
            ("income", "AND", "annual_family_income", "lte", 120000, 0, 1, "Combined annual income of applicant and spouse must not exceed ₹1,20,000"),
            ("excl_govt", "AND", "is_govt_employee", "is_true", None, 1, 1, "Applicants receiving another public or private pension are excluded"),
        ],
        "documents": [
            ("Aadhaar Card", 1, "Identity proof"),
            ("Age Proof (Birth Certificate / Voter ID / SSLC)", 1, "Confirming age 65+"),
            ("Income Certificate", 1, "Confirming annual income <= ₹1,20,000"),
            ("Bank or Post Office Passbook", 1, "For pension credit"),
        ],
        "sources": [
            ("Govt Schemes India - Karnataka Sandhya Suraksha", "https://m.govtschemes.in/karnataka-sandhya-suraksha-yojana", "SCHEME_GUIDE", "2026-11-21"),
        ],
        "faqs": [],
    },
    {
        "id": "manaswini-karnataka",
        "slug": "manaswini-karnataka",
        "name": "Manaswini Pension Scheme",
        "description": "Monthly financial assistance pension for poor unmarried, divorced, or legally separated women aged 40 to 64 in Karnataka.",
        "level": "KARNATAKA_STATE",
        "category": "Women and child welfare",
        "department": "Revenue Department (Social Security and Pensions), Government of Karnataka",
        "target_beneficiaries": "Unmarried, divorced, or legally separated BPL women aged 40–64 in Karnataka.",
        "application_portal": "https://sevasindhu.karnataka.gov.in/",
        "notification_ref": None,
        "deadline": None,
        "verification_status": "VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": None,
        "last_verified_date": "2026-08-12",
        "benefits": [
            ("Monthly Pension", "Monthly pension as notified by State Government", "Monthly", "Bank DBT", "Exact current rate subject to latest state budget notification")
        ],
        "rules": [
            ("residency", "AND", "state", "eq", "Karnataka", 0, 1, "Applicant must be a permanent resident of Karnataka"),
            ("gender", "AND", "gender", "eq", "Female", 0, 1, "Applicant must be a woman"),
            ("marital", "AND", "marital_status", "in", ["Unmarried", "Divorced", "Separated"], 0, 1, "Applicant must be unmarried, divorced, or legally separated"),
            ("age", "AND", "age", "between", [40, 64], 0, 1, "Age must be between 40 and 64 years"),
            ("ration", "AND", "ration_card_type", "in", ["BPL", "Antyodaya"], 0, 1, "Applicant must belong to BPL / economically weaker section"),
        ],
        "documents": [
            ("Aadhaar Card", 1, "Identity proof"),
            ("Age Proof", 1, "Confirming age 40–64"),
            ("BPL Ration Card / Income Certificate", 1, "Proof of BPL / income eligibility"),
            ("Bank Passbook", 1, "For DBT"),
        ],
        "sources": [
            ("IndiaFilings - Manaswini Scheme", "https://www.indiafilings.com/learn/manaswini-scheme-for-poor-women", "SCHEME_GUIDE", "2026-08-12"),
        ],
        "faqs": [],
    },
    {
        "id": "bhagyalakshmi-karnataka",
        "slug": "bhagyalakshmi-karnataka",
        "name": "Bhagyalakshmi Scheme",
        "description": "Financial support and maturity bond for up to two girl children born after 31 March 2006 in BPL families in Karnataka.",
        "level": "KARNATAKA_STATE",
        "category": "Women and child welfare",
        "department": "Women and Child Development Department, Government of Karnataka",
        "target_beneficiaries": "Girl children born in BPL families in Karnataka (up to 2 girl children per family).",
        "application_portal": "https://dwcd.karnataka.gov.in/",
        "notification_ref": None,
        "deadline": "Birth enrollment within 1 year of birth",
        "verification_status": "VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": "2006-04-01",
        "last_verified_date": "2026-09-18",
        "benefits": [
            ("Girl Child Maturity Bond & Scholarships", "Fixed deposit bond maturing at age 18 (subject to completing 8th standard & not marrying before 18)", "One-time maturity + annual scholarship", "Bond / DBT", "Up to 2 girl children per BPL family")
        ],
        "rules": [
            ("residency", "AND", "state", "eq", "Karnataka", 0, 1, "Family must reside in Karnataka"),
            ("gender", "AND", "gender", "eq", "Female", 0, 1, "Beneficiary must be a girl child"),
            ("age", "AND", "age", "lte", 18, 0, 1, "Child / beneficiary under 18 years"),
            ("ration", "AND", "ration_card_type", "in", ["BPL", "Antyodaya"], 0, 1, "Family must hold a BPL Ration Card"),
        ],
        "documents": [
            ("Birth Certificate", 1, "Registered within 1 year of birth"),
            ("BPL Ration Card", 1, "Proof of Below Poverty Line family"),
            ("Immunization Record", 1, "As per Health Department programme"),
            ("Parents Aadhaar & Bank Details", 1, "For enrollment"),
        ],
        "sources": [
            ("myScheme - Bhagyalaxmi Scheme", "https://www.myscheme.gov.in/schemes/bys", "OFFICIAL_PORTAL", "2026-09-18"),
            ("UMANG - Bhagyalaxmi Scheme", "https://web.umang.gov.in/landing/scheme/detail/bhagyalaxmi-scheme_bys.html", "OFFICIAL_PORTAL", "2026-11-20"),
        ],
        "faqs": [],
    },
    {
        "id": "ssp-post-matric",
        "slug": "ssp-post-matric",
        "name": "Karnataka SSP Post-Matric Scholarship (SC/ST/OBC/Minority)",
        "description": "State Scholarship Portal (SSP) post-matric tuition fee reimbursement and maintenance scholarship for SC, ST, OBC, and Minority students in Karnataka.",
        "level": "KARNATAKA_STATE",
        "category": "Education and scholarships",
        "department": "Social Welfare / Tribal Welfare / Backward Classes Welfare / Minority Welfare Departments, Karnataka",
        "target_beneficiaries": "Karnataka-domicile SC, ST, OBC, and Minority students pursuing post-matric courses.",
        "application_portal": "https://ssp.postmatric.karnataka.gov.in/",
        "notification_ref": "SSP Post-Matric 2026-27 Notification",
        "deadline": None,
        "verification_status": "VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": "2026-06-01",
        "last_verified_date": "2026-09-03",
        "benefits": [
            ("Tuition & Maintenance Allowance", "Course fee reimbursement + maintenance allowance (and Vidyasiri food/hostel add-on where eligible)", "Annual", "Aadhaar-seeded Bank DBT", "Rates vary by category and course group")
        ],
        "rules": [
            ("residency", "AND", "state", "eq", "Karnataka", 0, 1, "Student must be a permanent resident / domicile of Karnataka"),
            ("occ", "AND", "occupation", "eq", "Student", 0, 1, "Applicant must be a student"),
            ("edu", "AND", "education", "in", ["College", "IT / Computer course", "Skill / Vocational course", "Graduate", "Postgraduate"], 0, 1, "Must be pursuing a post-matric course at a recognised institution"),
            ("cat", "AND", "social_category", "in", ["SC", "ST", "SC/ST", "OBC", "Minority"], 0, 1, "Must belong to SC, ST, OBC, or Minority category"),
            ("income", "AND", "annual_family_income", "lte", 250000, 0, 1, "Annual family income within prescribed limit (₹2.5 lakh confirmed for SC; check SSP notice for other categories)"),
        ],
        "documents": [
            ("Aadhaar Card", 1, "Student & parents Aadhaar"),
            ("Caste Certificate (RD Number)", 1, "Issued by Revenue Dept"),
            ("Income Certificate (RD Number)", 1, "Valid family income certificate"),
            ("College Admission / Fee Receipt & Marks Cards", 1, "Current academic year"),
        ],
        "sources": [
            ("SSP Post-Matric Portal", "https://ssp.postmatric.karnataka.gov.in/", "OFFICIAL_PORTAL", "2026-09-03"),
            ("Buddy4Study - SSP Scholarship 2026-27", "https://www.buddy4study.com/article/ssp-scholarship", "EDUCATION_PORTAL", "2026-09-03"),
        ],
        "faqs": [],
    },
    {
        "id": "arivu-kmdc",
        "slug": "arivu-kmdc",
        "name": "Arivu Education Loan Scheme (KMDC)",
        "description": "Low-interest (2% p.a.) education loan up to ₹3,00,000 for religious minority students in Karnataka admitted to professional courses.",
        "level": "KARNATAKA_STATE",
        "category": "Minority welfare",
        "department": "Minorities Welfare Department / Karnataka Minorities Development Corporation (KMDC)",
        "target_beneficiaries": "Karnataka religious minority students pursuing CET/NEET professional courses with family income < ₹8 lakh.",
        "application_portal": "https://kmdc.karnataka.gov.in/",
        "notification_ref": None,
        "deadline": None,
        "verification_status": "VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": None,
        "last_verified_date": "2026-10-13",
        "benefits": [
            ("Education Loan", "Up to ₹3,00,000 per course duration at 2% per annum interest", "Per Course", "Direct to Institution / KMDC", "Repayable after moratorium period")
        ],
        "rules": [
            ("residency", "AND", "state", "eq", "Karnataka", 0, 1, "Student must be a resident of Karnataka"),
            ("occ", "AND", "occupation", "eq", "Student", 0, 1, "Applicant must be a student"),
            ("cat", "AND", "social_category", "eq", "Minority", 0, 1, "Must belong to a notified religious minority community"),
            ("income", "AND", "annual_family_income", "lte", 800000, 0, 1, "Annual family income must be below ₹8,00,000"),
        ],
        "documents": [
            ("Aadhaar Card", 1, "Identity proof"),
            ("Minority Community Certificate", 1, "Issued by competent authority"),
            ("Income Certificate", 1, "Family income < ₹8 lakh"),
            ("CET / NEET Admission & Fee Structure", 1, "Proof of admission"),
        ],
        "sources": [
            ("myScheme - Arivu Education Loan Scheme", "https://www.myscheme.gov.in/schemes/aels", "OFFICIAL_PORTAL", "2026-09-18"),
        ],
        "faqs": [],
    },
    {
        "id": "pm-kisan",
        "slug": "pm-kisan",
        "name": "PM-KISAN Samman Nidhi",
        "description": "Central Government income support of ₹6,000 per year in three equal installments of ₹2,000 to landholding farmer families.",
        "level": "CENTRAL",
        "category": "Agriculture and farmers",
        "department": "Ministry of Agriculture and Farmers Welfare, Government of India",
        "target_beneficiaries": "All landholding farmer families (subject to exclusion criteria).",
        "application_portal": "https://pmkisan.gov.in/",
        "notification_ref": "PM-KISAN Revised Operational Guidelines",
        "deadline": None,
        "verification_status": "VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": "2018-12-01",
        "last_verified_date": "2026-09-18",
        "benefits": [
            ("Income Support", "₹6,000 per year (3 installments of ₹2,000 every 4 months)", "Tri-annual", "Aadhaar-seeded Bank DBT", "Subject to eKYC and land seeding")
        ],
        "rules": [
            ("occ", "AND", "occupation", "eq", "Farmer", 0, 1, "Applicant must be a farmer"),
            ("land", "AND", "land_owned_acres", "gt", 0, 0, 1, "Farmer family must own cultivable land"),
            ("excl_tax", "AND", "is_taxpayer", "is_true", None, 1, 1, "Income Tax payers in last assessment year are excluded"),
            ("excl_govt", "AND", "is_govt_employee", "is_true", None, 1, 1, "Serving/retired Central or State Govt officers/employees (excluding Group D/MTS) are excluded"),
        ],
        "documents": [
            ("Aadhaar Card", 1, "Mandatory for eKYC"),
            ("Land Ownership Record (RTC / Pahani)", 1, "Cultivable landholding proof"),
            ("Bank Account Passbook", 1, "Aadhaar-linked for DBT"),
        ],
        "sources": [
            ("PM-KISAN Official Portal", "https://pmkisan.gov.in/", "OFFICIAL_PORTAL", "2026-09-18"),
            ("myScheme - PM-KISAN", "https://www.myscheme.gov.in/schemes/pm-kisan", "OFFICIAL_PORTAL", "2026-09-18"),
        ],
        "faqs": [],
    },
    {
        "id": "ab-pmjay",
        "slug": "ab-pmjay",
        "name": "Ayushman Bharat - Pradhan Mantri Jan Arogya Yojana (AB PM-JAY)",
        "description": "Cashless secondary and tertiary hospitalization coverage up to ₹5,00,000 per family per year; also covers all senior citizens aged 70+ irrespective of income.",
        "level": "CENTRAL",
        "category": "Health and medical assistance",
        "department": "National Health Authority, Ministry of Health & Family Welfare, Government of India",
        "target_beneficiaries": "Eligible SECC/BPL vulnerable families AND all senior citizens aged 70+ regardless of income.",
        "application_portal": "https://beneficiary.nha.gov.in/",
        "notification_ref": "Union Cabinet Expansion (Sep 2024 - 70+ Senior Citizens)",
        "deadline": None,
        "verification_status": "VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": "2024-09-11",
        "last_verified_date": "2026-11-24",
        "benefits": [
            ("Health Insurance Cover", "Up to ₹5,00,000 per family per year", "Annual", "Cashless Hospitalization", "Covers pre- and post-hospitalization at empaneled hospitals")
        ],
        "rules": [
            ("elig_or", "OR", "age", "gte", 70, 0, 1, "All senior citizens aged 70 years and above qualify irrespective of income"),
            ("elig_or", "OR", "ration_card_type", "in", ["BPL", "Antyodaya"], 0, 1, "OR household belongs to BPL / Antyodaya / SECC vulnerable category"),
        ],
        "documents": [
            ("Aadhaar Card", 1, "For eKYC & Ayushman Card generation"),
            ("Ration Card / Family ID", 0, "For SECC/BPL family verification (not required for 70+ senior citizen cover)"),
        ],
        "sources": [
            ("India.gov.in - AB PM-JAY", "https://www.india.gov.in/spotlight/details/ayushman-bharat-pradhan-mantri-jan-arogya-yojana", "OFFICIAL_PORTAL", "2026-11-24"),
            ("NHA Beneficiary Portal", "https://beneficiary.nha.gov.in/", "OFFICIAL_PORTAL", "2026-11-24"),
        ],
        "faqs": [],
    },
    {
        "id": "pmegp",
        "slug": "pmegp",
        "name": "Prime Minister's Employment Generation Programme (PMEGP)",
        "description": "Credit-linked subsidy scheme for setting up new micro-enterprises in manufacturing and service sectors with no income ceiling.",
        "level": "CENTRAL",
        "category": "Small businesses and entrepreneurship",
        "department": "Ministry of MSME (implemented by KVIC), Government of India",
        "target_beneficiaries": "Individuals aged 18+ starting new non-farm micro-enterprises.",
        "application_portal": "https://pmegp.msme.gov.in/",
        "notification_ref": "KVIC PMEGP Guidelines",
        "deadline": None,
        "verification_status": "VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": "2008-08-15",
        "last_verified_date": "2026-09-18",
        "benefits": [
            ("Margin Money Subsidy", "15% to 35% government subsidy on project cost (higher for Rural & Special Categories SC/ST/OBC/Women/Minority)", "One-time", "Bank Loan + Subsidy Adjustment", "No income ceiling for applicants")
        ],
        "rules": [
            ("age", "AND", "age", "gte", 18, 0, 1, "Applicant must be at least 18 years old"),
            ("occ", "AND", "occupation", "in", ["Business", "Worker", "Unemployed", "Other"], 0, 1, "Applicant intends to run/start a non-farm micro-enterprise"),
        ],
        "documents": [
            ("Aadhaar Card & PAN Card", 1, "Identity and tax ID"),
            ("Project Report / Business Plan", 1, "Detailing manufacturing or service unit"),
            ("Educational Qualification Certificate", 0, "8th pass required if project cost > ₹10L (mfg) or > ₹5L (service)"),
            ("Social Category / Rural Area Certificate", 0, "For higher subsidy slab"),
        ],
        "sources": [
            ("myScheme - PMEGP", "https://www.myscheme.gov.in/schemes/pmegp", "OFFICIAL_PORTAL", "2026-09-18"),
            ("PMEGP Official Portal", "https://pmegp.msme.gov.in/", "OFFICIAL_PORTAL", "2026-09-18"),
        ],
        "faqs": [],
    },
    {
        "id": "igndps-disability",
        "slug": "igndps-disability",
        "name": "Indira Gandhi National Disability Pension Scheme (IGNDPS) & UDID",
        "description": "Monthly social security pension for BPL persons with severe or multiple disabilities (80%+) aged 18 and above.",
        "level": "CENTRAL",
        "category": "Disability welfare",
        "department": "Ministry of Rural Development (NSAP) & Dept of Empowerment of Persons with Disabilities",
        "target_beneficiaries": "BPL persons aged 18+ with 80% or more disability.",
        "application_portal": "https://swavlambancard.gov.in/",
        "notification_ref": "NSAP IGNDPS Guidelines",
        "deadline": None,
        "verification_status": "VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": "2009-02-01",
        "last_verified_date": "2026-11-20",
        "benefits": [
            ("Monthly Disability Pension", "Central assistance + State top-up (₹800–₹1,400+ depending on state)", "Monthly", "Bank DBT", "Plus UDID card travel/welfare concessions")
        ],
        "rules": [
            ("age", "AND", "age", "gte", 18, 0, 1, "Applicant must be 18 years or older"),
            ("dis", "AND", "disability_status", "eq", "Yes", 0, 1, "Applicant must be a person with disability"),
            ("dis_pct", "AND", "disability_percentage", "gte", 80, 0, 1, "Disability percentage must be 80% or more for IGNDPS"),
            ("ration", "AND", "ration_card_type", "in", ["BPL", "Antyodaya"], 0, 1, "Applicant must belong to a BPL family"),
        ],
        "documents": [
            ("UDID Card / Disability Certificate", 1, "Confirming 80%+ disability"),
            ("Aadhaar Card", 1, "Identity proof"),
            ("BPL Ration Card", 1, "Poverty line proof"),
            ("Bank Passbook", 1, "For DBT"),
        ],
        "sources": [
            ("myScheme - IGNDPS", "https://www.myscheme.gov.in/schemes/igndps", "OFFICIAL_PORTAL", "2026-09-18"),
            ("UDID Portal", "https://swavlambancard.gov.in/", "OFFICIAL_PORTAL", "2026-11-24"),
        ],
        "faqs": [],
    },
    {
        "id": "krishi-bhagya",
        "slug": "krishi-bhagya",
        "name": "Krishi Bhagya Scheme",
        "description": "Karnataka dryland agriculture support providing subsidies for farm ponds (Krishi Honda), polythene lining, diesel/solar pump sets, and micro-irrigation.",
        "level": "KARNATAKA_STATE",
        "category": "Agriculture and farmers",
        "department": "Department of Agriculture, Government of Karnataka",
        "target_beneficiaries": "Dryland farmers in Karnataka.",
        "application_portal": "https://raitamitra.karnataka.gov.in/",
        "notification_ref": None,
        "deadline": None,
        "verification_status": "PARTIALLY_VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": None,
        "last_verified_date": "2026-11-01",
        "benefits": [
            ("Farm Pond & Irrigation Subsidy", "Up to 80% subsidy for General farmers (pump sets capped at 50%); higher slab for SC/ST", "Project-based", "Subsidy Reimbursement", "Exact district-wise component caps require Raitha Samparka Kendra verification")
        ],
        "rules": [
            ("residency", "AND", "state", "eq", "Karnataka", 0, 1, "Farmer must be a resident of Karnataka"),
            ("occ", "AND", "occupation", "eq", "Farmer", 0, 1, "Applicant must be a farmer"),
            ("land", "AND", "land_owned_acres", "gt", 0, 0, 1, "Must own agricultural land"),
        ],
        "documents": [
            ("Aadhaar Card", 1, "Identity proof"),
            ("RTC / Pahani (Land Record)", 1, "Proof of agricultural land"),
            ("Bank Passbook", 1, "For subsidy transfer"),
        ],
        "sources": [
            ("Krishi Bhagya Guide", "https://allindiacschelp.com/krishi-bhagya-scheme/", "SCHEME_GUIDE", "2026-11-01"),
        ],
        "faqs": [],
    },
    {
        "id": "anna-bhagya",
        "slug": "anna-bhagya",
        "name": "Anna Bhagya Scheme",
        "description": "Food security guarantee providing free foodgrains / DBT cash-in-lieu to Antyodaya and BPL ration card holders in Karnataka.",
        "level": "KARNATAKA_STATE",
        "category": "Food security",
        "department": "Department of Food, Civil Supplies and Consumer Affairs, Government of Karnataka",
        "target_beneficiaries": "BPL and Antyodaya Anna Yojana (AAY) ration card holders in Karnataka.",
        "application_portal": "https://ahara.karnataka.gov.in/",
        "notification_ref": None,
        "deadline": None,
        "verification_status": "PARTIALLY_VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": "2023-07-01",
        "last_verified_date": "2026-09-23",
        "benefits": [
            ("Free Foodgrains / DBT", "Free rice / cash equivalent per family member on BPL/AAY ration card", "Monthly", "PDS Fair Price Shop / DBT", "Exact per-kg vs DBT split varies by current state supply order")
        ],
        "rules": [
            ("residency", "AND", "state", "eq", "Karnataka", 0, 1, "Applicant must reside in Karnataka"),
            ("ration", "AND", "ration_card_type", "in", ["BPL", "Antyodaya"], 0, 1, "Household must hold a BPL or Antyodaya Ration Card"),
        ],
        "documents": [
            ("BPL / Antyodaya Ration Card", 1, "Active card on Ahara portal"),
            ("Aadhaar Card", 1, "Seeded with ration card for eKYC"),
        ],
        "sources": [
            ("Karnataka.com - Anna Bhagya", "https://www.karnataka.com/govt/anna-bhagya-scheme/", "STATE_INFO_PORTAL", "2026-09-23"),
        ],
        "faqs": [],
    },
    {
        "id": "pm-awas-yojana",
        "slug": "pm-awas-yojana",
        "name": "Pradhan Mantri Awas Yojana (PMAY - Urban & Gramin)",
        "description": "Housing assistance and interest subsidy for eligible houseless or kutcha-house families in rural (PMAY-G) and urban (PMAY-U) areas.",
        "level": "CENTRAL",
        "category": "Housing and shelter",
        "department": "Ministry of Housing and Urban Affairs / Ministry of Rural Development, Government of India",
        "target_beneficiaries": "EWS/LIG families without a pucca house.",
        "application_portal": "https://pmaymis.gov.in/",
        "notification_ref": None,
        "deadline": None,
        "verification_status": "PARTIALLY_VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": "2015-06-25",
        "last_verified_date": "2026-09-18",
        "benefits": [
            ("Housing Financial Assistance / Subsidy", "Central & State assistance for pucca house construction", "Milestone-linked", "Bank DBT", "Exact PMAY-U 2.0 vs PMAY-G slab depends on urban/rural component")
        ],
        "rules": [
            ("income", "AND", "annual_family_income", "lte", 600000, 0, 1, "Annual family income within EWS/LIG limit (up to ₹6,00,000 for EWS/LIG)"),
        ],
        "documents": [
            ("Aadhaar Card", 1, "Identity proof"),
            ("Income Certificate", 1, "EWS/LIG verification"),
            ("Residence / Land / BPL Proof", 1, "Rural or urban household proof"),
        ],
        "sources": [
            ("myScheme - PMAY-U", "https://www.myscheme.gov.in/schemes/pmay-u", "OFFICIAL_PORTAL", "2026-09-18"),
            ("myScheme - PMAY-G", "https://www.myscheme.gov.in/schemes/pmay-g", "OFFICIAL_PORTAL", "2026-09-18"),
        ],
        "faqs": [],
    },
    {
        "id": "pmmsy-fisheries",
        "slug": "pmmsy-fisheries",
        "name": "Pradhan Mantri Matsya Sampada Yojana (PMMSY)",
        "description": "Financial subsidy for fish farmers, fishers, and aquaculture enterprises to develop inland and marine fisheries.",
        "level": "CENTRAL",
        "category": "Animal husbandry and fisheries",
        "department": "Department of Fisheries, Ministry of Fisheries, Animal Husbandry & Dairying",
        "target_beneficiaries": "Fish farmers, fishers, SHGs, and fisheries societies aged 18+.",
        "application_portal": "https://dof.gov.in/",
        "notification_ref": None,
        "deadline": None,
        "verification_status": "VERIFIED",
        "operational_status": "ACTIVE",
        "effective_date": "2020-09-10",
        "last_verified_date": "2026-09-18",
        "benefits": [
            ("Capital Subsidy", "40% subsidy (General) or 60% subsidy (SC/ST/Women) on approved fisheries project cost", "Project-based", "Bank / Department DBT", "Requires own land or 10-year lease for construction units")
        ],
        "rules": [
            ("age", "AND", "age", "gte", 18, 0, 1, "Applicant must be above 18 years of age"),
            ("occ", "AND", "occupation", "in", ["Farmer", "Business", "Worker", "Other"], 0, 1, "Applicant must be involved in fisheries / aquaculture"),
        ],
        "documents": [
            ("Aadhaar Card / Voter ID", 1, "Identity proof"),
            ("Bank Account Passbook", 1, "Own bank account"),
            ("Land Ownership or 10-Year Lease Document", 1, "For aquaculture pond/unit construction"),
        ],
        "sources": [
            ("myScheme - PMMSY", "https://www.myscheme.gov.in/schemes/pmmsy", "OFFICIAL_PORTAL", "2026-09-18"),
        ],
        "faqs": [],
    },
    # Example of a scheme whose current 2026 operational status / rules could not be verified from official sources:
    {
        "id": "karnataka-unverified-livelihood-grant",
        "slug": "karnataka-unverified-livelihood-grant",
        "name": "Karnataka Rural Artisan Livelihood Top-Up (Pending Verification)",
        "description": "Scheme record awaiting official department circular verification before eligibility can be evaluated.",
        "level": "KARNATAKA_STATE",
        "category": "Livelihood and self-employment",
        "department": "Rural Development and Panchayat Raj Department, Karnataka",
        "target_beneficiaries": None,
        "application_portal": None,
        "notification_ref": None,
        "deadline": None,
        "verification_status": "NOT_VERIFIED",
        "operational_status": "NOT_VERIFIED",
        "effective_date": None,
        "last_verified_date": None,
        "benefits": [],
        "rules": [],
        "documents": [],
        "sources": [],
        "faqs": [],
    },
]


def _default_10_steps(scheme_name: str, portal: str | None, department: str | None) -> list[tuple]:
    p_url = portal or "https://sevasindhu.karnataka.gov.in/"
    dept = department or "the concerned Government Department"
    return [
        (1, "WHERE_TO_APPLY", "Where to apply", f"Apply online via the official portal or visit an authorised Karnataka One / Grama One / CSC centre for {scheme_name}.", "HYBRID", p_url),
        (2, "OFFICIAL_PORTAL", "Open the official portal", f"Open {p_url} in your browser (verify the .gov.in / .nic.in domain).", "ONLINE", p_url),
        (3, "LOGIN_REQUIREMENTS", "Registration or login", "Register or log in using your Aadhaar-linked mobile number and OTP (or Seva Sindhu / Jan Parichay credentials).", "ONLINE", p_url),
        (4, "SELECT_SCHEME", "Select the scheme", f"Search for '{scheme_name}' in the services list and open the official application form.", "ONLINE", p_url),
        (5, "COMPLETE_FORM", "Complete the application", "Enter your personal, family, income, and bank account details carefully matching your Aadhaar and Ration Card.", "ONLINE", p_url),
        (6, "UPLOAD_DOCUMENTS", "Upload required documents", "Scan and upload clear copies of all mandatory documents listed under the scheme requirements.", "ONLINE", p_url),
        (7, "REVIEW_SUBMIT", "Review and submit", "Preview every field, read the official self-declaration, and click Submit.", "ONLINE", p_url),
        (8, "ACKNOWLEDGEMENT", "Save acknowledgement number", "Download or print the acknowledgement receipt and note the Application Reference Number.", "ONLINE", p_url),
        (9, "TRACK_STATUS", "Track application status", f"Return to {p_url} and use 'Track Your Application' with your Application Reference Number.", "ONLINE", p_url),
        (10, "OFFICIAL_ASSISTANCE", "Obtain official assistance", f"For help, contact {dept} or visit your nearest Taluk Office, Karnataka One, or Grama One centre.", "CSC_SERVICE_CENTRE", p_url),
    ]


def seed_database(db_path: str | None = None) -> int:
    init_db(db_path)
    conn = get_connection(db_path)
    now = utc_now()
    count = 0

    for sc in VERIFIED_SCHEMES:
        existing = conn.execute("SELECT id FROM schemes WHERE id = ?", (sc["id"],)).fetchone()
        if existing:
            continue

        conn.execute(
            """
            INSERT INTO schemes (
                id, slug, name, description, level, category, department,
                target_beneficiaries, application_portal, notification_ref, deadline,
                verification_status, operational_status, effective_date, last_verified_date,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sc["id"], sc["slug"], sc["name"], sc["description"], sc["level"],
                sc["category"], sc["department"], sc["target_beneficiaries"],
                sc["application_portal"], sc["notification_ref"], sc["deadline"],
                sc["verification_status"], sc["operational_status"],
                sc["effective_date"], sc["last_verified_date"], now, now,
            ),
        )

        for rg, logic, field, op, exp, is_excl, is_mand, desc in sc["rules"]:
            conn.execute(
                """
                INSERT INTO eligibility_rules (
                    scheme_id, rule_group, logic_operator, field_name, operator,
                    expected_value, is_exclusion, is_mandatory, description, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sc["id"], rg, logic, field, op, json.dumps(exp) if exp is not None else None, is_excl, is_mand, desc, now),
            )

        for b_type, amt, freq, mode, notes in sc["benefits"]:
            conn.execute(
                "INSERT INTO scheme_benefits (scheme_id, benefit_type, amount_or_value, frequency, disbursement_mode, notes) VALUES (?, ?, ?, ?, ?, ?)",
                (sc["id"], b_type, amt, freq, mode, notes),
            )

        for d_name, is_mand, notes in sc["documents"]:
            conn.execute(
                "INSERT INTO required_documents (scheme_id, document_name, is_mandatory, notes) VALUES (?, ?, ?, ?)",
                (sc["id"], d_name, is_mand, notes),
            )

        for step_num, step_cat, title, instr, mode, p_url in _default_10_steps(sc["name"], sc["application_portal"], sc["department"]):
            conn.execute(
                "INSERT INTO application_steps (scheme_id, step_number, step_category, title, instruction, mode, portal_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sc["id"], step_num, step_cat, title, instr, mode, p_url),
            )

        for s_name, s_url, s_type, v_date in sc["sources"]:
            conn.execute(
                "INSERT INTO official_sources (scheme_id, source_name, source_url, source_type, verified_date) VALUES (?, ?, ?, ?, ?)",
                (sc["id"], s_name, s_url, s_type, v_date),
            )

        for q, a in sc["faqs"]:
            conn.execute(
                "INSERT INTO scheme_faqs (scheme_id, question, answer) VALUES (?, ?, ?)",
                (sc["id"], q, a),
            )

        count += 1

    conn.commit()
    conn.close()
    return count


if __name__ == "__main__":
    inserted = seed_database()
    print(f"Seeded {inserted} schemes into SQLite database.")
