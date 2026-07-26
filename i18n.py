import os

LANGUAGE = os.getenv('LANGUAGE', 'en')

TRANSLATIONS = {
    'en': {
        'welcome': '=== GHANA VOTING SYSTEM MAIN MENU ===',
        'reg_setup': '1. Registration & Setup (Admin/Voter)',
        'cast_vote': '2. Cast Vote',
        'view_results': '3. View Election Results',
        'exit': '4. Exit',
        'enter_choice': 'Enter your choice: ',
        'invalid_choice': 'Invalid choice. Please try again.',
        'exiting': 'Exiting system. Goodbye!',
        'reg_menu': '--- Registration Menu ---',
        'admin_setup': '1. Administrative Setup (Candidates, Constituencies, MPs)',
        'voter_reg': '2. Voter Registration',
        'back': '3. Back to Main Menu',
        'voting_section': '--- Voting Section ---',
        'results_section': '--- Election Results ---',
        'vote_mp': '** Vote for your preferred MP for {constituency} **',
        'vote_president': '** Vote for your preferred presidential candidate **',
        'enter_id': 'Enter voter ID: ',
        'enter_password': 'Enter password: ',
        'already_voted': 'Sorry, but it seems you have casted your vote already',
        'vote_success': 'Vote successfully cast!',
        'invalid_id': 'Sorry, you have entered an invalid id.',
        'polling_station': 'Polling Station: ',
        'region': 'Region: ',
        'constituency': 'Constituency: ',
        'president_results': 'Presidential vote results',
        'mp_results': 'MP vote results for {constituency} constituency',
        'party': 'Party',
        'candidate': 'Candidate',
        'votes': 'Votes',
        'percentage': 'Percentage',
        'form_1a': '--- EC GHANA FORM 1A: PRESIDENTIAL RESULTS ---',
        'form_1c': '--- EC GHANA FORM 1C: PARLIAMENTARY RESULTS ---',
        'total_valid': 'Total Valid Votes',
        'rejected': 'Rejected Votes',
        'registered': 'Registered Voters',
        'turnout': 'Voter Turnout',
    },
    'tw': {
        'welcome': '=== GHANA VOTING SYSTEM - TWI EDITION ===',
        'reg_setup': '1. Nkontaabu ne Nhyehyee (Admin/Osoo)',
        'cast_vote': '2. To Ba',
        'view_results': '3. Hwɛ Abatoɔ Rezɔti',
        'exit': '4. Pue',
        'enter_choice': 'Wɔ wo bedwɛ: ',
        'invalid_choice': 'Bedwɛ a woafa no nnye. Yɛsrɛ sɛ pɛsɛnkaw.',
        'exiting': 'Opuw. Nante yiye!',
        'reg_menu': '--- Nkontaabu Nhyehyee ---',
        'admin_setup': '1. Nhyehyee a Ɛfa Adwumayɛfo (Dibegufo, Mmransɛm, MP ho)',
        'voter_reg': '2. Osooni Nkontaabu',
        'back': '3. Kɔ Main Menu',
        'voting_section': '--- Ba Toe ---',
        'results_section': '--- Abatoɔ Rezɔti ---',
    },
    'ee': {
        'welcome': '=== GHANA VOTING SYSTEM - EWE EDITION ===',
        'reg_setup': '1. Nyaɖeɖefe kple Dɔwɔwɔ (Admin/Votɔ)',
        'cast_vote': '2. Ɖo Vot',
        'view_results': '3. Kpɔ Rezɔtiwo',
        'exit': '4. Do Go',
        'enter_choice': 'Tia wò nya: ',
        'invalid_choice': 'Wò tiatia mele eŋu o. Taflatse ga tia.',
        'exiting': 'Do go. Nyo ayi!',
        'reg_menu': '--- Nyaɖeɖefe Menu ---',
        'admin_setup': '1. Dɔwɔlawo (Kandidawo, Nutomewo, MP)',
        'voter_reg': '2. Votɔ Nyaɖeɖefe',
        'back': '3. Gbɔ yi Main Menu',
        'voting_section': '--- Vot Ɖoɖo Fe ---',
        'results_section': '--- Abatoɔwo Ƒe Seɖoƒe ---',
    },
}


def _(key, **kwargs):
    """Translate a key into the configured language, falling back to English, with optional formatting."""
    lang = LANGUAGE
    if lang not in TRANSLATIONS:
        lang = 'en'
    msg = TRANSLATIONS[lang].get(key, TRANSLATIONS['en'].get(key, key))
    if kwargs:
        return msg.format(**kwargs)
    return msg
