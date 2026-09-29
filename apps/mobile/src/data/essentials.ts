/**
 * Offline essentials (Master Plan §17, §34). Emergency contacts carry a
 * source and a verification date: until someone verifies an entry and sets
 * `last_verified` (in the emergency_contacts table), the app labels it as
 * unverified and tells the traveller to confirm locally. The AI never
 * produces these numbers — they come only from this structured data.
 */
export interface EmergencyContact {
  id: string;
  service: 'police' | 'gendarmerie' | 'ambulance_fire' | 'mobile_emergency';
  label: string;
  number: string;
  scope: string;
  source: string;
  last_verified: string | null;
}

export const EMERGENCY_CONTACTS: EmergencyContact[] = [
  { id: 'ma-police', service: 'police', label: 'Police', number: '19', scope: 'Cities', source: 'Moroccan national emergency numbers', last_verified: null },
  { id: 'ma-gendarmerie', service: 'gendarmerie', label: 'Royal Gendarmerie', number: '177', scope: 'Rural areas & highways', source: 'Moroccan national emergency numbers', last_verified: null },
  { id: 'ma-ambulance-fire', service: 'ambulance_fire', label: 'Ambulance & fire (Protection Civile)', number: '15', scope: 'Nationwide', source: 'Moroccan national emergency numbers', last_verified: null },
  { id: 'ma-112', service: 'mobile_emergency', label: 'Emergency from a mobile phone', number: '112', scope: 'Nationwide (mobile)', source: 'Moroccan national emergency numbers', last_verified: null },
];

export interface Phrase {
  en: string;
  darija: string;
  pronunciation: string;
}

/** Everyday Moroccan Arabic (Darija), Latin transliteration. */
export const PHRASES: Phrase[] = [
  { en: 'Hello', darija: 'السلام عليكم', pronunciation: 'salam alaykum' },
  { en: 'Thank you', darija: 'شكرا', pronunciation: 'shukran' },
  { en: 'No, thank you', darija: 'لا شكرا', pronunciation: 'la, shukran' },
  { en: 'Please', darija: 'عافاك', pronunciation: "3afak (afak)" },
  { en: 'Excuse me / sorry', darija: 'سمح ليا', pronunciation: 'smeh liya' },
  { en: 'How much?', darija: 'بشحال؟', pronunciation: 'bshhal?' },
  { en: 'Too expensive', darija: 'غالي بزاف', pronunciation: 'ghali bzaf' },
  { en: 'Where is…?', darija: 'فين كاين…؟', pronunciation: 'fin kayn…?' },
  { en: 'OK / agreed', darija: 'واخا', pronunciation: 'wakha' },
  { en: 'Good / fine', darija: 'مزيان', pronunciation: 'mzyan' },
  { en: 'Goodbye', darija: 'بسلامة', pronunciation: 'bslama' },
];
