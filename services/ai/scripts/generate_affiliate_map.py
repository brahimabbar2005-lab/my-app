#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
create_affiliate_map.py — builds 07_AFFILIATE_MAP.xlsx for the ComeMorocco AI.

Input Table 1 (Affiliate Programs):  27 programs   -> "Affiliate Map"  (AFF-001..AFF-027)
Input Table 2 (GYG Activities):      77 activities -> "GetYourGuide Activities" (GYG-001..GYG-077)

SOURCE FIDELITY: every link, description, widget code and activity name is preserved
EXACTLY as supplied (source typos included). Nothing invented. Unknown values read
"Not specified in source". Inferences are labeled in "Source / Mapping Basis".

Requires:  pip install openpyxl
Run:       python create_affiliate_map.py
"""

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

OUT = "07_AFFILIATE_MAP.xlsx"
NS  = "Not specified in source"

# =============================================================================
# 1) CATEGORY-LEVEL MAPPING LOGIC (inference layer — identical per category)
# =============================================================================
CAT = {
"Luggage Storage": dict(
  use="Finding short-term luggage storage: before check-in, after check-out, during layovers or day trips",
  intent="'Where can I leave my luggage in Marrakech?' / 'What do I do with my bags before check-in or after checkout?' / 'Is there luggage storage near the medina, station or airport?'",
  dest=NS + " — confirm covered Moroccan cities before recommending a specific location",
  rec="Recommend ONLY when the traveler explicitly needs to store luggage: early arrival, late checkout or flight, layover, or a day trip/medina visit with suitcases.",
  notrec="Never show luggage storage merely because the traveler mentions a destination, an airport, a hotel or 'bags'. Never insert into sightseeing, food, accommodation or transport-comparison answers.",
  types="Any traveler; especially Backpacker, Budget traveler, Family, Solo traveler, Long-stay traveler",
  comm="High", live="Yes",
  pres="Contextual link / natural text link inside a direct answer to a luggage-storage question",
  content="Guides: 'What to do with your luggage on arrival/departure day', 'Marrakech layover tips', 'Late checkout & last-day plans' (opportunity mapping — no URLs invented)",
  trigger="Traveler explicitly needs luggage storage"),
"Flight Compensation": dict(
  use="Claiming compensation after a flight delay, cancellation or denied boarding (up to EUR 600 per Compensair's source description)",
  intent="'My flight was delayed/cancelled — can I get compensation?' / 'Am I entitled to compensation?' / 'How do I claim against the airline?'",
  dest="Morocco / General (depends on the flight and applicable rules, not the destination)",
  rec="Recommend ONLY when the traveler reports an actual flight disruption AND asks about compensation or claiming.",
  notrec="Never mention during normal trip planning or flight booking. NEVER promise the traveler qualifies — eligibility depends on route, airline, timing and current rules, which require verification. Never state a guaranteed payout; the EUR 600 figure is 'up to' per source only.",
  types="Any traveler who experienced a flight disruption",
  comm="High", live="Sometimes",
  pres="Contextual link only after explaining the general situation (both partners have widgets)",
  content="Guide: 'What to do when your flight to/from Morocco is delayed or cancelled' (opportunity mapping — no URLs invented)",
  trigger="Actual disruption + explicit compensation question"),
"Car Rental": dict(
  use="Renting a car in Morocco: booking, comparing suppliers and prices, choosing pickup locations",
  intent="'I want to rent a car in Morocco' / 'Should I rent a car?' / 'Compare car rental options in Marrakech/Casablanca' / 'Car rental for a road trip'",
  dest="Morocco / General (global platforms per source; Moroccan pickup locations inferred — verify)",
  rec="Recommend ONLY when the traveler wants to rent a car, compare rental options, asks where to book one, or has decided to self-drive and wants booking help.",
  notrec="Never when the traveler wants trains (ONCF), CTM/Supratours buses or shared taxis. Never inside itinerary or sightseeing answers. If asked 'Should I rent a car?', give honest itinerary-based advice first; show the affiliate only if they then want options.",
  types="Road trip traveler, Family, Group, Couple, Business traveler, First-time visitor, Long-stay traveler",
  comm="High", live="Yes",
  pres="Comparison / deep link / search widget",
  content="Guides: 'Driving in Morocco', 'Morocco road trip itineraries', 'Car rental tips: insurance, medina parking, mountain roads' (opportunity mapping — no URLs invented)",
  trigger="Traveler wants to rent, compare or book a car"),
"Airport Transfer": dict(
  use="Booking a pre-arranged airport pickup / private transfer",
  intent="'Airport transfer in Marrakech' / 'How do I get from Marrakech airport to the medina?' (when a pre-booked/private option is wanted) / 'I want a private driver to pick me up'",
  dest=NS + " — confirm served Moroccan airports (RAK, CMN, AGA, FEZ, TNG) before airport-specific recommendations",
  rec="Recommend ONLY when the traveler asks about airport pickup, private or pre-booked transfers, or explicitly prefers a fixed-price arranged ride.",
  notrec="Never push a paid transfer when the traveler asks for the cheapest way, the airport bus, shared shuttle or taxi advice — cover budget options honestly first. Never inside general destination answers.",
  types="Family, Couple, Older traveler, Business traveler, Luxury traveler, First-time visitor; travelers with heavy luggage or night arrivals",
  comm="High", live="Sometimes",
  pres="Booking CTA / widget",
  content="Guides: 'Marrakech airport to the medina: all options compared', 'Casablanca CMN airport guide', 'Avoiding taxi overcharging on arrival' (opportunity mapping — no URLs invented)",
  trigger="Traveler requests airport pickup / pre-booked transfer"),
"Private Transfer": dict(
  use="Booking individual/private transfers (airport and intercity) and private car tours (Kiwitaxi per source)",
  intent="'Book a private transfer from Marrakech to Merzouga' / 'Private driver between cities' / 'Pre-booked door-to-door transfer'",
  dest="Morocco / General — specific routes/vehicles must be verified at search time (intui: 175 countries per source; Kiwitaxi: transfers + private car tours per source)",
  rec="Recommend ONLY when the traveler explicitly wants a private or pre-booked transfer between specific points.",
  notrec="Never when the traveler asks about buses, trains or shared taxis; never in general itinerary answers; never quote prices as current without live data.",
  types="Family, Business traveler, Older traveler, Couple, Group; travelers with luggage, sports equipment or accessibility needs (intui source mentions these groups)",
  comm="High", live="Sometimes",
  pres="Booking CTA / widget",
  content="Guides: 'Marrakech to Merzouga: all transport options', 'Private driver vs rental car vs bus' (opportunity mapping — no URLs invented)",
  trigger="Traveler requests a private/pre-booked transfer"),
"Connectivity / eSIM": dict(
  use="Getting mobile data in Morocco via eSIM (Airalo, Yesim, Saily) or international SIM card (Drimsim)",
  intent="'How do I get mobile data in Morocco?' / 'Which eSIM should I use?' / 'Do I need a SIM card?'",
  dest="Morocco / General (international providers per source: Yesim 150+ countries, Saily 200+ countries; Morocco plan details need verification)",
  rec="Recommend ONLY when the traveler asks about mobile data, SIM cards, eSIMs or connectivity in Morocco — and only AFTER answering the question.",
  notrec="Never insert into sightseeing, hotel, restaurant or itinerary answers. Never claim a specific Morocco plan, price or coverage beyond the source; never present connectivity as mandatory.",
  types="Any traveler; First-time visitor, Solo traveler, Business traveler, Long-stay traveler, Family (shared data needs)",
  comm="Medium", live="Sometimes",
  pres="Contextual link after answering the connectivity question (Airalo has a widget)",
  content="Guides: 'Morocco SIM/eSIM guide', 'Morocco travel essentials', 'Wi-Fi in Morocco: what to expect' (opportunity mapping — no URLs invented)",
  trigger="Traveler asks about mobile data / SIM / eSIM"),
"VPN / Privacy": dict(
  use="Secure, private internet access while traveling (public Wi-Fi safety)",
  intent="'Is public Wi-Fi safe in Morocco?' / 'Do I need a VPN when traveling?' / 'How do I stay secure online abroad?'",
  dest="Morocco / General",
  rec="Recommend ONLY when the traveler explicitly asks about online security, privacy or VPNs while traveling.",
  notrec="Never insert into unrelated travel answers. Never imply Morocco is unsafe online; never present a VPN as required.",
  types="Any traveler; Business traveler, Long-stay traveler, remote workers",
  comm="Medium", live="Sometimes",
  pres="Contextual link only inside a direct answer about online security",
  content="Guides: 'Staying connected safely in Morocco', 'Digital travel essentials checklist' (opportunity mapping — no URLs invented)",
  trigger="Traveler explicitly asks about online security / VPN"),
"Password Manager": dict(
  use="Secure password storage for travelers (NordPass per source)",
  intent="'How do I keep my accounts and passwords secure while traveling?' (only when password security is explicitly the topic)",
  dest="Morocco / General",
  rec="Recommend ONLY when the traveler explicitly raises password security/management.",
  notrec="Extremely rare relevance: never insert into travel answers of any kind. Only on explicit request or topic.",
  types="Any traveler; Business traveler, remote workers",
  comm="Medium", live="Sometimes",
  pres="Only when explicitly requested / contextual link",
  content="Digital travel security checklist (opportunity mapping — no URLs invented)",
  trigger="Traveler explicitly raises password security"),
"Accommodation": dict(
  use="Finding and booking accommodation: hotels, riads, apartments",
  intent="'I need a hotel in Marrakech' / 'Where should I stay?' / 'Find accommodation in Fes' / 'I want a cheap place to stay'",
  dest="Morocco / General (global booking platform; Moroccan city coverage inferred from program name — verify)",
  rec="Recommend ONLY when the traveler is actively looking for accommodation or asks for hotel/riad/apartment options.",
  notrec="Never show merely because the traveler mentions a destination or itinerary (e.g., 'I'm going to Marrakech for 4 days — what should I see?'). Answer the travel question first; affiliate only on genuine accommodation intent.",
  types="Any traveler; Couple, Family, Budget traveler, Luxury traveler, Business traveler, Long-stay traveler",
  comm="High", live="Yes",
  pres="Natural text link / booking CTA / widget",
  content="Guides: 'Marrakech: where to stay (medina vs Gueliz vs Palmeraie)', 'Riad vs hotel', 'Where to stay in Fes' (opportunity mapping — no URLs invented)",
  trigger="Traveler actively seeks accommodation"),
"Hostels": dict(
  use="Booking hostels and budget social accommodation",
  intent="'Cheap places to stay in Morocco' / 'Best hostels in Marrakech' / 'Where do backpackers stay in Fes?'",
  dest="Morocco / General (global hostel platform per source; Moroccan coverage inferred — verify)",
  rec="Recommend ONLY when the traveler explicitly wants hostels or budget/social accommodation.",
  notrec="Never when the traveler asks for hotels, riads or luxury stays; never just because a destination is mentioned.",
  types="Backpacker, Budget traveler, Solo traveler, Group, Any traveler",
  comm="High", live="Yes",
  pres="Natural text link / booking CTA / widget",
  content="Guides: 'Best hostels in Marrakech', 'Backpacker route through Morocco', 'Hostel vs riad on a budget' (opportunity mapping — no URLs invented)",
  trigger="Traveler wants hostels / budget social stays"),
"Travel Insurance": dict(
  use="Buying travel insurance online before or during a trip (EKTA per source: ages 3-85, policy by email in 2-3 minutes, 24/7 multilingual support)",
  intent="'Do I need travel insurance for Morocco?' / 'Where can I buy travel insurance?' / 'Is insurance worth it for this trip?'",
  dest="Morocco / General",
  rec="Recommend ONLY when the traveler asks about travel insurance or explicitly wants to buy it.",
  notrec="Never claim insurance is mandatory for Morocco unless current authoritative information confirms it. Never insert into itinerary, packing or sightseeing answers. Source claims (ages, delivery time) must not be extended or restated as guarantees.",
  types="Any traveler; Older traveler, Family, Adventure travelers, Long-stay traveler, First-time visitor",
  comm="Medium", live="Sometimes",
  pres="Contextual link after answering the insurance question",
  content="Guides: 'Do you need travel insurance for Morocco?', 'Insurance for desert trips & activities' (opportunity mapping — no URLs invented)",
  trigger="Traveler asks about travel insurance"),
"Tours & Activities": dict(
  use="Booking tours, activities and experiences (Viator, Klook, getyourguide, WeGoTrip per source)",
  intent="'I want a camel ride in Marrakech' / 'Book a desert tour' / 'What activities can I book?' / 'Tickets for an attraction'",
  dest="Morocco / General — inventory per destination/activity must be verified; for specific Morocco activities use the GetYourGuide Activities sheet (77 mapped activities)",
  rec="Recommend ONLY when a specific activity or experience matches the traveler's destination AND stated interest. For Morocco activity requests, match the GetYourGuide Activities sheet first.",
  notrec="Never recommend an activity merely because links exist. Never attach to 'What should I see?' questions — answer with content first. Never recommend for the wrong destination. No generic link drops.",
  types="Any traveler",
  comm="High", live="Sometimes",
  pres="Activity card / deep link / widget",
  content="Guides: 'Things to do in Marrakech', 'Sahara tours explained', 'Essaouira activities' (opportunity mapping — no URLs invented)",
  trigger="Specific destination + activity match"),
"Attractions": dict(
  use="Booking museum and attraction tickets; self-guided audio tours with tickets (Tiqets, WeGoTrip per source)",
  intent="'Tickets for [museum/attraction]' / 'Skip-the-line tickets' / 'Audio tour' / 'Explore on my own'",
  dest="Morocco / General — attraction inventory must be verified per site",
  rec="Recommend ONLY when the traveler asks about tickets/entry for a specific attraction or wants a self-guided audio tour.",
  notrec="Never insert into general sightseeing answers; never claim a specific attraction is bookable without verification.",
  types="Any traveler; Couple, Family, First-time visitor, Independent travelers",
  comm="High", live="Sometimes",
  pres="Activity card / deep link / widget",
  content="Guides: 'Morocco's unmissable museums', 'Marrakech attractions & how to book' (opportunity mapping — no URLs invented)",
  trigger="Specific attraction tickets / self-guided tour request"),
"Ride-hailing": dict(
  use="Affordable city rides via ride-hailing (InDrive per source)",
  intent="'How do I get around Marrakech?' / 'Is there a taxi app in Morocco?' / 'Cheap alternatives to taxis'",
  dest=NS + " — verify the service operates in the traveler's specific Moroccan city before recommending",
  rec="Recommend ONLY when the traveler asks about getting around a city, taxi alternatives, or specifically about ride-hailing apps.",
  notrec="Never inside general destination answers. Never claim availability in a specific city without live verification. When the traveler asks about petit taxis or walking the medina, answer that directly first.",
  types="Any traveler; Budget traveler, Solo traveler, Business traveler",
  comm="Medium", live="Yes",
  pres="Contextual link / app referral",
  content="Guides: 'Getting around Marrakech: petit taxis, apps, walking', 'Casablanca city transport' (opportunity mapping — no URLs invented)",
  trigger="Traveler asks about city transport / taxi alternatives"),
"Flights": dict(
  use="Finding and booking flights (Aviasales: cheap tickets per source; Kiwi.com: flight+train+bus combinations via virtual interlining per source)",
  intent="'Find flights to Morocco' / 'Cheap flights to Marrakech' / 'Flights from Casablanca to Fes' / 'Combine flight, train and bus in one itinerary'",
  dest="Morocco / General",
  rec="Recommend ONLY when the traveler is actively looking for flights or flight+ground combinations.",
  notrec="Never present flight offers when the traveler only asks about things to do at the destination. Never inside itinerary answers unless 'how do I get there' is the actual question.",
  types="Any traveler; Budget traveler, Solo traveler, Couple, Family",
  comm="High", live="Yes",
  pres="Comparison / deep link / search widget",
  content="Guides: 'When to book flights to Morocco', 'RAK vs CMN: which airport', 'Getting to Morocco cheaply' (opportunity mapping — no URLs invented)",
  trigger="Traveler is actively searching flights"),
}

# =============================================================================
# 2) SOURCE DATA — Input Table 1 (27 programs). Fields program/desc/links/widget
#    are EXACT transcriptions. Optional keys override category defaults.
# =============================================================================
NO_WIDGET = NS + " (no widget code provided in source)"
NA_WIDGET = "N/A (per source)"

PROGRAMS = [
 dict(program="Radical Storage", cat="Luggage Storage",
  desc="Radical Storage provides travellers with luggage storage solutions so they can enjoy their holiday to the fullest, giving them the opportunity to eliminate problems with early arrivals or late departures from the home/hotel",
  links="https://radicalstorage.tpx.li/b8urQSvB", widget=NO_WIDGET,
  notes="No widget code in source. Moroccan city coverage unconfirmed — see Review Notes.",
  review="Yes — Morocco city coverage unconfirmed"),
 dict(program="Compensair", cat="Flight Compensation",
  desc="Compensair is a UK based online service that helps air travelers to receive up to €600 compensation from airlines in case of a flight delay, cancellation, or denied boarding.",
  links="https://compensair.tpx.li/TmyX2hsX",
  widget='<script async src="https://tpemb.com/content?trs=408932&shmarker=605900&locale=en&border_radius=5&plain=false&powered_by=true&promo_id=3408&campaign_id=86" charset="utf-8"></script>',
  notes="The €600 figure comes from the source description — restate only as 'up to', never as guaranteed; eligibility depends on route, airline, timing and current rules."),
 dict(program="Localrent", cat="Car Rental",
  desc="Car rental service for travelers in Morocco.",
  links="https://localrent.tpx.li/9dMe1bKa",
  widget='<script async src="https://tpemb.com/content?trs=408932&shmarker=605900&powered_by=true&country=99&lang=en&width=100&background=transparent&logo=false&header=true&gearbox=false&cars=true&border=false&footer=true&campaign_id=87&promo_id=4322" charset="utf-8"></script>',
  dest="Morocco / General (source: 'Car rental service for travelers in Morocco')",
  basis="Source data + destination from description (Morocco)",
  notes="Morocco-specific per source. Widget contains a country=99 parameter — verify it targets Morocco (see Review Notes).",
  review="Yes — verify widget country=99 = Morocco"),
 dict(program="Welcome Pickups", cat="Airport Transfer",
  desc="Airport transfer and pickup service for travelers.",
  links="https://tpx.li/UCD3SE15",
  widget='<script async src="https://tpemb.com/content?trs=408932&shmarker=605900&locale=en&show_header=true&powered_by=true&campaign_id=627&promo_id=8951" charset="utf-8"></script>',
  notes="Moroccan airport coverage not stated in source — confirm before airport-specific recommendations (see Review Notes).",
  review="Yes — Morocco airport coverage unconfirmed"),
 dict(program="Airalo", cat="Connectivity / eSIM",
  desc="eSIM provider for international travelers to stay connected.",
  links="https://airalo.tpx.li/OWDSjnzC",
  widget='<script async src="https://tpemb.com/content?trs=408932&shmarker=605900&locale=en&powered_by=true&color_button=%23006233&color_focused=%23006233&secondary=%23FFFFFF&dark=%2311100f&light=%23FFFFFF&special=%23C4C4C4&border_radius=10&plain=true&no_labels=&promo_id=8588&campaign_id=541" charset="utf-8"></script>'),
 dict(program="Drimsim", cat="Connectivity / eSIM",
  desc="International SIM card provider for travelers.",
  links="https://drimsim.tpx.li/hPXhbolE", widget=NA_WIDGET,
  use="Getting mobile data in Morocco via an international SIM card (Drimsim per source)",
  notes="International SIM card rather than eSIM-only, per source. Widget: N/A per source."),
 dict(program="AirHelp", cat="Flight Compensation",
  desc="Flight compensation service for delayed or canceled flights.",
  links="https://airhelp.tpx.li/212let6O",
  widget='<script async src="https://tpemb.com/content?trs=408932&shmarker=605900&lang=en&powered_by=true&campaign_id=120&promo_id=8679" charset="utf-8"></script>',
  notes="Same gating as Compensair: only after an actual disruption + compensation question; never promise eligibility."),
 dict(program="Qeeq", cat="Car Rental",
  desc="Car rental comparison platform for travelers.",
  links="https://qeeq.tpx.li/168HLIEc",
  widget='<script async src="https://tpemb.com/content?trs=408932&shmarker=605900&locale=en&powered_by=true&campaign_id=172&promo_id=4850" charset="utf-8"></script>',
  notes="Comparison platform per source; Morocco coverage not explicit — verify."),
 dict(program="InDrive", cat="Ride-hailing",
  desc="Ride-hailing service for affordable and fair-priced rides.",
  links="https://indrive.tpx.li/dASaItfP",
  widget='<script async src="https://tpemb.com/content?trs=408932&shmarker=605900&locale=en&powered_by=false&color_button=%23A7E92F&color_icons=%23A7E92F&dark=%23323942&light=%23FFFFFF&secondary=%23006233&special=%23a7e92f&color_focused=%23A7E92F&border_radius=30&plain=false&promo_id=8450&campaign_id=371" charset="utf-8"></script>',
  notes="City coverage in Morocco not stated in source; ride-hailing availability is city-specific — never claim current availability (see Review Notes).",
  review="Yes — Morocco city coverage unconfirmed"),
 dict(program="NordVPN", cat="VPN / Privacy",
  desc="VPN service for secure and private internet access while traveling.",
  links="NordVPN: https://nordvpn.tpx.li/Ps3hCOh8", widget=NA_WIDGET,
  notes="Link preserved exactly as supplied, including the 'NordVPN:' label prefix. Widget: N/A per source."),
 dict(program="NordPass", cat="Password Manager",
  desc="Password manager for secure password storage.",
  links="NordPass: https://nordvpn.tpx.li/Yk9mbemK", widget=NA_WIDGET,
  notes="Link preserved exactly as supplied ('NordPass: https://nordvpn.tpx.li/Yk9mbemK') — note the domain is nordvpn.tpx.li; verify it resolves to NordPass (see Review Notes). Widget: N/A per source.",
  review="Yes — verify link (nordvpn.tpx.li domain)"),
 dict(program="GetRentacar.com", cat="Car Rental",
  desc="GetRentacar.com is an international car rental marketplace that aggregates offers from national rental companies and local car owners. The platform uses a bidding-based pricing model that allows customers to receive offers below the average market price. Vehicle delivery to a chosen location is available, as well as rental options with no deposit or full deposit cancellation.",
  links="https://getrentacar.tpx.li/DR8xPPkm",
  widget='<script src="https://tp.media/content?campaign_id=222&promo_id=8813&shmarker=605900&trs=408932" charset="utf-8"></script>',
  notes="Bidding-based marketplace with vehicle delivery and no-deposit options per source; verify Morocco coverage."),
 dict(program="Booking.com", cat="Accommodation",
  desc=NS + " — description cell empty in source.",
  links="https://booking.tpx.li/XkezrIhu",
  widget='<script async src="https://tpemb.com/content?trs=408932&shmarker=605900&locale=en&sustainable=false&deals=false&border_radius=12&plain=false&powered_by=true&promo_id=2693&campaign_id=84" charset="utf-8"></script>',
  basis="Needs manual review — description not in source; category inferred from program name",
  notes="Description not provided in source — category 'Accommodation' inferred from the program name (see Review Notes). Link and widget preserved exactly.",
  review="Yes — description missing; category inferred"),
 dict(program="Yesim", cat="Connectivity / eSIM",
  desc="Yesim stands out as a premier Swiss-based eSIM provider, renowned for its comprehensive coverage across 150+ countries and its innovative approach to connectivity solutions.",
  links="https://yesim.tpx.li/fq1ku0px", widget=NO_WIDGET,
  notes="150+ countries per source. No widget code in source."),
 dict(program="EKTA", cat="Travel Insurance",
  desc="This offer is for people who travel or go abroad. Everyone between the ages of 3 and 85 can buy it online on a website. You will receive your insurance policy by email within 2-3 minutes. There is a multilingual technical support chat 24/7.",
  links="https://ektatraveling.tpx.li/NxsHgVst", widget=NO_WIDGET,
  notes="Age range 3-85, 2-3 minute policy delivery and 24/7 support are source claims — preserve wording; do not extend or restate as guarantees. No widget code in source."),
 dict(program="Kiwitaxi", cat="Private Transfer",
  desc="Kiwitaxi is an online booking platform of individual transfer servicies and private car tours",
  links="https://kiwitaxi.tpx.li/8oyINvb4",
  widget='<script async src="https://tpemb.com/content?currency=USD&trs=408932&shmarker=605900&language=en&theme=1&powered_by=true&campaign_id=1&promo_id=1486" charset="utf-8"></script>',
  notes="Source description covers both individual transfers and private car tours ('servicies' typo preserved); also relevant for private-tour intents."),
 dict(program="WeGoTrip", cat="Tours & Activities",
  desc="WeGoTrip is an AI-based app for self-guided tours. Enjoy immersive audio tours with included attraction tickets—everything you need for independent exploration, all in one.",
  links="https://wegotrip.tpx.li/LjaY557n", widget=NO_WIDGET,
  use="Self-guided audio tours with included attraction tickets (WeGoTrip per source)",
  intent="'Audio tour of the medina' / 'Explore on my own with an audio guide' / 'Tickets + self-guided tour'",
  notes="Self-guided audio focus per source — matches 'explore independently' intent, not group-guided intent. No widget code in source."),
 dict(program="Viator", cat="Tours & Activities",
  desc="Viator, a Tripadvisor company, is the world’s largest experiences marketplace, connecting travelers with tours and activities that they will remember for a lifetime.",
  links="https://viator.tpx.li/5q0L8alm",
  widget='<script async src="https://tpemb.com/content?currency=usd&trs=408932&shmarker=605900&locale=en&lowest_price=10&highest_price=250&destination=5407&product=36697P26&powered_by=true&promo_id=8601&campaign_id=47" charset="utf-8"></script>',
  notes="Widget contains destination=5407 and product=36697P26 parameters — verify the widget's configured destination/product before embedding (see Review Notes).",
  review="Yes — widget destination/product params unverified"),
 dict(program="Hostelworld", cat="Hostels",
  desc="Hostelworld, the global hostel-focused online booking platform, inspires passionate travelers to see the world, meet new people, and come back with extraordinary stories to tell.",
  links="https://hostelworld.tpx.li/2spOlqJq",
  widget='<script async src="https://tpemb.com/content?trs=408932&shmarker=605900&locale=en_us&default_direction=New%20York&border_radius=5&plain=false&powered_by=true&promo_id=4294&campaign_id=93" charset="utf-8"></script>',
  notes="Widget contains default_direction=New%20York — likely needs reconfiguration for Morocco traffic (see Review Notes).",
  review="Yes — widget default_direction=New York"),
 dict(program="Saily", cat="Connectivity / eSIM",
  desc="Saily is a data-only eSIM service developed by Nord Security, the company behind NordVPN. Designed for travelers seeking affordable and flexible mobile data solutions, Saily offers coverage in over 200 countries and regions.",
  links="https://saily.tpx.li/TuQTV019", widget=NO_WIDGET,
  notes="Data-only eSIM; 200+ countries per source; by Nord Security per source. No widget code in source."),
 dict(program="DiscoverCars", cat="Car Rental",
  desc="DiscoverCars.com is a global car rental comparison platform offering deals from 1,000+ suppliers in 10,000+ locations across 160+ countries. Customers benefit from transparent pricing, free cancellation, and 24/7 multilingual support. The DiscoverCars.com program helps partners monetize travel traffic through links, and a customizable booking widget. Partners get a 365-day attribution window and competitive commission terms. Trusted by more than 7 million travelers worldwide, DiscoverCars.com has a 4.6/5 TrustScore on Trustpilot based on 240,000+ reviews and has received multiple industry awards.",
  links="https://discovercars.tpx.li/P7HL5u4i",
  widget='<script async src="https://tpemb.com/content?trs=408932&shmarker=605900&locale=en&powered_by=true&bg_color=%23fad130&font_color=%23333333&button_color=%2300a200&button_font_color=%23ffffff&button_text=Search&rounded_corners=false&benefits=false&dc_powered_by=false&supplier_logos=false&top_logo=false&logo_style=dark&top_color=%23007ac2&campaign_id=117&promo_id=3873" charset="utf-8"></script>',
  notes="Source description contains partner-program claims (365-day attribution window, Trustpilot 4.6/5, commission terms) — preserved verbatim for internal reference only; never surface commission claims to travelers.",
  review="Low — keep partner claims internal"),
 dict(program="Klook", cat="Tours & Activities",
  desc="Klook is a booking platform on which travelers can book hotels, cars, tours and activities, tickets to attractions, and shows at great prices. Thanks to the convenient app, travelers can access the most popular attractions and hidden gems at their fingertips.",
  links="https://klook.tpx.li/o3g2El95",
  widget='<script async src="https://tpemb.com/content?currency=USD&trs=408932&shmarker=605900&locale=en&city_id=289&category=4&amount=3&powered_by=true&campaign_id=137&promo_id=4497" charset="utf-8"></script>',
  intent="'Book tours, activities, attraction tickets or shows' — per source Klook also covers hotels and cars (multi-vertical)",
  notes="Multi-vertical platform per source (hotels, cars, tours & activities, attractions, shows). Widget contains city_id=289 — verify target city (see Review Notes).",
  review="Yes — widget city_id=289 target unverified"),
 dict(program="Tiqets", cat="Attractions",
  desc="Tiqets has brought millions of people to museums and attractions around the world with their instant and intuitive mobile booking technology. Every day, Tiqets works with thousands of renowned museums, thrilling attractions, and hidden gems to offer unforgettable travel experiences.",
  links="https://tiqets.tpx.li/8Qz6nrJl",
  widget='<script async src="https://tpemb.com/content?currency=USD&trs=408932&shmarker=605900&product=&language=en&layout=horizontal&powered_by=true&campaign_id=89&promo_id=3948" charset="utf-8"></script>'),
 dict(program="Kiwi.com", cat="Flights",
  desc="Kiwi.com is a company that changes the travel industry! Kiwi is a pioneer in virtual interlining (connecting flights from airlines that do not codeshare). With Kiwi’s unique algorithm, Kiwi is able to create combinations of flight, train, and bus tickets and offer them in a single itinerary.",
  links=NS + " — only a widget code is provided in source",
  widget='<script async src="https://tpemb.com/content?currency=usd&trs=408932&shmarker=605900&locale=en&powered_by=true&limit=4&primary_color=00AE98&results_background_color=FFFFFF&form_background_color=FFFFFF&campaign_id=111&promo_id=3411" charset="utf-8"></script>',
  basis="Needs manual review — affiliate link not provided in source (widget only)",
  notes="CRITICAL: no affiliate link in source — only a widget code. Do NOT fabricate a link; obtain it from the partner program (see Review Notes).",
  review="Yes — CRITICAL: affiliate link missing (widget only)"),
 dict(program="Aviasales", cat="Flights",
  desc="Aviasales is a trusted service for buying cheap flight tickets. No extra fees or markups! In the mobile application and on aviasales.com only the lowest possible rates from reliable agencies",
  links="https://aviasales.tpx.li/jEU5Xg2V",
  widget='<script async src="https://tpemb.com/content?currency=usd&trs=408932&shmarker=605900&lat=31.6294723&lng=-7.9810845&powered_by=true&search_host=www.aviasales.com%2Fsearch&locale=en&origin=RAK&value_min=0&value_max=1000000&only_direct=true&radius=1&draggable=true&disable_zoom=false&show_logo=false&scrollwheel=true&primary=%230C3B2E&secondary=%23FFBA00&light=%23F5F0E8&width=1500&height=500&zoom=3&promo_id=4054&campaign_id=100" charset="utf-8"></script>',
  notes="Widget is preconfigured with origin=RAK (Marrakech) and Marrakech-area map coordinates — suited to Marrakech-origin flight search; verify before reuse for other origins."),
 dict(program="intui.travel", cat="Private Transfer",
  desc="Intui.Travel transfer — is a platform for booking transfers in 175 countries from the best local transport companies.\\n\\nTarget audience of buyers: independent travellers who do not use packages, business people, delegations, families with children, aged people, people with disabilities, tourists with a language barrier, first time tourists, sportsmen travelling with sports equipment.\\n\\nHandy and fast transfer search: by name — just specify the destination, by address — just specify the addresses of destinations, on map — just point on the map from and where to you wanna go.",
  links="https://intui.tpx.li/ppGqSOi1",
  widget='<script async src="https://tpemb.com/content?trs=408932&shmarker=605900&powered_by=true&locale=en&curr=USD&color=basic&pbi=0&ag=18&ap=34&rid=481&campaign_id=22&promo_id=3507" charset="utf-8"></script>',
  notes="Transfers in 175 countries per source; the target-audience list is preserved verbatim in the description. Verify specific Moroccan routes before recommending."),
 dict(program="getyourguide", cat="Tours & Activities",
  desc=NS + " — description cell empty in source.",
  links="https://www.getyourguide.com/marrakesh-l208/marrakech-camel-ride-in-the-oasis-palmeraie-t38164/?partner_id=7BARAIK&utm_medium=online_publisher",
  widget='<div data-gyg-widget="auto" data-gyg-partner-id="7BARAIK" data-gyg-cmp="morocco"></div>',
  dest="Morocco / General (widget data-gyg-cmp='morocco'; supplied deep link targets Marrakech)",
  use="Booking tours & activities via GetYourGuide (supplied program link is a single Marrakech camel-ride deep link; 77 activity-level gyg.me links are mapped in the GetYourGuide Activities sheet)",
  basis="Needs manual review — description not in source; activity-level links mapped separately",
  notes="Program name appears as lowercase 'getyourguide' in source — preserved. No description in source. The supplied program link is a deep link to ONE Marrakech camel-ride activity (partner_id=7BARAIK); for specific activity requests use the 77 activity links in the GetYourGuide Activities sheet. Widget: GYG auto widget, partner 7BARAIK, cmp='morocco' (consistent with the deep link).",
  review="Yes — description missing; deep-link handling"),
]

# =============================================================================
# 3) SOURCE DATA — Input Table 2 (77 activities).
#    (activity, affiliate link, category, destination, basis) — activity & link
#    are EXACT transcriptions. basis: title | inferred | missing | template
# =============================================================================
GYG = [
 ("Cooking class in Berber village with hike and home-cooked lunch","https://gyg.me/9UF2ENzy","Cooking Class","Berber village / Atlas region (inferred)","inferred"),
 ("Berber village tour, cooking class & lunch from Agadir","https://gyg.me/8wy7wkvD","Cooking Class","Berber villages / Atlas region — departure: Agadir","title"),
 ("2-day trek in High Atlas virgin villages","https://gyg.me/Xft3Renv","Mountain Activity","High Atlas","title"),
 ("Anima Garden & Ourika Valley Berber village day trip","https://gyg.me/kqQocVj2","Day Trip","Ourika Valley (Anima Garden)","title"),
 ("Ourika Valley, Berber villages & waterfall tour","https://gyg.me/UFNhSwjM","Day Trip","Ourika Valley","title"),
 ("Ouzoud Waterfalls guided hike & boat trip from Marrakech","https://gyg.me/J1GuturO","Day Trip","Ouzoud Waterfalls — from Marrakech","title"),
 ("Atlas Mountains, Berber villages & Waterfall tour from Marrakech","https://gyg.me/UFNhSwjM","Day Trip","Atlas Mountains — from Marrakech","title"),
 ("Merzouga 3-Day Desert Safari with Food from Marrakech","https://gyg.me/g1fuBxbi","Desert Tour","Merzouga — from Marrakech","title"),
 ("Agadir: Taghazout Beach Surf Lesson with Lunch & Transfer","https://gyg.me/Kto06TKl","Water Activity","Taghazout (Agadir)","title"),
 ("Essaouira: Surf Lesson with changing rooms & hot showers (budget-friendly activity)","https://gyg.me/lguomVfh","Water Activity","Essaouira","title"),
 ("Half-Day Sand Boarding Experience near Agadir with Dinner","https://gyg.me/idlfa9w6","Adventure","Agadir area","title"),
 ("Shared 3-day desert tour from Marrakech to Merzouga (all-inclusive)","https://gyg.me/0uHwbk0B","Desert Tour","Merzouga — from Marrakech","title"),
 ("Ait Benhaddou & Ouarzazate Day Trip from Marrakech by land","https://gyg.me/HMzbdhU7","Day Trip","Ait Benhaddou & Ouarzazate — from Marrakech","title"),
 ("Airport transfer in Marrakech (pre-booked on GYG)","https://gyg.me/F5LbBKJC","Airport Transfer","Marrakech (RAK)","title"),
 ("3-Day Desert Tour including flights (if available; otherwise select combo tour)","https://gyg.me/IXPVdolL","Desert Tour","Not specified in source (Sahara/Merzouga likely — verify)","missing"),
 ("Self-drive itinerary suggestions with pit-stop tours (link to nearby GYG tours)","(Add link when available)","Other","Not specified in source","template"),
 ("Tour starting from train station (e.g., Rabat city tour from station)","https://gyg.me/P7C6yMPl","Cultural Tour","Rabat (example in title — generic row)","template"),
 ("Marrakech City Tour: Souks, Palaces & Hidden Gems","https://gyg.me/jAS3YyIn","Cultural Tour","Marrakech","title"),
 ("Overnight Camel Trek over Erg Chebbi Dunes (from Merzouga)","https://gyg.me/DaTDgd4Q","Camel Ride","Erg Chebbi / Merzouga","title"),
 ("Marrakech: Agafay Desert Dinner Show + Camel Ride + Buggy","https://gyg.me/qWHfPVjU","Desert Tour","Agafay Desert (Marrakech)","title"),
 ("5-Day Surf Camp in Taghazout with lessons & excursions","https://gyg.me/IinwT8s5","Water Activity","Taghazout","title"),
 ("From Marrakech: Ouzoud Waterfalls Guided Hike and Boat Trip","https://gyg.me/J1GuturO","Day Trip","Ouzoud Waterfalls — from Marrakech","title"),
 ("Marrakesh: Agafay Desert Sunset, Camel Ride & Dinner Show","https://gyg.me/C05HKKgL","Desert Tour","Agafay Desert (Marrakech)","title"),
 ("Marrakech: Agafay Desert Tour with Quad, Camel Ride & Dinner","https://gyg.me/yJwlrrk5","Desert Tour","Agafay Desert (Marrakech)","title"),
 ("From Marrakech: Agafay Desert Sunset Dinner & Camel Ride","https://gyg.me/C05HKKgL","Desert Tour","Agafay Desert (Marrakech)","title"),
 ("Marrakech Quad Bike Experience: Desert and Palmeraie","https://gyg.me/Tgb2S5qC","Adventure","Marrakech (Palmeraie / desert)","title"),
 ("Marrakesh: Agafay Desert Quad or Camel Trip with Dinner Show","https://gyg.me/qfb4mVAa","Desert Tour","Agafay Desert (Marrakech)","title"),
 ("From Marrakesh: Essaouira Full-Day Trip","https://gyg.me/sMNDpK1r","Day Trip","Essaouira — from Marrakech","title"),
 ("Agadir/Taghazout: Sandboarding & Sunset Tea with Fire Show","https://gyg.me/idlfa9w6","Adventure","Agadir / Taghazout","title"),
 ("Marrakech: Cocktail Tasting Mixology & Moroccan Tapas","https://gyg.me/nDVekk0X","Food Tour","Marrakech","title"),
 ("Agadir: Atlas Mountains Cross Berber Villages Tour","https://gyg.me/FxbBMVx9","Day Trip","Atlas Mountains — from Agadir","title"),
 ("Sandboarding in the Small Sahara at Sunset (from Agadir/Taghazout)","https://gyg.me/q1xSODzG","Adventure","Agadir / Taghazout (Small Sahara)","title"),
 ("Dakhla: City Excursion with Lagoon, White Dune & Oyster Farm","https://gyg.me/3SSoCC0H","Excursion","Dakhla","title"),
 ("Agadir: Quad Bike and Sandboarding Tour","https://gyg.me/tJFBpqnT","Adventure","Agadir","title"),
 ("Sunset Timlalin Desert Experience – Camel Ride & Fire Show","https://gyg.me/ZYZyeV9o","Desert Tour","Timlalin (Agadir/Taghazout coast — inferred)","inferred"),
 ("From Agadir: 3-Day Merzouga Desert Adventure","https://gyg.me/FxbBMVx9","Desert Tour","Merzouga — from Agadir","title"),
 ("Agadir: Traditional Moroccan Cooking Class","https://gyg.me/IrRgu3sN","Cooking Class","Agadir","title"),
 ("Marrakech: 3-Hour Hammam Experience with Massage & Pickup","https://gyg.me/myJFjmiW","Hammam / Wellness","Marrakech","title"),
 ("Dakhla: Quad Tour with Panoramic Views","https://gyg.me/3SSoCC0H","Adventure","Dakhla","title"),
 ("marrakech food tour","https://gyg.me/nDVekk0X","Food Tour","Marrakech","title"),
 ("Todra Gorge Hiking Tour","https://gyg.me/BKSjOCMX","Mountain Activity","Todra Gorge","title"),
 ("Dades Valley Day Trip","https://gyg.me/g2hzuVsg","Day Trip","Dades Valley","title"),
 ("Toubkal Summit Trek","https://gyg.me/Nmo6UeAB","Mountain Activity","Toubkal / High Atlas","title"),
 ("Legzira Beach Day Trip","https://gyg.me/4UiGggCn","Day Trip","Legzira Beach","title"),
 ("Ifrane & Cedar Forest Tour","https://gyg.me/nNzm4orf","Day Trip","Ifrane & Azrou cedar forest","title"),
 ("Fes Medina Guided Tour","https://gyg.me/H4jokpqW","Cultural Tour","Fes","title"),
 ("Volubilis & Meknes Day Trip","https://gyg.me/YxHg9jR2","Historical / Sightseeing","Volubilis & Meknes","title"),
 ("Chefchaouen Blue City Tour","https://gyg.me/XOx1uZc8","Cultural Tour","Chefchaouen","title"),
 ("Casablanca Half-Day Tour","https://gyg.me/Mz6qiq9n","Cultural Tour","Casablanca","title"),
 ("Rabat City Tour","https://gyg.me/IlEZCaNw","Cultural Tour","Rabat","title"),
 ("Star Gazing in the Sahara Desert","https://gyg.me/7YGR3eC3","Excursion","Sahara (Merzouga region likely — inferred)","inferred"),
 ("Pottery Workshop in Safi","https://gyg.me/ln4PggFk","Other","Safi","title"),
 ("Argan Oil Cooperative Visit","https://gyg.me/yJwlrrk5","Other","Not specified in source (argan region unconfirmed)","missing"),
 ("Hot Air Balloon Ride over Marrakech","https://gyg.me/KNssbakQ","Adventure","Marrakech","title"),
 ("Jewish Heritage Tour in Marrakech","https://gyg.me/gbJHrs4i","Historical / Sightseeing","Marrakech","title"),
 ("Marrakech Horse Carriage Ride","https://gyg.me/qVTQoiI6","Other","Marrakech","title"),
 ("Camel Ride & Picnic in the Palmeraie","https://gyg.me/tX7yJSJN","Camel Ride","Marrakech (Palmeraie)","title"),
 ("Aquapark Day Pass in Marrakech","https://gyg.me/fxpeSXUc","Other","Marrakech","title"),
 ("Interactive Museum of Moroccan Music","https://gyg.me/gbJHrs4i","Historical / Sightseeing","Not specified in source (city not stated)","missing"),
 ("Private Sunset Cruise in Essaouira","https://gyg.me/jlSoYYkV","Water Activity","Essaouira","title"),
 ("Luxury Spa Day in Marrakech","https://gyg.me/URKgRJTY","Hammam / Wellness","Marrakech","title"),
 ("Private Dinner in a Riad Courtyard","https://gyg.me/0jKlCHBo","Other","Not specified in source (city not stated)","missing"),
 ("Hot Air Balloon & Champagne Breakfast","https://gyg.me/zy3TNILA","Adventure","Marrakech (inferred — sister listing GYG-054 is 'over Marrakech')","inferred"),
 ("Free Walking Tour of Marrakech Medina","https://gyg.me/wWHizLXD","Walking Tour","Marrakech","title"),
 ("Budget-Friendly Hostel Pub Crawl in Fes","https://gyg.me/H4jokpqW","Other","Fes","title"),
 ("Self-Guided Audio Tour of Casablanca","https://gyg.me/v5dCHWGr","Walking Tour","Casablanca","title"),
 ("Street Food Tour in Fes","https://gyg.me/H4jokpqW","Food Tour","Fes","title"),
 ("Tagine Cooking Workshop in Tangier","https://gyg.me/VWwGwAZZ","Cooking Class","Tangier","title"),
 ("Moroccan Pastry Class in Rabat","https://gyg.me/EGyhPhT0","Cooking Class","Rabat","title"),
 ("Atlas Mountains Paragliding Experience","https://gyg.me/3dzlxF3U","Adventure","Atlas Mountains","title"),
 ("Draa Valley Oasis Tour","https://gyg.me/YWsi9Kes","Day Trip","Draa Valley","title"),
 ("Moulay Idriss & Volubilis Day Trip","https://gyg.me/YxHg9jR2","Historical / Sightseeing","Moulay Idriss & Volubilis","title"),
 ("El Jadida Portuguese City Tour","https://gyg.me/dS7JqtkV","Cultural Tour","El Jadida","title"),
 ("Sidi Ifni Coastal Adventure","https://gyg.me/6nNIPVL9","Excursion","Sidi Ifni","title"),
 ("Anti-Atlas Mountains Exploration","https://gyg.me/kqQocVj2","Day Trip","Anti-Atlas Mountains","title"),
 ("Taza Hidden Gem Tour","https://gyg.me/GZ3HS8AS","Cultural Tour","Taza","title"),
 ("Oujda & Eastern Morocco Discovery","https://gyg.me/lD47A6MH","Cultural Tour","Oujda / Eastern Morocco","title"),
]

# Per-category intent & traveler types for GYG activities (inference layer)
GYG_CAT = {
 "Cooking Class": ("Traveler wants a hands-on cooking experience: 'cooking class', 'learn to make tagine/couscous/pastilla', 'Berber cooking'", "Family, Couple, Food-focused travelers, Any traveler"),
 "Mountain Activity": ("Traveler wants hiking/trekking: 'trek in the Atlas', 'climb Toubkal', 'gorge hike', '2-day trek'", "Adventure travelers, Solo traveler, Group, Couple, Any fit traveler"),
 "Day Trip": ("Traveler wants a guided day trip / excursion from their base city to this destination", "First-time visitor, Family, Couple, Group, Any traveler"),
 "Desert Tour": ("Traveler wants a desert/Sahara experience: 'desert tour', 'Merzouga/Agafay', 'desert camp', 'sunset dinner in the desert', 'camel + dinner'", "First-time visitor, Couple, Family, Group, Solo traveler, Any traveler"),
 "Water Activity": ("Traveler wants water activities: 'surf lesson', 'surf camp', 'boat trip', 'sunset cruise'", "Backpacker, Budget traveler, Solo traveler, Group, Couple, Any traveler"),
 "Adventure": ("Traveler wants adventure activities: quad biking, sandboarding, paragliding, hot-air balloon", "Adventure travelers, Group, Couple, Solo traveler, Family (activity-dependent), Any traveler"),
 "Camel Ride": ("Traveler explicitly wants a camel ride or camel trek: 'camel ride in Marrakech', 'ride a camel', 'overnight camel trek'", "Family, Couple, First-time visitor, Solo traveler, Any traveler"),
 "Food Tour": ("Traveler wants a food/drink experience: 'food tour', 'street food', 'cocktails and tapas', 'where should I eat'", "Food-focused travelers, Couple, Solo traveler, Group, Any traveler"),
 "Cultural Tour": ("Traveler wants a guided city/cultural tour: 'city tour', 'guided tour of the medina', 'souks and palaces'", "First-time visitor, Couple, Family, Group, Older traveler, Any traveler"),
 "Walking Tour": ("Traveler wants a walking or self-guided audio tour: 'walking tour', 'free tour', 'explore on foot with a guide/audio'", "Budget traveler, Backpacker, Solo traveler, First-time visitor, Any traveler"),
 "Airport Transfer": ("Traveler wants a pre-booked airport transfer at this destination", "Family, Business traveler, Older traveler, Any traveler with luggage or a night arrival"),
 "Excursion": ("Traveler wants a local excursion or experience at this destination (city excursion, stargazing, coastal adventure)", "Any traveler matching the specific interest"),
 "Historical / Sightseeing": ("Traveler wants museums, ruins and heritage sites: 'Volubilis', 'Jewish heritage', 'museum', 'Roman ruins', 'historic sites'", "First-time visitor, Couple, Family, Older traveler, Any traveler"),
 "Hammam / Wellness": ("Traveler wants hammam, massage or spa: 'hammam experience', 'spa day', 'traditional bath'", "Couple, Solo traveler, Luxury traveler, Any traveler"),
 "Other": ("Traveler asks about this specific experience type (workshop, carriage ride, aquapark, pub crawl, private dinner, argan cooperative)", "Depends on the specific experience; any traveler matching the interest"),
}

GYG_BASIS = {
 "title":    "Source data + destination from activity name",
 "inferred": "Source data + destination inferred from activity name",
 "missing":  "Source data — destination not specified in source (needs review)",
 "template": "Source data — template/placeholder row, not a specific bookable activity (needs review)",
}

# =============================================================================
# 4) SHEET CONTENT — Intent Map, Review Notes, README
# =============================================================================
INTENT_ROWS = [
 ["Accommodation (hotels, riads, apartments)","Booking.com (AFF-013 — category inferred, see Review Notes)","—","High","Yes","Only when the traveler is actively looking for accommodation or asks for hotel/riad/apartment options. Never on a mere destination/itinerary mention."],
 ["Hostels / budget social stay","Hostelworld (AFF-019)","—","High","Yes","Only when the traveler explicitly wants hostels or budget social accommodation."],
 ["Car rental","Localrent (AFF-003), Qeeq (AFF-008), GetRentacar.com (AFF-012), DiscoverCars (AFF-021)","—","High","Yes","Only when the traveler wants to rent or compare cars. 'Should I rent a car?' → honest itinerary advice first; affiliate only if they then want options. Never for train/bus/taxi questions."],
 ["Flights","Aviasales (AFF-025); Kiwi.com (AFF-024 — affiliate link missing, see Review Notes)","—","High","Yes","Only when actively searching flights or flight+ground combos. Never for destination things-to-do questions."],
 ["Airport transfer","Welcome Pickups (AFF-004)","GYG-014 (Marrakech airport transfer)","High","Yes","Only for airport pickup / pre-booked transfer requests; cover budget options (bus, taxi) honestly first."],
 ["Private / intercity transfer","Kiwitaxi (AFF-016), intui.travel (AFF-026)","—","High","Sometimes","Only when a private/pre-booked transfer between specific points is requested."],
 ["Luggage storage","Radical Storage (AFF-001)","—","High","Yes","Only when the traveler explicitly needs to store luggage (early arrival, late checkout, layover, day trip with bags)."],
 ["eSIM / SIM / mobile data","Airalo (AFF-005), Drimsim (AFF-006), Yesim (AFF-014), Saily (AFF-020)","—","Medium","Sometimes","Only for connectivity questions; answer the question first, then present options naturally."],
 ["Travel insurance","EKTA (AFF-015)","—","Medium","Sometimes","Only when insurance is asked about; never claim it is mandatory for Morocco."],
 ["Flight delay/cancellation compensation","Compensair (AFF-002), AirHelp (AFF-007)","—","High","Sometimes (eligibility rules)","Only after an actual disruption + explicit compensation question; never promise eligibility or payouts."],
 ["Ride-hailing / getting around a city","InDrive (AFF-009)","—","Medium","Yes","Only for city-transport / taxi-alternative questions; verify city availability before recommending."],
 ["VPN / online security","NordVPN (AFF-010)","—","Medium","Sometimes","Only for explicit online-security questions while traveling; never in unrelated answers."],
 ["Password security","NordPass (AFF-011)","—","Medium","Sometimes","Only when explicitly raised/requested — extremely rare; never in general travel answers."],
 ["Tours & activities (general)","getyourguide (AFF-027), Viator (AFF-018), Klook (AFF-022)","All 77 GYG activities (GetYourGuide Activities sheet)","High","Sometimes","Only on destination + activity match. For specific Morocco requests, match the GetYourGuide Activities sheet first; never generic link drops."],
 ["Attraction / museum tickets, self-guided audio tours","Tiqets (AFF-023), WeGoTrip (AFF-017), Klook (AFF-022)","Matching GYG activities (e.g., GYG-059, GYG-066)","High","Sometimes","Only when tickets/entry for a specific attraction or a self-guided audio tour is requested."],
 ["Camel ride","— (AFF-027's program link is itself a Marrakech camel-ride deep link)","GYG-019, GYG-057; Agafay camel combos GYG-020/023/024/025/027; Timlalin GYG-035","High","Sometimes","Only when the traveler wants a camel ride AND the destination matches (Marrakech/Palmeraie/Agafay, Merzouga/Erg Chebbi, Timlalin)."],
 ["Desert / Sahara tour","—","GYG-008, GYG-012, GYG-015, GYG-019, GYG-036, Agafay GYG-020/023/024/025/027, GYG-035, GYG-051, GYG-071","High","Sometimes","Only when the traveler wants a desert experience matching their departure city, duration and comfort level."],
 ["Surf / water activities","—","GYG-009, GYG-010, GYG-021, GYG-060","High","Sometimes","Only for surf/water requests matching Taghazout, Agadir or Essaouira."],
 ["Cooking class","—","GYG-001, GYG-002, GYG-037, GYG-068, GYG-069","High","Sometimes","Only for cooking-class requests matching the destination (Agadir, Atlas/Berber village, Tangier, Rabat)."],
 ["Food & street-food experiences","—","GYG-030, GYG-040, GYG-067","High","Sometimes","Only for food-tour requests matching the city (Marrakech, Fes)."],
 ["Hammam / spa / wellness","—","GYG-038, GYG-061","High","Sometimes","Only for hammam/spa requests matching the destination (Marrakech)."],
 ["Hiking & trekking","—","GYG-003, GYG-041, GYG-043, GYG-070","High","Sometimes","Only for trek requests matching the region (High Atlas, Toubkal, Todra)."],
 ["Day trips & excursions from a base city","—","GYG-004-007, GYG-013, GYG-022, GYG-028, GYG-031, GYG-042, GYG-044, GYG-045, GYG-047, GYG-071, GYG-072, GYG-075 and others","High","Sometimes","Only when the traveler wants an excursion from their stated base city to that destination."],
 ["General sightseeing / itinerary ('What should I see in Marrakech?')","— none, by design","— none, by design","Low","No","NO affiliate of any category. Answer the travel question first with ComeMorocco content. Affiliates only when intent becomes specific — this row encodes the traveler-first rule."],
]

REVIEW_ROWS = [
 ["Kiwi.com affiliate link missing","Kiwi.com (AFF-024)","No Affiliate Link in source — only a widget code is provided","Deep links / contextual links cannot be built; only the widget can be embedded","Obtain the affiliate link from the partner program and add it to Affiliate Map","Critical"],
 ["Shared gyg.me links across different activities","Multiple GYG rows — 12 link groups covering 25 rows (e.g., FxbBMVx9 = GYG-031 'Agadir: Atlas Mountains… Tour' AND GYG-036 'From Agadir: 3-Day Merzouga Desert Adventure'; kqQocVj2 = GYG-004 Ourika AND GYG-075 Anti-Atlas; yJwlrrk5 = GYG-024 Agafay quad AND GYG-053 Argan Oil Cooperative; H4jokpqW = GYG-046/065/067 three different Fes activities; gbJHrs4i = GYG-055/059; nDVekk0X = GYG-030/040; 3SSoCC0H = GYG-033/039; UFNhSwjM = GYG-005/007; idlfa9w6 = GYG-011/029; YxHg9jR2 = GYG-047/072)","The same short link is attached to clearly different activities","A traveler asking for X may be sent to activity Y — relevance and trust risk; violates the destination+activity match rule","Verify every shared link's actual destination activity in the GYG partner dashboard; correct or split links","Critical"],
 ["Booking.com description missing","Booking.com (AFF-013)","Description cell is empty in source","Category 'Accommodation' was inferred from the program name and must be confirmed","Confirm category and intended use; add the official description if available","High"],
 ["getyourguide: description missing + deep link","getyourguide (AFF-027)","No description in source; program name lowercase; supplied link points to ONE Marrakech camel-ride activity (partner_id=7BARAIK)","Program-level vs activity-level linking must be distinguished; 77 separate gyg.me activity links exist","Keep the deep link as-is; use the GYG Activities sheet for activity-level recommendations; consider adding a general program landing link","High"],
 ["NordPass link domain","NordPass (AFF-011)","Link is 'NordPass: https://nordvpn.tpx.li/Yk9mbemK' — the domain says nordvpn while the program is NordPass","Link may be mislabeled or resolve to the wrong product","Verify in the partner dashboard that the link resolves to NordPass, not NordVPN","High"],
 ["Widget preconfigurations (non-Morocco targets)","Hostelworld (AFF-019), Klook (AFF-022), Viator (AFF-018), Localrent (AFF-003)","Widgets contain preset targets: Hostelworld default_direction=New%20York; Klook city_id=289; Viator destination=5407 & product=36697P26; Localrent country=99","Embedding as-is may show the wrong city/destination to Morocco travelers","Verify each widget's configured target; reconfigure for Morocco (Marrakech etc.) before embedding","High"],
 ["GYG-016 has no link","'Self-drive itinerary suggestions with pit-stop tours' (GYG-016)","Source link cell says '(Add link when available)'","Row is a content/itinerary idea, not a bookable activity; link is missing","Supply a matching GYG tour link or move this row out of the activity dataset","High"],
 ["GYG destinations not stated in title","GYG-015, GYG-053, GYG-059, GYG-062 (missing); GYG-001, GYG-035, GYG-051, GYG-063 (inferred)","Destination cannot be reliably determined from the activity name","Wrong-destination recommendations would violate the core rule","Confirm each activity's location via the GYG dashboard; update Destination","High"],
 ["Near-duplicate activity rows","GYG-006/GYG-022 (Ouzoud, link J1GuturO); GYG-023/GYG-025 (Agafay sunset, link C05HKKgL)","Same activity listed twice under slightly different titles with the same link","Duplicates must be preserved per the rules, but the AI should not present both","Keep both rows; deduplicate at recommendation time (present one)","Medium"],
 ["GYG-017 generic template row","'Tour starting from train station (e.g., Rabat city tour from station)' (GYG-017)","Generic template with an example, not a specific bookable product","May not correspond to an actual GYG product","Verify the link's actual product; rename or remove","Medium"],
 ["Morocco coverage unconfirmed","Radical Storage (AFF-001), Welcome Pickups (AFF-004), InDrive (AFF-009)","Source descriptions do not state Moroccan city/airport coverage","Recommending an uncovered location would mislead travelers","Confirm coverage (storage cities; served airports; ride-hailing cities) before location-specific recommendations","Medium"],
 ["Transfer route availability","Kiwitaxi (AFF-016), intui.travel (AFF-026)","Global transfer platforms; specific Moroccan routes unconfirmed in source","Route availability must be verified before recommending a specific transfer","Check route search results for the traveler's exact cities before recommending","Medium"],
 ["DiscoverCars partner claims in description","DiscoverCars (AFF-021)","Description includes commission/attribution/Trustpilot claims (365-day window, 4.6/5 TrustScore)","Preserved verbatim per source fidelity; must not be presented to travelers as travel advice","Keep for internal reference only; never surface commission claims in AI answers","Low"],
]

README_PAIRS = [
 ("File","07_AFFILIATE_MAP.xlsx — ComeMorocco AI affiliate mapping (developer reference)"),
 ("Purpose","Defines how the ComeMorocco AI may use affiliate programs and GetYourGuide activities without turning the assistant into a sales bot. This is an AI decision-support dataset — not an SEO keyword sheet and not a click-maximization tool."),
 ("Source","Input Table 1 — Affiliate Programs (27 programs; columns: Affiliate Program, Description, Affiliate Link(s), Widget Code). Input Table 2 — GetYourGuide Activities (77 activities; columns: Activity, Affiliate Link). All values transcribed exactly; source typos and formatting are preserved deliberately."),
 ("Core rule","Help the traveler first. Recommend an affiliate only when it genuinely matches the traveler's intent. Priority hierarchy: 1) help the traveler; 2) give useful ComeMorocco content when relevant; 3) show an affiliate only on a genuine intent match. An affiliate link is never recommended simply because it exists."),
 ("Example behavior","'I'm visiting Marrakech for 3 days — what should I do?' → answer the travel question; NO affiliate links. 'Where can I book a camel ride in Marrakech?' → a matching GYG activity may be shown (e.g., GYG-057). 'Should I rent a car?' → honest itinerary advice first; affiliate only if the traveler then wants options. 'Do I need an eSIM?' → answer first, then relevant options naturally. 'My flight was cancelled — compensation?' → explain carefully; a flight-compensation affiliate only after an actual disruption + explicit question; never promise eligibility."),
 ("Disclosure","All affiliate recommendations require 'Yes — affiliate disclosure'. Never present an affiliate link as a neutral booking/search result."),
 ("Data limitations","This workbook guarantees nothing about availability, pricing, commissions, inventory, schedules, booking success or current policies. No live integration is defined: prices and availability may only be presented via partner links, never as AI-verified facts."),
 ("Source fidelity","Links, descriptions, widget codes and activity names are preserved exactly (including source typos such as Kiwitaxi's 'servicies', lowercase 'getyourguide' and 'marrakech food tour'). Inferred values are labeled in 'Source / Mapping Basis'. Unknown values read 'Not specified in source'."),
 ("Sheet guide","Affiliate Map — one row per program (27), with When to Recommend and (more important) When NOT to Recommend gates. GetYourGuide Activities — one row per activity (77). Intent Map — traveler intent → affiliate options, including the deliberate 'no affiliate' row. Program Summary — quick reference. Review Notes — 14 items needing manual verification. README — this sheet."),
 ("IDs","AFF-001..AFF-027 (stable; never renumber). GYG-001..GYG-077. A widget belonging to a program does NOT get its own ID."),
 ("Known issues — read before use","1) Kiwi.com (AFF-024): no affiliate link in source — widget only. 2) TWELVE gyg.me links are shared by multiple different activity titles (25 rows; see Review Notes) — verify before trusting activity-level matching. 3) Hostelworld/Klook/Viator/Localrent widgets contain non-Morocco preconfigurations (New York default, city_id=289, destination=5407, country=99). 4) Booking.com & getyourguide descriptions are missing in source — categories inferred from names. 5) GYG-016 has no link ('(Add link when available)'). Full list: Review Notes sheet."),
 ("How to use","Developers: use 'When to Recommend' / 'When NOT to Recommend' as hard gates; require the matching Commercial Intent before showing anything; show at most one affiliate per intent unless the traveler asks to compare; always disclose. Content team: use 'ComeMorocco Content Opportunity' as topic ideas — it is not a URL field."),
]

# =============================================================================
# 5) ROW BUILDERS
# =============================================================================
def affiliate_rows():
    rows = []
    for i, p in enumerate(PROGRAMS, start=1):
        t = CAT[p["cat"]]
        def g(k): return p.get(k, t[k])
        rows.append([
            f"AFF-{i:03d}", p["program"], p["cat"], p["desc"], p["links"], p["widget"],
            g("use"), g("intent"), g("dest"), g("rec"), g("notrec"), g("types"),
            g("comm"), g("live"), "Yes — affiliate disclosure", g("pres"), g("content"),
            p.get("notes", "—"),
            p.get("basis", "Source data + reasonable intent mapping"),
        ])
    return rows

def gyg_rows():
    link_map = {}
    for i, (_, link, _, _, _) in enumerate(GYG, start=1):
        if link.startswith("http"):
            link_map.setdefault(link, []).append(i)
    rows, n_shared = [], 0
    for i, (act, link, cat, dest, basis) in enumerate(GYG, start=1):
        gid = f"GYG-{i:03d}"
        t_intent, t_types = GYG_CAT[cat]
        dest_head = dest.split(" (")[0].split(" —")[0]
        if dest.startswith("Not specified"):
            when_rec = ("Recommend ONLY on a destination + activity match — this activity's destination is "
                        "NOT SPECIFIED in source: verify it before recommending, and only if it matches the traveler's plans "
                        f"AND the request matches this {cat}.")
            content = "None until the destination is verified — pair with a destination guide after confirmation"
        else:
            when_rec = (f"Recommend ONLY on a destination + activity match: the traveler's plans include {dest} "
                        f"AND the request matches this {cat}.")
            content = f"'Things to do in {dest_head}' guide / {cat} guidance for this destination (opportunity mapping — no URLs invented)"
        flags = []
        if not link.startswith("http"):
            flags.append("Review — no affiliate link in source")
        else:
            peers = [f"GYG-{j:03d}" for j in link_map[link] if j != i]
            if peers:
                flags.append("Review — link shared with " + ", ".join(peers)); n_shared += 1
        if basis == "missing":  flags.append("Review — destination not stated in source")
        if basis == "template": flags.append("Review — template/placeholder row, not a specific bookable activity")
        if basis == "inferred": flags.append("OK — destination inferred from title (verify)")
        review = "; ".join(flags) if flags else "OK — mapped"
        rows.append([
            gid, act, link, cat, dest,
            t_intent + f" — matched against destination: {dest}",
            t_types, when_rec,
            "Do NOT recommend merely because this link exists; never for a wrong destination or wrong activity type; "
            "never attached to general 'What should I see…?' questions — answer those with ComeMorocco content first.",
            "High — explicit activity-booking intent",
            "Sometimes — availability, departure times, prices and languages need live confirmation; this workbook has no live feed",
            "Activity card / deep link (gyg.me short link)",
            content, GYG_BASIS[basis], review,
        ])
    return rows, n_shared

def summary_rows():
    rows = []
    for i, p in enumerate(PROGRAMS, start=1):
        t = CAT[p["cat"]]
        n_links = sum(1 for tok in p["links"].split() if tok.startswith("http"))
        has_widget = "Yes" if p["widget"].startswith("<") else ("No (N/A per source)" if "N/A" in p["widget"] else "No — not provided in source")
        if p["links"].startswith("Not specified"):
            has_widget += " — but affiliate link MISSING"
        rows.append([
            f"AFF-{i:03d} — {p['program']}", p["cat"], p.get("use", t["use"]),
            n_links if n_links else "0 — not provided in source", has_widget,
            p.get("intent", t["intent"]), t["trigger"], t["comm"], t["live"],
            p.get("review", "No"),
        ])
    return rows

# =============================================================================
# 6) WORKBOOK ASSEMBLY
# =============================================================================
HEADER_FILL = PatternFill("solid", fgColor="D9E2F3")
HEADER_FONT = Font(bold=True, size=10, color="1F3864")
BODY_FONT   = Font(size=10)
WRAP_TOP    = Alignment(wrap_text=True, vertical="top")
THIN        = Side(style="thin", color="BFBFBF")
BORDER      = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

def build_table(ws, headers, rows, widths, freeze="A2", add_filter=True):
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font, cell.fill, cell.alignment, cell.border = HEADER_FONT, HEADER_FILL, WRAP_TOP, BORDER
        ws.column_dimensions[get_column_letter(c)].width = widths[c - 1]
    ws.row_dimensions[1].height = 32
    for r, row in enumerate(rows, start=2):
        for c, value in enumerate(row, start=1):
            cell = ws.cell(row=r, column=c, value=value)
            cell.font, cell.alignment, cell.border = BODY_FONT, WRAP_TOP, BORDER
    if freeze: ws.freeze_panes = freeze
    if add_filter: ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{ws.max_row}"

def build_readme(ws, title, pairs):
    ws.merge_cells("A1:B1")
    ws.cell(row=1, column=1, value=title).font = Font(bold=True, size=13, color="1F3864")
    ws.row_dimensions[1].height = 24
    for c, h in enumerate(["Section", "Details"], start=1):
        cell = ws.cell(row=3, column=c, value=h)
        cell.font, cell.fill, cell.alignment, cell.border = HEADER_FONT, HEADER_FILL, WRAP_TOP, BORDER
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 115
    for i, (section, detail) in enumerate(pairs, start=4):
        a, b = ws.cell(row=i, column=1, value=section), ws.cell(row=i, column=2, value=detail)
        for cell in (a, b):
            cell.alignment, cell.border = WRAP_TOP, BORDER
        a.font, b.font = Font(bold=True, size=10), BODY_FONT
    ws.freeze_panes = "A4"

wb = Workbook()

AFF_HEADERS = ["Affiliate ID","Affiliate Program","Affiliate Category","Description (Source)","Affiliate Link(s)","Widget Code",
 "Primary Use Case","Relevant Traveler Intent","Relevant Destinations","When to Recommend","When NOT to Recommend",
 "Relevant Traveler Types","Commercial Intent","Live Data Required","Disclosure Required","Preferred Presentation",
 "ComeMorocco Content Opportunity","Notes","Source / Mapping Basis"]
AFF_WIDTHS = [10,26,18,46,40,44,34,40,30,46,50,28,12,14,20,26,38,44,34]

GYG_HEADERS = ["GYG Activity ID","Activity","Affiliate Link","Activity Category","Destination","Relevant Traveler Intent",
 "Relevant Traveler Types","When to Recommend","When NOT to Recommend","Commercial Intent","Live Data Required",
 "Preferred Presentation","ComeMorocco Content Opportunity","Source / Mapping Basis","Review Status"]
GYG_WIDTHS = [12,40,26,20,26,40,26,44,46,14,20,22,36,34,34]

INTENT_HEADERS = ["Intent","Affiliate Program(s)","GYG Activities","Typical Commercial Intent","Live Data Required","Recommendation Rule"]
INTENT_WIDTHS = [28,40,42,12,14,64]

SUMMARY_HEADERS = ["Affiliate Program","Category","Primary Use Case","Number of Affiliate Links","Has Widget",
 "Relevant Traveler Intent","Main Recommendation Trigger","Commercial Intent","Live Data Required","Manual Review Needed"]
SUMMARY_WIDTHS = [34,18,36,14,24,38,34,12,14,36]

REVIEW_HEADERS = ["Item","Affiliate Program / Activity","Issue","Why Review Is Needed","Suggested Action","Priority"]
REVIEW_WIDTHS = [28,44,52,40,44,12]

ws = wb.active; ws.title = "Affiliate Map"
build_table(ws, AFF_HEADERS, affiliate_rows(), AFF_WIDTHS)

build_readme(wb.create_sheet("README"), "07_AFFILIATE_MAP.xlsx — ComeMorocco AI Affiliate Mapping (developer reference)", README_PAIRS)
build_table(wb.create_sheet("Program Summary"), SUMMARY_HEADERS, summary_rows(), SUMMARY_WIDTHS)
build_table(wb.create_sheet("Intent Map"), INTENT_HEADERS, INTENT_ROWS, INTENT_WIDTHS)

gyg_sheet_rows, n_shared = gyg_rows()
build_table(wb.create_sheet("GetYourGuide Activities"), GYG_HEADERS, gyg_sheet_rows, GYG_WIDTHS)
build_table(wb.create_sheet("Review Notes"), REVIEW_HEADERS, REVIEW_ROWS, REVIEW_WIDTHS)

wb.save(OUT)

n_links_aff = sum(1 for p in PROGRAMS for tok in p["links"].split() if tok.startswith("http"))
n_links_gyg = sum(1 for (_, l, *_ ) in GYG if l.startswith("http"))
n_widgets = sum(1 for p in PROGRAMS if p["widget"].startswith("<"))
print(f"Created {OUT}")
print(f"  Sheets: {', '.join(wb.sheetnames)}")
print(f"  Affiliate programs mapped:  {len(PROGRAMS)} (AFF-001..AFF-{len(PROGRAMS):03d}); links preserved: {n_links_aff}; widget codes preserved: {n_widgets}")
print(f"  GYG activities mapped:      {len(GYG)} (GYG-001..GYG-{len(GYG):03d}); links preserved: {n_links_gyg}")
print(f"  Rows flagged (shared/missing links etc.): {n_shared + 2}")
print(f"  Review Notes items: {len(REVIEW_ROWS)} (2 Critical)")
