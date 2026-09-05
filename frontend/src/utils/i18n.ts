/**
 * RISKSETU AI — Multilingual translation layer.
 *
 * Supports English (en), Hindi (hi), and Assamese (as).
 * Translates core UI navigation, action triggers, SOS flows, and safety guidance.
 * Preserves source-language operational evidence without machine translation artifacts.
 */

export type SupportedLanguage = 'en' | 'hi' | 'as';

export const TRANSLATIONS = {
  en: {
    // Navigation & Workflow
    risk: 'RISK',
    impact: 'IMPACT',
    priority: 'PRIORITY',
    alerts: 'ALERTS',
    weather: 'WEATHER',
    sos: 'SOS',
    report: 'REPORT',
    simulate: 'SIMULATE ROAD FAILURE',
    officer: 'OFFICER OPS',

    // SOS Flow
    sosTitle: 'EMERGENCY REPORT',
    sosPrompt: 'Send an emergency location report to the system?',
    sosDisclaimer: 'RiskSetu does not replace official emergency services. For direct emergency help, dial 112 or 108.',
    call112: 'Call 112 (National)',
    call108: 'Call 108 (Ambulance)',
    sendSos: 'SEND SOS',
    confirmSos: 'CONFIRM & SEND SOS',
    queueSos: 'CONFIRM & QUEUE SOS (OFFLINE)',
    cancel: 'CANCEL',
    close: 'CLOSE',
    offlineNotice: 'Device is offline. Your report is securely queued in local storage and will sync automatically upon reconnection.',

    // Verification & Disclaimers
    communitySignal: 'COMMUNITY SIGNAL',
    communityNotice: 'Community signals provide field awareness; authorized officers provide verified operational status.',
    shelterUnavail: 'VERIFIED SHELTER DATA UNAVAILABLE',
    terrainUnavail: 'TERRAIN INTELLIGENCE UNAVAILABLE',
    sirenNotice: 'Browser siren operates under web audio permissions and cannot override phone hardware silent mode.',

    // Actions
    confirm: 'Confirm',
    yes: 'I can confirm',
    no: 'Do not see it',
    unsure: 'Unsure',
    submit: 'Submit Report',

    // Extended keys for ported features
    emergencyReport: 'EMERGENCY REPORT',
    emergencyDisclaimer: 'RiskSetu is decision-support software. It does not replace official emergency services. For direct emergency assistance, call 112 (National) or 108 (Ambulance).',
    submitReport: 'REPORT',
    simulateRoadFailure: 'SIMULATE',
    officerWorkspace: 'OFFICER COMMAND WORKSPACE',
    sosQueue: 'SOS QUEUE',
    massAlertBroadcast: 'MASS ALERT',
    osintScanner: 'OSINT INTEL',
    catchmentScreening: 'Upstream Catchment Screening',
    confirmObservation: 'I can confirm',
    disputeObservation: 'Do not see it',
    unsureObservation: 'Unsure',
  },
  hi: {
    // Navigation & Workflow
    risk: 'जोखिम',
    impact: 'प्रभाव',
    priority: 'प्राथमिकता',
    alerts: 'चेतावनियाँ',
    weather: 'मौसम',
    sos: 'आपातकाल',
    report: 'रिपोर्ट करें',
    simulate: 'सड़क विफलता सिमुलेशन',
    officer: 'अधिकारी संचालन',

    // SOS Flow
    sosTitle: 'आपातकालीन रिपोर्ट',
    sosPrompt: 'क्या आप इस स्थान के लिए आपातकालीन संदेश भेजना चाहते हैं?',
    sosDisclaimer: 'जोखिमसेतु आधिकारिक आपातकालीन सेवाओं का विकल्प नहीं है। तत्काल सहायता हेतु 112 या 108 पर कॉल करें।',
    call112: '112 पर कॉल करें',
    call108: '108 एम्बुलेंस',
    sendSos: 'एसओएस भेजें',
    confirmSos: 'पुष्टि करें और भेजें',
    queueSos: 'पुष्टि करें और ऑफलाइन सहेजें',
    cancel: 'रद्द करें',
    close: 'बंद करें',
    offlineNotice: 'डिवाइस ऑफलाइन है। आपका संदेश सुरक्षित रूप से कतारबद्ध है और इंटरनेट वापस आने पर स्वतः भेजा जाएगा।',

    // Verification & Disclaimers
    communitySignal: 'सामुदायिक संकेत',
    communityNotice: 'नागरिक रिपोर्ट जागरूकता हेतु हैं; अधिकृत अधिकारी अंतिम परिचालन सत्यापन प्रदान करते हैं।',
    shelterUnavail: 'सत्यापित आश्रय डेटा अनुपलब्ध',
    terrainUnavail: 'भूभाग विश्लेषण अनुपलब्ध',
    sirenNotice: 'वेब सायरन केवल ब्राउज़र अनुमति पर कार्य करता है और फोन के साइलेंट मोड को बाईपास नहीं कर सकता।',

    // Actions
    confirm: 'पुष्टि करें',
    yes: 'मैं पुष्टि करता हूँ',
    no: 'मुझे नहीं दिखा',
    unsure: 'अनिश्चित',
    submit: 'रिपोर्ट जमा करें',

    // Extended keys
    emergencyReport: 'आपातकालीन रिपोर्ट',
    emergencyDisclaimer: 'जोखिमसेतु आधिकारिक आपातकालीन सेवाओं का विकल्प नहीं है। तत्काल सहायता हेतु 112 या 108 पर कॉल करें।',
    submitReport: 'रिपोर्ट',
    simulateRoadFailure: 'सिमुलेशन',
    officerWorkspace: 'अधिकारी कमांड कार्यक्षेत्र',
    sosQueue: 'एसओएस कतार',
    massAlertBroadcast: 'सामूहिक सतर्कता',
    osintScanner: 'ओपन इंटेलिजेंस',
    catchmentScreening: 'ऊपरी जलग्रहण स्क्रीनिंग',
    confirmObservation: 'मैं पुष्टि करता हूँ',
    disputeObservation: 'मुझे नहीं दिखा',
    unsureObservation: 'अनिश्चित',
  },
  as: {
    // Navigation & Workflow
    risk: 'বিপদ',
    impact: 'প্ৰভাৱ',
    priority: 'প্ৰাথমিকতা',
    alerts: 'সতৰ্কবাণী',
    weather: 'বতৰ',
    sos: 'জৰুৰীকালীন',
    report: 'প্ৰতিবেদন',
    simulate: 'পথ বন্ধৰ অনুকৰণ',
    officer: 'বিষয়াসকলৰ কাৰ্যালয়',

    // SOS Flow
    sosTitle: 'জৰুৰীকালীন প্ৰতিবেদন',
    sosPrompt: 'আপুনি এই স্থানৰ বাবে জৰুৰীকালীন সংকেত প্ৰেৰণ কৰিব বিচাৰে নেকি?',
    sosDisclaimer: 'ৰিস্কসেতু চৰকাৰী জৰুৰীকালীন সেৱাৰ বিকল্প নহয়। পোনপটীয়া সহায়ৰ বাবে ১১২ বা ১০৮ নম্বৰত যোগাযোগ কৰক।',
    call112: '১১২ লৈ কল কৰক',
    call108: '১০৮ এম্বুলেন্স',
    sendSos: 'এছঅ’এছ প্ৰেৰণ কৰক',
    confirmSos: 'নিশ্চিত কৰি প্ৰেৰণ কৰক',
    queueSos: 'নিশ্চিত কৰি অফলাইন সংৰক্ষণ কৰক',
    cancel: 'বাতিল কৰক',
    close: 'বন্ধ কৰক',
    offlineNotice: 'ইন্টাৰনেট সংযোগ নাই। আপোনাৰ তথ্য সংৰক্ষিত কৰা হৈছে আৰু পুনৰ সংযোগ হ’লে প্ৰেৰণ কৰা হ’ব।',

    // Verification & Disclaimers
    communitySignal: 'ৰাজহুৱা সংকেত',
    communityNotice: 'ৰাজহুৱা প্ৰতিবেদনে প্ৰাৰম্ভিক তথ্য প্ৰদান কৰে; নিৰ্দিষ্ট বিষয়াসকলেহে চূড়ান্ত অনুমোদন কৰে।',
    shelterUnavail: 'সত্যাপন কৰা আশ্ৰয়ৰ তথ্য উপলব্ধ নহয়',
    terrainUnavail: 'ভূ-খণ্ডৰ তথ্য উপলব্ধ নহয়',
    sirenNotice: 'ৱেব চাইৰেনে ব্ৰাউজাৰৰ অনুমতি সাপেক্ষেহে কাম কৰিব আৰু ফোনৰ ছাইলেন্ট ম’ড বাইপাছ কৰিব নোৱাৰে।',

    // Actions
    confirm: 'নিশ্চিত কৰক',
    yes: 'মই নিশ্চিত কৰিব পাৰোঁ',
    no: 'মই দেখা নাই',
    unsure: 'অনিশ্চিত',
    submit: 'প্ৰতিবেদন দাখিল কৰক',

    // Extended keys
    emergencyReport: 'জৰুৰীকালীন প্ৰতিবেদন',
    emergencyDisclaimer: 'ৰিস্কসেতু চৰকাৰী জৰুৰীকালীন সেৱাৰ বিকল্প নহয়। পোনপটীয়া সহায়ৰ বাবে ১১২ বা ১০৮ নম্বৰত যোগাযোগ কৰক।',
    submitReport: 'প্ৰতিবেদন',
    simulateRoadFailure: 'অনুকৰণ',
    officerWorkspace: 'বিষয়া কমাণ্ড কাৰ্যক্ষেত্ৰ',
    sosQueue: 'এছঅএছ কিউ',
    massAlertBroadcast: 'সামূহিক সতৰ্কবাণী',
    osintScanner: 'মুকলি গুপ্তচৰ',
    catchmentScreening: 'ওপৰৰ জলভাগ পৰীক্ষা',
    confirmObservation: 'মই নিশ্চিত কৰিব পাৰোঁ',
    disputeObservation: 'মই দেখা নাই',
    unsureObservation: 'অনিশ্চিত',
  },
} as const;

export function getTranslation(lang: SupportedLanguage = 'en') {
  return TRANSLATIONS[lang] || TRANSLATIONS.en;
}

export type TranslationKey = keyof typeof TRANSLATIONS['en'];

/**
 * t(lang, key) — shorthand translation accessor.
 * Falls back to English if key not found in selected language.
 */
export function t(lang: SupportedLanguage, key: TranslationKey | (string & {})): string {
  const dict = TRANSLATIONS[lang] ?? TRANSLATIONS.en;
  return (dict as Record<string, string>)[key]
    ?? (TRANSLATIONS.en as Record<string, string>)[key]
    ?? key;
}

