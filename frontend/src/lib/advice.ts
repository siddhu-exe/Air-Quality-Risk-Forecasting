import type { AqiTierKey } from '@/design/tokens'

export interface Advice {
  /** Serif headline on the dark panel. */
  headline: string
  /** Numbered actions (desktop panel). */
  actions: readonly string[]
  /** One-paragraph version (phone panel). */
  summary: string
}

/**
 * Plain-language guidance per CPCB category.
 *
 * REVIEW BEFORE LAUNCH: only the "Very Poor" entry comes from the design. The
 * other five are drafted from the CPCB AQI health-impact bands and are health
 * guidance, so they need sign-off from someone qualified. The "7 am and 11 pm"
 * particle-peak claim is also taken from the design copy and is unverified here.
 */
export const ADVICE: Record<AqiTierKey, Advice> = {
  good: {
    headline: 'Enjoy the outdoors.',
    actions: [
      'Normal outdoor activity is fine for everyone.',
      'Good day to air out your home.',
    ],
    summary: 'Air quality is good. Normal outdoor activity is fine for everyone.',
  },
  satisfactory: {
    headline: 'Fine for most people.',
    actions: [
      'Normal activity is fine for most people.',
      'Unusually sensitive people may notice minor breathing discomfort on long outdoor efforts.',
    ],
    summary:
      'Fine for most people. Unusually sensitive people may notice minor breathing discomfort.',
  },
  moderate: {
    headline: 'Sensitive groups, take care.',
    actions: [
      'People with asthma, lung or heart disease should limit long or heavy outdoor effort.',
      'Children and older adults should take more breaks outdoors.',
      'Everyone else can carry on as normal.',
    ],
    summary:
      'People with asthma, lung or heart disease, children and older adults should limit long outdoor effort.',
  },
  poor: {
    headline: 'Cut back on long outdoor effort.',
    actions: [
      'Shorten outdoor workouts and prefer indoor exercise.',
      'Fine particles peak around 7 am and 11 pm; keep windows shut then.',
      'People with asthma, lung or heart disease should stay indoors where possible.',
    ],
    summary:
      'Shorten outdoor workouts, keep windows shut around 7 am and 11 pm, and keep sensitive people indoors where possible.',
  },
  veryPoor: {
    headline: 'Keep outdoor effort short.',
    actions: [
      'Skip long runs and outdoor workouts; move them indoors.',
      'Fine particles peak around 7 am and 11 pm — keep windows shut then.',
      'Children, older adults and anyone with asthma or heart disease should stay indoors where possible.',
      'If you must go out, a well-fitted N95 helps; cloth masks do little.',
    ],
    summary:
      'Move workouts indoors, keep windows shut around 7 am and 11 pm, and keep children and anyone with asthma inside.',
  },
  severe: {
    headline: 'Stay indoors where you can.',
    actions: [
      'Avoid outdoor exercise and long trips outside.',
      'Fine particles peak around 7 am and 11 pm — keep windows shut then.',
      'Children, older adults and anyone with asthma or heart disease should stay indoors.',
      'If you must go out, wear a well-fitted N95; cloth masks do little.',
    ],
    summary:
      'Avoid outdoor effort, keep windows shut, and keep children, older adults and anyone with asthma or heart disease indoors.',
  },
}
